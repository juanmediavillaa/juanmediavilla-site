#!/usr/bin/env python3
"""Build /notebook from content/positions/*.md, data/prices.json, data/portfolio.json.

Three inputs, kept apart on purpose:

  content/positions/*.md   what I wrote, and the facts I supply per position —
                           ticker, average cost, weight, and prose. A feed never
                           touches it.
  data/prices.json         the last price of each ticker, in the price currency.
                           Read only through tools/prices.py.
  data/portfolio.json      book-level state: cash, the NAV index series, the two
                           aggregate returns. Read only through tools/portfolio.py.

**Percentages and prices only.** No amount, share count, unit count or account
value appears in any of these files or on any page built from them, and both
accessors refuse fields that look like one. A single absolute number, set beside
a percentage that is already published, reconstructs the size of the book — so
the rule is not "round the amounts down", it is "never carry one".

Two currencies, which is why the returns need care. Prices are quoted in one
currency and the book is denominated in another, so a position's return in the
book includes the currency move and is NOT recoverable from the price alone. The
book figure is what the page shows, because it is what actually happened; the
price-derived figure is computed anyway and the gap between the two is reconciled
by --selftest, which is how a mistyped cost or a stale price gets caught.

Standard library only. Run:

  python3 tools/build_notebook.py             # write the pages
  python3 tools/build_notebook.py --check     # fail if any output would change
  python3 tools/build_notebook.py --selftest  # reconcile every derived number
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from portfolio import Portfolio, PortfolioError  # noqa: E402
from prices import Prices, Quote  # noqa: E402
from sitegen import (  # noqa: E402
    SITE, MINUS, ContentError, blocks, date as _date, emit, esc, foot, head,
    parse_front_matter, slugify,
)

CONTENT = SITE / "content" / "positions"
OUT = SITE / "notes" / "investing"

# CONTENT-RULES.md §4.3 forbids publishing fund state outright. This section is
# built and reviewable but NOT published, the same way
# research/thesis/pre-registration/ is. Publishing needs that rule amended first.
NOINDEX = True

UP = "↑"
DOWN = "↓"
STATUS_LABEL = {"open": "Open", "closed": "Closed", "watchlist": "Watchlist"}


# --------------------------------------------------------------- logo ground
# Brand marks are drawn for a light page. On the dark plane a near-black one
# disappears, and recolouring somebody else's logo to suit the theme is not an
# option. So the ground is pinned instead — but only for the marks that actually
# need it, measured rather than assumed: any fill under 2:1 against --plane in
# dark means part of the artwork would be lost.
DARK_PLANE_LUM = 0.003785   # #0C0C10, computed the same way tools/audit.js does


def _lum(hexcolour: str) -> float | None:
    h = hexcolour.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    except ValueError:
        return None
    f = lambda v: v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


# The handful of CSS colour keywords that turn up in real brand SVGs. An
# unrecognised keyword is deliberately NOT added here: it is treated as dark
# below, so a mark painted in something this cannot read gets a ground rather
# than disappearing.
NAMED = {
    "black": "#000000", "white": "#ffffff", "red": "#ff0000", "lime": "#00ff00",
    "blue": "#0000ff", "yellow": "#ffff00", "cyan": "#00ffff", "aqua": "#00ffff",
    "magenta": "#ff00ff", "fuchsia": "#ff00ff", "silver": "#c0c0c0",
    "gray": "#808080", "grey": "#808080", "maroon": "#800000",
    "olive": "#808000", "green": "#008000", "purple": "#800080",
    "teal": "#008080", "navy": "#000080", "orange": "#ffa500",
}

DRAWABLE = {"path", "rect", "circle", "ellipse", "polygon", "polyline", "line",
            "text", "tspan"}


def _paint_lum(token: str | None) -> float | None:
    """Relative luminance of one paint value, or None where nothing is painted.

    `None` as the token means the property was never set anywhere up the tree.
    In SVG the initial value of `fill` is black, so that is the answer — not
    "unknown". Reading it as unknown is what made a black logo look safe.
    """
    if token is None:
        return _lum("#000000")
    tok = token.strip().lower()
    if tok in ("none", "transparent"):
        return None                       # nothing is drawn, so nothing to lose
    if tok.startswith("url(") or tok == "currentcolor":
        return None                       # a gradient or an inherited context;
                                          # gradient stops are measured separately
    if tok in NAMED:
        tok = NAMED[tok]
    if tok.startswith("#"):
        return _lum(tok)
    m = re.match(r"rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)", tok)
    if m:
        vals = []
        for raw in m.groups():
            v = float(raw)
            vals.append(v * 255 / 100 if "%" in tok else v)
        return _lum("#" + "".join(f"{max(0, min(255, int(round(v)))):02x}" for v in vals))
    # Unreadable. Treat it as the dangerous case rather than the safe one.
    return 0.0


def _class_fills(text: str) -> dict[str, str]:
    """fill declarations from any <style> block, keyed by class name."""
    out: dict[str, str] = {}
    for block in re.findall(r"<style[^>]*>(.*?)</style>", text, re.S | re.I):
        for selector, body in re.findall(r"([^{}]+)\{([^{}]*)\}", block):
            m = re.search(r"(?:^|[;\s])fill\s*:\s*([^;}]+)", body)
            if not m:
                continue
            for sel in selector.split(","):
                sel = sel.strip()
                if sel.startswith("."):
                    out[sel[1:]] = m.group(1).strip()
    return out


def effective_fills(text: str) -> list[float]:
    """Luminance of every fill the renderer would actually paint."""
    css = _class_fills(text)
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return [0.0]                      # unparseable: assume the worst

    found: list[float] = []

    def resolve(el, inherited: str | None) -> None:
        tag = el.tag.split("}")[-1]
        fill = el.get("fill")
        style = el.get("style") or ""
        m = re.search(r"(?:^|[;\s])fill\s*:\s*([^;]+)", style)
        if m:
            fill = m.group(1).strip()
        if fill is None:
            for cls in (el.get("class") or "").split():
                if cls in css:
                    fill = css[cls]
                    break
        current = fill if fill is not None else inherited
        if tag in DRAWABLE:
            lum = _paint_lum(current)
            if lum is not None:
                found.append(lum)
        elif tag == "stop":               # gradient stops are painted too
            lum = _paint_lum(el.get("stop-color"))
            if lum is not None:
                found.append(lum)
        for child in el:
            resolve(child, current)

    resolve(root, root.get("fill"))
    return found


def needs_ground(slug: str) -> bool:
    """True where any painted part of the mark would be lost on the dark plane.

    Recolouring somebody else's logo is not an option, so the fix is a light
    ground behind it — but only where it is needed, which is a measurement
    rather than a judgement. The bar is 2:1 against --plane.
    """
    svg = SITE / "assets" / "logos" / f"{slug}.svg"
    if not svg.exists():
        # A raster logo, or none at all. tools/make_logos.py refuses to install
        # a raster that would need a ground, so False is correct by
        # construction here rather than by luck.
        return False
    for lum in effective_fills(svg.read_text(encoding="utf-8")):
        if (max(lum, DARK_PLANE_LUM) + 0.05) / (min(lum, DARK_PLANE_LUM) + 0.05) < 2.0:
            return True
    return False


# ====================================================================== load

def _num(value: object, where: str, field: str, *, positive: bool = True) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ContentError(f"{where}: {field} must be a number, got {value!r}")
    if positive and value <= 0:
        raise ContentError(f"{where}: {field} must be above zero, got {value!r}")
    return float(value)


def _fills(rows: object, where: str, field: str) -> list[dict]:
    """Dated prices, optionally carrying a share OF THE POSITION.

    `share` is a percentage of the position's own units — never an amount and
    never a count — so it weights the average without disclosing size.
    """
    if not isinstance(rows, list):
        raise ContentError(f"{where}: {field} must be a list")
    out = []
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ContentError(f"{where}: {field}[{i}] must be a mapping")
        fill = {"date": _date(row.get("date"), where, f"{field}[{i}].date"),
                "price": _num(row.get("price"), where, f"{field}[{i}].price")}
        if "share" in row:
            fill["share"] = _num(row["share"], where, f"{field}[{i}].share")
        out.append(fill)
    out.sort(key=lambda f: f["date"])
    shares = [f for f in out if "share" in f]
    if shares and len(shares) != len(out):
        raise ContentError(f"{where}: {field} mixes rows with and without a share")
    if shares and abs(sum(f["share"] for f in shares) - 100) > 0.01:
        raise ContentError(f"{where}: {field} shares must total 100")
    return out


def load_position(path: pathlib.Path) -> dict:
    where = path.relative_to(SITE).as_posix()
    front, body = parse_front_matter(path.read_text(encoding="utf-8"), where)

    for required in ("ticker", "name", "status", "updated"):
        if required not in front:
            raise ContentError(f"{where}: missing required field {required}")

    status = str(front["status"])
    if status not in STATUS_LABEL:
        raise ContentError(f"{where}: status must be open, closed or watchlist")

    entries = _fills(front.get("entries", []), where, "entries")
    exits = _fills(front.get("exits", []), where, "exits")
    if status == "closed" and not exits:
        raise ContentError(f"{where}: a closed position needs at least one exit")
    if status == "open" and exits:
        raise ContentError(f"{where}: an open position cannot carry an exit")
    if not entries and "avgCost" not in front and status != "watchlist":
        raise ContentError(f"{where}: needs either an entries ledger or avgCost")


    return {
        "file": where,
        "ticker": str(front["ticker"]).strip().upper(),
        "name": str(front["name"]).strip(),
        # Optional: the themes are his classification, and a position sits
        # without one rather than being filed under a guess.
        "theme": str(front.get("theme", "")).strip(),
        "status": status,
        "entries": entries,
        "exits": exits,
        "avgCost": _num(front["avgCost"], where, "avgCost") if "avgCost" in front else None,

        "summary": str(front.get("summary", "")).strip(),
        "updated": _date(front["updated"], where, "updated"),
        # The filename is authoritative, so content/positions/x.md, notebook/x/
        # and assets/logos/x.* always line up. Deriving it from the name instead
        # silently detaches an asset from its position.
        "slug": str(front.get("slug") or path.stem or slugify(front["name"])),
        # Logo is optional and derived from the slug. Until one exists the card
        # shows a monogram in the same box, so the layout does not shift when
        # the artwork arrives.
        "logo": next((f"{p.stem}{p.suffix}" for p in sorted(
            (SITE / "assets" / "logos").glob(f"{path.stem}.*"))), None),
        "logoGround": needs_ground(path.stem),
        "sections": parse_body(body, where),
    }


def parse_body(body: str, where: str) -> list[dict]:
    sections: list[dict] = []
    for chunk in re.split(r"^(##\s+.*)$", body, flags=re.M):
        chunk = chunk.strip("\n")
        if chunk.startswith("## "):
            sections.append({"title": chunk[3:].strip(), "md": ""})
        elif chunk.strip():
            if not sections:
                raise ContentError(f"{where}: prose before the first ## heading")
            sections[-1]["md"] = (sections[-1]["md"] + "\n\n" + chunk).strip()
    return sections


# ==================================================================== derive

def cost_basis(entries: list[dict]) -> float | None:
    """Weighted average entry price, computed from the ledger. Never stored.

    Weights are each entry's `share` when given, equal otherwise. A position
    whose per-trade ledger was not supplied falls back to a stated average cost,
    and the page says which of the two a reader is looking at.
    """
    if not entries:
        return None
    if all("share" in e for e in entries):
        total = sum(e["share"] for e in entries)
        return sum(e["price"] * e["share"] for e in entries) / total
    return sum(e["price"] for e in entries) / len(entries)


def view(position: dict, prices: Prices) -> dict:
    v = dict(position)
    computed = cost_basis(position["entries"])
    v["basis"] = computed if computed is not None else position["avgCost"]
    v["basisSource"] = "computed" if computed is not None else "supplied"
    v["opened"] = position["entries"][0]["date"] if position["entries"] else None

    if position["status"] == "closed":
        last = position["exits"][-1]
        v.update(price=last["price"], asOf=last["date"], previousClose=None,
                 priceSource="exit", priceNote="frozen at my exit")
    elif position["status"] == "watchlist":
        v.update(price=None, asOf=None, previousClose=None,
                 priceSource="none", priceNote="not held")
    else:
        q: Quote = prices.quote(position["ticker"])
        v.update(price=q.price, asOf=q.as_of, previousClose=q.previous_close,
                 priceSource="feed" if q.available else "none",
                 priceNote="" if q.available else q.reason)

    # Derived from cost and price, never stored. One currency throughout, so
    # this is the whole of the return and there is no second figure to reconcile
    # against — which is what makes it correct the moment a new price lands.
    if v["basis"] and v["price"] is not None:
        v["returnPct"] = (v["price"] - v["basis"]) / v["basis"] * 100
    else:
        v["returnPct"] = None
    return v


# =================================================================== format

def signed(value: float, places: int = 1) -> str:
    return ("+" if value >= 0 else MINUS) + f"{abs(value):.{places}f}%"


def money(value: float) -> str:
    return f"{value:,.2f}"


def return_html(v: dict, *, big: bool = False) -> str:
    """Direction encoded three ways: arrow, sign, then colour.

    Colour alone would fail a reader with deuteranopia — CONTENT-RULES §11 puts
    green and pink at delta-E 7.7 on the dark plane — so the arrow and the sign
    carry the same information and the colour is the third copy.
    """
    size = " pos__ret--big" if big else ""
    if v["returnPct"] is None:
        reason = v["priceNote"] or "price unavailable"
        return (f'<span class="pos__ret is-unknown{size}">'
                f'<span class="pos__dash">{MINUS}</span> '
                f'<span class="pos__why">{esc(reason)}</span></span>')
    cls = "is-gain" if v["returnPct"] >= 0 else "is-loss"
    arrow = UP if v["returnPct"] >= 0 else DOWN
    return (f'<span class="pos__ret {cls}{size}">'
            f'<span class="pos__dir" aria-hidden="true">{arrow}</span> '
            f'{signed(v["returnPct"])}</span>')


# =================================================================== figures

def read_series(name: str) -> dict:
    """A figure's numbers and its caption, both from the committed CSV.

    The numbers are never retyped into markup (CONTENT-RULES §7), and the file
    is linked under the chart so a reader can take the same numbers away.
    Lines beginning `#` carry the title, caption and provenance, so a figure
    cannot drift from the words describing it — they live in one file.
    """
    path = SITE / "data" / name
    if not path.exists():
        raise ContentError(f"figure source {name} does not exist")
    meta, rows = {}, []
    header = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        if line.startswith("#"):
            key, _, value = line.lstrip("# ").partition(":")
            meta[key.strip().lower()] = value.strip()
        elif header is None:
            header = [c.strip() for c in line.split(",")]
        else:
            cells = [c.strip() for c in line.split(",")]
            rows.append(dict(zip(header, cells)))
    if not rows:
        raise ContentError(f"figure source {name} has no rows")
    # How a value is written. Defaults to a percentage because most figures here
    # are rates, but a chart of dollars must not be able to render "220%".
    meta.setdefault("format", "{v}%")
    if "{v}" not in meta["format"]:
        raise ContentError(f"figure source {name}: `# format:` must contain {{v}}")
    for k in ("title", "caption", "provenance"):
        if k not in meta:
            raise ContentError(f"figure source {name} has no `# {k}:` line")
    return {"meta": meta, "rows": rows, "file": name}


def bar_chart(series: dict) -> str:
    """Horizontal bars as inline SVG.

    Inline so it inherits the page's custom properties and follows the manual
    theme toggle; a referenced <img> can only see prefers-color-scheme (§16).
    One colour for every bar — the label carries the meaning, so a greyscale
    print loses nothing and no series slot is cycled (§11). Authored at 640
    wide with 12px type and never scaled down (§14, §15).
    """
    rows = series["rows"]
    fmt = series["meta"]["format"]
    # The label gutter is measured, not fixed: Plex Mono advances about 0.6em,
    # so a 12px glyph is ~7.2px wide. A hardcoded 210px gutter clipped
    # "Share of subscription revenue" straight off the left edge of the viewBox.
    # The canvas is a CONSTANT 640 wide for every chart on the site. Sizing it
    # to content instead gave two charts different viewBox widths, and since
    # both stretch to the same container, identical 12px type rendered at
    # different sizes on the same page.
    CHAR, W, R, TOP, ROW = 7.2, 640, 54, 30, 42
    longest = max(max(len(r["measure"]), len(r.get("note", ""))) for r in rows)
    L = min(round(longest * CHAR) + 24, 300)
    BARS = W - L - R
    H = TOP + ROW * len(rows) + 12
    top = max(float(r["percent"]) for r in rows)
    scale = BARS / (top * 1.12)

    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="'
           + esc(series["meta"]["title"]) + ": "
           + esc(", ".join(f'{r["measure"]} {fmt.replace("{v}", r["percent"])}'
                             for r in rows)) + '">']
    for i, r in enumerate(rows):
        y = TOP + i * ROW
        w = float(r["percent"]) * scale
        out.append(f'<text x="{L - 12}" y="{y + 15:.0f}" text-anchor="end" '
                   f'font-family="var(--mono)" font-size="12" fill="var(--ink)">'
                   f'{esc(r["measure"])}</text>')
        out.append(f'<rect x="{L}" y="{y + 4:.0f}" width="{w:.1f}" height="16" rx="2" '
                   f'fill="var(--accent)"/>')
        out.append(f'<text x="{L + w + 8:.1f}" y="{y + 16:.0f}" '
                   f'font-family="var(--mono)" font-size="12" fill="var(--ink)">'
                   f'{fmt.replace("{v}", r["percent"])}</text>')
        if r.get("note"):
            out.append(f'<text x="{L - 12}" y="{y + 29:.0f}" text-anchor="end" '
                       f'font-family="var(--mono)" font-size="12" fill="var(--ink-3)">'
                       f'{esc(r["note"])}</text>')
    out.append(f'<line x1="{L}" y1="{TOP - 6}" x2="{L}" y2="{H - 10}" '
               f'stroke="var(--line-2)" stroke-width="1"/>')
    out.append("</svg>")
    return "\n            ".join(out)


def ticks(top: float) -> list[int]:
    """Gridline levels that fit the range, rather than a fixed ladder.

    The levels were hardcoded to 0/25/50/75/100. On any column chart topping out
    below about 60 that put three of the five lines at a negative y, outside the
    viewBox: the Meta revenue chart peaks at 33% and was drawing its 50, 75 and
    100 lines at y=-37, -154 and -271, so they were silently clipped and the
    chart shipped with two gridlines and no usable axis.

    Steps are chosen from a round-number ladder so the labels stay readable, and
    at most five lines are drawn.
    """
    for step in (1, 2, 5, 10, 20, 25, 50, 100, 200, 500, 1000):
        if top / step <= 5:
            break
    return [step * i for i in range(int(top // step) + 1)]


def column_chart(series: dict) -> str:
    """A time series as columns, on the same 640 canvas.

    A target is drawn open rather than filled: an ambition and a result must not
    look like the same kind of thing.
    """
    rows = series["rows"]
    fmt = series["meta"]["format"]
    W, H, L, R, TOP, BASE = 640, 250, 46, 16, 26, 196
    step = (W - L - R) / len(rows)
    bw = min(step * 0.58, 54)
    top = max(float(r["value"]) for r in rows) * 1.1

    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="'
           + esc(series["meta"]["title"]) + ": "
           + esc(", ".join(f'{r["period"]} {fmt.replace("{v}", r["value"])}'
                             for r in rows)) + '">']
    for level in ticks(top):
        y = BASE - level / top * (BASE - TOP)
        out.append(f'<line x1="{L}" y1="{y:.1f}" x2="{W - R}" y2="{y:.1f}" '
                   f'stroke="var(--line)" stroke-width="1"/>')
        out.append(f'<text x="{L - 9}" y="{y + 4:.1f}" text-anchor="end" '
                   f'font-family="var(--mono)" font-size="12" fill="var(--ink-3)">{level}</text>')
    for i, r in enumerate(rows):
        v = float(r["value"])
        x = L + i * step + (step - bw) / 2
        h = v / top * (BASE - TOP)
        target = r.get("kind") == "target"
        fill = ('fill="none" stroke="var(--accent)" stroke-width="2" stroke-dasharray="5 3"'
                if target else 'fill="var(--accent)"')
        out.append(f'<rect x="{x:.1f}" y="{BASE - h:.1f}" width="{bw:.1f}" height="{h:.1f}" '
                   f'rx="2" {fill}/>')
        out.append(f'<text x="{x + bw / 2:.1f}" y="{BASE - h - 7:.1f}" text-anchor="middle" '
                   f'font-family="var(--mono)" font-size="12" fill="var(--ink)">'
                   f'{fmt.replace("{v}", r["value"])}</text>')
        out.append(f'<text x="{x + bw / 2:.1f}" y="{BASE + 18:.0f}" text-anchor="middle" '
                   f'font-family="var(--mono)" font-size="12" fill="var(--ink-3)">'
                   f'{esc(r["period"])}</text>')
        if r.get("note"):
            out.append(f'<text x="{x + bw / 2:.1f}" y="{BASE + 34:.0f}" text-anchor="middle" '
                       f'font-family="var(--mono)" font-size="12" fill="var(--ink-3)">'
                       f'{esc(r["note"])}</text>')
    out.append(f'<line x1="{L}" y1="{BASE}" x2="{W - R}" y2="{BASE}" '
               f'stroke="var(--line-2)" stroke-width="1"/>')
    out.append("</svg>")
    return "\n            ".join(out)


def figure(name: str) -> str:
    s = read_series(name)
    m = s["meta"]
    if "unit" not in m:
        raise ContentError(f"figure source {name} has no `# unit:` line — a chart that "
                           f"does not say what its numbers are invites the reader to guess")
    columns = m.get("kind") == "columns"
    key, val = ("period", "value") if columns else ("measure", "percent")
    svg = column_chart(s) if columns else bar_chart(s)
    table = "".join(
        f'<tr><td>{esc(r[key])}</td>' + f'<td class="n">{m["format"].replace(chr(123) + "v" + chr(125), r[val])}</td>'
        f'<td>{esc(r.get("note", ""))}</td></tr>' for r in s["rows"])
    return f"""        <figure>
          <p class="fig-title">{esc(m["title"])}</p>
          <p class="fig-unit">{esc(m["unit"])}</p>
          <div class="scroll" role="region" aria-label="{esc(m["title"])}" tabindex="0">
            {svg}
          </div>
          <p class="scroll-hint">Scroll the chart sideways&nbsp;&rarr;</p>
          <figcaption>
            <b>What you're looking at:</b> {esc(m["caption"])}
            <span class="prov">{esc(m["provenance"])}
              Source numbers: <a href="../../../data/{esc(name)}">{esc(name)}</a>.</span>
          </figcaption>
          <details class="figdata"><summary>Show the numbers</summary>
            <table><thead><tr><th>{"Period" if columns else "Measure"}</th>
            <th class="n">Value</th><th>Note</th></tr></thead>
            <tbody>{table}</tbody></table>
          </details>
        </figure>
