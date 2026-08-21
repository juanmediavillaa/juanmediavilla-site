# Maintaining this site

Everything you need to edit this site safely, without rereading how it was built.

**Read [CONTENT-RULES.md](CONTENT-RULES.md) first.** It is the binding document; this one explains
the machinery.

---

## 1. The one command

```sh
bash tools/audit.sh
```

Runs every check. Non-zero exit means something is wrong. **Run it before every commit**, and
certainly before merging to `main`.

A green audit is not permission to publish. **Do not `git push` unless the owner asks for it in
that exchange** — see [CONTENT-RULES.md §0](CONTENT-RULES.md). Commit locally, report what
changed, and wait.

It needs a Chrome. If yours is elsewhere:

```sh
CHROME=/path/to/chrome bash tools/audit.sh
```

### What it checks, and why each one exists

| Check | Catches |
|---|---|
| **Layout** at 320, 390, 768, 1440 | page overflow, elements overflowing a non-scrolling parent, any text under 12px, scroll regions missing `role`/`aria-label`/`tabindex` |
| **Computed contrast**, both themes | any text below WCAG AA against its *effective* background, resolved through the ancestor chain — **including SVG text, measured on `fill`** |
| **Structure**, scripting on and off | heading order, one `h1`, the nav item count, landmarks, dead in-page anchors, external subresources, and anything hidden when JS is off |
| **Internal links** | every relative `href` resolves to a file, and every `#fragment` to a real `id` |
| **Generator idempotence** | a figure, diagram or glossary entry that has drifted from its source |
| **Prohibited content** | external subresources, infrastructure, secrets, identifiers, student data, retired figures |
| **Framing** | a heading, card face or one-liner built on a null result |
| **Budgets** | markup over 90 KB, page over 600 KB (home 400 KB), JS over 25 KB — fonts included |

**Why measured and not reviewed.** Four separate defects here were rules written into
`CONTENT-RULES.md` that nothing enforced in code:

- `--muted` was documented as graphical-only while twenty rules used it for text (3.96:1);
- a scroll animation hid every below-fold section and handed visibility back via script;
- charts were pinned to 640px and overflowed every phone, while the overflow check compared
  against `window.innerWidth` — which *stretches to fit overflowing content* under mobile
  emulation, so the test passed while the page was 662px wide at 390;
- every generated SVG carried its own `prefers-color-scheme` palette, so using the theme toggle
  left the charts and diagrams on the opposite theme from the page. The contrast audit could not
  see it either, because it read `color` on SVG text when SVG text is painted by `fill`.

The August 2026 redesign added two more checkers for the same reason. **Internal links** are
checked because splitting the long pages into per-project pages moved a dozen targets, and a
stale `href` is invisible until someone clicks it — it caught two immediately. **Fonts are now
charged to the page-weight budget**: they are referenced from `style.css`, not from the markup,
so the old budget script never counted them and 70 KB of typeface was invisible to it.

A CSS review found none of them. Measuring the rendered page found all four in minutes. **If a
rule matters, give it a checker, not a paragraph.**

---

## 2. The generators

Nothing on this site is drawn by hand or retyped. Three scripts, standard library only, no
dependencies:

```sh
python3 tools/make_figures.py     # charts from real result files + their source CSVs
python3 tools/make_diagrams.py    # the nine explainer diagrams
python3 tools/build_glossary.py   # /glossary from one term list
```

The link-preview card is the fourth generated artifact, and the only one that needs a browser:

```sh
chrome --headless=new --window-size=1200,630 --hide-scrollbars \
       --blink-settings=preferredColorScheme=1 --virtual-time-budget=3000 \
       --screenshot=assets/og.png tools/og-card.html
```

`tools/og-card.html` is the source. Its four numbers are the home page's stat tiles — if those
change, change both. It is referenced only from `og:image` / `twitter:image` `<meta>` tags, which
are absolute by necessity and never fetched by a reader's browser.

Each takes `--check`, which re-runs and fails if any output would change. That is the idempotence
contract: **a stale figure is a detectable condition, never a silent one.**

