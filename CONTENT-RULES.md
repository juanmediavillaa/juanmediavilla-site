# Content rules

These rules bind anyone — human or agent — editing this site. They exist because several
claims on the previous version of this site were overstatements that had to be retracted.
**If a change would violate one of these, do not make the change.**

## 1. Every number traces to a source

No figure appears on this site unless it traces to one of:

- the MSc thesis single-source draft (`poly-research/writing/thesis_source/thesis.md`), whose own
  header states that every number is transcribed from committed `results/*/REPORT.md`;
- a committed results package under `poly-research/results/<package>/REPORT.md`;
- the BSc thesis PDF;
- a verifiable repository fact (e.g. commit counts from `git rev-list --count HEAD`).

If a figure cannot be traced, it does not ship. Mark it `<!-- TO CONFIRM: ... -->` and raise it.
**Never invent, round, or "approximately" a number into existence.** Never upgrade a hedge.

## 2. Figures that are retired — do not reintroduce

The previous site advertised these. They are wrong, superseded, or were retracted in kind:

| Retired claim | Status |
|---|---|
| `+665 nats` consensus model as evidence of belief consensus | Dead as a headline. Now `+6,731` at n=318, and the *claim* is retracted: the covariates correlate at `r = −0.998`, so the comparison distinguishes two functional forms of price extremity, **not belief from mechanics**. |
| `+17,349 nats` Hawkes over regime model | Superseded by `+48,970` at n=318, and now contested — a post-hoc three-state competitor reverses the ordering by `37,868` nats. |
| branching ratio `0.939` | Revised to `0.920 [0.917, 0.923]` at n=318. Never publish without the apparent-criticality bias caveat. |
| Brier `0.063` | Retired — traced to a lifetime-mean price on a different pull. |
| Brier `0.0585` | A legitimate variant on a disjoint archive, **not** interchangeable with the canonical `0.040`. |
| `n=105` as the corpus size | The final corpus is `n=318`. Pre-registered values must be labelled as such. |
| `~118 GB` corpus | Superseded. That was the **on-server working set**, not the archive. |
| `~236 GB` archive | Superseded. Was the portal documentation's figure at the time. |
| `~800 GB` archive | Superseded 20 August 2026 by `~1.05 TB`. It was correct when written; the archive grew. Do not reintroduce it as a current figure. |

**The corpus figure is `~1.05 TB archived as of August 2026`, and it is self-reported.** Unlike the
git-derived counts it cannot be verified from a committed file, so it always carries the as-of
date. Keep the two quantities distinct: the **250 GB server working set** that fills and is
periodically offloaded, and the **archived total on cloud storage**.

Sanity-checked against the recorded 12.8 GiB/day each time it moves. Over the ~102-day window the
ceiling is ~1,402 GB, so 1.05 TB implies a **9.6 GiB/day realised average (75% of peak)** — up from
the 9.0 GiB/day the previous 800 GB figure implied over 83 days, still short of peak, and explained
by the disclosed outage and the offload cycle. **A figure that cannot clear this check does not
ship.**

**Growing the corpus figure must not inflate anything downstream.** The audited panel (400
resolved markets, 188,856 trades) and the curated tier (206 markets, 408,414 repricing events)
are derived from committed files and do not move.

## 3. Language that is not licensed

- **Not** "belief consensus" as an identified economic mechanism. The thesis explicitly refuses it.
- **Not** "endogenous self-excitation" as identified. Licensed wording: *consistent with*
  self-excitation.
- **Not** "near-critical" or "criticality" as a mechanism claim without the estimation-bias caveat.
- **Not** "founder", "venture", or "startup" for ResolveIt or Alphatrack. ResolveIt was a
  five-person TU Delft course project; Alphatrack was a solo side product. Both are real; neither
  was a company.
- **Not** "my project" for AI4MDE Studio — it is a contribution of ~3% of commits.
- **Not** any characterisation of the MSc thesis as finished, submitted, examined or graded.