"""


# ================================================================ components

def card(v: dict) -> str:
    """One holding, as a card. The same shape as the shelf on /books: a brief
    overview here, the thesis and the movements one click away."""
    if v["logo"]:
        ground = " pos__logo--ground" if v["logoGround"] else ""
        mark = (f'              <img class="pos__logo{ground}" src="../../assets/logos/{v["logo"]}" '
                f'alt="" loading="lazy" decoding="async" width="96">\n')
    else:
        mark = (f'              <span class="pos__logo pos__logo--none" aria-hidden="true">'
                f'{esc(v["ticker"][:2])}</span>\n')
    ret = "" if v["returnPct"] is None else f'{v["returnPct"]:.4f}'
    return (
        f'          <a class="card pos" href="{esc(v["slug"])}/index.html"\n'
        f'             data-return="{ret}" data-ticker="{esc(v["ticker"])}">\n'
        f'            <span class="pos__head">\n{mark}'
        f'              <span class="pos__id">\n'
        f'                <span class="pos__ticker">{esc(v["ticker"])}</span>\n'
        f'                <span class="pos__class">{esc(v["theme"])}</span>\n'
        f'              </span>\n'
        f'            </span>\n'
        f'            <h3>{esc(v["name"])}</h3>\n'
        f'            <span class="pos__sum">{esc(v["summary"])}</span>\n'
        f'            <span class="pos__figs">\n'
        f'              <span class="pos__fig">\n'
        f'                <span class="pos__lab">Bought at</span>\n'
        f'                <span class="pos__val">{money(v["basis"])}</span>\n'
        f'              </span>\n'
        f'              <span class="pos__fig">\n'
        f'                <span class="pos__lab">Now</span>\n'
        f'                <span class="pos__val">{money(v["price"]) if v["price"] else MINUS}</span>\n'
        f'              </span>\n'
        f'              <span class="pos__fig">\n'
        f'                <span class="pos__lab">Unrealised</span>\n'
        f'                {return_html(v)}\n'
        f'              </span>\n'
        f'            </span>\n'
        f'            <span class="pos__go">Thesis and movements&nbsp;&rarr;</span>\n'
        f'          </a>\n')


def grid(views: list[dict]) -> str:
    if not views:
        return '        <p class="pos__empty">No open positions.</p>\n'
    return ('        <div class="cards cards--pos">\n'
            + "".join(card(v) for v in views) + "        </div>\n")


# ================================================================ index page

STANDING_NOTE = """
        <p>
          This is not advice, and it is not a suggestion that anyone buy or sell anything. I have
          no idea what would suit anybody else's circumstances and I am not trying to work it out.
          Positions appear here after I have already taken them, so nothing on this page is a
          signal about what I am about to do, and I change my mind without updating it promptly.
        </p>
        <p>
          There are no position sizes anywhere on this page — no weight, no share of equity, no
          cash line and no amounts — and none in the files it is built from either.
        </p>
