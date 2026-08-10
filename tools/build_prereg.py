#!/usr/bin/env python3
"""Build the embargoed pre-registration page from the committed research documents.

Reproduces research/thesis/pre-registration/index.html verbatim from the SPEC,
REPORT and CAVEATS of each pre-registered study, with one transformation: venue
market identifiers are replaced by stable pseudonyms.

That redaction is not cosmetic. An 8-hex prefix of a market's condition id is
effectively unique within the corpus, so publishing one alongside its per-market
statistics would identify a specific venue market — which CONTENT-RULES.md
forbids. Pseudonyms are assigned in order of first appearance across all
documents, so the same market keeps the same label throughout.

Standard library only. Run:  python3 tools/build_prereg.py
"""

from __future__ import annotations

import html
import pathlib
import re
import sys

SITE = pathlib.Path(__file__).resolve().parent.parent
RESULTS = pathlib.Path("/mnt/c/Users/jmedi/Documents/poly-research/results")
OUT = SITE / "research/thesis/pre-registration/index.html"

PACKAGES = [
    ("hier_mmpp_v0", "Hierarchical MMPP fit and pooling study",
     "SPEC ab05bc1 committed 2026-06-16, before any fit; results 5293b7a."),
    ("wf_mmpp_v0", "Walk-forward predictive-validity study",
     "SPEC ba92b6c committed 2026-06-17, before any outcome statistic; results a90c9bf."),
]
DOCUMENTS = ("SPEC.md", "REPORT.md", "CAVEATS.md")
MARKET_ID = re.compile(r"0x[0-9a-fA-F]{6,}")

HEAD_COMMENT = """<!--
  EMBARGOED. Built but deliberately unpublished: not linked from anywhere on the
  site, excluded from sitemap.xml, and carrying noindex.

  It publishes after the MSc thesis is submitted in September 2026. Publishing a
  pre-registered SPEC next to the report that fails its own primary test is the
  strongest evidence of method on this site, because it is the one claim that
  cannot be constructed retroactively - the commit ordering proves it. Worth doing
  properly after submission rather than half-doing before it.

  REDACTION: venue market identifiers in the source documents are replaced with
  stable pseudonyms ("market A", "market B", ...) by tools/build_prereg.py. Do not
  paste the raw documents in; regenerate with that script.

  TO PUBLISH: delete the robots meta above, add this page to sitemap.xml, and link
  it from research/index.html and research/thesis/index.html.
-->"""


def main() -> int:
    pseudonyms: dict[str, str] = {}

    def scrub(text: str) -> str:
        def replace(m: re.Match[str]) -> str:
            key = m.group(0).lower()
            if key not in pseudonyms:
                pseudonyms[key] = f"market {chr(ord('A') + len(pseudonyms))}"
            return pseudonyms[key]
        return MARKET_ID.sub(replace, text)

    sections = []
    for pkg, title, receipt in PACKAGES:
        blocks = []
        for doc in DOCUMENTS:
            path = RESULTS / pkg / doc
            if not path.exists():
                print(f"  ! missing {path}", file=sys.stderr)
                continue
            blocks.append(f'    <h3>{doc}</h3>\n    <pre class="code">'
                          f"{html.escape(scrub(path.read_text()))}</pre>")
        sections.append(
            f'  <section class="section">\n'
            f'    <p class="eyebrow">{pkg}</p>\n'
            f"    <h2>{title}</h2>\n"
            f'    <p class="meta">{receipt}</p>\n'
            + "\n".join(blocks)
            + "\n  </section>"
        )

    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pre-registration and reports — embargoed until submission</title>
<meta name="robots" content="noindex, nofollow">
<link rel="stylesheet" href="../../../style.css">
<link rel="icon" href="data:,">
</head>
{HEAD_COMMENT}
<body>
<a class="skip" href="#main">Skip to content</a>

<nav class="nav" aria-label="Primary">
  <div class="wrap">
    <a class="nav__home" href="../../../index.html">Juan Mediavilla</a>
    <a href="../../../projects/index.html">Projects</a>
    <a href="../../index.html">Research</a>
    <a href="../../../how-i-work/index.html">How I Work</a>
    <a href="../../../about/index.html">About</a>
  </div>
</nav>

<main id="main">
  <header class="head">
    <div class="wrap">
      <h1>Pre-registered specifications and reports</h1>
      <p class="standfirst">
        The committed specifications for two MSc thesis studies, reproduced verbatim, each next to
        the report of what the study actually returned and the caveats carried with it.
      </p>
      <p class="meta">
        <b>Embargoed until submission, September 2026.</b> Not linked, not indexed, not in the
        sitemap. Venue market identifiers are replaced with stable pseudonyms; nothing else is
        altered.
      </p>
    </div>
  </header>
  <div class="wrap">
{chr(10).join(sections)}
  </div>
</main>

<footer class="foot">
  <div class="wrap"><p>Juan Mediavilla · London</p></div>
</footer>
</body>
</html>
"""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(page)
    print(f"  wrote {OUT.relative_to(SITE)} ({len(page):,} bytes)")
    print(f"  pseudonymised {len(pseudonyms)} venue market identifier(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
