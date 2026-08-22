#!/usr/bin/env python3
"""Sanitise and install company logos for /notebook.

    python3 tools/make_logos.py [--check]

Sources live in `images/` alongside the book covers — that directory is
gitignored, so nothing full-size or unreviewed reaches the repository. A file is
treated as a logo when its name maps to a position's content file:
`images/meta.svg` becomes `assets/logos/meta-platforms.svg`. **The content
filename is the slug**, and it ties the markdown, the page URL and the artwork
together.

Raster files that map to no position are ignored, because `images/` also holds
the book covers. An **SVG** that maps to nothing is reported, since covers are
never SVG and an unmatched one means a misnamed logo that will silently never
appear.

Why SVGs are rewritten rather than copied
-----------------------------------------
Downloaded brand SVGs routinely carry things that should not enter a public
repository or a page:

  * `<metadata>` / RDF blocks from the exporting editor, which can embed an
    author name and a local filesystem path;
  * `<script>` elements and `on*` event handlers — inert while the file is
    loaded through `<img>`, and live the moment anyone inlines it;
  * editor-private namespaces and comments that are pure weight.

All of it is stripped, and the result is parsed as XML before it is written —
the same contract the two SVG generators here already hold. An external
reference (`href`/`src`/`url()` pointing off-origin) is refused outright rather
than cleaned, because it would breach CONTENT-RULES.md §4.9 and it means the
file is not self-contained.

Needs no third-party package. `tools/make_covers.py` needs Pillow; this does not,
because nothing here is rasterised.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys
import xml.etree.ElementTree as ET

SITE = pathlib.Path(__file__).resolve().parent.parent
SRC = SITE / "images"
OUT = SITE / "assets" / "logos"
CONTENT = SITE / "content" / "positions"

RASTER = (".png", ".jpg", ".jpeg", ".webp")

# Where the download's filename does not normalise onto the position's slug.
ALIASES = {
    "google": "alphabet",
    "meta": "meta-platforms",
    "nubank": "nu-holdings",
    "robinhood": "robinhood-markets",
    "hims": "hims-and-hers-health",
    "fico": "fair-isaac",
    "fairisaac": "fair-isaac",
    "hinge": "hinge-health",
    "hingehealth": "hinge-health",
}

EXTERNAL = re.compile(r'(?:href|src)\s*=\s*["\']\s*https?://|url\(\s*["\']?\s*https?://', re.I)

STRIP = [
    (re.compile(r"<\?xml[^>]*\?>\s*", re.I), ""),            # declaration
    (re.compile(r"<!--.*?-->", re.S), ""),                    # comments
    (re.compile(r"<!DOCTYPE[^>]*>\s*", re.I), ""),
    (re.compile(r"<script\b.*?</script\s*>", re.S | re.I), ""),
    (re.compile(r"<(metadata|sodipodi:namedview)\b.*?</\1\s*>", re.S | re.I), ""),
    (re.compile(r"<(metadata|sodipodi:namedview)\b[^>]*/>", re.I), ""),
    (re.compile(r'\s(?:sodipodi|inkscape|dc|cc|rdf):[\w-]+\s*=\s*"[^"]*"', re.I), ""),
    (re.compile(r'\sxmlns:(?:sodipodi|inkscape|dc|cc|rdf|svgjs)\s*=\s*"[^"]*"', re.I), ""),
    (re.compile(r'\son\w+\s*=\s*"[^"]*"', re.I), ""),         # event handlers
    (re.compile(r">\s+<"), "><"),
]


def sanitise(text: str, name: str) -> str:
    if EXTERNAL.search(text):
        raise ValueError("references an off-origin resource (CONTENT-RULES §4.9)")
    for pattern, repl in STRIP:
        text = pattern.sub(repl, text)
    text = text.strip()
    try:
        ET.fromstring(text)          # must still be well-formed XML
    except ET.ParseError as exc:
        raise ValueError(f"is not valid XML after cleaning: {exc}") from exc
    return text + "\n"


def slugs() -> set[str]:
    return {p.stem for p in CONTENT.glob("*.md")}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="report coverage; write nothing")
    args = ap.parse_args()

    known = slugs()
    if not known:
        print(f"  no position files in {CONTENT}", file=sys.stderr)
        return 2
    if not SRC.exists():
        print(f"  {SRC.name}/ does not exist — drop the logos in, named after the content files")
        return 0

    mapped: dict[str, pathlib.Path] = {}
    orphan_svgs = []
    for p in sorted(SRC.glob("*")):
        if p.suffix.lower() not in RASTER + (".svg",):
            continue
        slug = ALIASES.get(p.stem.lower(), p.stem.lower())
        if slug in known:
            mapped[slug] = p
        elif p.suffix.lower() == ".svg":
            orphan_svgs.append(p.name)

    missing = sorted(known - set(mapped))
    for name in orphan_svgs:
        print(f"  ! {name} maps to no position — rename it, or add it to ALIASES",
              file=sys.stderr)
    for slug in missing:
        print(f"  · {slug} has no logo yet (the card shows a monogram)")

    if args.check:
        print(f"  {len(mapped)} of {len(known)} positions have a logo, "
              f"{len(orphan_svgs)} unmatched SVG(s)")
        return 1 if orphan_svgs else 0

    OUT.mkdir(parents=True, exist_ok=True)
    total = saved = 0
    failed = []
    for slug, src in sorted(mapped.items()):
        if src.suffix.lower() != ".svg":
            print(f"  ! {src.name} is not an SVG; raster logos are not handled", file=sys.stderr)
            failed.append(src.name)
            continue
        raw = src.read_text(encoding="utf-8", errors="replace")
        try:
            clean = sanitise(raw, src.name)
        except ValueError as exc:
            print(f"  ! {src.name} {exc}", file=sys.stderr)
            failed.append(src.name)
            continue
        dest = OUT / f"{slug}.svg"
        dest.write_text(clean, encoding="utf-8", newline="\n")
        before, after = len(raw.encode()), dest.stat().st_size
        total += after
        saved += before - after
        print(f"  {slug:22} {before / 1024:5.1f} KB → {after / 1024:5.1f} KB")

    print(f"  {len(mapped) - len(failed)} logos, {total / 1024:.1f} KB "
          f"({saved / 1024:.1f} KB of metadata and cruft removed)")
    return 1 if (orphan_svgs or failed) else 0


if __name__ == "__main__":
    sys.exit(main())