"""


def build_index(views: list[dict], prices: Prices, pf: Portfolio) -> str:
    open_v = sorted([v for v in views if v["status"] == "open"], key=lambda v: v["ticker"])
    # Oldest quote actually used, never the newest: printing the freshest date
    # would imply the whole page is that fresh.
    priced = prices.oldest_as_of([v["ticker"] for v in open_v
                                  if v["priceSource"] == "feed"])
    rddt = next((v["returnPct"] for v in open_v if v["ticker"] == "RDDT"), None)

    doc = [head("Investing — Notes — Juan Mediavilla",
                "What I bought, when, and what happened since — the ledger, in percentages and "
                "share prices, with no amounts anywhere.", 2,
                here="notes/index.html", noindex=NOINDEX)]

    doc.append(f"""
<header class="head">
  <div class="wrap">
    <p class="eyebrow">Notebook</p>
    <h1>What I bought, and what happened</h1>
    <p class="standfirst">
      {len(open_v)} positions: the price I paid for each, and what it trades at now.
    </p>
  </div>
</header>

<section class="section reveal">
  <div class="wrap">
    <div class="rail">
      <div class="rail__label">
        <p class="eyebrow">Standing note</p>
        <p class="meta">One note.<br>It applies to<br>everything here.</p>
      </div>
      <div class="rail__body">
{STANDING_NOTE}      </div>
    </div>
  </div>
