#!/usr/bin/env python3
"""The only code on this site that opens data/prices.json.

Every component reads prices through this module. That is the whole point of it:
when a live feed replaces the mock file, the thing that changes is *what writes
data/prices.json*, and nothing downstream is restructured. The generator, the
index page and the position pages all go through `Prices.quote()` and none of
them knows where the number came from.

Two rules are enforced here rather than left to callers:

  * A missing or malformed quote is a `Quote` with `available = False` and a
    reason, never a NaN, a zero or an exception. A zero price silently rendered
    as "-100%" is the failure mode this module exists to make impossible.
  * Every quote carries the `as_of` date that came with the price. Nothing here
    reads the clock. A stale price displayed as current is the other failure
    mode, and build time is exactly the wrong source for that date.

Standard library only.
"""

from __future__ import annotations

import json
import pathlib
from typing import NamedTuple

SITE = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_PATH = SITE / "data" / "prices.json"


class Quote(NamedTuple):
    """One ticker's price, or a stated reason there is not one."""

    ticker: str
    price: float | None
    as_of: str | None
    previous_close: float | None
    available: bool
    reason: str  # "" when available; a short human phrase when not

    @classmethod
    def missing(cls, ticker: str, reason: str) -> "Quote":
        return cls(ticker, None, None, None, False, reason)


def _number(value: object) -> float | None:
    """A price, or None. Rejects everything that would poison arithmetic.

    bool is checked before int because bool is an int in Python, and `True`
    arriving from a hand-edited JSON file would otherwise become a price of 1.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if number != number or number in (float("inf"), float("-inf")):  # NaN, inf
        return None
    if number <= 0:
        return None
    return number


class Prices:
    """A loaded price snapshot. Read-only, and it never raises on lookup."""

    def __init__(self, quotes: dict[str, Quote], source: pathlib.Path, feed: str) -> None:
        self._quotes = quotes
        self.source = source
        # What produced the snapshot, named on the page. "mock" while this is a
        # prototype; a feed's name once one writes the file. The pages read this
        # rather than hard-coding the word, so going live relabels them.
        self.feed = feed

    # -- loading ---------------------------------------------------------
    @classmethod
    def load(cls, path: pathlib.Path | None = None) -> "Prices":
        path = path or DEFAULT_PATH
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            # No snapshot at all is a legitimate state: every position then
            # renders "price unavailable" rather than the build failing.
            return cls({}, path, "none")

        feed = raw.get("source")
        feed = feed.strip() if isinstance(feed, str) and feed.strip() else "unnamed"

        quotes: dict[str, Quote] = {}
        for ticker, row in (raw.get("quotes") or {}).items():
            key = str(ticker).strip().upper()
            if not isinstance(row, dict):
                continue
            price = _number(row.get("price"))
            as_of = row.get("asOf")
            if price is None or not isinstance(as_of, str) or not as_of.strip():
                # A row without both a usable price and the date it belongs to
                # is not half a quote; it is no quote.
                continue
            quotes[key] = Quote(
                ticker=key,
                price=price,
                as_of=as_of.strip(),
                previous_close=_number(row.get("previousClose")),
                available=True,
                reason="",
            )
        return cls(quotes, path, feed)

    # -- reading ---------------------------------------------------------
    def quote(self, ticker: str) -> Quote:
        key = str(ticker).strip().upper()
        return self._quotes.get(key) or Quote.missing(key, "no price on file")

    def oldest_as_of(self, tickers: list[str]) -> str | None:
        """The oldest date among the quotes actually used.

        Deliberately the oldest and not the newest: a page that prints the
        freshest date in the file implies the whole page is that fresh. ISO
        dates sort lexically, so this is a plain min().
        """
        dates = [q.as_of for q in (self.quote(t) for t in tickers) if q.as_of]
        return min(dates) if dates else None

    def __len__(self) -> int:
        return len(self._quotes)


__all__ = ["Prices", "Quote", "DEFAULT_PATH"]
