#!/usr/bin/env python3
"""Build the explainer diagrams as inline SVG.

Hand-authored, themeable, and small enough to inline (which is what lets them
carry <title> hover readouts). Written to figures/dia-*.svg and injected into the
pages between <!-- DIAGRAM:name --> markers, the same contract make_figures.py uses.

Standard library only. Run:  python3 tools/make_diagrams.py [--check]
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys
import xml.etree.ElementTree as ET

SITE = pathlib.Path(__file__).resolve().parent.parent
W = 660

STYLE = (
    "svg{--ink:#0D0B14;--ink2:#4A4759;--muted:#7B7890;--line:#E4E2EE;--surface:#FBFAFC;"
    "--c1:#4F46E5;--c2:#E8590C;--c3:#0E9384;"
    "--mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;"
    "--sans:system-ui,-apple-system,'Segoe UI',Roboto,Arial,sans-serif}"
    "@media (prefers-color-scheme:dark){svg{--ink:#F5F4FA;--ink2:#BFBCD0;--muted:#8A87A0;"
    "--line:#26233A;--surface:#12101C;--c1:#8079F0;--c2:#DD5F24;--c3:#0F8B73}}"
    ".bx{fill:var(--surface);stroke:var(--line);stroke-width:1}"
    ".bx1{stroke:var(--c1);stroke-width:1.5}"
    ".bx2{stroke:var(--c2);stroke-width:1.5}"
    ".bx3{stroke:var(--c3);stroke-width:1.5}"
    ".t{font:12px var(--sans);fill:var(--ink)}"
    ".ts{font:10.5px var(--mono);fill:var(--ink2)}"
    ".tm{font:10.5px var(--mono);fill:var(--ink2)}"
    ".ar{stroke:var(--muted);stroke-width:1.2;fill:none;marker-end:url(#a)}"
    ".ar1{stroke:var(--c1)}.ar2{stroke:var(--c2)}"
    ".dash{stroke-dasharray:4 3}"
)


def esc(s: object) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class Dia:
    def __init__(self, h: int, title: str, desc: str) -> None:
        self.h, self.title, self.desc, self.p = h, title, desc, []

    def add(self, m: str) -> None:
        self.p.append("  " + m)

    def box(self, x, y, w, h, label, sub="", cls="bx", tip="") -> None:
        t = f"<title>{esc(tip)}</title>" if tip else ""
        self.add(f'<g><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" class="bx {cls}"/>{t}'
                 f'<text x="{x + w / 2:.0f}" y="{y + (h / 2 if not sub else h / 2 - 5):.0f}" '
                 f'class="t" text-anchor="middle" dominant-baseline="middle">{esc(label)}</text>'
                 + (f'<text x="{x + w / 2:.0f}" y="{y + h / 2 + 11:.0f}" class="ts" '
                    f'text-anchor="middle" dominant-baseline="middle">{esc(sub)}</text>' if sub else "")
                 + "</g>")

    def arrow(self, x1, y1, x2, y2, cls="") -> None:
        self.add(f'<path d="M{x1} {y1} L{x2} {y2}" class="ar {cls}"/>')

    def label(self, x, y, s, cls="ts", anchor="start") -> None:
        self.add(f'<text x="{x}" y="{y}" class="{cls}" text-anchor="{anchor}">{esc(s)}</text>')

    def render(self, slug: str) -> str:
        return (f'<svg viewBox="0 0 {W} {self.h}" role="img" aria-labelledby="dt-{slug} dd-{slug}" '
                f'xmlns="http://www.w3.org/2000/svg">\n'
                f'  <title id="dt-{slug}">{esc(self.title)}</title>\n'
                f'  <desc id="dd-{slug}">{esc(self.desc)}</desc>\n'
                f'  <defs><marker id="a" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" '
                f'markerHeight="6" orient="auto"><path d="M0 0 L8 4 L0 8 z" fill="var(--muted)"/>'
                f"</marker></defs>\n  <style>{STYLE}</style>\n"
                + "\n".join(self.p) + "\n</svg>")


def d_pipeline() -> tuple[str, Dia]:
    d = Dia(240, "The collection pipeline",
            "Six scheduled collectors write to storage on a 15 to 60 minute cadence. A gap audit "
            "checks continuity, and the audited output is a panel of 400 resolved markets and "
            "188,856 trades.")
    for i in range(6):
        y = 18 + i * 24
        d.box(8, y, 118, 20, f"collector {i + 1}", cls="bx1",
              tip=f"scheduled collector {i + 1}, dispatched every 15–60 minutes")
    d.label(8, 172, "6 scheduled + 1 dormant")
    d.box(160, 60, 116, 56, "systemd timers", "15–60 min", cls="bx1",
          tip="each collector runs on a systemd timer")
    d.box(310, 60, 110, 56, "storage", "~118 GB", cls="bx3", tip="on-disk corpus at survey time")
    d.box(452, 20, 200, 46, "gap audit", "continuity accounting", cls="bx2",
          tip="every feed gap is logged and masked, never interpolated")
    d.box(452, 96, 200, 56, "audited panel",
          "400 markets · 188,856 trades", cls="bx3",
          tip="licence-clean and hash-verified; 382 used in the backtests")
    for i in range(6):
        d.arrow(128, 28 + i * 24, 158, 88, "ar1")
    d.arrow(278, 88, 308, 88)
    d.arrow(422, 80, 450, 52, "ar2")
    d.arrow(422, 96, 450, 118)
    d.label(8, 196, "every gap logged and masked — never interpolated", cls="tm")
    d.label(8, 212, "reconstruction validated by delta replay", cls="tm")
    return "dia-pipeline", d


def d_two_state() -> tuple[str, Dia]:
    d = Dia(230, "The two-state market",
            "A market switches between a quiet state, moving its price about once every 25 "
            "minutes, and a busy state, moving about once every 53 seconds. The state itself is "
            "hidden and has to be inferred from the price moves.")
    d.box(60, 30, 200, 66, "QUIET state", "one move ≈ every 25 min", cls="bx3",
          tip="lambda_cold 0.041 moves per minute; dwell about 37 minutes")
    d.box(400, 30, 200, 66, "BUSY state", "one move ≈ every 53 s", cls="bx2",
          tip="lambda_hot 1.141 moves per minute; dwell about 8 minutes")
    d.add('<path d="M262 50 Q330 18 398 50" class="ar"/>')
    d.add('<path d="M398 82 Q330 114 262 82" class="ar"/>')
    d.label(330, 14, "switches", anchor="middle")
    d.label(330, 132, "switches back", anchor="middle")
    d.label(160, 112, "stays ~37 min", anchor="middle")
    d.label(500, 112, "stays ~8 min", anchor="middle")
    d.label(330, 160, "28× faster in the busy state", cls="t", anchor="middle")
    d.add('<rect x="60" y="180" width="540" height="34" rx="6" class="bx dash"/>')
    d.label(330, 201, "you never observe the state — only the moves it produces",
            cls="ts", anchor="middle")
    return "dia-two-state", d


def d_tiers() -> tuple[str, Dia]:
    d = Dia(250, "The three-tier wallet engine",
            "Three independent checks run on each wallet. Only when all three agree is a wallet "
            "labelled an insider; if on-chain tracing is unavailable the classification is capped "
            "rather than guessed.")
    for i, (t, sub, cls) in enumerate((
            ("tier 1 · trading pattern", "timing vs news", "bx1"),
            ("tier 2 · profit history", "early on winners", "bx1"),
            ("tier 3 · on-chain funding", "traced up to 3 hops", "bx1"))):
        d.box(8, 18 + i * 58, 220, 44, t, sub, cls=cls, tip=f"{t}: {sub}")
    d.box(280, 76, 150, 60, "all three agree?", cls="bx2",
          tip="corroboration gate — an insider label needs every tier")
    for i in range(3):
        d.arrow(230, 40 + i * 58, 278, 106, "ar1")
    d.arrow(432, 92, 500, 60, "ar2")
    d.arrow(432, 120, 500, 156)
    d.box(500, 38, 152, 44, "INSIDER", "all three", cls="bx2", tip="only when all tiers corroborate")
    d.box(500, 134, 152, 44, "SHARP / WHALE", "capped", cls="bx3",
          tip="without an on-chain key, tier 3 is disabled and the label is capped here")
    d.label(8, 210, "no on-chain key → tier 3 disabled → the label is capped, never guessed", cls="tm")
    d.label(8, 228, "one heuristic retired: it fired on the venue's proxy-wallet architecture", cls="tm")
    return "dia-tiers", d


def d_nav() -> tuple[str, Dia]:
    d = Dia(220, "Unitisation, and the ledger invariant",
            "Money paid in is converted to units at today's price per unit. The fund's value "
            "always equals its cash plus the market value of its positions.")
    d.box(8, 30, 140, 50, "money in", "€ deposit", cls="bx3", tip="a member deposits")
    d.box(190, 30, 150, 50, "price per unit", "value ÷ units", cls="bx1",
          tip="net asset value per unit, computed at the moment of the deposit")
    d.box(382, 30, 150, 50, "units issued", "deposit ÷ price", cls="bx1",
          tip="the member is issued units at that price")
    d.arrow(150, 55, 188, 55)
    d.arrow(342, 55, 380, 55)
    d.add('<rect x="8" y="112" width="524" height="50" rx="6" class="bx bx2"/>')
    d.label(270, 132, "fund value  =  cash  +  Σ (position market value)", cls="t", anchor="middle")
    d.label(270, 150, "checked on every write — the ledger cannot drift", cls="ts", anchor="middle")
    d.label(8, 190, "money is held as exact decimals and written as text, so nothing rounds", cls="tm")
    d.label(8, 206, "withdrawals redeem units at the price of the day, by the same arithmetic", cls="tm")
    return "dia-nav", d


def d_ssl() -> tuple[str, Dia]:
    d = Dia(230, "The self-supervised pipeline",
            "A model learns structure from a large pile of unlabelled sensor data, is then "
            "fine-tuned on the small labelled set, and is finally tested on people it has never "
            "seen.")
    d.box(8, 26, 176, 58, "unlabelled sensor data", "pretraining", cls="bx3",
          tip="learn the shape of the data without labels")
    d.box(240, 26, 160, 58, "small labelled set", "fine-tuning", cls="bx1",
          tip="labels are expensive; only a small set exists")
    d.box(456, 26, 196, 58, "held-out person", "leave-one-subject-out", cls="bx2",
          tip="tested on a person never seen in training — the only question that matters")
    d.arrow(186, 55, 238, 55, "ar1")
    d.arrow(402, 55, 454, 55, "ar2")
    d.label(8, 116, "repeated for each of 22 people in turn, then pooled", cls="tm")
    d.add('<rect x="8" y="132" width="644" height="76" rx="6" class="bx dash"/>')
    d.label(24, 154, "six architectures compared this way:", cls="t")
    d.label(24, 174, "SimCLR · DeepConvLSTM · SelfHARModel · SelfPAB · XGBoost · MOMENT", cls="ts")
    d.label(24, 194, "spread 0.880 to 0.843 — a Friedman test says that ordering is noise", cls="ts")
    return "dia-ssl", d


DIAGRAMS = [d_pipeline, d_two_state, d_tiers, d_nav, d_ssl]


def build() -> dict[str, str]:
    out = {}
    for fn in DIAGRAMS:
        slug, d = fn()
        markup = d.render(slug)
        try:
            ET.fromstring(markup)
        except ET.ParseError as exc:
            raise SystemExit(f"diagram {slug} is not well-formed XML: {exc}") from exc
        path = SITE / "figures" / f"{slug}.svg"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(markup + "\n")
        out[slug] = markup
        print(f"  built {slug} ({len(markup):,} bytes)")
    return out


def inject(diagrams: dict[str, str]) -> list[str]:
    changed = []
    for page in sorted(SITE.rglob("*.html")):
        text = original = page.read_text()
        for m in re.finditer(r"<!-- DIAGRAM:([\w-]+) -->.*?<!-- /DIAGRAM:\1 -->", text, re.S):
            slug = m.group(1)
            if slug not in diagrams:
                print(f"  ! {page.name}: no diagram named {slug}", file=sys.stderr)
                continue
            text = text.replace(
                m.group(0),
                f"<!-- DIAGRAM:{slug} -->\n{diagrams[slug]}\n<!-- /DIAGRAM:{slug} -->")
        if text != original:
            page.write_text(text)
            changed.append(str(page.relative_to(SITE)))
    return changed


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    before = {p: p.read_bytes() for p in SITE.glob("figures/dia-*.svg")}
    diagrams = build()
    for p in inject(diagrams):
        print(f"  inlined into {p}")
    if args.check:
        after = {p: p.read_bytes() for p in SITE.glob("figures/dia-*.svg")}
        if before != after:
            print("STALE: diagrams changed", file=sys.stderr)
            return 1
        print("check: diagrams are up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main())
