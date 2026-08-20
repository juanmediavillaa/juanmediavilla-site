#!/usr/bin/env python3
"""The only code that opens data/portfolio.json.

Sibling of tools/prices.py, and the same contract: this is the single file a
ledger export would ever write, and every component reads portfolio-level state
through here. Going live means replacing what writes it, and nothing else.

What it holds and what it must never hold:

  The currency, and the date the snapshot was taken. Nothing else. Everything is
  quoted and reported in one currency, so a position's return is recoverable
  from its cost and its price and needs no second figure carried alongside.

  There is deliberately NO performance history and NO aggregate return here.
  Those were removed when the strategy and structure changed: a record running
  through that change describes a way of investing that is no longer in use, and
  keeping it in a public repository would publish it whether or not a page
  rendered it.

  NEVER an amount, a share count, a unit count, a member count or a member. A
  single absolute number anywhere in this file, combined with a percentage that
  is already published, reconstructs the size of the book — which is the one
  thing the whole section is built to make impossible. The loader rejects any
  key it does not recognise for exactly that reason: a field added by hand and
  never reviewed is how the first amount would arrive.

Standard library only.
"""

from __future__ import annotations

import json
import pathlib
from typing import NamedTuple

SITE = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_PATH = SITE / "data" / "portfolio.json"

# An allow-list, not a deny-list. Anything else is refused rather than ignored.
ALLOWED = {"source", "asOf", "currency"}

# Words that would signal an absolute quantity had crept in. Belt and braces on
# top of the allow-list, because the allow-list only protects the top level.
BANNED = ("amount", "value_eur", "eur", "usd", "nav", "aum", "total", "return",
          "shares", "units", "members", "deposit", "balance", "capital", "pct")


class PortfolioError(Exception):
    """A portfolio file that cannot be trusted. Never guessed around."""


class Portfolio(NamedTuple):
    source: str
    as_of: str
    currency: str

    @classmethod
    def load(cls, path: pathlib.Path | None = None) -> "Portfolio":
        path = path or DEFAULT_PATH
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise PortfolioError(f"{path}: {exc}") from exc

        unknown = set(raw) - ALLOWED
        if unknown:
            raise PortfolioError(
                f"{path}: unrecognised field(s) {sorted(unknown)} — this file carries the "
                "snapshot's currencies and date, and nothing else")
        for key in raw:
            if any(b in key.lower() for b in BANNED):
                raise PortfolioError(f"{path}: field {key!r} looks like a quantity or a return")

        return cls(
            source=str(raw.get("source", "unnamed")),
            as_of=str(raw["asOf"]),
            currency=str(raw.get("currency", "USD")),
        )


__all__ = ["Portfolio", "PortfolioError", "DEFAULT_PATH"]
