# juanmediavilla.com

Personal site. Hand-written static HTML and one stylesheet. No framework, no build step, no
package manager, no dependencies, and **no third-party network requests of any kind**.

Read [CONTENT-RULES.md](CONTENT-RULES.md) before editing anything. It is not optional — it
records claims that had to be retracted from the previous version of this site.

## Structure

```
index.html              home
projects/index.html     one entry per project, with results including the negative ones
research/index.html     MSc thesis + BSc thesis + the method
research/thesis/        MSc thesis deep-dive (deliberately not in the primary nav)
how-i-work/index.html   agentic systems, stated as artifacts rather than claims
about/index.html        education, teaching, skills tiered by demonstrability
cv/index.html           the CV; prints to a 2-page PDF (not in the primary nav)
404.html                served by Pages for any missing path
style.css               the entire design system
```

Nav is exactly five items: Home, Projects, Research, How I Work, About. `/cv` and
`/research/thesis/` are reachable but unlisted.

## Build

There is no build. Edit the HTML, open it in a browser. Every page works from `file://`, so
links are written as `projects/index.html` rather than `/projects/` — that resolves both on
GitHub Pages and from the local filesystem.

## Deploy

This repository is the live site: GitHub Pages, default branch, root directory.

- `CNAME` contains `juanmediavilla.com` and has **no trailing newline**. Leave it exactly as it
  is; rewriting it is the one change that breaks the custom domain.
- `.nojekyll` is present so Jekyll never touches the output.
- Settings → Pages → Source: *Deploy from a branch*, branch `main`, folder `/ (root)`.

Merging a change to `main` publishes it. There is no build step and no action to wait on.

### The one file with absolute paths

`404.html` is served by Pages for a missing path at any depth, so its links must be absolute
(`/research/`, not `../research/`). It is therefore the only page that does not resolve from
`file://`, by necessity. Every other page uses relative links and works offline.

## The CV

`cv/index.html` **is** the CV — there is no separate PDF in the repository. To produce one,
open the page and print to PDF. The print stylesheet drops the navigation and footer, sets
9.5pt type and 12mm page margins, and avoids breaking inside an entry. Verified at 2 pages.

Keeping the CV as HTML rather than a binary means it is diffable, and it is the only editable
CV source that exists.

## Evidence

Every figure is generated from a real result file by a committed script. Nothing is drawn by
hand and no number is retyped into markup.

```sh
python3 tools/make_figures.py           # regenerate figures + data, re-inline into pages
python3 tools/make_figures.py --check   # non-zero exit if any figure is stale
python3 tools/build_prereg.py           # rebuild the embargoed pre-registration page
```

`make_figures.py` reads the committed research result files, writes the source numbers to
`data/*.csv`, writes hand-authored SVG to `figures/*.svg`, and inlines each figure into its page
between `<!-- FIGURE:name -->` markers. Standard library only — no numpy, no plotting library.

It also recomputes the BSc thesis Friedman test from the per-fold logs rather than quoting it:
χ² = 6.104, df = 5, p = 0.296, which reproduces the thesis's own "not significant" verdict.

Each figure caption states n, the date of the data, whether the analysis was pre-registered, and
whether the result is in-sample or held-out, and links the CSV behind it. **Read
[CONTENT-RULES.md](CONTENT-RULES.md) §7 before adding a figure** — the aggregate-only and
10-minute-resolution rules are what keep this publishable.

### The embargoed page

`research/thesis/pre-registration/` is built but deliberately unpublished: unlinked, `noindex`,
and absent from `sitemap.xml`. It publishes after the MSc thesis is submitted in September 2026.
Publishing a pre-registered SPEC beside the report that fails its own primary test is the one
claim on this site that cannot be constructed retroactively — the commit ordering is the proof —
so it is worth doing properly after submission rather than half-doing before it. To publish:
drop the robots meta, add it to the sitemap, and link it. Regenerate it with `build_prereg.py`,
never by pasting the source documents, because that script pseudonymises venue market
identifiers.

## JavaScript

There is none, and the site ships zero `<script>` tags. A hover readout on the figures is
provided by SVG `<title>`, which browsers render natively at zero bytes. If script is ever
added, `CONTENT-RULES.md` §8 caps it at 3 KB and requires every chart to stay fully readable
with JS disabled.

## Design system

One stylesheet, ~9 KB. Light and dark via `prefers-color-scheme`; no toggle, so there is no
JavaScript on the site at all.

Typography is system font stacks — `system-ui` for text, `ui-monospace` for figures. This is a
deliberate departure from the original spec, which asked for self-hosted subset woff2: a
self-hosted pair would have cost 40–80 KB per page against a 100 KB budget, to replace stacks
that already render well and cost zero bytes and zero requests. Revisit only if a licensed
font file is actually available offline.

Numbers are set in monospace with `tabular-nums` — they are the ornament, so they are meant to
carry the visual interest rather than illustration. Two hues: green for links and positive
results, clay for the negative-result marker.

## Verification

Contrast, layout and weight are checked rather than eyeballed.

- **Contrast** — all 30 foreground/background pairs clear WCAG AA in both themes, minimum
  5.13:1.
- **Layout** — no horizontal overflow at 390px or 1440px on any page, in either theme.
- **Structure** — one `<h1>` per page, no skipped heading levels, `<main>` landmark and a skip
  link on every page.
- **Weight** — largest page is 27.6 KB uncompressed including the shared stylesheet, against a
  100 KB budget.

Note that headless Chrome's `--window-size` clamps to ~526px on Windows and *crops* rather than
reflows, so any narrow-viewport check must emulate the viewport over the DevTools Protocol
(`Emulation.setDeviceMetricsOverride`) instead. A screenshot taken with `--window-size=390`
will show false overflow.
