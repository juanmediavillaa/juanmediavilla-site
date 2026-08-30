#!/usr/bin/env python3
"""Generate every figure on juanmediavilla.com from the underlying result files.

Standard library only, to match the site's zero-dependency rule. Reads committed
result files from the research repositories, writes:

  data/*.csv        the source numbers behind each figure, published for download
  figures/*.svg     hand-authored SVG, inlined into the pages between
                    <!-- FIGURE:name --> ... <!-- /FIGURE:name --> markers

Re-run with:  python3 tools/make_figures.py [--roots ...] [--check]

--check re-runs and fails if any output would change, so a stale figure is a
detectable condition rather than a silent one.

Colours are CSS custom properties inherited from style.css, so the figures theme
with the page. No colour is load-bearing: every series carries a text label.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import pathlib
import re
import sys
import xml.etree.ElementTree as ET

SITE = pathlib.Path(__file__).resolve().parent.parent
DOCS = pathlib.Path("/mnt/c/Users/jmedi/Documents")
POLY = DOCS / "poly-research"
BSC = DOCS / "University/Thesis/Thesis_Desktop/Statistical_Testing/results/Final_NoXGB"

W = 640  # viewBox width; every figure scales to its container
PAD_L, PAD_R, PAD_T, PAD_B = 52, 16, 22, 40


# ---------------------------------------------------------------- svg helpers

def esc(s: object) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


class Svg:
    """Minimal SVG builder. Emits markup meant to be inlined into HTML."""

    def __init__(self, height: int, title: str, desc: str) -> None:
        self.h = height
        self.parts: list[str] = []
        self.title = title
        self.desc = desc

    def add(self, markup: str) -> None:
        self.parts.append("  " + markup)

    def text(self, x: float, y: float, s: object, cls: str = "lbl", anchor: str = "start",
             extra: str = "") -> None:
        self.add(f'<text x="{x:.1f}" y="{y:.1f}" class="{cls}" text-anchor="{anchor}"{extra}>'
                 f"{esc(s)}</text>")

    def line(self, x1: float, y1: float, x2: float, y2: float, cls: str = "axis") -> None:
        self.add(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" class="{cls}"/>')

    def rect(self, x: float, y: float, w: float, h: float, cls: str,
             title: str = "") -> None:
        """A rect, optionally carrying a <title> hover readout.

        Emits a properly closed element in both cases: an SVG referenced by <img>
        is parsed as strict XML, where `</rect/>` is fatal.
        """
        head = (f'<rect x="{x:.1f}" y="{y:.1f}" width="{max(w, 0):.2f}" '
                f'height="{max(h, 0):.2f}" class="{cls}"')
        self.add(f"{head}><title>{esc(title)}</title></rect>" if title else f"{head}/>")

    def path(self, d: str, cls: str) -> None:
        self.add(f'<path d="{d}" class="{cls}"/>')

    def render(self) -> str:
        style = (
            # No palette here on purpose. These SVGs are INLINE, so they inherit the
            # page's custom properties — which respond to prefers-color-scheme AND to
            # the manual data-theme toggle. A self-contained palette can only see the
            # OS setting, so it desynchronises the moment someone uses the toggle.
            ".lbl{font:12px var(--mono,monospace);fill:var(--ink-2)}"
            ".lbl-i{font:12px var(--mono,monospace);fill:var(--ink,#0D0B14)}"
            ".ttl{font:13px var(--sans,sans-serif);fill:var(--ink,#111)}"
            ".axis{stroke:var(--line,#E4E2EE);stroke-width:1}"
            ".rule{stroke:var(--muted,#7B7890);stroke-width:1;stroke-dasharray:3 3}"
            ".bar{fill:var(--c1,#4F46E5)}"
            ".bar-2{fill:var(--c3,#0E9384)}"
            ".ser{fill:none;stroke:var(--c1,#4F46E5);stroke-width:2}"
            ".ser-2{fill:none;stroke:var(--c2,#E8590C);stroke-width:1.5;stroke-dasharray:5 3}"
            ".dot{fill:var(--c1,#4F46E5)}"
            ".dot-2{fill:var(--ink-2)}"
            ".cell{fill:var(--c1,#4F46E5)}"
            ".cv{font:12px var(--mono,monospace);fill:var(--ink,#111)}"
            ".cv.hi{fill:#fff}"
        )
        body = "\n".join(self.parts)
        # Compact the numeric literals. These figures are inlined into pages that
        # carry a markup budget, and trailing zeros are pure weight.
        body = re.sub(r"(\d)\.0(?=[^\d])", r"\1", body)
        body = re.sub(r"(\.\d*?)0+(?=[^\d])", r"\1", body)
        body = re.sub(r"(\d)\.(?=[^\d])", r"\1", body)
        return (
            f'<svg viewBox="0 0 {W} {self.h}" role="img" '
            f'aria-labelledby="t-{self.slug} d-{self.slug}" '
            f'preserveAspectRatio="xMidYMid meet" xmlns="http://www.w3.org/2000/svg">\n'
            f'  <title id="t-{self.slug}">{esc(self.title)}</title>\n'
            f'  <desc id="d-{self.slug}">{esc(self.desc)}</desc>\n'
            f"  <style>{style}</style>\n{body}\n</svg>"
        )

    slug = "fig"


def write_csv(name: str, header: list[str], rows: list[list[object]]) -> pathlib.Path:
    p = SITE / "data" / name
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", newline="") as fh:
        # LF terminator: csv.writer defaults to CRLF, .gitattributes normalises to LF
        # on commit, and the mismatch would make --check report false drift.
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)
    return p


def write_svg(name: str, svg: Svg) -> pathlib.Path:
    svg.slug = name
    markup = svg.render()
    # An SVG referenced by <img> is parsed as strict XML, so a malformed element is
    # fatal rather than merely untidy. Fail here instead of shipping a broken figure.
    try:
        ET.fromstring(markup)
    except ET.ParseError as exc:
        raise SystemExit(f"figure {name} is not well-formed XML: {exc}") from exc
    p = SITE / "figures" / f"{name}.svg"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(markup + "\n")
    return p


def nice_ticks(lo: float, hi: float, n: int = 4) -> list[float]:
    if hi <= lo:
        return [lo]
    raw = (hi - lo) / n
    mag = 10 ** math.floor(math.log10(raw))
    step = min((m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw), default=mag)
    start = math.ceil(lo / step) * step
    out, v = [], start
    while v <= hi + step * 1e-9:
        out.append(round(v, 10))
        v += step
    return out


# ---------------------------------------------------------------- sources

def load_wf() -> dict:
    return json.loads((POLY / "results/wf_mmpp_v0/logs/wf_gates.json").read_text())


def load_gpool() -> dict:
    return json.loads((POLY / "results/hier_mmpp_v0/logs/gpool.json").read_text())


def load_fit() -> dict:
    return json.loads((POLY / "results/hier_mmpp_v0/logs/fit.json").read_text())


def load_agent_programme() -> dict:
    """The synthetic-bed measurements behind the three agent-programme figures.

    Unlike the other sources here, this one lives in this repository rather than in
    a research repo: the bed it came from is a sealed environment that is not
    checked out beside the site, and the sealed-side numbers were never inside it
    at all. The file is a transcription of the bed's own report plus the answer-key
    measurement taken afterwards, and it carries its provenance in a `_source` key.
    Keeping it as a data file rather than as literals in this script is what lets
    the chart, the published CSV and the download all come from one place.
    """
    return json.loads((SITE / "data" / "agent-programme-results.json").read_text())


def load_strategies() -> list[dict]:
    with open(POLY / "results/backtests_historical_v0/results_table.csv", newline="") as fh:
        return list(csv.DictReader(fh))


BSC_MODELS = ["SimCLR", "DeepConvLSTM", "SelfHARModel", "SelfPAB", "XGBoost", "MOMENT"]


def bsc_per_fold(model: str) -> dict[str, float]:
    d = BSC / model / "logs_and_csv"
    out: dict[str, float] = {}
    info = d / f"loso_info_{model}.txt"
    if info.exists():
        for subj, f1 in re.findall(r"Subject (S\d+)\): F1=([0-9.]+)", info.read_text(errors="ignore")):
            out[subj] = float(f1)
        if out:
            return out
    c = d / f"loso_log_{model}.csv"
    if c.exists():
        with open(c, newline="") as fh:
            for row in csv.DictReader(fh):
                out[row["Subject"]] = float(row["Val F1"])
        if out:
            return out
    p = d / f"loso_log_{model}.txt"
    if p.exists():
        for line in p.read_text(errors="ignore").splitlines():
            cells = [c.strip() for c in line.split("|")]
            if len(cells) >= 6 and cells[0].isdigit():
                out[cells[1]] = float(cells[4])
    return out


def bsc_aggregated(model: str) -> tuple[float, list[tuple[str, float, int]]]:
    """(macro-F1, [(class, f1, support)]) from the pooled LOSO report."""
    d = BSC / model / "logs_and_csv"
    text = ""
    for cand in (d / f"loso_info_{model}.txt", d / f"loso_log_{model}.txt"):
        if cand.exists():
            text = cand.read_text(errors="ignore")
            if "macro avg" in text:
                break
    per = [(c, float(f1), int(sup))
           for c, _p, _r, f1, sup in re.findall(
               r"^\s+(\d+)\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s+(\d+)\s*$", text, re.M)]
    m = re.search(r"macro avg\s+[0-9.]+\s+[0-9.]+\s+([0-9.]+)\s+\d+", text)
    return (float(m.group(1)) if m else float("nan")), per


# ---------------------------------------------------------------- statistics

def gammainc_upper_reg(s: float, x: float) -> float:
    if x <= 0.0:
        return 1.0
    if x < s + 1.0:
        term, total, n = 1.0 / s, 1.0 / s, 0
        while n < 500:
            n += 1
            term *= x / (s + n)
            total += term
            if abs(term) < abs(total) * 1e-14:
                break
        return 1.0 - total * math.exp(-x + s * math.log(x) - math.lgamma(s))
    tiny = 1e-300
    b, c = x + 1.0 - s, 1.0 / tiny
    d = 1.0 / b
    h = d
    for i in range(1, 500):
        an = -i * (i - s)
        b += 2.0
        d = an * d + b
        d = tiny if abs(d) < tiny else d
        c = b + an / c
        c = tiny if abs(c) < tiny else c
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-14:
            break
    return h * math.exp(-x + s * math.log(x) - math.lgamma(s))


def friedman(matrix: dict[str, dict[str, float]]) -> tuple[float, int, float, dict[str, float]]:
    """Friedman test over {model: {block: score}}. Returns chi2, df, p, mean ranks."""
    models = list(matrix)
    blocks = sorted(set.intersection(*(set(v) for v in matrix.values())))
    k, n = len(models), len(blocks)
    sums = dict.fromkeys(models, 0.0)
    for b in blocks:
        vals = sorted(((matrix[m][b], m) for m in models), key=lambda t: -t[0])
        i = 0
        while i < len(vals):
            j = i
            while j + 1 < len(vals) and vals[j + 1][0] == vals[i][0]:
                j += 1
            avg = (i + j) / 2.0 + 1.0
            for t in range(i, j + 1):
                sums[vals[t][1]] += avg
            i = j + 1
    chi2 = (12.0 / (n * k * (k + 1))) * sum(v * v for v in sums.values()) - 3.0 * n * (k + 1)
    return chi2, k - 1, gammainc_upper_reg((k - 1) / 2.0, chi2 / 2.0), {m: sums[m] / n for m in models}


# ---------------------------------------------------------------- figures

def fig_hazard() -> None:
    """Falling discrete hazard, with the rejected Weibull drawn alongside."""
    g = load_wf()["G_DURATION"]
    edges, obs, n_end = g["hazard_edges"], g["hazard_observed"], g["hazard_n_end"]
    k = g["weibull_hot_ARTIFACT"]["k"]
    mids = [(edges[i] + min(edges[i + 1], 45)) / 2 for i in range(len(obs))]

    # The rejected Weibull is stored in the source file as a shape parameter only
    # (k = 1.434), not as a fitted curve. What is drawn is therefore the hazard
    # SHAPE that k implies, h(t) proportional to t^(k-1), normalised to meet the
    # observed curve at the first bin. The column name says so, because the curve
    # is derived here rather than read from the file.
    weib = [obs[0] * (m / mids[0]) ** (k - 1) for m in mids]

    write_csv("hazard.csv",
              ["bin_start_min", "bin_end_min", "hazard_per_min_observed",
               "rejected_weibull_shape_from_k_normalised_at_first_bin",
               "n_episodes_ending_in_bin"],
              [[edges[i], edges[i + 1], obs[i], round(weib[i], 4), n_end[i]]
               for i in range(len(obs))])

    h = 250
    x0, x1 = PAD_L, W - PAD_R
    y0, y1 = PAD_T + 10, h - PAD_B
    lo, hi = 0.0, 0.90
    sx = lambda t: x0 + (min(t, 45) - 3) / (45 - 3) * (x1 - x0)
    sy = lambda v: y1 - (v - lo) / (hi - lo) * (y1 - y0)

    s = Svg(h, "Hot-episode hazard against elapsed time",
            "The truncation-robust discrete hazard falls from 0.325 to 0.167 per minute over "
            "3 to 40 minutes elapsed. The rejected Weibull fit rises instead.")
    for t in nice_ticks(lo, hi, 4):
        s.line(x0, sy(t), x1, sy(t))
        s.text(x0 - 6, sy(t) + 3.5, f"{t:.1f}", anchor="end")
    s.line(x0, y1, x1, y1)
    for t in (3, 10, 20, 30, 40):
        s.text(sx(t), y1 + 15, t, anchor="middle")
    s.text((x0 + x1) / 2, h - 8, "minutes the burst has already lasted", anchor="middle")
    s.text(12, (y0 + y1) / 2, "chance it ends this minute", anchor="middle",
           extra=f' transform="rotate(-90 12 {(y0 + y1) / 2:.0f})"')

    s.path("M" + " L".join(f"{sx(m):.1f} {sy(v):.1f}" for m, v in zip(mids, weib)), "ser-2")
    s.path("M" + " L".join(f"{sx(m):.1f} {sy(v):.1f}" for m, v in zip(mids, obs)), "ser")
    for m, v, n in zip(mids, obs, n_end):
        s.add(f'<circle cx="{sx(m):.1f}" cy="{sy(v):.1f}" r="3.5" class="dot">'
              f"<title>{v:.4f}/min, {n} episodes ended</title></circle>")
    for m, v in zip(mids, weib):
        s.add(f'<circle cx="{sx(m):.1f}" cy="{sy(v):.1f}" r="2.5" class="dot-2"/>')

    s.text(sx(mids[1]) + 8, sy(obs[1]) - 10, "observed — falls", cls="lbl-i")
    s.text(sx(mids[4]), sy(weib[4]) - 12, "rejected Weibull (k=1.43) — rises", cls="lbl",
           anchor="end")
    write_svg("fig-hazard", s)


def fig_lead() -> None:
    """Distribution of per-episode lead against the first raw repricing."""
    d = load_wf()["G_DETECT"]["primary"]
    leads = d["all_causal_leads"]
    summ = d["lead_vs_first_raw_count_min"]
    write_csv("lead-episodes.csv", ["episode_index", "lead_min_vs_causal_detector"],
              [[i + 1, v] for i, v in enumerate(leads)])

    counts: dict[float, int] = {}
    for v in leads:
        counts[v] = counts.get(v, 0) + 1
    xs = sorted(counts)
    h = 220
    x0, x1, y1 = PAD_L, W - PAD_R, h - PAD_B
    y0 = PAD_T + 10
    mx = max(counts.values())
    bw = (x1 - x0) / max(len(xs), 1)

    s = Svg(h, "Per-episode detection lead",
            f"Distribution of lead in minutes across {len(leads)} held-out hot episodes. "
            f"Against the first raw repricing the median lead is {summ['median']} minutes.")
    for i, v in enumerate(xs):
        c = counts[v]
        bh = (y1 - y0) * c / mx
        s.rect(x0 + i * bw + 1, y1 - bh, bw - 2, bh, "bar",
               f"lead {v:g} min: {c} episode(s)")
        if c == mx or i % 3 == 0:
            s.text(x0 + i * bw + bw / 2, y1 + 15, f"{v:g}", anchor="middle")
    s.line(x0, y1, x1, y1)
    s.text((x0 + x1) / 2, h - 8, "minutes early (negative = the model was late)", anchor="middle")
    s.text(x0 - 6, y0 + 4, mx, anchor="end")
    s.text(12, (y0 + y1) / 2, "episodes", anchor="middle",
           extra=f' transform="rotate(-90 12 {(y0 + y1) / 2:.0f})"')
    write_svg("fig-lead", s)


def fig_lead_metrics() -> None:
    """Five lead definitions on one axis: the pre-registered one, and the honest one."""
    d = load_wf()["G_DETECT"]["primary"]
    keys = [("lead_preReg_min", "pre-registered metric"),
            ("lead_upcross_vs_centered_min", "vs centred label"),
            ("lead_vs_causal_detector_min", "vs causal detector"),
            ("end_lead_min", "episode end"),
            ("lead_vs_first_raw_count_min", "vs first raw repricing")]
    rows = [[k, lbl, d[k]["median"], d[k]["lo"], d[k]["hi"], d[k]["n"], d[k]["frac_positive"]]
            for k, lbl in keys]
    write_csv("lead-metrics.csv",
              ["metric", "label", "median_min", "ci_lo", "ci_hi", "n_episodes", "frac_positive"],
              rows)

    h = 40 + 34 * len(keys)
    x0, x1 = 210, W - PAD_R - 168
    lo, hi = -6.0, 12.0
    sx = lambda v: x0 + (v - lo) / (hi - lo) * (x1 - x0)
    s = Svg(h, "Five definitions of detection lead",
            "The pre-registered metric reports a +10 minute lead. Measured against the first raw "
            "repricing the same model is 2 minutes late, and never early.")
    s.line(sx(0), PAD_T, sx(0), h - 26, "rule")
    s.text(sx(0), h - 10, "0 = simultaneous", anchor="middle")
    for i, (k, lbl) in enumerate(keys):
        y = PAD_T + 16 + i * 34
        m = d[k]
        s.text(0, y + 4, f'{lbl} (n={m["n"]})', cls="lbl-i")
        s.line(sx(m["lo"]), y, sx(m["hi"]), y, "axis")
        cls = "dot-2" if m["frac_positive"] == 0.0 else "dot"
        s.add(f'<circle cx="{sx(m["median"]):.1f}" cy="{y:.1f}" r="4.5" class="{cls}">'
              f'<title>median {m["median"]:g} min, CI [{m["lo"]:g}, {m["hi"]:g}], '
              f'n={m["n"]}, frac&gt;0 = {m["frac_positive"]:g}</title></circle>')
        s.text(W - PAD_R, y + 4,
               f'{m["median"]:+g} min · frac>0 {m["frac_positive"]:.2f}', anchor="end")
    write_svg("fig-lead-metrics", s)


def fig_pooling() -> None:
    """Per-market change in held-out log-evidence from partial pooling."""
    g = load_gpool()
    rows = sorted(g["per_market"], key=lambda r: r["delta"])
    write_csv("pooling-per-market.csv",
              ["rank", "delta_nats", "n_events", "category", "regime"],
              [[i + 1, round(r["delta"], 3), int(r["n_events"]), r["category"], r["regime"]]
               for i, r in enumerate(rows)])

    h = 250
    x0, x1, y1 = PAD_L + 14, W - PAD_R, h - PAD_B
    y0 = PAD_T + 10
    vals = [r["delta"] for r in rows]
    # Log axis. The gains span 0.63 to 4,770 nats, so on a linear scale two thirds
    # of the markets would render as invisible slivers and the "all positive"
    # claim could not be checked by eye. Every value is positive, so log is safe.
    lo_e, hi_e = -1.0, 4.0
    bw = (x1 - x0) / len(vals)
    sy = lambda v: y1 - (max(math.log10(v), lo_e) - lo_e) / (hi_e - lo_e) * (y1 - y0)
    s = Svg(h, "Per-market change in held-out log-evidence",
            f"Partial pooling improves held-out predictive log-evidence on all {len(vals)} of "
            f"{len(vals)} markets, leave-one-market-out. Log scale; every bar is above zero.")
    for e in range(int(lo_e), int(hi_e) + 1):
        t = 10.0 ** e
        s.line(x0, sy(t), x1, sy(t))
        s.text(x0 - 6, sy(t) + 3.5, f"{t:,.1f}" if e < 0 else f"{t:,.0f}", anchor="end")
    s.line(x0, y1, x1, y1)
    for i, r in enumerate(rows):
        s.rect(x0 + i * bw + 0.6, sy(r["delta"]), bw - 1.2, y1 - sy(r["delta"]), "bar",
               f'market {i + 1}: +{r["delta"]:.1f} nats, '
               f'{int(r["n_events"])} events, {r["category"]}')
    s.text((x0 + x1) / 2, h - 8,
           f"{len(vals)} markets, sorted — log scale, or one market flattens the other 33",
           anchor="middle")
    s.text(12, (y0 + y1) / 2, "better prediction \u2192", anchor="middle",
           extra=f' transform="rotate(-90 12 {(y0 + y1) / 2:.0f})"')
    s.text(x1, y0 + 4, f"all {len(vals)} positive", cls="lbl-i", anchor="end")
    write_svg("fig-pooling", s)


def fig_two_state() -> None:
    """Population cold and hot repricing intensity, with dwell times."""
    n = load_fit()["mu_natural"]
    rows = [["cold", n["lam_cold"]["median"], n["lam_cold"]["lo"], n["lam_cold"]["hi"],
             n["cold_dwell_bins"]["median"], n["cold_dwell_bins"]["lo"], n["cold_dwell_bins"]["hi"]],
            ["hot", n["lam_hot"]["median"], n["lam_hot"]["lo"], n["lam_hot"]["hi"],
             n["hot_dwell_bins"]["median"], n["hot_dwell_bins"]["lo"], n["hot_dwell_bins"]["hi"]]]
    write_csv("two-state.csv",
              ["state", "lambda_per_min_median", "lambda_lo", "lambda_hi",
               "dwell_min_median", "dwell_lo", "dwell_hi"],
              [[r[0]] + [round(v, 4) for v in r[1:]] for r in rows])

    h = 200
    x0, x1 = 96, W - PAD_R
    hi = 1.5
    sx = lambda v: x0 + v / hi * (x1 - x0)
    s = Svg(h, "Two-state repricing intensity",
            "The hot state reprices about 27 times faster than the cold state. Cold dwells last "
            "about 37 minutes, hot about 8.")
    for i, r in enumerate(rows):
        y = PAD_T + 30 + i * 62
        s.text(0, y + 4, f"{r[0]} state", cls="lbl-i")
        s.rect(x0, y - 11, sx(r[1]) - x0, 22, "bar" if i else "bar-2",
               f"{r[0]}: {r[1]:.3f}/min, CI [{r[2]:.3f}, {r[3]:.3f}]")
        s.line(sx(r[2]), y, sx(r[3]), y, "axis")
        s.text(sx(r[1]) + 8, y + 4, f"{r[1]:.3f} /min", cls="lbl-i")
        s.text(0, y + 22, f"~{r[4]:.0f} min dwell")
    s.line(x0, h - PAD_B + 4, x1, h - PAD_B + 4)
    for t in (0, 0.5, 1.0, 1.5):
        s.text(sx(t), h - PAD_B + 19, f"{t:g}", anchor="middle")
    s.text((x0 + x1) / 2, h - 6, "price moves per minute (further right = busier)", anchor="middle")
    write_svg("fig-two-state", s)


def fig_strategies() -> None:
    """Four candidate strategies against the 0.05 significance line."""
    rows = [r for r in load_strategies() if not r["strategy"].startswith("baseline")]
    write_csv("strategies.csv",
              ["strategy", "n_markets", "trades_taken", "p_value_vs_random", "verdict"],
              [[r["strategy"], r["n_markets"], r["trades_taken"], r["p_value_vs_random"],
                r["verdict"]] for r in rows])

    h = 52 + 40 * len(rows)
    x0, x1 = 168, W - PAD_R - 96
    sx = lambda v: x0 + v * (x1 - x0)
    s = Svg(h, "Four strategies against a random baseline",
            "Three strategies score no edge with p-values far above 0.05. The fourth is not "
            "plotted: it abstained on every market because the data lacks the signal it needs.")
    s.line(sx(0.05), PAD_T, sx(0.05), h - 26, "rule")
    s.text(sx(0.05), PAD_T - 6, "p = 0.05", anchor="middle")
    for i, r in enumerate(rows):
        y = PAD_T + 22 + i * 40
        s.text(0, y + 4, r["strategy"], cls="lbl-i")
        if r["verdict"] == "NOT_APPLICABLE":
            s.line(x0, y, x1, y, "axis")
            s.text(x0 + 4, y - 6, "no bar — abstained on every market", cls="lbl-i")
            s.text(W - PAD_R, y + 4, "NOT_APPLICABLE", anchor="end", cls="lbl-i")
        else:
            p = float(r["p_value_vs_random"])
            s.rect(x0, y - 9, sx(p) - x0, 18, "bar",
                   f'{r["strategy"]}: p = {p:.3f} vs random, {r["trades_taken"]} trades')
            s.text(sx(p) + 8, y + 4, f"p = {p:.3f}", cls="lbl-i")
            s.text(W - PAD_R, y + 4, r["verdict"], anchor="end")
    s.line(x0, h - 30, x1, h - 30)
    for t in (0, 0.25, 0.5, 0.75):
        s.text(sx(t), h - 18, f"{t:g}", anchor="middle")
    s.text((x0 + x1) / 2, h - 5, "how easily chance alone explains it (longer = more likely chance)",
           anchor="middle")
    write_svg("fig-strategies", s)


def fig_models() -> None:
    """Six architectures: pooled macro-F1, per-subject spread, and the Friedman null."""
    agg = {m: bsc_aggregated(m)[0] for m in BSC_MODELS}
    folds = {m: bsc_per_fold(m) for m in BSC_MODELS}
    chi2, df, p, ranks = friedman(folds)
    subjects = sorted(set.intersection(*(set(v) for v in folds.values())))

    write_csv("models-macro-f1.csv",
              ["model", "pooled_macro_f1", "mean_per_fold_macro_f1", "min_fold", "max_fold",
               "mean_friedman_rank"],
              [[m, round(agg[m], 4),
                round(sum(folds[m][s] for s in subjects) / len(subjects), 4),
                round(min(folds[m][s] for s in subjects), 4),
                round(max(folds[m][s] for s in subjects), 4),
                round(ranks[m], 3)] for m in BSC_MODELS])
    write_csv("models-per-fold.csv", ["subject"] + BSC_MODELS,
              [[s] + [folds[m][s] for m in BSC_MODELS] for s in subjects])

    h = 40 + 42 * len(BSC_MODELS) + 46
    x0, x1 = 132, W - PAD_R - 60
    lo, hi = 0.25, 1.0
    sx = lambda v: x0 + (v - lo) / (hi - lo) * (x1 - x0)
    s = Svg(h, "Six architectures under leave-one-subject-out cross-validation",
            f"Pooled macro-F1 spans {min(agg.values()):.3f} to {max(agg.values()):.3f}, but the "
            f"per-subject ranges overlap almost completely. A Friedman test over {len(subjects)} "
            f"subjects gives p = {p:.3f}, so the ranking is not statistically significant.")
    for i, m in enumerate(BSC_MODELS):
        y = PAD_T + 20 + i * 42
        vals = [folds[m][sj] for sj in subjects]
        s.text(0, y + 4, m, cls="lbl-i")
        s.line(sx(min(vals)), y, sx(max(vals)), y, "axis")
        # one group carries the class for all 22 subject dots rather than repeating it
        s.add('<g class="dot-2">'
              + "".join(f'<circle cx="{sx(v):.1f}" cy="{y:.1f}" r="1.8"/>' for v in vals)
              + "</g>")
        s.add(f'<circle cx="{sx(agg[m]):.1f}" cy="{y:.1f}" r="4.5" class="dot">'
              f"<title>{m}: pooled macro-F1 {agg[m]:.4f}; per-subject range "
              f"{min(vals):.3f}–{max(vals):.3f}</title></circle>")
        s.text(W - PAD_R, y + 4, f"{agg[m]:.3f}", anchor="end", cls="lbl-i")
    yb = PAD_T + 20 + len(BSC_MODELS) * 42 - 12
    s.line(x0, yb, x1, yb)
    for t in (0.3, 0.5, 0.7, 0.9):
        s.text(sx(t), yb + 15, f"{t:g}", anchor="middle")
    s.text((x0 + x1) / 2, yb + 30,
           "accuracy score, higher is better   \u25cf overall   \u00b7 one person",
           anchor="middle")
    s.text(0, h - 6, f"Friedman χ² = {chi2:.3f}, df = {df}, p = {p:.3f} — not significant",
           cls="lbl-i")
    write_svg("fig-models", s)


def fig_perclass() -> None:
    """Per-class F1 for every model: where all six fail together."""
    data = {m: bsc_aggregated(m)[1] for m in BSC_MODELS}
    classes = [c for c, _f, _s in data[BSC_MODELS[0]]]
    support = {c: s for c, _f, s in data[BSC_MODELS[0]]}
    write_csv("models-per-class-f1.csv", ["class", "support"] + BSC_MODELS,
              [[c, support[c]] + [dict((k, v) for k, v, _ in data[m])[c] for m in BSC_MODELS]
               for c in classes])

    cw, rh = 66, 30
    x0, y0 = 132, PAD_T + 30
    h = y0 + rh * len(BSC_MODELS) + 44
    s = Svg(h, "Per-class F1 across six architectures",
            "Every architecture fails on the same two minority classes, which is the class "
            "imbalance the thesis records as its persistent limitation.")
    # Value as text on the page background plus a proportional bar. Deliberately not a
    # colour-shaded heatmap: shading by opacity cannot hold WCAG AA for the cell text in
    # both themes at once, and this encoding also survives greyscale unchanged.
    for j, c in enumerate(classes):
        cx = x0 + j * cw
        s.text(cx + cw / 2 - 4, y0 - 18, f"c{c}", anchor="middle", cls="lbl-i")
        s.text(cx + cw / 2 - 4, y0 - 6, f"{support[c]:,}", anchor="middle")
    s.add('<g class="bar">')
    for i, m in enumerate(BSC_MODELS):
        y = y0 + i * rh
        s.text(0, y + 13, m, cls="lbl-i")
        vmap = dict((k, v) for k, v, _ in data[m])
        for j, c in enumerate(classes):
            v = vmap[c]
            cx = x0 + j * cw
            s.add(f'<rect x="{cx:.0f}" y="{y + 14:.0f}" width="{(cw - 10) * v:.1f}" '
                  f'height="4"><title>c{c}: {v:.3f}</title></rect>'
                  f'<text x="{cx:.0f}" y="{y + 10:.0f}">{v:.2f}</text>')
    s.add("</g>")
    s.text(0, h - 26, "column = activity class, with its sample count below the label")
    s.text(0, h - 12, "bar length = F1 for that class; full width would be 1.00")
    write_svg("fig-perclass", s)


def _hatch(s: Svg, slug: str) -> str:
    """A 45-degree hatch, so 'inside the noise' survives greyscale and colourblindness.

    Defined per figure rather than in the shared <style>: these SVGs are inlined
    into HTML, where a <style> is document-scoped, and several figures share a page.
    A local <defs> keeps the pattern id the only thing that has to be unique.
    """
    pid = f"hz-{slug}"
    s.add(f'<defs><pattern id="{pid}" width="5" height="5" patternUnits="userSpaceOnUse" '
          f'patternTransform="rotate(45)"><rect width="5" height="5" fill="var(--surface)"/>'
          f'<line x1="0" y1="0" x2="0" y2="5" stroke="var(--muted)" stroke-width="2"/>'
          f"</pattern></defs>")
    return f"url(#{pid})"


def _whiskers(s: Svg, items: list[tuple[float, float, float]], cap: float = 4) -> None:
    """Every interval in one figure as a single <g>, drawn in ink not in a series colour.

    One group rather than one per row, for the same reason fig_models groups its
    subject dots: this page carries three charts against a 90 KB markup cap, and
    repeating the stroke attributes fourteen times is pure weight. Called after the
    bars so the whiskers sit on top of them.
    """
    if not items:
        return
    lines = "".join(
        f'<line x1="{lo:.1f}" y1="{y:.1f}" x2="{hi:.1f}" y2="{y:.1f}"/>'
        f'<line x1="{lo:.1f}" y1="{y - cap:.1f}" x2="{lo:.1f}" y2="{y + cap:.1f}"/>'
        f'<line x1="{hi:.1f}" y1="{y - cap:.1f}" x2="{hi:.1f}" y2="{y + cap:.1f}"/>'
        for lo, hi, y in items)
    s.add(f'<g stroke="var(--ink-2)" stroke-width="1.2" fill="none">{lines}</g>')


def fig_agent_ceiling() -> None:
    """How close an honest search got, against how far a compromised one appears to get."""
    rows = load_agent_programme()["ceiling"]
    write_csv("agent-ceiling.csv",
              ["quantity", "average_precision", "interval_lo", "interval_hi",
               "measured_from", "is_candidate_model"],
              [[r["long"], r["value"],
                "" if r["lo"] is None else r["lo"], "" if r["hi"] is None else r["hi"],
                r["side"], "yes" if r["candidate"] else "no"] for r in rows])

    slug = "fig-agent-ceiling"
    h = 40 + 40 * len(rows) + 44
    x0, x1 = 152, W - PAD_R - 62
    hi = 0.68
    sx = lambda v: x0 + v / hi * (x1 - x0)
    s = Svg(h, "How far the search got, against the ceiling and against the trap",
            "The honest search reached 0.3971 against an achievable ceiling of 0.4198. The same "
            "model with the excluded settlement column added back reaches 0.6194, which is not a "
            "candidate model and is drawn hatched.")
    hatch = _hatch(s, slug)
    bars: list[tuple[float, float, float]] = []

    for i, r in enumerate(rows):
        y = PAD_T + 24 + i * 40
        # Two stacked lines in the left gutter rather than a second column on the
        # right: the longest bar's value label ran straight through a right-hand
        # column, and there is no width at 640 for both.
        s.text(0, y - 2, r["label"], cls="lbl-i")
        s.text(0, y + 12,
               {"sealed": "from the answer key", "file": "from the data itself",
                "agent": "from the search"}[r["side"]])
        w = sx(r["value"]) - x0
        if r["candidate"]:
            s.rect(x0, y - 10, w, 20, "bar", f'{r["long"]}: {r["value"]:.4f}')
        else:
            # Third encoding on top of colour and hatch: the row is also the only
            # one carrying a cross and a stated exclusion, so greyscale loses nothing.
            s.add(f'<rect x="{x0:.1f}" y="{y - 10:.1f}" width="{w:.2f}" height="20" '
                  f'fill="{hatch}" stroke="var(--c2)" stroke-width="1.5">'
                  f'<title>{esc(r["long"])}: {r["value"]:.4f} — not a candidate model</title></rect>')
        if r["lo"] is not None:
            bars.append((sx(r["lo"]), sx(r["hi"]), y))
        label = f'{r["value"]:.4f}' if r["candidate"] else f'\u2715 {r["value"]:.4f}'
        s.text(sx(r["value"]) + 9, y + 4, label, cls="lbl-i")

    _whiskers(s, bars)
    yb = PAD_T + 24 + len(rows) * 40 - 14
    s.line(x0, yb, x1, yb)
    for t in (0, 0.2, 0.4, 0.6):
        s.text(sx(t), yb + 15, f"{t:g}", anchor="middle")
    s.text((x0 + x1) / 2, yb + 30,
           "average precision, higher is better \u00b7 whiskers are 95% intervals",
           anchor="middle")
    s.text(0, h - 6, "\u2715 hatched = uses a column excluded on availability grounds",
           cls="lbl-i")
    write_svg(slug, s)


def fig_agent_changes() -> None:
    """Every change the search made, sorted by effect, against the zero line."""
    rows = load_agent_programme()["changes"]
    # An interval that REACHES zero has not crossed it. One row here is
    # [-0.0140, -0.0000], which the source calls a real loss "by an amount whose
    # interval reaches exactly to zero"; -0.0 is not < 0, so a strict test filed it
    # as noise and the legend miscounted. Straddling is lo < 0 < hi, nothing looser.
    verdict = lambda r: ("gain" if r["lo"] >= 0 else "loss" if r["hi"] <= 0
                         else "inside the noise")
    write_csv("agent-search-changes.csv",
              ["change", "delta_average_precision", "interval_lo", "interval_hi", "verdict"],
              [[r["label"], r["delta"], r["lo"], r["hi"], verdict(r)] for r in rows])

    slug = "fig-agent-changes"
    row_h = 25
    h = PAD_T + 22 + row_h * len(rows) + 66
    x0, x1 = 232, W - PAD_R - 66
    lo, hi = -0.05, 0.13
    sx = lambda v: x0 + (v - lo) / (hi - lo) * (x1 - x0)
    straddle = sum(1 for r in rows if verdict(r) == "inside the noise")
    s = Svg(h, "Every change the search made, sorted by effect",
            f"Of {len(rows)} changes, {straddle} have an interval that crosses zero and bought "
            "nothing that can be told apart from noise. Three are real gains and three are real "
            "losses.")
    hatch = _hatch(s, slug)
    bars: list[tuple[float, float, float]] = []

    zero = sx(0)
    s.line(zero, PAD_T + 6, zero, PAD_T + 14 + row_h * len(rows), "rule")
    s.text(zero, PAD_T, "no change", anchor="middle")

    for i, r in enumerate(rows):
        y = PAD_T + 26 + i * row_h
        v = verdict(r)
        s.text(0, y + 4, r.get("short", r["label"]), cls="lbl-i")
        a, b = sorted((zero, sx(r["delta"])))
        if v == "inside the noise":
            s.add(f'<rect x="{a:.1f}" y="{y - 7:.1f}" width="{b - a:.2f}" height="14" '
                  f'fill="{hatch}" stroke="var(--muted)" stroke-width="1">'
                  f'<title>{esc(r["label"])}: {r["delta"]:+.4f} — interval crosses zero</title></rect>')
        else:
            fill = "var(--c3)" if v == "gain" else "var(--c2)"
            s.add(f'<rect x="{a:.1f}" y="{y - 7:.1f}" width="{b - a:.2f}" height="14" '
                  f'fill="{fill}">'
                  f'<title>{esc(r["label"])}: {r["delta"]:+.4f} — a real {v}</title></rect>')
        bars.append((sx(r["lo"]), sx(r["hi"]), y))
        # Position (side of the zero line) and glyph both repeat what colour says.
        mark = {"gain": "\u25b2", "loss": "\u25bc", "inside the noise": "\u2248"}[v]
        s.text(W - PAD_R, y + 4, f'{mark} {r["delta"]:+.4f}', anchor="end", cls="lbl-i")

    _whiskers(s, bars, cap=3.5)
    yb = PAD_T + 20 + row_h * len(rows) + 8
    s.line(x0, yb, x1, yb)
    for t in (-0.04, 0, 0.04, 0.08, 0.12):
        s.text(sx(t), yb + 15, f"{t:+g}".replace("+0", "0") if t == 0 else f"{t:+g}",
               anchor="middle")
    s.text((x0 + x1) / 2, yb + 28, "change in average precision", anchor="middle")
    s.text(0, h - 8,
           f"\u25b2 gain  \u25bc loss  \u2248 hatched, interval crosses zero ({straddle} of {len(rows)})",
           cls="lbl-i")
    write_svg(slug, s)


def fig_agent_near_miss() -> None:
    """The three correlations the agent computed and did not conclude from."""
    rows = load_agent_programme()["near_miss"]
    write_csv("agent-near-miss.csv", ["pair", "correlation"],
              [[r["label"], r["r"]] for r in rows])

    slug = "fig-agent-near-miss"
    h = 40 + 46 * len(rows) + 74
    x0, x1 = 150, W - PAD_R - 58
    sx = lambda v: x0 + v * (x1 - x0)
    s = Svg(h, "The correlations that carry the lookahead signature",
            "The merchant score tracks each period's own fraud rate more closely than the two "
            "periods track each other. A score fixed before the data begins could not do that.")
    hatch = _hatch(s, slug)
    third = rows[-1]["r"]

    # The reference line IS the finding: everything to its right is the anomaly.
    s.line(sx(third), PAD_T + 4, sx(third), PAD_T + 18 + 46 * len(rows), "rule")

    for i, r in enumerate(rows):
        y = PAD_T + 28 + i * 46
        above = r["r"] > third
        s.text(0, y - 2, r["short"], cls="lbl-i")
        s.text(0, y + 12, "above the reference" if above else "the reference")
        if above:
            s.rect(x0, y - 11, sx(r["r"]) - x0, 22, "bar", f'{r["label"]}: r = {r["r"]:.3f}')
        else:
            s.add(f'<rect x="{x0:.1f}" y="{y - 11:.1f}" width="{sx(r["r"]) - x0:.2f}" height="22" '
                  f'fill="{hatch}" stroke="var(--muted)" stroke-width="1">'
                  f'<title>{esc(r["label"])}: r = {r["r"]:.3f} — the reference</title></rect>')
        s.text(sx(r["r"]) + 9, y + 4, f'r = {r["r"]:.3f}', cls="lbl-i")

    yb = PAD_T + 24 + 46 * len(rows)
    s.line(x0, yb, x1, yb)
    for t in (0, 0.25, 0.5, 0.75, 1.0):
        s.text(sx(t), yb + 15, f"{t:g}", anchor="middle")
    s.text((x0 + x1) / 2, yb + 28, "correlation, 0 to 1", anchor="middle")
    # The second footnote said what the caption already says, and cost a line the
    # footer did not have. Interpretation belongs in the caption, not on the canvas.
    s.text(0, h - 8, "dashed line: how well the two periods track each other", cls="lbl-i")
    write_svg(slug, s)


FIGURES = [fig_hazard, fig_lead, fig_lead_metrics, fig_pooling,
           fig_two_state, fig_strategies, fig_models, fig_perclass,
           fig_agent_ceiling, fig_agent_changes, fig_agent_near_miss]


# which published CSV backs which figure
FIGURE_DATA = {
    "fig-hazard": "hazard.csv",
    "fig-lead": "lead-episodes.csv",
    "fig-lead-metrics": "lead-metrics.csv",
    "fig-pooling": "pooling-per-market.csv",
    "fig-two-state": "two-state.csv",
    "fig-strategies": "strategies.csv",
    "fig-models": "models-macro-f1.csv",
    "fig-perclass": "models-per-class-f1.csv",
    "fig-agent-ceiling": "agent-ceiling.csv",
    "fig-agent-changes": "agent-search-changes.csv",
    "fig-agent-near-miss": "agent-near-miss.csv",
}
MAX_ROWS = 12


def data_table(name: str, up: str) -> str:
    """A real table of the numbers behind a figure, as a native <details>.

    This is the accessibility path and the evidence path at once: it needs no
    JavaScript, it is keyboard reachable, it prints, and it lets a reader check
    the chart against the data without downloading anything.
    """
    csv_name = FIGURE_DATA.get(name)
    if not csv_name:
        return ""
    path = SITE / "data" / csv_name
    if not path.exists():
        return ""
    with open(path, newline="") as fh:
        rows = list(csv.reader(fh))
    if not rows:
        return ""
    head, body = rows[0], rows[1:]
    shown, note = body[:MAX_ROWS], ""
    if len(body) > MAX_ROWS:
        note = (f"<p class=\"prov\">First {MAX_ROWS} of {len(body)} rows. "
                f'<a href="{up}data/{csv_name}">Download all {len(body)}</a>.</p>')
    th = "".join(f"<th scope=\"col\">{esc(c.replace('_', ' '))}</th>" for c in head)
    tb = "".join("<tr>" + "".join(f"<td>{esc(c)}</td>" for c in r) + "</tr>" for r in shown)
    return (f'<details class="figdata"><summary>Show the numbers</summary>'
            f'<div class="scroll" role="region" tabindex="0" aria-label="Data table"><table><thead><tr>{th}</tr></thead>'
            f"<tbody>{tb}</tbody></table></div>{note}</details>\n")


def inject() -> list[str]:
    """Reference each generated SVG from the pages, between its FIGURE markers.

    Referenced rather than inlined: six inline figures pushed /research past its
    60 KB markup budget. Each <img> carries explicit dimensions so nothing shifts,
    and alt text drawn from the figure's own <title>.
    """
    changed = []
    for page in sorted(SITE.rglob("*.html")):
        text = original = page.read_text()
        depth = len(page.relative_to(SITE).parts) - 1
        up = "../" * depth
        for m in re.finditer(r"<!-- FIGURE:([\w-]+) -->.*?<!-- /FIGURE:\1 -->", text, re.S):
            name = m.group(1)
            svg = SITE / "figures" / f"{name}.svg"
            if not svg.exists():
                print(f"  ! {page.name}: no figure named {name}", file=sys.stderr)
                continue
            src = svg.read_text()
            vb = re.search(r'viewBox="0 0 (\d+) (\d+)"', src)
            title = re.search(r"<title[^>]*>(.*?)</title>", src, re.S)
            alt = esc(title.group(1)) if title else name
            block = (f"<!-- FIGURE:{name} -->\n"
                     f'<div class="scroll" role="region" tabindex="0" '
                     f'aria-label="{alt} — scrollable chart">\n{src.strip()}\n</div>\n'
                     f'<p class="scroll-hint">Chart scrolls sideways on a narrow screen — '
                     f'or open “Show the numbers” below.</p>\n'
                     + data_table(name, up)
                     + f"<!-- /FIGURE:{name} -->")
            text = text.replace(m.group(0), block)
        if text != original:
            page.write_text(text)
            changed.append(str(page.relative_to(SITE)))
    return changed


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="fail if regenerating would change any committed output")
    args = ap.parse_args()

    before = {p: p.read_bytes() for p in
              list((SITE / "figures").glob("*.svg")) + list((SITE / "data").glob("*.csv"))}
    for fn in FIGURES:
        fn()
        print(f"  built {fn.__name__}")
    changed_pages = inject()
    for p in changed_pages:
        print(f"  inlined into {p}")

    if args.check:
        after = {p: p.read_bytes() for p in
                 list((SITE / "figures").glob("*.svg")) + list((SITE / "data").glob("*.csv"))}
        drift = [str(p.name) for p in set(before) | set(after)
                 if before.get(p) != after.get(p)]
        if drift or changed_pages:
            print("STALE:", ", ".join(sorted(drift + changed_pages)), file=sys.stderr)
            return 1
        print("check: figures and data are up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main())