- `make_figures.py` reads committed result files under `poly-research/results/` and the BSc LOSO
  logs, writes `data/*.csv` and `figures/fig-*.svg`, then injects each into its page between
  `<!-- FIGURE:name -->` markers along with a "Show the numbers" data table. It also recomputes
  the BSc Friedman test from the per-fold logs rather than quoting it.
- `make_diagrams.py` writes `figures/dia-*.svg` and injects them between `<!-- DIAGRAM:name -->`
  markers. These are inline, so they carry `<title>` hover readouts.
- `build_glossary.py` generates `/glossary` from one `TERMS` list and, under `--check`, fails on
  a link to a missing anchor **and** on a term defined but never linked.
- `tools/build_prereg.py` builds the embargoed page. **Always regenerate with it; never paste the
  source documents in.** It pseudonymises venue market identifiers, which a hand-copy would leak.

Both SVG generators validate their output as XML before writing. This is not decorative: an SVG
referenced by `<img>` is parsed strictly, and an unclosed element that HTML tolerates inline is
fatal there. Five of eight figures were silently broken this way once.

---

## 3. How to add a project

Each substantial project is **its own page** at `projects/<slug>/index.html`. Copy the nearest
existing one — they all share a single shell, so head, nav and footer must not drift apart.

1. `projects/<slug>/index.html` — `<header class="head">` with the eyebrow, `<h1>`, the one-line
   summary as `.standfirst`, `.case__meta`, and a `<ul class="keyfacts">` of four traced numbers.
2. Body sections go inside `<div class="rail">`: the label column carries the eyebrow, the content
   column everything else.
3. Add a `<a class="work__row">` to `projects/index.html`, with `id="<slug>"` so any old anchor
   into the long page still resolves.
4. Add the page to `PAGES` in `tools/audit.js` and a `<url>` to `sitemap.xml`. **The audit only
   checks pages it is told about.**
5. Wire the `.pager` at the foot of the neighbouring case studies.

Within the page, order is fixed, and it is the framing rule:

1. `<p class="oneline">` — **what was built**, in one sentence. Concrete nouns.
2. `<h2>What I built</h2>` + `<div class="plain">` — the system, the scale, the engineering.
3. `<h2>What was hard</h2>` — the real problem and the choice made. This is the section engineers
   read.
4. `<h2>What I found</h2>` — results, positive first where positive exists. Nulls stated plainly,
   in context.
5. `<details><summary>The technical version</summary><div class="inner">` — statistics, method,
   intervals, pre-registration.

Headings inside a case page start at `<h2>`, because the project title is the page's `<h1>`. The
audit fails on a skipped level, so do not open a section with `<h3>`.

**No heading, card face or opening sentence may be built on a null result.** The negative results
are why the positive ones can be believed; they are not the achievement. `tools/audit.sh` enforces
this.

Keep the plain-language layer: a reader with no background follows steps 1–4, and every technical
term is defined inline at first use on that page and linked to `/glossary`.

---

## 3a. How to add a position to /notes/investing

`/notes/investing` is **generated**, not hand-written. Three inputs, kept apart on purpose:

```text
content/positions/<slug>.md   my writing, and the facts I supply per position
data/prices.json              last price per ticker      -> tools/prices.py
data/portfolio.json           the currency and the cost date -> tools/portfolio.py
```

```sh
python3 tools/build_notebook.py             # write the pages
python3 tools/build_notebook.py --check     # fail if any page would change
python3 tools/build_notebook.py --selftest  # reconcile every derived number
```

1. Add `content/positions/<slug>.md`. Front matter needs `ticker`, `name`, `theme`, `status`,
   `summary`, `updated`, plus **either** an `entries` ledger **or** an `avgCost`. Optional:
   `bookReturnPct`, `exits`, `slug`.
2. **Every position gets a page**, because every card opens onto it. The body is two sections in
   this order: `## Thesis` and `## Latest movements`. Where there is no memo the thesis section
   says so plainly — it is never filled in from the outcome.
