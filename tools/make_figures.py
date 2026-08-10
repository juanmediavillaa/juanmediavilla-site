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

    def rect(self, x: float, y: float, w: float, h: float, cls: str, extra: str = "") -> None:
        self.add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{max(w, 0):.2f}" '
                 f'height="{max(h, 0):.2f}" class="{cls}"{extra}/>')

    def path(self, d: str, cls: str) -> None:
        self.add(f'<path d="{d}" class="{cls}"/>')

    def render(self) -> str:
        style = (
            ".lbl{font:11px var(--mono,monospace);fill:var(--muted,#555)}"
            ".lbl-i{font:11px var(--mono,monospace);fill:var(--ink,#111)}"
            ".ttl{font:12px var(--sans,sans-serif);fill:var(--ink,#111)}"
            ".axis{stroke:var(--line,#ddd);stroke-width:1}"
            ".rule{stroke:var(--ink,#111);stroke-width:1;stroke-dasharray:3 3}"
            ".bar{fill:var(--accent,#0B6B52)}"
            ".bar-2{fill:var(--muted,#555)}"
            ".ser{fill:none;stroke:var(--accent,#0B6B52);stroke-width:2}"
            ".ser-2{fill:none;stroke:var(--muted,#555);stroke-width:1.5;stroke-dasharray:5 3}"
            ".dot{fill:var(--accent,#0B6B52)}"
            ".dot-2{fill:var(--muted,#555)}"
            ".cell{fill:var(--accent,#0B6B52)}"
            ".cv{font:9.5px var(--mono,monospace);fill:var(--ink,#111)}"
            ".cv.hi{fill:#fff}"
        )
        body = "\n".join(self.parts)
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
    with open(p, "w", newline="\n") as fh:  # LF, so --check survives a fresh clone
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)
    return p


def write_svg(name: str, svg: Svg) -> pathlib.Path:
    svg.slug = name
    p = SITE / "figures" / f"{name}.svg"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(svg.render() + "\n")
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
    s.text((x0 + x1) / 2, h - 8, "minutes elapsed in episode", anchor="middle")
    s.text(12, (y0 + y1) / 2, "hazard / min", anchor="middle",
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
               f'><title>lead {v:g} min: {c} episode(s)</title></rect'.replace("</rect", "</rect"))
        if c == mx or i % 3 == 0:
            s.text(x0 + i * bw + bw / 2, y1 + 15, f"{v:g}", anchor="middle")
    s.line(x0, y1, x1, y1)
    s.text((x0 + x1) / 2, h - 8, "lead (min) vs the causal detector", anchor="middle")
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
               f'><title>market {i + 1}: +{r["delta"]:.1f} nats, '
               f'{int(r["n_events"])} events, {esc(r["category"])}</title></rect')
    s.text((x0 + x1) / 2, h - 8, f"{len(vals)} markets, sorted by gain (log scale)",
           anchor="middle")
    s.text(12, (y0 + y1) / 2, "Δ nats", anchor="middle",
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
               f'><title>{r[0]}: {r[1]:.3f}/min, CI [{r[2]:.3f}, {r[3]:.3f}]</title></rect')
        s.line(sx(r[2]), y, sx(r[3]), y, "axis")
        s.text(sx(r[1]) + 8, y + 4, f"{r[1]:.3f} /min", cls="lbl-i")
        s.text(0, y + 22, f"~{r[4]:.0f} min dwell")
    s.line(x0, h - PAD_B + 4, x1, h - PAD_B + 4)
    for t in (0, 0.5, 1.0, 1.5):
        s.text(sx(t), h - PAD_B + 19, f"{t:g}", anchor="middle")
    s.text((x0 + x1) / 2, h - 6, "repricings per minute", anchor="middle")
    write_svg("fig-two-state", s)


def fig_strategies() -> None:
    """Four candidate strategies against the 0.05 significance line."""
    rows = [r for r in load_strategies() if not r["strategy"].startswith("baseline")]
    write_csv("strategies.csv",
              ["strategy", "n_markets", "trades_taken", "p_value_vs_random", "verdict"],
              [[r["strategy"], r["n_markets"], r["trades_taken"], r["p_value_vs_random"],
                r["verdict"]] for r in rows])

    h = 40 + 40 * len(rows)
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
                   f'><title>{r["strategy"]}: p = {p:.3f} vs random, {r["trades_taken"]} '
                   f"trades</title></rect")
            s.text(sx(p) + 8, y + 4, f"p = {p:.3f}", cls="lbl-i")
            s.text(W - PAD_R, y + 4, r["verdict"], anchor="end")
    s.line(x0, h - 22, x1, h - 22)
    for t in (0, 0.25, 0.5, 0.75):
        s.text(sx(t), h - 8, f"{t:g}", anchor="middle")
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
        for v in vals:
            s.add(f'<circle cx="{sx(v):.1f}" cy="{y:.1f}" r="1.8" class="dot-2"/>')
        s.add(f'<circle cx="{sx(agg[m]):.1f}" cy="{y:.1f}" r="4.5" class="dot">'
              f"<title>{m}: pooled macro-F1 {agg[m]:.4f}; per-subject range "
              f"{min(vals):.3f}–{max(vals):.3f}</title></circle>")
        s.text(W - PAD_R, y + 4, f"{agg[m]:.3f}", anchor="end", cls="lbl-i")
    yb = PAD_T + 20 + len(BSC_MODELS) * 42 - 12
    s.line(x0, yb, x1, yb)
    for t in (0.3, 0.5, 0.7, 0.9):
        s.text(sx(t), yb + 15, f"{t:g}", anchor="middle")
    s.text((x0 + x1) / 2, yb + 30, "macro-F1   ● pooled   · one subject", anchor="middle")
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

    cw, rh = 58, 26
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
    for i, m in enumerate(BSC_MODELS):
        y = y0 + i * rh
        s.text(0, y + 13, m, cls="lbl-i")
        vmap = dict((k, v) for k, v, _ in data[m])
        for j, c in enumerate(classes):
            v = vmap[c]
            cx = x0 + j * cw
            s.rect(cx, y + 14, (cw - 10) * v, 4, "bar",
                   f"><title>c{c}: {v:.3f}</title></rect")
            s.text(cx, y + 10, f"{v:.2f}", cls="lbl-i")
    s.text(0, h - 26, "column = activity class, with its sample count below the label")
    s.text(0, h - 12, "bar length = F1 for that class; full width would be 1.00")
    write_svg("fig-perclass", s)


FIGURES = [fig_hazard, fig_lead, fig_lead_metrics, fig_pooling,
           fig_two_state, fig_strategies, fig_models, fig_perclass]


def inject() -> list[str]:
    """Inline each generated SVG into the pages between its FIGURE markers."""
    changed = []
    for page in sorted(SITE.rglob("*.html")):
        text = original = page.read_text()
        for m in re.finditer(r"<!-- FIGURE:([\w-]+) -->.*?<!-- /FIGURE:\1 -->", text, re.S):
            name = m.group(1)
            svg = SITE / "figures" / f"{name}.svg"
            if not svg.exists():
                print(f"  ! {page.name}: no figure named {name}", file=sys.stderr)
                continue
            block = (f"<!-- FIGURE:{name} -->\n{svg.read_text().strip()}\n<!-- /FIGURE:{name} -->")
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
