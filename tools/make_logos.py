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

Vector logos need no third-party package. A **raster** logo needs Pillow, imported
lazily inside that branch alone, so the SVG path still runs on a machine without
it — `tools/audit.sh` never calls this script, but the split matters if it ever
does.

A raster is accepted only where it can be shown to work. The dark-mode ground is
decided in `tools/build_notebook.py` by reading fills out of the SVG, which
cannot be done to a bitmap and cannot grow a Pillow dependency because the price
workflow runs that generator in CI. So the measurement happens here instead, and
a raster that would be lost against the dark plane is refused rather than
installed invisibly.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys
import xml.etree.ElementTree as ET
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
OUT = SITE / "assets" / "logos"
CONTENT = SITE / "content" / "positions"

RASTER = (".png", ".jpg", ".jpeg", ".webp")

# Alpha-capable formats only. A JPEG cannot carry transparency, so a JPEG
# "logo" arrives as artwork in a white box that would sit on the page as a
# white box; it is almost certainly a book cover anyway.
LOGO_RASTER = (".png", ".webp")

# The mark renders in a 2.5rem box, 3.5rem on a position page. 240px is a little
# over 4x the largest of those, which covers every plausible display density
# while keeping the file small.
MAX_PX = 240

# --plane in dark mode, #0C0C10, matching DARK_PLANE_LUM in tools/build_notebook.py.
DARK_PLANE_LUM = 0.003785

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


def _relative_luminance(r: int, g: int, b: int) -> float:
    def channel(c: int) -> float:
        c /= 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def raster_contrast(im) -> float:
    """Contrast of the mark's opaque pixels against the dark plane.

    Averaged over pixels that are actually drawn — a logo is mostly
    transparency, and including it would measure the background instead of the
    artwork. Mirrors the ratio build_notebook.needs_ground() computes from SVG
    fills, so both paths answer the same question the same way.
    """
    opaque = [p for p in im.getdata() if p[3] > 128]
    if not opaque:
        raise ValueError("is fully transparent")
    mean = sum(_relative_luminance(r, g, b) for r, g, b, _ in opaque) / len(opaque)
    return ((max(mean, DARK_PLANE_LUM) + 0.05)
            / (min(mean, DARK_PLANE_LUM) + 0.05))


def install_raster(src: pathlib.Path, slug: str) -> tuple[pathlib.Path, int]:
    """Downscale a transparent logo and write it as an optimised PNG."""
    try:
        from PIL import Image          # lazy: the SVG path must not need Pillow
    except ImportError as exc:
        raise ValueError("needs Pillow to install a raster logo "
                         "(pip install Pillow), or supply an SVG") from exc

    if src.suffix.lower() not in LOGO_RASTER:
        raise ValueError(f"is {src.suffix} — a logo raster must carry alpha, so "
                         f"use {' or '.join(LOGO_RASTER)}, or supply an SVG")

    im = Image.open(src).convert("RGBA")
    ratio = raster_contrast(im)
    if ratio < 2.0:
        raise ValueError(
            f"measures {ratio:.2f}:1 against the dark plane and would be lost there. "
            "A raster cannot be given a ground the way an SVG can (see the module "
            "docstring), so supply an SVG instead")

    if max(im.size) > MAX_PX:
        scale = MAX_PX / max(im.size)
        im = im.resize((max(1, round(im.width * scale)),
                        max(1, round(im.height * scale))), Image.LANCZOS)
    dest = OUT / f"{slug}.png"
    im.save(dest, "PNG", optimize=True)
    return dest, ratio


def drop_siblings(slug: str, keep: pathlib.Path) -> None:
    """One file per slug.

    The page resolves artwork with glob("<slug>.*") and takes the first match,
    so a slug holding both a .png and a .svg is decided by sort order rather
    than by intent. Replacing a logo with one in another format removes the old.
    """
    for other in OUT.glob(f"{slug}.*"):
        if other != keep:
            other.unlink()
            print(f"  · removed {other.name}, superseded by {keep.name}")


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
            # Covers are never SVG, so an unmatched one is a misnamed logo.
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
        before = src.stat().st_size
        note = ""
        try:
            if src.suffix.lower() == ".svg":
                clean = sanitise(src.read_text(encoding="utf-8", errors="replace"), src.name)
                dest = OUT / f"{slug}.svg"
                dest.write_text(clean, encoding="utf-8", newline="\n")
            else:
                dest, ratio = install_raster(src, slug)
                note = f"  raster, {ratio:.1f}:1 on the dark plane"
        except ValueError as exc:
            print(f"  ! {src.name} {exc}", file=sys.stderr)
            failed.append(src.name)
            continue
        drop_siblings(slug, dest)
        after = dest.stat().st_size
        total += after
        saved += before - after
        print(f"  {slug:22} {before / 1024:5.1f} KB → {after / 1024:5.1f} KB{note}")

    print(f"  {len(mapped) - len(failed)} logos, {total / 1024:.1f} KB "
          f"({saved / 1024:.1f} KB of metadata and cruft removed)")
    return 1 if (orphan_svgs or failed) else 0


if __name__ == "__main__":
    sys.exit(main())