3. Drop the logo into `images/` (gitignored, shared with the book covers) and run
   `python3 tools/make_logos.py`. Name it after the content file, or add an entry to `ALIASES` —
   `images/meta.svg` becomes `assets/logos/meta-platforms.svg`. A position without one shows a
   monogram in the same fixed box, so nothing shifts when the artwork lands. An unmatched **SVG**
   is an error (covers are never SVG, so it means a misnamed logo); an unmatched raster is ignored,
   because it is a book cover.

**SVG logos are rewritten, not copied.** Downloaded brand SVGs carry `<metadata>` blocks that can
embed an author name and a local filesystem path, plus editor namespaces and, in principle,
`<script>` and `on*` handlers — inert behind `<img>`, live the moment anyone inlines one. All of it
is stripped and the result is parsed as XML before writing, the same contract the other SVG
generators hold. A file referencing anything off-origin is **refused**, not cleaned: that breaches
CONTENT-RULES.md §4.9 and means it is not self-contained.

**Logos keep a fixed light ground in both themes** — the fourth such block after the gradient hero,
the institution card and the terminal (§13). Amazon's wordmark measures 0.012 relative luminance,
Micron's 0.051 and Reddit's shading 0.002: on the dark plane they would be invisible. Re-colouring
someone else's mark is the wrong fix, so the ground is pinned and the artwork left alone.
3. Add the ticker to `data/prices.json`, and update `data/portfolio.json` for cash and NAV.
4. Register any new page in `PAGES` in `tools/audit.js`.

**The safety rule, and why it is in the code rather than in this file:**

- **No position weight, and no amount, share count or account value, anywhere.** Share prices,
  per-position returns and index levels only. What is held is public; how much of it is held is
  not — not a weight, not a share of equity, not a cash line.
- **This repository is public, so a content file is published whether or not a page renders it.**
  Removing a figure from the markup is not removing it. It has to come out of
  `content/positions/*.md` and `data/*.json` as well, and `--selftest` asserts that it has.
- `tools/portfolio.py` refuses any field it does not recognise and any field whose name looks like
  a quantity; it is an allow-list, not a deny-list. The risk is not a careless sentence — it is one
  absolute number added months later, beside figures that are already public.
- **The table is ordered alphabetically on purpose.** Ordering by size would re-encode the ranking
  that removing the weights was meant to withhold.
- **No performance history and no aggregate return.** The NAV series, the realized figure and the
  live-book figure were removed when the strategy and structure changed: a record running through
  that change describes an approach no longer in use. `tools/portfolio.py` now *rejects* `nav`,
  `cashPct`, `liveBookPct` and `realizedPct` outright, so putting one back is a build failure
  rather than a quiet reintroduction. The page says the history is absent and why, instead of
  leaving a gap where a chart used to be.
- **`share` on an entry is a percentage of the position's own units**, so it weights the average
  without disclosing size.
- **Never point this generator at the raw ledger exports or `reports/`.** Those carry member names,
  deposits, email addresses and an IBAN. Everything here is derived from a hand-written summary of
  them, and that boundary is the whole design.

**One currency throughout.** The return is derived from cost and price and nothing else, so it is
correct the moment a new quote lands and there is no second figure to keep in step.

**Prices update themselves.** `.github/workflows/update-prices.yml` runs `tools/fetch_prices.py`
on weekday evenings, rebuilds, and commits only if something moved. No API key, so there is no
secret to leak from a public repository. The fetch is **all-or-nothing**: one bad ticker aborts the
run and yesterday's complete snapshot stays up rather than a half-updated one. The as-of date comes
from the quote, resolved in the exchange's timezone — a UTC date stamps a Friday close as Saturday.

`tools/fetch_prices.py` is the only writer of `data/prices.json` and `tools/prices.py` the only
reader. CONTENT-RULES.md §4.9 is about what the *page* requests; this runs on a build machine and
ships nothing but a committed JSON file.

**Cost basis is computed from `entries` when the ledger is supplied, and taken from `avgCost` when
it is not** — and the page states which of the two a reader is looking at. Supplying the per-trade
ledger is strictly better: it makes the basis recomputable and keeps it correct as trades are
appended.

