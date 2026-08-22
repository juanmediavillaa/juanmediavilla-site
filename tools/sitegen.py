#!/usr/bin/env python3
"""Shared machinery for the generated sections — /notebook and /books.

Both are the same shape: one markdown file per item, front matter for the facts,
a small prose subset for the body, and a page shell identical to the hand-written
pages. Everything both need lives here so the two generators cannot drift apart —
in particular the nav, which is repeated on 22 pages and is exactly the kind of
thing that goes stale in one place and not the others.

Standard library only.
"""

from __future__ import annotations

import html as _html
import pathlib
import re
import sys

# Done here rather than in each generator because all three import this module.
# A Windows console is cp1252 and cannot encode the em dash this file prints in
# its orphan warning; the encode raises, and since pages are written before the
# summary line, the run aborts having already applied part of its work. Force
# UTF-8 on the streams so a status line can never take down the job it reports.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):   # already wrapped, or not a real tty
        pass

SITE = pathlib.Path(__file__).resolve().parent.parent

ICON = ("data:image/svg+xml,%3Csvg%20xmlns='http://www.w3.org/2000/svg'%20viewBox='0%200%2064%2064'"
        "%3E%3Crect%20width='64'%20height='64'%20rx='13'%20fill='%234F46E5'/%3E%3Ctext%20x='32'%20"
        "y='45'%20font-family='Helvetica,Arial,sans-serif'%20font-size='33'%20font-weight='700'%20"
        "fill='%23ffffff'%20text-anchor='middle'%3EJM%3C/text%3E%3C/svg%3E")

MINUS = "−"   # true minus sign; a hyphen is not it, and the font subsets it

# The primary nav, in one place. Order is editorial: the work first, then one
# entry for everything written alongside it, then the pages about the author.
# /notes is an index; Investing and Books live under it rather than competing
# with Projects and Research for the reader's attention. tools/audit.js asserts this
# count — a link added here raises the assertion in the same change.
NAV = [
    ("projects/index.html", "Projects"),
    ("research/index.html", "Research"),
    ("notes/index.html", "Notes"),
    ("how-i-work/index.html", "How I Work"),
    ("about/index.html", "About"),
]
FOOT = NAV + [("cv/index.html", "CV"), ("glossary/index.html", "Glossary")]


class ContentError(Exception):
    """A content file that cannot be trusted. Never guessed around."""


def esc(value: object) -> str:
    return _html.escape(str(value), quote=True)


# =============================================================== front matter

def parse_front_matter(text: str, where: str) -> tuple[dict, str]:
    """A deliberately small subset: scalars, [] and lists of flat mappings.

    Small enough to read in one sitting, strict enough that a typo is an error
    rather than a silently dropped field. There is no YAML library because this
    repository has no dependencies and is not about to acquire one.
    """
    if not text.startswith("---\n"):
        raise ContentError(f"{where}: missing opening --- front-matter fence")
    _, _, rest = text.partition("---\n")
    block, fence, body = rest.partition("\n---\n")
    if not fence:
        raise ContentError(f"{where}: missing closing --- front-matter fence")

    data: dict = {}
    key: str | None = None
    for lineno, raw in enumerate(block.split("\n"), start=2):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        line = raw.strip()

        if indent == 0:
            key, _, value = line.partition(":")
            key, value = key.strip(), value.strip()
            if not key:
                raise ContentError(f"{where}:{lineno}: line has no key")
            data[key] = [] if value in ("", "[]") else scalar(value)
            continue

        if key is None or not isinstance(data.get(key), list):
            raise ContentError(f"{where}:{lineno}: indented line under no list key")
        if line.startswith("- "):
            data[key].append({})
            line = line[2:].strip()
        if not data[key]:
            raise ContentError(f"{where}:{lineno}: list item must start with '- '")
        field, _, value = line.partition(":")
        data[key][-1][field.strip()] = scalar(value.strip())

    return data, body


def scalar(value: str) -> object:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    try:
        return int(value) if re.fullmatch(r"-?\d+", value) else float(value)
    except ValueError:
        return value


DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def date(value: object, where: str, field: str) -> str:
    if not isinstance(value, str) or not DATE.match(value):
        raise ContentError(f"{where}: {field} must be an ISO date, got {value!r}")
    return value


def slugify(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value).lower()).strip("-")


# ============================================================ markdown subset

INLINE = [
    (re.compile(r"`([^`]+)`"), r"<code>\1</code>"),
    (re.compile(r"\[([^\]]+)\]\(([^)]+)\)"), r'<a href="\2">\1</a>'),
    (re.compile(r"\*\*([^*]+)\*\*"), r"<strong>\1</strong>"),
    (re.compile(r"(?<!\*)\*([^*]+)\*(?!\*)"), r"<em>\1</em>"),
]


