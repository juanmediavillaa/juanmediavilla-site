#!/usr/bin/env python3
"""Build /books from content/books/*.md.

One file per book. The front matter is the shelf — title, author, the year I
read it, the verdict — and the body, when there is one, is the write-up. Books
with no body are still listed: most of what I read never got written up, and a
page that showed only the books I wrote about would misrepresent the shelf.

The verdict scale is the one I already keep: loved / good / fine / dropped. It
measures enjoyment, and the write-ups are increasingly clear that enjoyment and
what a book actually yields are different axes — so the two are shown separately
rather than collapsed into a score.

Standard library only. Run:

  python3 tools/build_books.py            # write the pages
  python3 tools/build_books.py --check    # fail if any output would change
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from sitegen import (  # noqa: E402
    SITE, ContentError, blocks, emit, esc, foot, head, inline,
    parse_front_matter, slugify,
)

CONTENT = SITE / "content" / "books"
OUT = SITE / "notes" / "books"

# Not in the sitemap, and CONTENT-RULES.md §4.8 currently forbids this section
# existing at all ("No interests, reading, routines..."). Marked noindex the same
# way research/thesis/pre-registration/ is until that rule is amended.
NOINDEX = True

VERDICTS = ["loved", "good", "fine", "dropped"]


def load_book(path: pathlib.Path) -> dict:
    where = path.relative_to(SITE).as_posix()
    front, body = parse_front_matter(path.read_text(encoding="utf-8"), where)

    for required in ("title", "author", "read", "verdict"):
        if required not in front:
            raise ContentError(f"{where}: missing required field {required}")

    verdict = str(front["verdict"]).strip().lower()
    if verdict not in VERDICTS:
        raise ContentError(f"{where}: verdict must be one of {', '.join(VERDICTS)}")

    sections = parse_body(body, where)
    # The filename is authoritative, so content/books/x.md, books/x/ and
    # assets/covers/x.jpg always line up. Deriving it from the title instead
    # silently detached five covers from their books.
    slug = str(front.get("slug") or path.stem or slugify(front["title"]))
    cover = SITE / "assets" / "covers" / f"{slug}.jpg"
    return {
        "cover": f"{slug}.jpg" if cover.exists() else None,
        "file": where,
        "title": str(front["title"]).strip(),
        "author": str(front["author"]).strip(),
        "read": str(front["read"]).strip(),       # a year, or a date range in prose
        # `or` would discard a falsy-but-valid key such as 0, silently
        # falling back to the display string and misordering the shelf.
        "sort": str(front["sortKey"] if "sortKey" in front else front["read"]).strip(),
        "verdict": verdict,
        "shelf": str(front.get("shelf", "")).strip(),
        "summary": str(front.get("summary", "")).strip(),
        "slug": slug,
        "sections": sections,
        "written": bool(sections),
    }


def parse_body(body: str, where: str) -> list[dict]:
    """`##` sections, free wording. No book needs more structure than that."""
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


# ===================================================================== cards

def row(b: dict) -> str:
    """One book on the shelf. A link only when there is something to link to."""
    cover = (f'            <img class="bk__cover" src="../../../assets/covers/{b["cover"]}" '
             f'alt="" loading="lazy" decoding="async" width="200">\n'
             if b["cover"] else '            <span class="bk__cover bk__cover--none"></span>\n')
    inner = cover + f"""            <span class="bk__text">
              <span class="bk__top">
                <span class="bk__verdict bk__verdict--{b['verdict']}">{b['verdict']}</span>
                <span class="bk__when">{esc(b['read'])}</span>
              </span>
              <h3 class="work-title">{esc(b['title'])}</h3>
              <span class="bk__by">{esc(b['author'])}</span>
"""
    if b["summary"]:
        inner += f'              <span class="bk__sum">{esc(b["summary"])}</span>\n'
    inner += (f'              <span class="bk__go">Read the write-up&nbsp;&rarr;</span>\n'
              if b["written"] else
              '              <span class="bk__go bk__go--none">No write-up</span>\n')
    inner += "            </span>\n"

    if b["written"]:
        return (f'          <a class="card bk" href="{esc(b["slug"])}/index.html"'
                f' data-verdict="{b["verdict"]}">\n{inner}          </a>\n')
    return (f'          <div class="card bk bk--flat" data-verdict="{b["verdict"]}">\n'
            f'{inner}          </div>\n')


def shelf(books: list[dict], empty: str) -> str:
    if not books:
        return f'        <p class="pos__empty">{esc(empty)}</p>\n'
    return ('        <div class="cards cards--bk">\n'
            + "".join(row(b) for b in books) + "        </div>\n")


# ================================================================ index page

STANDING_NOTE = ""


def build_index(books: list[dict]) -> str:
    written = [b for b in books if b["written"]]
    counts = {v: sum(1 for b in books if b["verdict"] == v) for v in VERDICTS}

    doc = [head("Books — Notes — Juan Mediavilla",
                "What I have read, what I thought of it, and what I actually took from it — "
                "including the books that gave me nothing.", 2,
                here="notes/index.html", noindex=NOINDEX)]

    legend = "".join(
        f'          <li><span class="bk__verdict bk__verdict--{v}">{v}</span>'
        f'<span class="bk__legend">{counts[v]}</span></li>' + chr(10)
        for v in VERDICTS)

    doc.append(f"""
