#!/usr/bin/env python3
"""Build /notes — the index of everything written alongside the work.

    python3 tools/build_notes.py [--check]

One nav entry stands in front of several sections, so this page is what the nav
points at. It is generated rather than hand-written for one reason: the counts on
it ("9 positions", "23 books") are read from the content directories, so they
cannot drift from what is actually there.

Adding a section means adding an entry to SECTIONS below. A section whose
directory does not exist yet is skipped rather than linked into a 404.

Standard library only.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from sitegen import SITE, ContentError, emit, esc, foot, head  # noqa: E402

OUT = SITE / "notes"
NOINDEX = True

# slug, title, one line, content dir, singular/plural noun for the count
SECTIONS = [
    ("investing", "Investing",
     "What I bought, what I paid for it, and what it trades at now.",
     "positions", ("position", "positions")),
    ("books", "Books",
     "What I have read, with a verdict beside each.",
     "books", ("book", "books")),
]


def count(folder: str) -> int:
    """Entries that are actually part of the section.

    A book that is unread, or being read now, is on the reading list rather than
    the shelf, so it is not what "23 books" on this page means.
    """
    d = SITE / "content" / folder
    if not d.exists():
        return 0
    return sum(1 for f in d.glob("*.md")
               if not re.search(r"^status:\s*(unread|reading)\s*$", f.read_text(encoding="utf-8"), re.M))


def build() -> str:
    rows = []
    for slug, title, blurb, folder, (one, many) in SECTIONS:
        if not (OUT / slug / "index.html").exists():
            continue
        n = count(folder)
        rows.append(
            f'          <a class="card note" href="{esc(slug)}/index.html">\n'
            f'            <span class="note__count">{n} {one if n == 1 else many}</span>\n'
            f'            <h3>{esc(title)}</h3>\n'
            f'            <span class="note__sum">{esc(blurb)}</span>\n'
            f'            <span class="pos__go">Open&nbsp;&rarr;</span>\n'
            f'          </a>\n')
    if not rows:
        raise ContentError("no built sections to index — run the section generators first")

    doc = [head("Notes — Juan Mediavilla",
                "Writing alongside the work: an investing record, a reading log, and whatever "
                "else earns a page.", 1, here="notes/index.html", noindex=NOINDEX)]
    doc.append(f"""
<header class="head">
  <div class="wrap">
    <p class="eyebrow">Notes</p>
    <h1>Written alongside the work</h1>
    <p class="standfirst">
      An index of what I keep and publish outside the project and research pages.
    </p>
  </div>
</header>

<section class="section reveal">
  <div class="wrap">
    <div class="rail">
      <div class="rail__label">
        <p class="eyebrow">Sections</p>
        <p class="meta">{len(rows)} so far.<br>More as they<br>earn a page.</p>
      </div>
      <div class="rail__body">
        <h2>What is here</h2>
        <div class="cards cards--note">
{"".join(rows)}        </div>
      </div>
    </div>
  </div>
</section>
""")
    doc.append(foot(1))
    return "".join(doc)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="fail if the page would change")
    args = ap.parse_args()
    try:
        page = build()
    except ContentError as exc:
        print(f"  content error: {exc}", file=sys.stderr)
        return 2
    return emit({OUT / "index.html": page}, OUT, args.check, "notes", orphans=False)


if __name__ == "__main__":
    sys.exit(main())