def inline(text: str) -> str:
    out = esc(text.strip())
    for pattern, repl in INLINE:
        out = pattern.sub(repl, out)
    return out


def blocks(md: str, indent: str = "        ") -> str:
    """Paragraphs, bullet lists and block quotes. That is the whole vocabulary.

    Anything richer belongs on a hand-written page. Keeping the subset this small
    means the generator can never emit markup nobody reviewed.
    """
    out: list[str] = []
    bullets: list[str] = []

    def flush() -> None:
        if bullets:
            out.append(f"{indent}<ul>")
            out.extend(f"{indent}  <li>{b}</li>" for b in bullets)
            out.append(f"{indent}</ul>")
            bullets.clear()

    for para in re.split(r"\n\s*\n", md.strip()):
        para = para.strip()
        if not para:
            continue
        if para.startswith("- "):
            # A bullet runs until the next "- ", so it may wrap over several
            # lines; the source is written to a readable measure.
            for line in para.split("\n"):
                line = line.strip()
                if line.startswith("- "):
                    bullets.append(line[2:].strip())
                elif bullets:
                    bullets[-1] += " " + line
                else:
                    raise ContentError(f"ragged bullet list near: {para[:48]!r}")
            bullets[:] = [inline(b) for b in bullets]
            flush()
        elif para.startswith("> "):
            flush()
            quote = " ".join(ln.strip().lstrip(">").strip() for ln in para.split("\n"))
            out.append(f'{indent}<blockquote class="pull">{inline(quote)}</blockquote>')
        else:
            flush()
            out.append(f"{indent}<p>{inline(' '.join(para.split()))}</p>")
    flush()
    return "\n".join(out)


# ===================================================================== shell

def nav_html(up: str, here: str) -> str:
    rows = []
    for href, label in NAV:
        current = ' aria-current="page"' if href == here else ""
        rows.append(f'    <a href="{up}{href}"{current}>{label}</a>')
    return "\n".join(rows)


def head(title: str, description: str, depth: int, *, here: str = "",
         noindex: bool = True) -> str:
    up = "../" * depth
    robots = '\n<meta name="robots" content="noindex, nofollow">' if noindex else ""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">{robots}
<script>try{{var t=localStorage.getItem('theme');if(t&&t!=='system')document.documentElement.setAttribute('data-theme',t)}}catch(e){{}}</script>
<link rel="stylesheet" href="{up}style.css">
<link rel="stylesheet" href="{up}sections.css">
<link rel="icon" href="{ICON}">
</head>
<body>
<a class="skip" href="#main">Skip to content</a>

<nav class="nav" aria-label="Primary">
  <div class="wrap">
    <a class="nav__home" href="{up}index.html">Juan Mediavilla</a>
{nav_html(up, here)}
    <span data-theme-slot></span>
  </div>
</nav>

<main id="main">
"""


def foot(depth: int) -> str:
    up = "../" * depth
    links = " · ".join([f'<a href="{up}index.html">Home</a>'] +
                       [f'<a href="{up}{href}">{label}</a>' for href, label in FOOT])
    return f"""</main>

<footer class="foot">
  <div class="wrap">
    <p>Juan Mediavilla · London · {links}</p>
  </div>
</footer>

<script src="{up}app.js"></script>
</body>
</html>
"""


# ==================================================================== writing

def emit(pages: dict[pathlib.Path, str], out_dir: pathlib.Path, check: bool,
         label: str, *, orphans: bool = True) -> int:
    """Write the pages, or report which would change. The idempotence contract.

    `orphans=False` for a generator that owns only the index of a directory
    other generators also write into — /notes holds Investing and Books, and
    they are not strays just because this script did not produce them.
    """
    stale = []
    for path, text in pages.items():
        if path.exists() and path.read_text(encoding="utf-8") == text:
            continue
        stale.append(path.relative_to(SITE).as_posix())
        if not check:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8", newline="\n")

    known = {p.resolve() for p in pages}
    strays = ([p.relative_to(SITE).as_posix() for p in out_dir.glob("*/index.html")
               if p.resolve() not in known] if orphans else [])

    if check:
        for p in stale:
            print(f"  stale: {p}")
        for p in strays:
            print(f"  orphan: {p} (no content file builds it)")
        if not stale and not strays:
            print(f"  {len(pages)} {label} pages up to date")
        return 1 if (stale or strays) else 0

    for p in strays:
        print(f"  orphan: {p} — delete it or restore its content file")
    print(f"  wrote {len(stale)} of {len(pages)} {label} pages")
    return 1 if strays else 0