## 4. Hard prohibitions

1. **No links to the private source repositories.** The research platform, the wallet engine, the
   fund terminal, the data portal and the fund are private, are never linked, and nothing may imply
   they are public or reader-verifiable. **One exception, named explicitly:**
   `github.com/juanmediavillaa/default-fail` — public, MIT, mine — may be linked, and is, from
   `/how-i-work`, `/projects` and `/about`. This rule previously read "no repository links of any
   kind"; that was written when every repository was private, and the blanket form outlived its
   reason. Adding a second exception means editing this line first, and a repository qualifies only
   if it is already public and carries nothing covered by 4.2, 4.3, 4.4 or 4.10.
2. **No server hostnames, VPS providers, RPC endpoints, API keys, IP addresses, storage
   topology or private remote URLs** — not in markup, not in comments, not in commit messages.
3. **No fund data.** No AUM, returns, member names, member count, or any fund state. Never link
   or attach the fund repository; it contains credential files.
4. **No pricing, tiers, licence terms or purchase path for the data portal**, and nothing sourced
   from its `docs/internal/` (unpublished legal assessment and competitor teardown).
5. **No student names, grades or submissions** from teaching material.
6. **No self-reported Sharpe ratio** from any backtest.
7. **No user counts, traffic figures or analytics** — none exist for any project.
8. **No personal-life content.** No interests, reading, routines, health, relationships, or
   introspection. This site is professional only.
9. **No third-party network requests.** No CDN, no analytics, no external images, no embeds, and
   no font served from anyone else's host. Every subresource is same-origin and relative, so the
   site works from `file://` and no third party learns who read it.
   **Self-hosted fonts are permitted**, and there are two: Instrument Sans and IBM Plex Mono, both
   under the SIL Open Font Licence, subset to latin and latin-ext, committed under `assets/fonts/`
   with their licences beside them. They are `@font-face`d from `style.css` with a `unicode-range`,
   so a reader who never hits an accented character never downloads the latin-ext file.
   `rel="canonical"` and the Open Graph `<meta>` tags may carry absolute `https://juanmediavilla.com`
   URLs: they name a page for crawlers and are never fetched. `tools/audit.sh` enforces exactly
   this line — anything the browser actually requests must be same-origin.
10. **No raw feed data** hosted or linked, and no implication that the research repository is
    public or reader-verifiable.

## 5. Named third parties

Do not name a colleague, collaborator or student on this site. **Prof. Philip Treleaven is named
as MSc thesis supervisor on `/research` and `/research/thesis/` only** — not on the home page,
and never in an assessment context (no grades, no examiner marks, no rubric language, no
correspondence).

## 6. `/how-i-work` — the private-vault boundary

This page describes an agent-run personal knowledge vault. **The vault is private; only the
method is public.** On that page:

- **Never** reproduce note titles, file trees, directory names, screenshots, or any vault
  content beyond the short operating-rule fragments already quoted there.
- **Never** carry across personal-life material from the vault — it holds health, relationship
  and psychological notes, and rule 4.8 applies with full force.
- Quote only *operating rules*, never *stored facts*.
- Every principle on the page must keep an artifact attached. If a claim cannot point at
  something that was actually built or caught, delete the claim.
- The two self-critical catches (the fund-goal contradiction, and the two "founded ventures"
  corrected downward) are load-bearing. Do not soften them into successes.
- No tool-name badges or "built with" lists. Name a tool only when the sentence needs it.
- Keep it under 900 words.

## 7. Evidence: figures, data and code

**Every figure is generated by `tools/make_figures.py` from a real result file.** Never hand-draw
a chart, never retype a number into markup. Run `python3 tools/make_figures.py --check`; a
non-zero exit means a figure is stale.

