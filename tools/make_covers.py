#!/usr/bin/env python3
"""Resize downloaded book covers into the small versions the site ships.

    python3 tools/make_covers.py [--check]

**This is the one tool here that needs a third-party package** (Pillow), and it
is deliberately not part of `tools/audit.sh`. It is an asset-preparation step in
the same category as the Chrome screenshot that builds `assets/og.png`: run it by
hand when new covers arrive, commit the output, and the stdlib-only build takes
it from there. Nothing on the site depends on Pillow being installed.

Sources live in `images/`, which is **gitignored**. The originals are full-size
publisher artwork — one is 2.4 MB at 1835x2560, and together they are 4.7 MB,
roughly eight times the whole page budget. Only the resized versions are
committed, which keeps the page inside its budget and keeps this repository from
republishing high-resolution copyrighted art it has no need for.

Every cover must belong to a book — an unmatched file is a misnamed one that
will never appear, so it fails. A book without a cover is not an error: it can
be added before the artwork arrives, and the card shows a neutral placeholder
until it does.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys
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
SRC = SITE / "images"
OUT = SITE / "assets" / "covers"
CONTENT = SITE / "content" / "books"

# Displayed at 88px on the shelf and 120px on a write-up page, so 200px
# covers both on a 2x screen. WebP would save a further 65 KB; not worth
# introducing a second image format to the site for that.
WIDTH = 200
MAX_HEIGHT = 400
QUALITY = 78

# Where the download's filename does not normalise onto the book's slug.
ALIASES = {
    "how_to_talk_to_anyone": "92-little-tricks",
    "how_to_win_friends_and_influence_people": "how-to-win-friends",
    "the_7_habits_of_highly_effective_people": "the-7-habits",
    "the_subtle_art_of_not_giving_a_fuck": "the-subtle-art",
    "48_laws_of_power": "the-48-laws-of-power",
}


def slugs() -> set[str]:
    return {p.stem for p in CONTENT.glob("*.md")}


def target_for(stem: str, known: set[str]) -> str | None:
    if stem in ALIASES:
        return ALIASES[stem]
    guess = re.sub(r"[^a-z0-9]+", "-", stem.lower()).strip("-")
    return guess if guess in known else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="verify every book has a cover; do not write anything")
    args = ap.parse_args()

    try:
        from PIL import Image
    except ImportError:
        print("  Pillow is required for this tool: python3 -m pip install Pillow",
              file=sys.stderr)
        return 2

    known = slugs()
    if not known:
        print(f"  no book files in {CONTENT}", file=sys.stderr)
        return 2

    sources = sorted(p for p in SRC.glob("*") if p.suffix.lower() in (".jpg", ".jpeg", ".png"))
    mapped: dict[str, pathlib.Path] = {}
    orphans = []
    for src in sources:
        slug = target_for(src.stem, known)
        if slug is None:
            orphans.append(src.name)
        else:
            mapped[slug] = src

    missing = sorted(known - set(mapped))
    for name in orphans:
        print(f"  ! {name} does not match any book — add it to ALIASES", file=sys.stderr)
    for slug in missing:
        # Not an error: a book can be added before its cover arrives, and the
        # card shows a neutral placeholder until it does. An unmatched FILE is
        # an error, because it means a misnamed cover nothing will ever use.
        print(f"  · {slug} has no cover yet")

    if args.check:
        print(f"  {len(mapped)} covers matched, {len(orphans)} unmatched, "
              f"{len(missing)} still to come")
        return 1 if orphans else 0

    OUT.mkdir(parents=True, exist_ok=True)
    written = total = 0
    for slug, src in sorted(mapped.items()):
        with Image.open(src) as im:
            im = im.convert("RGB")
            h = round(im.height * WIDTH / im.width)
            if h > MAX_HEIGHT:
                im = im.resize((round(im.width * MAX_HEIGHT / im.height), MAX_HEIGHT),
                               Image.LANCZOS)
            else:
                im = im.resize((WIDTH, h), Image.LANCZOS)
            dest = OUT / f"{slug}.jpg"
            im.save(dest, "JPEG", quality=QUALITY, optimize=True, progressive=True)
        size = dest.stat().st_size
        total += size
        written += 1
        print(f"  {slug:38} {im.width:>3}x{im.height:<3} {size / 1024:6.1f} KB")

    print(f"  {written} covers, {total / 1024:.1f} KB total "
          f"(sources were {sum(p.stat().st_size for p in sources) / 1024 / 1024:.1f} MB)")
    return 1 if orphans else 0


if __name__ == "__main__":
    sys.exit(main())