**Write behaviour, not reconstructed theses.** Across the current ledger exactly one trade carries
a written note. A thesis composed now, after the outcome is known, is the most flattering thing
this section could contain and the least honest. Where a memo exists, say so; where it does not,
say that.

**`NOINDEX = True`, and `CONTENT-RULES.md` §4.3 currently forbids this section outright** — "No
fund data. No AUM, returns, member names, member count, or any fund state." Publishing needs that
rule amended first, and needs a view taken on whether a published track record counts as a
financial promotion.

## 3b. How to add a book to /notes/books

Same machinery as `/notebook`, one file per book:

```sh
python3 tools/build_books.py            # write the pages
python3 tools/build_books.py --check    # fail if any page would change
```

1. Add `content/books/<slug>.md`. Front matter needs `title`, `author`, `read` (a year, or
   whatever precision the memory actually has) and `verdict` (`loved` | `good` | `fine` |
   `dropped`). Optional: `summary`, `shelf`, `sortKey`, `slug`.
2. **A body is optional, and that is the point.** With no `##` sections the book is a flat card on
   the shelf and gets no page. Most reading never gets written up, and a shelf showing only the
   books worth a page would be a flattering shelf rather than an accurate one.
3. With a body, the shape is fixed by the note template: the thesis in a sentence, the two or
   three ideas worth keeping, the disagreement, and what would actually change. **An empty last
   field means the book was entertainment — label it, never invent a lesson.**
4. Register the page in `PAGES` in `tools/audit.js` if it has a body.

**The verdict measures enjoyment, not yield**, and the two come apart — the book that produced the
most usable ideas is marked `fine`. Do not collapse them into one score.

**Titles of cited works carry `class="work-title"`.** The framing check in `tools/audit.sh` bans
words like "failed" from a heading; *When Genius Failed* is the name of a book, not a claim about
my own work, and that class is the exemption. Use it only for the title of someone else's work.

## 3c. Adding a whole new section under /notes

`/notes` is one nav entry standing in front of several sections, so the nav stays at five items no
matter how many accumulate. To add one:

1. Write its generator, following `tools/build_books.py` — output to `notes/<slug>/`, pages at
   depth 2, item pages at depth 3, `here="notes/index.html"`.
2. Add an entry to `SECTIONS` in `tools/build_notes.py`. The counts on the index are read from the
   content directory, so they cannot drift.
3. Register its pages in `PAGES` in `tools/audit.js`.

**Do not add it to the nav.** The nav is the professional surface — Projects and Research first,
one entry for everything written alongside them, then the pages about the author. `NAV_LINKS` in
`tools/audit.js` asserts the count, and `tools/audit.sh` compares every page's nav against
`sitegen.NAV`.

## 3d. Two stylesheets, and the nav

**`style.css` is charged to every page; `sections.css` only to the pages that link it.** The
notebook and books components live in the second file because the budget check charges every page
for the whole of any stylesheet it loads, and `/research/msc` sits close to its 90 KB markup cap.
Putting a section nobody else uses into `style.css` cost that page 7 KB it did not have.
`tools/audit.sh` now sums the stylesheets each page actually links, rather than assuming one file —
the same class of blind spot as the fonts.

**The nav is defined once in `tools/sitegen.py` `NAV`, and copied into 16 hand-written pages.**
Adding a section means: edit `NAV`, edit every hand-written page and both other generators, and
raise `NAV_LINKS` in `tools/audit.js`. `tools/audit.sh` compares every page's nav against `NAV`
and fails on any that has drifted, because a page left on the old nav is invisible until someone
lands on it and cannot get out.

**The nav wraps below 768px and always has.** `--nav-h` is derived from a single row, so
`scroll-padding-top` was ~36px short on every phone and in-page links landed under the nav. There
are now two measured bands for it. They are deliberately loose: too large only adds whitespace
above an anchor, too small hides the target, and the exact wrap point moves whenever a label
changes.

## 4. How to add a figure

1. Add a builder function in `tools/make_figures.py` that reads a **real committed result file**.
   If the number is not in a file, it does not ship.