</section>

<section class="section reveal">
  <div class="wrap">
    <div class="rail">
      <div class="rail__label">
        <p class="eyebrow">The book</p>
        <p class="meta">{len(open_v)} positions.<br>Priced {esc(priced or pf.as_of)}.</p>
      </div>
      <div class="rail__body">
        <h2>Positions</h2>
        <p>
          What I paid, what it trades at now, and the change between the two, quoted in
          {esc(pf.currency)}.
        </p>
{grid(open_v)}      </div>
    </div>
  </div>
</section>

<section class="section reveal">
  <div class="wrap">
    <div class="rail">
      <div class="rail__label"><p class="eyebrow">Provenance</p></div>
      <div class="rail__body">
        <h2>Where these numbers come from</h2>
        <p class="meta">
          Prices: {esc(prices.feed)}, {esc(pf.currency)}, as of {esc(priced or "—")}.<br>
          Cost: as supplied, {esc(pf.as_of)}. The per-trade ledger is not in these files.<br>
          No aggregate return, no history, no position sizes: none of it is in these files.
        </p>
      </div>
    </div>
  </div>
</section>
""")
    doc.append(foot(2))
    return "".join(doc)


# ============================================================= position page

def build_position(v: dict, prev: dict | None, nxt: dict | None, pf: Portfolio) -> str:
    basis_note = ("weighted average of "
                  f'{len(v["entries"])} entr{"y" if len(v["entries"]) == 1 else "ies"}'
                  if v["basisSource"] == "computed" else "average cost, as supplied")

    theme = (f'<span class="pos__class">{esc(v["theme"])}</span>' if v["theme"] else "")
    ground = " pos__logo--ground" if v["logoGround"] else ""
    mark = (f'<img class="pos__logo pos__logo--lg{ground}" src="../../../assets/logos/{v["logo"]}" '
            f'alt="" width="96">' if v["logo"] else
            f'<span class="pos__logo pos__logo--lg pos__logo--none" aria-hidden="true">'
            f'{esc(v["ticker"][:2])}</span>')


    doc = [head(f'{v["ticker"]} {v["name"]} — Investing — Notes — Juan Mediavilla',
                f'{v["ticker"]} — {v["name"]}', 3,
                here="notes/index.html", noindex=NOINDEX)]

    # Guarded, because prices.py returns an unavailable quote rather than
    # raising and this page has to survive one: a position added before its
    # first fetch has no price yet, and the card at the index already shows an
    # em dash in that case. Without the guard money(None) raised a TypeError and
    # took the whole build down.
    last_note = f"last · {v['asOf']}" if v["price"] else "no quote yet"

    doc.append(f"""