- **Aggregate and derived statistics only.** Fitted parameters, test statistics, per-market
  summary deltas, p-values, confusion matrices. **Never raw or near-raw venue market data, and
  nothing below 10-minute resolution.** This mirrors the derived-data carve-out in the buyer
  licence and holds regardless of the venue-ToS question.
- **Never publish venue market identifiers.** `gpool.json` carries market IDs; the published
  `pooling-per-market.csv` is anonymised to rank order deliberately. Keep it that way.
- Every figure caption states: what it shows, n, the date of the data, pre-registered yes/no, and
  in-sample vs held-out. A caption missing any of these is not finished.
- Every figure links its source numbers as a downloadable file in `data/`.
- If a curve is *derived* rather than read from a file, the column name must say so — see
  `rejected_weibull_shape_from_k_normalised_at_first_bin` in `hazard.csv`.

**Quarantined, never to be published** (found during the round-3 inventory):

| Artifact | Why |
|---|---|
| `wf_mmpp_v0/logs/wf_trace.npz`, `figs/F4_detection_trace.png` | 2,880 one-minute bins for a **named** market — below the 10-minute floor |
| `trader_profiler/tests/fixtures/*_raw/` | verbatim venue API bodies, 1,017 wallet addresses, real handles and bios |
| `poly-data-portal/site/src/data/sample/*.json` | raw depth snapshots, mid-price series, trade samples |
| `regime_v1/panel.parquet`, `reassess_v1/behavior_features_with_clusters.parquet` | raw panel; carries `taker_address` |
| every `Investment_Fund` view except `App.jsx` | all carry money figures |

**Figures considered and rejected as stale** — do not resurrect these from the old site's history:
the n=105-era freeze and dynamics plots (`f4-dynamics.png`, `f6-freeze.png`), and 15 of the 17
inline figures in the retired `technical/` page. Exactly one figure in that page was still valid,
and it is not one the current site needs.

**Screenshots.** No fund screenshot ships: every screen in that app carries money figures, and a
leaked one is worse than a missing one. If that is ever revisited, the caption must state that
figures are redacted, and no AUM, NAV, return, member name, member count, position size or
holding may appear.

## 8. JavaScript ceiling

JS is permitted and currently uses **~15.5 KB of the 25 KB budget** (see §11). It adds the theme
toggle, a reveal, the hero point field, a scroll progress bar, stat counters and chart tooltips —
and **nothing that enables content**. SVG `<title>` already gives a native hover readout at zero
bytes.

- Hard ceiling **25 KB total across the whole site**, inline scripts included. No library, no build
  step, no npm.
- **Every chart must be complete and readable as static SVG with JS disabled** — all labels, all
  values, all axes in the markup. JS may add a hover readout and nothing else.
- No JS for navigation, layout, theming or content. The site must keep working from `file://`.
- Respect `prefers-reduced-motion`; no transitions on chart elements.

## 9. Plain language

**Nothing on this site may depend on domain knowledge the reader arrives with.** The audience is
a smart person with no maths, statistics, machine-learning or markets background.

- Every project entry and research finding opens with **one plain sentence**, then an **"In plain
  terms"** block, then the figure, then a `<details>` expander holding the technical version.
  **Technical content is never deleted — it moves.**
- A plain-language block may never state something stronger than the technical text it
  translates. Simplification that quietly upgrades a hedged claim is worse than jargon.
- Every symbol, unit and acronym is defined **inline at its first use on that page**, as visible
  text. A `title` attribute alone is not enough: it does not exist on touch devices.
- Every term links to `/glossary`, which is generated by `tools/build_glossary.py`. Run
  `--check`: it fails on a link to a missing anchor, and on a term defined but never used.
- Every figure caption opens with **"What you're looking at:"** in plain present tense, and says
  what the opposite result would have looked like. The provenance line comes second.
- Axis labels carry a human reading. Where an axis is log-scaled, say so and say why.

## 10. Framing