2. Publish its source numbers with `write_csv(...)`.
3. Put `<!-- FIGURE:name -->` / `<!-- /FIGURE:name -->` where it belongs and run the generator.
4. Write the caption. It opens with **"What you're looking at:"** in plain present tense and says
   what the *opposite* result would have looked like. The provenance line comes second and states
   n, the date of the data, pre-registered yes/no, and in-sample vs held-out.
5. Authored SVG type is **never below 12px**, and charts display at 1:1 or larger — they scroll
   inside their own labelled region on a phone rather than shrinking into illegibility.

If a curve is *derived* rather than read from a file, the CSV column name must say so — see
`rejected_weibull_shape_from_k_normalised_at_first_bin` in `data/hazard.csv`.

---

## 5. Rules that are not obvious from the code

- **The fact ledger.** Every number traces to a committed result file, the thesis source, the BSc
  PDF, or a verifiable repository fact. Never invent, never round into existence, never upgrade a
  hedge.
- **Aggregate and derived statistics only**, nothing below 10-minute resolution, and **never a
  venue market identifier** — an 8-hex prefix is effectively unique in the corpus.
- **No fund figures** — no value, returns, members or positions. **No links to the private source
  repositories** — `default-fail` is the one public exception, named in `CONTENT-RULES.md` §4.1.
  **No student names, grades or submissions.**
- **University colours are quarantined** to `.inst` on `/about`. They never enter the series
  palette, a figure, or the gradient system. The card and both logos theme normally: the UCL mark is
  inlined so its fills read the card's tokens, and the monochrome Leiden seal is lifted on dark by a
  `filter` in `style.css` (which follows the toggle; a `prefers-color-scheme` variant file would
  not). Dark-theme brand tints are derived from the measured hex by raising lightness alone — see
  `CONTENT-RULES.md` §12.
- **`--muted` never carries text.** It is 3.96:1 in light. Tertiary text uses `--ink-3`.
- **Three blocks keep a fixed ground in both themes** — the gradient hero, the institution card,
  the terminal. Anything inside them that would inherit a themed ink (`strong`, `b`, `em`, `code`,
  `.num`) must be pinned, or it inverts and disappears.
- **Retired figures** are listed in `CONTENT-RULES.md` §2. They must not come back.
- **Nothing may be hidden by CSS that only script can reveal.**

---

## 6. Publishing the thesis pre-registration

`research/thesis/pre-registration/` is written, committed and deliberately unpublished. It goes
live **after the MSc is submitted in September 2026**. Three lines:

1. Delete `<meta name="robots" content="noindex, nofollow">` from
   `research/thesis/pre-registration/index.html`.
2. Add `<url><loc>https://juanmediavilla.com/research/thesis/pre-registration/</loc></url>` to
   `sitemap.xml`.
3. Link it from `research/index.html` (the "How to check this" block already names the embargo —
   replace that sentence with the link) and from `research/thesis/index.html`.

Then `bash tools/audit.sh` and commit. Five minutes.

Worth doing properly rather than early: a pre-registered specification published *beside* the
report that fails its own primary test is the one claim on this site that cannot be constructed
retroactively, because the commit ordering proves it.

---

## 7. Known soft spots

- **`~1.05 TB archived as of August 2026` is the only number on the site that is not
  machine-verifiable.** It is self-reported from cloud storage and always carries its as-of date.
  Re-checked on 20 August 2026 when it moved up from `~800 GB`: over a ~102-day window the recorded
  12.8 GiB/day implies a ~1,402 GB ceiling, so 1.05 TB means a 9.6 GiB/day realised average, 75% of
  peak — consistent, and up from 9.0 GiB/day at the previous figure. **Re-run that check every time
  it moves**, keep it distinct from the 250 GB server working set, and add the old value to the
  retired table in `CONTENT-RULES.md` §2 so it cannot come back as current.
  **Growing it changes nothing downstream**: the 12.8 GiB/day rate, the seven streams, the audited
  panel (400 markets, 188,856 trades) and the curated tier (206 markets, 408,414 events) are
  derived from committed files and do not move.