<header class="head">
  <div class="wrap">
    <p class="eyebrow"><a href="../index.html">Notebook</a></p>
    <h1>{esc(v['name'])}</h1>
    <p class="pos__ident">
      {mark}
      <span class="pos__ticker pos__ticker--lg">{esc(v['ticker'])}</span>
      <span class="pos__status pos__status--{esc(v['status'])}">{STATUS_LABEL[v['status']]}</span>
      {theme}
    </p>
    <ul class="keyfacts">
      <li>{return_html(v, big=True)}<span>unrealised, {esc(pf.currency)}</span></li>
      <li><b>{money(v['basis'])}</b><span>{esc(basis_note)}</span></li>
      <li><b>{money(v['price']) if v['price'] else MINUS}</b><span>{esc(last_note)}</span></li>
    </ul>
  </div>
</header>

<section class="section reveal">
  <div class="wrap">
    <div class="rail">
      <div class="rail__label">
        <p class="eyebrow">The record</p>
        <p class="meta">Updated<br>{esc(v['updated'])}.</p>
      </div>
      <div class="rail__body">
""")
    # Nothing is written for him. Both sections stay stubbed until he supplies
    # the words, because a page that invents a reason after the outcome is
    # already on screen is worse than a page that admits it is unfinished.
    have = {s["title"].lower() for s in v["sections"]}
    for title in ("Thesis", "Latest movements"):
        if title.lower() in have:
            continue
        doc.append(
            f"        <h2>{title}</h2>" + chr(10)
            + '        <div class="callout">' + chr(10)
            + "          <p>Under construction &mdash; not written up yet.</p>" + chr(10)
            + "        </div>" + chr(10))
    for s in v["sections"]:
        doc.append(f"        <h2>{esc(s['title'])}</h2>" + chr(10))
        # a line of "@figure name.csv" renders the chart; the rest is prose
        buf: list[str] = []
        for para in s["md"].split(chr(10) + chr(10)):
            if para.strip().startswith("@figure "):
                if buf:
                    doc.append(blocks((chr(10) * 2).join(buf)) + chr(10))
                    buf = []
                doc.append(figure(para.strip().split(None, 1)[1].strip()))
            else:
                buf.append(para)
        if buf:
            doc.append(blocks((chr(10) * 2).join(buf)) + chr(10))
    doc.append("""      </div>
    </div>
  </div>
