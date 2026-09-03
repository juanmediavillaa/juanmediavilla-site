# Open items

Things that need a decision later, recorded so the decision is made deliberately rather than
discovered when a check fails. Longer-running items live in `MAINTENANCE.md` §8.

---

## The cover ceiling on `/notes/books/`

**As of 31 August 2026, `/notes/books/index.html` is the heaviest page on the site: 513.9 KB
against the 600 KB total budget.** Cover art is most of it. Nothing is failing; this is a note
about where the next few books put the page.

Reproduce it with `bash tools/audit.sh` (the `budgets` block), or read the parts directly:

| Component | Bytes | Share |
|---|---|---|
| 26 covers in `assets/covers/` | 362,782 | 354.3 KB |
| fonts (charged to every page) | 71,564 | 69.9 KB |
| `style.css` + `sections.css` | 52,555 | 51.3 KB |
| `app.js` | 18,696 | 18.3 KB |
| markup | 20,589 | 20.1 KB |
| **total** | **526,186** | **513.9 KB of 600 KB** |

The audit prints KB as KiB, so the covers read as 354.3 KB there and 363 KB if divided by 1000.
Same 362,782 bytes either way.

**Each new book with a cover costs about 14 KB** — the mean cover is 13,953 bytes, the range 5,884
to 22,501. Headroom is 88,214 bytes, so **roughly six more books** before the page hits its cap. The
markup cap is not the constraint: 71.4 KB against 90 KB, and a card is only a few hundred bytes.

Two facts that bear on any fix:

- **All 26 covers carry `loading="lazy"`.** A reader scrolling part of the shelf fetches fewer than
  26, but the budget check charges the page for every asset it references, by design — the same
  decision that put fonts on the bill after 70 KB of typeface went unseen.
- **A book without a cover is not an error.** `build_books.py` renders a neutral placeholder, and
  `make_covers.py` only fails on an *unmatched* cover file, never on a missing one.

### Options, none chosen

1. **Split the shelf across pages.** `MAINTENANCE.md` §7 and `CONTENT-RULES.md` §16 both say to
   split rather than raise a cap — that is what removed `/research`'s 110 KB exception. By year, by
   verdict, or written-up versus not. Costs a navigation decision and probably a `sortKey` review.
2. **Re-encode the covers.** `make_covers.py` records WebP as considered and rejected: "would save a
   further 65 KB; not worth introducing a second image format to the site for that." That reasoning
   was written when the page had headroom, so it is the assumption to re-examine first, not a
   settled question.
3. **Shrink what is already there.** `WIDTH = 200`, `MAX_HEIGHT = 400`, `QUALITY = 78`. The 200px
   width is sized for 88px on the shelf and 120px on a write-up page at 2x, so dropping it trades
   against retina sharpness rather than being free.
4. **Show covers only on the write-up pages.** Keeps the artwork, moves the weight off the index,
   and changes what the shelf looks like — the covers are most of its character.
5. **Raise the cap.** Recorded for completeness. Both documents argue against it, and the argument
   is about referenced-versus-inlined figures rather than about images, so it would need making
   afresh.

Whichever is picked, `assets/covers/` is generated: `make_covers.py` needs Pillow and is
deliberately outside `tools/audit.sh`, so re-encoding is a by-hand step whose output gets committed.

---

## The 900-word cap on `/how-i-work` — resolved 3 September 2026

**Resolved as option 2 below: the cap is now 2,489 words, and `tools/audit.sh` enforces it.**
Kept here rather than deleted, because the entry records how a hard rule went 2.8× over without one
failure, and that is the part worth not forgetting.

**What it was.** `CONTENT-RULES.md` §6 capped the page at 900 words and nothing checked it, so it
reached 2,489 inside `<main>` — roughly 2.8× the cap. Nothing was failing, because nothing was
looking. No single edit could be blamed: the pass that repointed the repository links added about 87
words to an already-breached page without anything objecting.

**The problem was never the number, it was the asymmetry.** Every other hard rule in §4 and §7 had a
check behind it — external subresources, infrastructure leakage, retired figures, null results in
headings, expiring prose, byte budgets. This one was prose alone, so it failed silently and
permanently, and the page grew every time it was edited in good faith. That is the failure mode
`agent-research-protocol` labels `[UNENFORCED]` and requires a rule to declare about itself.

**What was chosen, and what was not.** Option 2 — enforce it at the real number and say why it
moved. It concedes that 900 was a guess, which nothing in the repository ever justified. The four
rejected options are still live if the page is ever cut: (1) cut to 900, expensive because §6
protects two catches by name; (3) count body prose only, since `<main>` charges the page for
headings and the artifact blocks §6 requires; (4) split it, per §16; (5) relabel the cap advisory,
which would have converted a breached hard rule into a satisfied soft one and changed nothing.

**The cap is a ratchet, not a budget.** It equals the measured count exactly, so there is no
headroom and the next addition fails. Moving it means editing §6 and `CAP` in `tools/audit.sh`
together, deliberately. Lower it freely when the page is cut; raise it only with a reason written
into §6.

Verified by construction rather than by reading: run with `CAP` one below the true count, the check
reports `OVER by 1` and exits non-zero; at the true count it passes.

---

## `/projects/agent-research-programme/` is at its markup cap

**After the 1 September 2026 correction to its headline finding, the page sits at 89.0 KB of the
90 KB markup cap — about 1 KB of headroom.** It is the largest markup on the site, and it was
already at 87.7 KB before that edit; correcting the finding and separating the four-week
measurement window from the four-month span of work took most of what was left, and the edit was
held to the cap by tightening its own new prose rather than by raising it. It stood at 89.9 KB —
roughly 140 bytes clear — until a later decision to keep the retraction in the repository rather
than on the page returned about 900 bytes. **That headroom came back from a content decision that
happened to go that way, not from anything structural**, so the entry stands.

### The trigger, and the seam it fires

**Trigger: the next substantive edit to this page. Not a byte threshold — an intent one.** Anything
that adds a claim, a figure, a section or a paragraph fires it. Fixing a typo, correcting a number
in place, or repointing a link does not. The page currently passes, so nothing fires today; the
point of writing the trigger down is that the *next* editor meets it before they start rather than
after they have written something that will not fit.

**When it fires, split at this seam:**

| stays on `/projects/agent-research-programme/` | moves to a second page |
|---|---|
| the finding — three of seven, the four attributions, ratio-not-a-rate | the two pre-registered predictions and their outcomes |
| the rig, and both synthetic beds | the 18-route permission audit |
| | the closing limitations |

The line is *argument* versus *apparatus*: what the measurement found, against how it was run and
what it could not see. `CONTENT-RULES.md` §16 requires the split rather than an exception, and that
is what removed `/research`'s 110 KB allowance once the two theses became separate pages — the
precedent is the same shape and it worked.

**The seam is recorded, not chosen.** Picking a different one is fine; picking none, and shaving a
sentence to fit instead, is the failure this entry exists to prevent — the page would lose content
to a byte budget rather than to a decision. Reproduce the measurement with the `budgets` block of
`bash tools/audit.sh`.