- **`assets/leiden-seal.svg` is 81 KB**, by far the heaviest asset. A precision-and-whitespace pass
  took it from 89 KB with a verified-identical render (0.1% of channels differing by more than
  8/255, edge antialiasing only). An aggressive pass that stripped elements dropped two visible
  fills, so it was reverted. A real optimiser (`svgo`) would do better but needs npm, which this
  repo does not use.
- **`/research/msc/` is 80.7 KB against the 90 KB cap** — the largest page on the site. Its charts
  are inlined, and inlining is the only way an SVG can inherit the page's custom properties and so
  follow the manual theme toggle; a referenced `<img>` can only see `prefers-color-scheme` and
  desynchronises the moment someone overrides the OS. `/research` needed a raised 110 KB cap while
  both theses shared one page; splitting them removed the exception. **If that page grows again,
  split it — do not raise the cap and do not go back to referenced figures.**
- **Two typefaces are committed under `assets/fonts/`**, 69.9 KB in total, and the budget check now
  charges every page for all of them. A reader typically downloads about 60 KB, because the
  latin-ext subsets carry a `unicode-range` and are only fetched if an accented character appears.
- **Charts scroll horizontally at 320px** rather than having hand-built portrait variants. The
  charts stay at 1:1 so their 12px type is legible, each scroll region is labelled and
  keyboard-reachable, and the same numbers are in the data table beside it. Building narrow
  portrait variants — taller aspect, fewer ticks, horizontal bars for the 34-market chart — is the
  next improvement if the mobile experience needs more.
- **`poly-research` has a second git remote pointing at a private host over SSH.** Nothing in this
  repo or its history references it (verified). **It must stay private** — never add it here, and
  never subtree-split that repo to extract code, because the remote config and unrelated history
  come with it.

---

## 8. Open items

**TraderProfiler — prepare, do not publish without a decision.**
Agreed: a fresh repository, squashed history, synthetic fixtures, MIT licence.

The blocker is content, not secrets. Credentials are clean — `.env` was never committed and no
credential value appears in any revision. But **every commit since the second ships raw venue API
responses containing per-trade data at second resolution, attached to two identifiable real people**
(handles, bios, wallet addresses). Because that is in nine of ten commits, `git rm` is not
sufficient: anyone can check out the earlier commit. It has to be a new repository with a single
initial commit.

Release path: copy the 63 tracked files from `poly-research/trader_profiler/` (not the archived
standalone repo, which carries committed `.pyc` and scratch data) into a clean directory,
`git init`, replace both raw fixture sets with synthetic data — same schema, fabricated wallets and
handles, timestamps quantised to ≥10 minutes — rename the fixtures so the names do not re-identify
the subjects, delete `OVERNIGHT_LOG.md` and the dangling `PROJECT_STATE.md` pointer, add a
`LICENSE`, and add the accuracy figures to the README **with their n=5 attached** plus a
false-positive caveat on the word "INSIDER".

**Credentials — Supabase project deleted. ✅ Closed 20 August 2026.** The abandoned
`GitHub/website` repo held `NEXTAUTH_SECRET`, `NEXT_PUBLIC_SUPABASE_URL` and
`NEXT_PUBLIC_SUPABASE_ANON_KEY` in an uncommitted `.env.local`. Deleting the project retired all
three at once, which was cleaner than rotating a key on a dead project.

Verified rather than assumed, and worth recording how, because the same four questions answer any
future version of this:

- **`.env.local` was never committed** — gitignored, and zero commits touch it.
- **No secret value is in the history.** One commit matches `SUPABASE_ANON`, and it is
  `src/lib/supabaseClient.js` referencing `process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY` — the
  variable name, not a value.
- **The repository is not public** (GitHub returns 404 unauthenticated).
- **The project is gone**: its `*.supabase.co` subdomain has no DNS record, while `supabase.co`
  itself resolves — so this is deletion, not a network fault.

The dead `.env.local` was deleted from the local disk on 20 August 2026. Nothing was committed by
that: the file was gitignored and had never been tracked. **This item is fully closed** — no live
credential remains from that project anywhere, on disk or in history.