</section>

<section class="section reveal">
  <div class="wrap">
    <nav class="pager" aria-label="Positions">
""")
    if prev:
        doc.append(f'      <a href="../{esc(prev["slug"])}/index.html">'
                   f'<span>Previous</span>{esc(prev["ticker"])} {esc(prev["name"])}</a>\n')
    else:
        doc.append("      <span></span>\n")
    if nxt:
        doc.append(f'      <a href="../{esc(nxt["slug"])}/index.html">'
                   f'<span>Next</span>{esc(nxt["ticker"])} {esc(nxt["name"])}</a>\n')
    doc.append("""    </nav>
    <p class="pos__back"><a href="../index.html">The whole book&nbsp;→</a></p>
  </div>
</section>
""")
    doc.append(foot(3))
    return "".join(doc)


# ==================================================================== runner

def render_all() -> dict[pathlib.Path, str]:
    files = sorted(CONTENT.glob("*.md"))
    if not files:
        raise ContentError(f"no position files in {CONTENT}")
    prices = Prices.load()
    pf = Portfolio.load()
    views = [view(load_position(p), prices) for p in files]

    seen: dict[str, str] = {}
    for v in views:
        for key in (v["ticker"], v["slug"]):
            if key in seen:
                raise ContentError(f'{v["file"]}: {key} already used by {seen[key]}')
            seen[key] = v["file"]

    rank = {"open": 0, "closed": 1, "watchlist": 2}
    # Alphabetical: ordering by size would re-encode the ranking that removing
    # the weights was meant to withhold.
    order = sorted(views, key=lambda v: (rank[v["status"]], v["ticker"]))

    pages = {OUT / "index.html": build_index(views, prices, pf)}
    written = list(order)
    for i, v in enumerate(written):
        pages[OUT / v["slug"] / "index.html"] = build_position(
            v, written[i - 1] if i else None,
            written[i + 1] if i + 1 < len(written) else None, pf)
    return pages


def selftest() -> int:
    """Reconcile every published number against its source."""
    checks: list[str] = []
    bad = 0

    def ok(label: str, passed: bool, detail: str = "") -> None:
        nonlocal bad
        checks.append(f'  {"ok  " if passed else "FAIL"} {label}'
                      f'{" — " + detail if detail else ""}')
        bad += 0 if passed else 1

    ok("share-weighted basis",
       abs(cost_basis([{"price": 41.80, "share": 60},
                       {"price": 52.15, "share": 40}]) - 45.94) < 1e-9)
    ok("equal-weighted basis",
       abs(cost_basis([{"price": 88.20}, {"price": 101.40}]) - 94.80) < 1e-9)
    ok("no-entry basis", cost_basis([]) is None)

    prices, pf = Prices.load(), Portfolio.load()
    views = [view(load_position(p), prices) for p in sorted(CONTENT.glob("*.md"))]
    open_v = [v for v in views if v["status"] == "open"]




    blob = (pathlib.Path("data/portfolio.json").read_text(encoding="utf-8")
            + pathlib.Path("data/prices.json").read_text(encoding="utf-8")).lower()
    src = "".join(f.read_text(encoding="utf-8") for f in CONTENT.glob("*.md"))
    ok("no content file carries a position weight",
       not any(k in src for k in ("weightPct", "equityPct", "% of book", "% of equity")))
    ok("no source file carries an absolute quantity",
       not any(k in blob for k in ("amount", "shares", "units", "member", "deposit", "balance")))

    print("\n".join(checks))
    print(f"  {sum(1 for c in checks if c.startswith('  ok'))} passed, {bad} failed")
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="fail if any page would change")
    ap.add_argument("--selftest", action="store_true", help="reconcile every derived number")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    try:
        pages = render_all()
    except (ContentError, PortfolioError) as exc:
        print(f"  content error: {exc}", file=sys.stderr)
        return 2
    return emit(pages, OUT, args.check, "notebook")


if __name__ == "__main__":
    sys.exit(main())
