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


def needs_ground(slug: str) -> bool:
    svg = SITE / "assets" / "logos" / f"{slug}.svg"
    if not svg.exists():
        return False
    fills = set(re.findall(r'(?:fill|stop-color)[=:]\s*["\']?(#[0-9a-fA-F]{3,6})',
                           svg.read_text(encoding="utf-8")))
    for f in fills:
        l = _lum(f)
        if l is None:
            continue
        if (max(l, DARK_PLANE_LUM) + 0.05) / (min(l, DARK_PLANE_LUM) + 0.05) < 2.0:
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

    for required in ("ticker", "name", "theme", "status", "updated"):
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
        "theme": str(front["theme"]).strip(),
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


# ================================================================ components

def card(v: dict) -> str:
    """One holding, as a card. The same shape as the shelf on /books: a brief
    overview here, the thesis and the movements one click away."""
    if v["logo"]:
        ground = " pos__logo--ground" if v["logoGround"] else ""
        mark = (f'              <img class="pos__logo{ground}" src="../../../assets/logos/{v["logo"]}" '
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
        f'                <span class="pos__lab">Unrealized</span>\n'
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
      Nine positions: the price I paid for each, and what it trades at now.
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

    ground = " pos__logo--ground" if v["logoGround"] else ""
    mark = (f'<img class="pos__logo pos__logo--lg{ground}" src="../../../assets/logos/{v["logo"]}" '
            f'alt="" width="96">' if v["logo"] else
            f'<span class="pos__logo pos__logo--lg pos__logo--none" aria-hidden="true">'
            f'{esc(v["ticker"][:2])}</span>')


    doc = [head(f'{v["ticker"]} {v["name"]} — Investing — Notes — Juan Mediavilla',
                f'{v["ticker"]} — {v["name"]}', 3,
                here="notes/index.html", noindex=NOINDEX)]

    doc.append(f"""
<header class="head">
  <div class="wrap">
    <p class="eyebrow"><a href="../index.html">Notebook</a></p>
    <h1>{esc(v['name'])}</h1>
    <p class="pos__ident">
      {mark}
      <span class="pos__ticker pos__ticker--lg">{esc(v['ticker'])}</span>
      <span class="pos__status pos__status--{esc(v['status'])}">{STATUS_LABEL[v['status']]}</span>
      <span class="pos__class">{esc(v['theme'])}</span>
    </p>
    <ul class="keyfacts">
      <li>{return_html(v, big=True)}<span>unrealized, {esc(pf.currency)}</span></li>
      <li><b>{money(v['basis'])}</b><span>{esc(basis_note)}</span></li>
      <li><b>{money(v['price'])}</b><span>last · {esc(v['asOf'])}</span></li>
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
        doc.append(f"        <h2>{esc(s['title'])}</h2>" + chr(10) + blocks(s["md"]) + chr(10))
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