<header class="head">
  <div class="wrap">
    <p class="eyebrow">Books</p>
    <h1>What I have read</h1>
    <p class="standfirst">
      A log of what I have read, with a verdict beside each.
    </p>
  </div>
</header>

<section class="section reveal">
  <div class="wrap">
    <div class="rail">
      <div class="rail__label">
        <p class="eyebrow">How I keep it</p>
        <p class="meta">{len(books)} books.<br>{len(written)} written up.</p>
      </div>
      <div class="rail__body">
{STANDING_NOTE}        <h2>Verdicts</h2>
        <ul class="bk__key">
{legend}        </ul>
      </div>
    </div>
  </div>
</section>

<section class="section reveal">
  <div class="wrap">
    <div class="rail">
      <div class="rail__label">
        <p class="eyebrow">The shelf</p>
        <p class="meta">Most recent<br>first.</p>
      </div>
      <div class="rail__body">
        <h2>Everything I have read</h2>
        <p>
          The log as I have kept it, at the precision I kept it. Several are recorded as a span of
          years rather than a date.
        </p>
{shelf(books, 'Nothing logged yet.')}      </div>
    </div>
  </div>
</section>
""")
    doc.append(foot(2))
    return "".join(doc)


# ================================================================= book page

def build_book(b: dict, prev: dict | None, nxt: dict | None) -> str:
    cover = (f'<img class="bk__cover bk__cover--lg" src="../../../assets/covers/{b["cover"]}" '
             f'alt="Cover of {esc(b["title"])}" width="200">' if b["cover"] else "")
    doc = [head(f'{b["title"]} — Books — Notes — Juan Mediavilla',
                b["summary"] or f'{b["title"]} by {b["author"]}', 3,
                here="notes/index.html", noindex=NOINDEX)]

    doc.append(f"""
<header class="head">
  <div class="wrap">
    <p class="eyebrow"><a href="../index.html">Books</a></p>
    <h1 class="work-title">{esc(b['title'])}</h1>
    <p class="pos__ident">
      <span class="bk__by bk__by--lg">{esc(b['author'])}</span>
      <span class="bk__verdict bk__verdict--{b['verdict']}">{b['verdict']}</span>
      <span class="pos__class">read {esc(b['read'])}</span>
    </p>
    <p class="standfirst">{esc(b['summary'])}</p>
    {cover}
  </div>
</header>

<section class="section reveal">
  <div class="wrap">
    <div class="rail">
      <div class="rail__label">
        <p class="eyebrow">Write-up</p>
        <p class="meta">{esc(b['shelf'] or 'Read ' + b['read'])}</p>
      </div>
      <div class="rail__body">
""")

    for s in b["sections"]:
        doc.append(f"        <h2>{esc(s['title'])}</h2>\n{blocks(s['md'])}\n")

    doc.append("""      </div>
    </div>
  </div>
</section>

<section class="section reveal">
  <div class="wrap">
    <nav class="pager" aria-label="Books">
""")
    if prev:
        doc.append(f'      <a href="../{esc(prev["slug"])}/index.html">'
                   f'<span>Previous</span>{esc(prev["title"])}</a>\n')
    else:
        doc.append("      <span></span>\n")
    if nxt:
        doc.append(f'      <a href="../{esc(nxt["slug"])}/index.html">'
                   f'<span>Next</span>{esc(nxt["title"])}</a>\n')
    doc.append("""    </nav>
    <p class="pos__back"><a href="../index.html">The whole shelf&nbsp;→</a></p>
  </div>
</section>
""")
    doc.append(foot(3))
    return "".join(doc)


# ==================================================================== runner

def render_all() -> dict[pathlib.Path, str]:
    files = sorted(CONTENT.glob("*.md"))
    if not files:
        raise ContentError(f"no book files in {CONTENT}")
    books = [load_book(p) for p in files]

    seen: dict[str, str] = {}
    for b in books:
        if b["slug"] in seen:
            raise ContentError(f'{b["file"]}: slug {b["slug"]} already used by {seen[b["slug"]]}')
        seen[b["slug"]] = b["file"]

    # Most recent first. `sortKey` exists because several of these are remembered
    # as "~2021-22" rather than as a date, and a made-up date would read as a
    # precision the record does not have.
    books.sort(key=lambda b: (b["sort"], b["title"]), reverse=True)

    pages = {OUT / "index.html": build_index(books)}
    written = [b for b in books if b["written"]]
    for i, b in enumerate(written):
        pages[OUT / b["slug"] / "index.html"] = build_book(
            b, written[i - 1] if i else None,
            written[i + 1] if i + 1 < len(written) else None)
    return pages


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="fail if any generated page would change")
    args = ap.parse_args()
    try:
        pages = render_all()
    except ContentError as exc:
        print(f"  content error: {exc}", file=sys.stderr)
        return 2
    return emit(pages, OUT, args.check, "books")


if __name__ == "__main__":
    sys.exit(main())