**Every project and finding is titled and summarised by what was built, explored or discovered.**
A null result never appears in a heading, a card face, or an opening sentence. It appears under
"What I found", stated plainly and without apology, because it is a finding.

- Entry structure, in order: **what I built → what was hard → what I found → how I know**
  (the last in a `<details>` expander).
- Banned from headings and card faces: "no edge", "not significant", "failed", "redundant",
  "does not", and any card whose single figure is a p-value.
- The rigour is a property of the work, not its subject. The negative results are why the
  positive ones can be believed — they are not the achievement.

## 11. Colour, motion and script

- The palette is **externally validated; do not substitute values.** Series slots are fixed and
  never cycled or reordered. The August 2026 redesign changed the page *around* the figures — the
  ground, the type, the layout — and deliberately left `--c1`..`--c6` untouched, so nothing that
  was validated had to be revalidated. Keep it that way: if a future design wants different series
  colours, they get measured first.
- **The page measure is measured, not assumed.** `ch` is the width of `0`, and Instrument Sans
  draws figures wide, so a `68ch` column rendered an 83-character line. `--measure` is `58ch`,
  which measures ~71 characters. Re-measure if the typeface ever changes.
- **Slot 4 (yellow) measures 2.82:1 in light** — anything drawn in it needs a direct label or a
  table. **Green and pink sit at ΔE 7.7 for deuteranopia in dark** — any chart using both needs a
  second encoding. Scatter and small-multiple charts cap at the first three slots.
- `--muted` is a **graphical** token (gridlines, axis rules) at 3:1. It measures 3.96:1 in light,
  so it never carries text; chart label text uses `--ink-2`.
- One y-axis per chart. Text wears text tokens, never a series colour.
- **JavaScript ceiling: 25 KB site-wide** (currently ~15.5 KB; see §8). No framework, no build step, no
  npm, no third-party request.
- **Nothing may be hidden by CSS that only script can reveal.** Reveal animations are applied by
  script only to elements it has already attached an observer to, so a blocked `app.js` costs the
  reader nothing. Verify with scripting disabled: zero hidden sections.
- Every animation stops under `prefers-reduced-motion`, and the hero pauses when the tab is
  hidden.

## 12. Institution identity

University colours are **quarantined to the education block on `/about`**. They never enter the
series palette, a figure, or the gradient system.

- Colours are **sampled from the institutions' own artwork**, not recalled: UCL `#9A3BFF` and
  `#361A54` (from `ucl-logo--primary.svg`), Leiden `#014189` (consistent across its seal SVG and
  logo PNG).
- **Two logo files are used**, both official vector artwork copied from the institution assets
  folder: `assets/ucl-logo.svg` (1.5 KB) and `assets/leiden-seal.svg` (89 KB). Nothing else from
  that folder is used — it also contains an authorisation letter, tuition records and a
  third-party low-resolution UCL raster, none of which may be copied.
- Logos state factually where I studied. Nothing on the site may imply endorsement by either
  institution.
- **The institution card and its logos all follow the theme.** No chip, no border, no fixed ground.
  The UCL logo is **inlined** so its two fills read the same tokens as the card. The Leiden seal is
  effectively monochrome, so a page-driven `filter` lifts it on dark — and because that filter lives
  in `style.css` it follows the manual toggle, which a variant file selected by
  `prefers-color-scheme` could not.
- The measured brand colours fall to **1.28:1 (UCL) and 1.90:1 (Leiden)** on the dark plane, so the
  dark theme uses variants derived from them — **same hue and saturation, lightness raised only**
  until they clear contrast: UCL name `#A54FFF` (4.62:1), Leiden name and rule `#0278FD` (4.57:1).
  UCL's measured primary `#9A3BFF` already clears 3:1 on dark and is kept as the rule. Derive any
  future variant the same way and record the measurement; never eyeball a brand colour.

## 13. Contrast is measured, not assumed

