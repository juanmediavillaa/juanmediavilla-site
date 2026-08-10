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

It needs a Chrome. If yours is elsewhere:

```sh
CHROME=/path/to/chrome bash tools/audit.sh
```

### What it checks, and why each one exists

| Check | Catches |
|---|---|
| **Layout** at 320, 390, 768, 1440 | page overflow, elements overflowing a non-scrolling parent, any text under 12px, scroll regions missing `role`/`aria-label`/`tabindex` |
| **Computed contrast**, both themes | any text below WCAG AA against its *effective* background, resolved through the ancestor chain — **including SVG text, measured on `fill`** |
| **Structure**, scripting on and off | heading order, one `h1`, five nav items, landmarks, dead in-page anchors, external subresources, and anything hidden when JS is off |
| **Generator idempotence** | a figure, diagram or glossary entry that has drifted from its source |
| **Prohibited content** | external subresources, infrastructure, secrets, identifiers, student data, retired figures |
| **Framing** | a heading, card face or one-liner built on a null result |
| **Budgets** | markup over 90 KB (110 KB for `/research`, see §7), page over 600 KB (home 400 KB), JS over 25 KB |

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

## 3. How to add a project entry

Order is fixed, and it is the framing rule:

1. `<p class="oneline">` — **what was built**, in one sentence. Concrete nouns.
2. `<h3>What I built</h3>` + `<div class="plain">` — the system, the scale, the engineering.
3. `<h3>What was hard</h3>` — the real problem and the choice made. This is the section engineers
   read.
4. `<h3>What I found</h3>` — results, positive first where positive exists. Nulls stated plainly,
   in context.
5. `<details><summary>The technical version</summary><div class="inner">` — statistics, method,
   intervals, pre-registration.

**No heading, card face or opening sentence may be built on a null result.** The negative results
are why the positive ones can be believed; they are not the achievement. `tools/audit.sh` enforces
this.

Keep the plain-language layer: a reader with no background follows steps 1–4, and every technical
term is defined inline at first use on that page and linked to `/glossary`.

---

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
- **No fund figures** — no value, returns, members or positions. **No repository links.** **No
  student names, grades or submissions.**
- **University colours are quarantined** to `.inst` on `/about`. They never enter the series
  palette, a figure, or the gradient system. The card itself themes normally; only the logo sits
  on a fixed light chip. Dark-theme brand tints are derived from the measured hex by raising
  lightness alone — see `CONTENT-RULES.md` §12.
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

- **`~800 GB archived as of August 2026` is the only number on the site that is not
  machine-verifiable.** It is self-reported from cloud storage. It always carries its as-of date.
  Sanity-checked once: over the 83-day window the recorded 12.8 GiB/day implies a ~1,141 GB
  ceiling, so 800 GB means a 9.0 GiB/day realised average — consistent. **Re-check it whenever you
  next quote it**, and keep it distinct from the 250 GB server working set.
- **`assets/leiden-seal.svg` is 81 KB**, by far the heaviest asset. A precision-and-whitespace pass
  took it from 89 KB with a verified-identical render (0.1% of channels differing by more than
  8/255, edge antialiasing only). An aggressive pass that stripped elements dropped two visible
  fills, so it was reverted. A real optimiser (`svgo`) would do better but needs npm, which this
  repo does not use.
- **`/research` markup is 106.5 KB against a 110 KB cap**, higher than the 90 KB other pages get.
  That is deliberate: its six charts are inlined, and inlining is the only way an SVG can inherit
  the page's custom properties and therefore follow the manual theme toggle. A referenced `<img>`
  can only see `prefers-color-scheme`, so it desynchronises the moment someone overrides the OS.
  If that page grows further, move a section rather than going back to referenced figures.
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

**Credentials — delete the Supabase project.** *Pending, Juan to action.* The abandoned
`GitHub/website` repo holds `NEXTAUTH_SECRET`, `NEXT_PUBLIC_SUPABASE_URL` and
`NEXT_PUBLIC_SUPABASE_ANON_KEY` in an uncommitted `.env.local`. Deleting the Supabase project
retires all three at once, which is cleaner than rotating a key on a dead project. The two
`NEXT_PUBLIC_` values were always shipped to browsers by design, so their safety depended on Row
Level Security, not secrecy.
