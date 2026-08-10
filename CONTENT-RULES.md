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

**The corpus figure is `~800 GB archived as of August 2026`, and it is self-reported.** Unlike the
git-derived counts it cannot be verified from a committed file, so it always carries the as-of
date. Keep the two quantities distinct: the **250 GB server working set** that fills and is
periodically offloaded, and the **archived total on cloud storage**. Sanity-checked against the
recorded 12.8 GiB/day: over the 83-day window the ceiling is ~1,141 GB, so 800 GB implies a 9.0
GiB/day realised average (70% of peak), which the disclosed outage and the offload cycle explain.

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

1. **No repository links of any kind.** All source repositories are private and are not linked.
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
9. **No third-party network requests.** No CDN, no web fonts, no analytics, no external images,
   no embeds. Fonts are system stacks; the only subresource is the relative `style.css`.
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

JS is permitted but currently **unused: 0 of the 3 KB budget**. SVG `<title>` gives a native hover
readout at zero bytes, so adding script to duplicate it would be worse. If that changes:

- Hard ceiling **3 KB total across the whole site**. No library, no build step, no npm.
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
  never cycled or reordered.
- **Slot 4 (yellow) measures 2.82:1 in light** — anything drawn in it needs a direct label or a
  table. **Green and pink sit at ΔE 7.7 for deuteranopia in dark** — any chart using both needs a
  second encoding. Scatter and small-multiple charts cap at the first three slots.
- `--muted` is a **graphical** token (gridlines, axis rules) at 3:1. It measures 3.96:1 in light,
  so it never carries text; chart label text uses `--ink-2`.
- One y-axis per chart. Text wears text tokens, never a series colour.
- **JavaScript ceiling: 25 KB site-wide** (currently ~7.8 KB). No framework, no build step, no
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
- The institution card keeps a **fixed light ground in both themes**, because the measured brand
  colours fall to 1.28:1 and 1.90:1 on the dark plane. On the card they measure 14.09:1 (UCL
  dark), 4.54:1 (UCL bright) and 9.53:1 (Leiden).

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

## 15. Checks before publishing

```sh
# no external subresources anywhere
grep -rnoE '<(link|script|img|iframe)[^>]*(src|href)="(https?:)?//[^"]*"' --include='*.html' .

# no infrastructure leakage
grep -rniE '(ssh://|[0-9]{1,3}(\.[0-9]{1,3}){3}|api[_-]?key|secret|bearer |infura|alchemy)' \
  --include='*.html' --include='*.css' --include='*.md' .
```

Both must return nothing.
