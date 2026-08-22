#!/usr/bin/env python3
"""Fetch the current price of every held ticker and write data/prices.json.

    python3 tools/fetch_prices.py [--dry-run]

This is the one piece of the notebook that talks to the network, and it runs in
CI, never in a reader's browser. **CONTENT-RULES.md §4.9 is about what the page
requests** — no CDN, no analytics, no off-origin subresource — and nothing here
changes that: the fetch happens on a build machine and only a committed JSON
file reaches the site. Worth stating plainly, because the audit's external
-subresource sweep reads HTML and would not notice this either way.

It is the only writer of `data/prices.json`. `tools/prices.py` is the only
reader. That split is the whole point of the design: going live meant replacing
this file and nothing else.

Rules it enforces, because a price feed is exactly where bad data enters:

  * **All or nothing.** Every ticker is fetched and validated before anything is
    written. A single failure aborts with a non-zero exit and leaves the existing
    file untouched, so a half-updated snapshot cannot ship.
  * **The date comes from the quote, never from the clock**, and is resolved in
    the exchange's own timezone — a UTC date rolls over while New York is still
    trading, which would stamp Friday's close as Saturday.
  * **The currency is checked against the one the site reports in.** A ticker
    that resolves to a different listing is refused rather than silently
    published as though it were comparable.
  * Nothing absolute is ever written here: a price is a price. No quantity, no
    holding, no total — see tools/portfolio.py for why that matters.

Standard library only, so CI needs no install step.
"""

from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request
import zoneinfo
# A Windows console is cp1252, which cannot encode the em dash, middle dot and
# arrow used in this script's progress output. The encode raises, and because
# the write to disk happens before the message, the run aborts having already
# applied part of its work. Force UTF-8 on the streams so a status line can
# never take down the job it is describing.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):   # already wrapped, or not a real tty
        pass


SITE = pathlib.Path(__file__).resolve().parent.parent
CONTENT = SITE / "content" / "positions"
OUT = SITE / "data" / "prices.json"
PORTFOLIO = SITE / "data" / "portfolio.json"

ENDPOINT = "https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=5d&interval=1d"
UA = {"User-Agent": "Mozilla/5.0 (compatible; juanmediavilla.com price updater)"}
FEED = "Yahoo Finance"
RETRIES = 3


def tickers() -> list[str]:
    """Every ticker the site actually holds, read from the content files."""
    out = []
    for f in sorted(CONTENT.glob("*.md")):
        m = re.search(r"^ticker:\s*(\S+)\s*$", f.read_text(encoding="utf-8"), re.M)
        if not m:
            raise SystemExit(f"  {f.name} has no ticker")
        out.append(m.group(1).upper())
    return out


def expected_currency() -> str:
    raw = json.loads(PORTFOLIO.read_text(encoding="utf-8"))
    return str(raw.get("currency", "USD")).upper()


def fetch(symbol: str) -> dict:
    """One quote, validated. Raises rather than returning something doubtful."""
    last = None
    for attempt in range(RETRIES):
        try:
            req = urllib.request.Request(ENDPOINT.format(sym=symbol), headers=UA)
            with urllib.request.urlopen(req, timeout=25) as r:
                payload = json.load(r)
            break
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last = exc
            if attempt < RETRIES - 1:
                time.sleep(2 ** attempt)
    else:
        raise RuntimeError(f"{symbol}: {last}")

    result = (payload.get("chart") or {}).get("result") or []
    if not result:
        err = ((payload.get("chart") or {}).get("error") or {}).get("description", "no result")
        raise RuntimeError(f"{symbol}: {err}")
    meta = result[0].get("meta") or {}

    price = meta.get("regularMarketPrice")
    if not isinstance(price, (int, float)) or isinstance(price, bool) or price <= 0:
        raise RuntimeError(f"{symbol}: price is {price!r}")

    stamp = meta.get("regularMarketTime")
    if not isinstance(stamp, (int, float)):
        raise RuntimeError(f"{symbol}: no market time on the quote")
    # The exchange's own day. Converting in UTC stamps a Friday close as Saturday
    # once New York's afternoon crosses midnight in London.
    tz = meta.get("exchangeTimezoneName") or "UTC"
    try:
        zone = zoneinfo.ZoneInfo(tz)
    except Exception:
        zone = datetime.timezone.utc
    as_of = datetime.datetime.fromtimestamp(stamp, zone).date().isoformat()

    row = {"price": round(float(price), 2), "asOf": as_of}
    prev = meta.get("chartPreviousClose") or meta.get("previousClose")
    if isinstance(prev, (int, float)) and not isinstance(prev, bool) and prev > 0:
        row["previousClose"] = round(float(prev), 2)
    return {"row": row, "currency": str(meta.get("currency", "")).upper()}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true",
                    help="fetch and report, but do not write the file")
    args = ap.parse_args()

    want = expected_currency()
    quotes: dict[str, dict] = {}
    problems: list[str] = []

    for sym in tickers():
        try:
            got = fetch(sym)
        except RuntimeError as exc:
            problems.append(str(exc))
            continue
        if got["currency"] and got["currency"] != want:
            problems.append(f"{sym}: quoted in {got['currency']}, the site reports {want}")
            continue
        quotes[sym] = got["row"]
        print(f"  {sym:6} {got['row']['price']:>10,.2f}  {got['row']['asOf']}")

    # All or nothing: a partial snapshot is worse than yesterday's complete one.
    if problems:
        for p in problems:
            print(f"  ! {p}", file=sys.stderr)
        print(f"  {len(problems)} of {len(quotes) + len(problems)} tickers failed; "
              f"{OUT.name} left unchanged", file=sys.stderr)
        return 1

    text = json.dumps({"source": FEED, "quotes": quotes}, indent=2) + "\n"
    dates = sorted({q["asOf"] for q in quotes.values()})
    span = dates[0] if len(dates) == 1 else f"{dates[0]}..{dates[-1]}"
    if args.dry_run:
        print(f"  dry run: {len(quotes)} quotes, {span}, {OUT.name} not written")
        return 0
    if OUT.exists() and OUT.read_text(encoding="utf-8") == text:
        print(f"  {len(quotes)} quotes, {span} — unchanged")
        return 0
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"  {len(quotes)} quotes, {span} — written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