`--muted` is **graphical only**. It measures 3.96:1 in light and must never appear in a `color:`
declaration. Tertiary text uses `--ink-3` (`#6B687E` light, `#8A87A0` dark), which clears AA on
every surface including the three section bands.

Three blocks keep a **fixed ground regardless of theme** — the gradient hero, the institution
card and the terminal. Anything inside them that would otherwise inherit a themed ink
(`strong`, `b`, `em`, `code`, `.num`) must be pinned explicitly, or it inverts and vanishes.

Run the computed-contrast audit before publishing: it walks every text node in a real browser,
resolves the effective background through the ancestor chain, and reports any pair below AA. A
palette table cannot catch token drift; this does.

## 14. Responsive charts

Charts are authored on a 640-wide canvas with 11px labels. **Never let one shrink to fit a phone**
— at 342px that type renders around 6px. Each referenced figure sits in a `.scroll` container with
`min-width: 30rem`, so it keeps a legible size and scrolls inside its own box while the page itself
never moves. A global `img { max-width: 100% }` is the safety net beneath that.

**The overflow check must compare against the emulated device width, not `window.innerWidth`.**
Under mobile emulation the layout viewport stretches to fit overflowing content, so `innerWidth`
grows to match `scrollWidth` and the comparison silently passes. That is how a 662px-wide page at a
390px viewport reported "no overflow" for two rounds.

## 15. Mobile is measured, not reviewed

**Never shrink text below 12px to make something fit**, in CSS or in an SVG. Charts display at
1:1 or larger and scroll inside a labelled region instead of scaling down; every scroll region
carries `role="region"`, an `aria-label` and `tabindex="0"`.

Run `bash tools/audit.sh`. It loads every page at 320, 390, 768 and 1440 in a real browser and
fails on page overflow, on any element overflowing a non-scrolling parent, on any computed
font-size under 12px, and on an unlabelled scroll region.

A CSS review cannot catch this. Charts were pinned to 640px for three rounds while the check
compared `scrollWidth` to `window.innerWidth` — which stretches to fit overflowing content under
mobile emulation, so a 662px page at a 390px viewport reported no overflow. Measure against the
intended device width, and measure the rendered page.

## 16. SVG must inherit the page, never carry its own palette

**A generated SVG never defines its own colour tokens.** Inline SVG inherits the page's custom
properties, which respond to `prefers-color-scheme` *and* to the manual `data-theme` toggle. A
self-contained palette can only see the OS setting, so the moment someone overrides the theme the
figure renders on the opposite scheme from the page it sits in — near-black boxes on a white page.

That also means **figures are inlined, not referenced**. That used to cost `/research` a raised
110 KB markup cap, because all six charts sat on one page. Since the two theses each became their
own page (`/research/msc/` and `/research/bsc/`), the largest of them fits the ordinary 90 KB
budget and **the exception has been removed**. If a page approaches the cap again, split it rather
than raising it — going back to referenced `<img>` figures would desynchronise them from the
theme toggle.

Token names inside an SVG must match the page exactly: it is `--ink-2`, not `--ink2`. An
undefined custom property in a `fill` silently falls back to black, which is invisible in dark
mode and which the audit only catches because it measures `fill` rather than `color`.

## 17. Checks before publishing

Run `bash tools/audit.sh` — it does all of this and more. The two sweeps it wraps:

```sh
# no external subresources anywhere (rel=canonical/alternate/me are metadata, never fetched)
grep -rnoE '<(link|script|img|iframe)[^>]*(src|href)="(https?:)?//[^"]*"' --include='*.html' . \
  | grep -vE 'rel="(canonical|alternate|me|author)"'

# no infrastructure leakage
grep -rniE '(ssh://|[0-9]{1,3}(\.[0-9]{1,3}){3}|api[_-]?key|secret|bearer |infura|alchemy)' \
  --include='*.html' --include='*.css' --include='*.md' .
```

Both must return nothing.
