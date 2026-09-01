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

## The 900-word cap on `/how-i-work`

**`CONTENT-RULES.md` §6 caps that page at 900 words. As of 1 September 2026 it holds 2,488 words
inside `<main>` — roughly 2.8× the cap — and `tools/audit.sh` does not check it.** Nothing is
failing, because nothing is looking. The cap has been exceeded for long enough that no single edit
can be blamed for it; the September 2026 pass that repointed the repository links added about 87
words to an already-breached page without anything objecting.

Reproduce it:

```sh
python3 - <<'PY'
import re
h = open('how-i-work/index.html', encoding='utf-8').read()
t = re.search(r'<main.*?</main>', h, re.S).group(0)
t = re.sub(r'<(script|style|svg)\b.*?</\1>', '', t, flags=re.S | re.I)
print(len(re.sub(r'&[a-z]+;', ' ', re.sub(r'<[^>]+>', ' ', t)).split()))
PY
```

**The problem is not the number, it is the asymmetry.** Every other hard rule in §4 and §7 has a
check behind it: external subresources, infrastructure leakage, retired figures, null results in
headings, expiring prose, byte budgets. This one is prose alone, so it fails silently and
permanently, and the page grows every time it is edited in good faith. §6 itself is the rule most
likely to be read as advisory for exactly that reason — which is the failure mode
`agent-research-protocol` labels `[UNENFORCED]` and requires a rule to declare about itself.

### Options, none chosen

1. **Enforce it and cut the page to 900.** Honest, and expensive: the page carries the vault
   boundary, the contract, the caught-error list and the site case study. Something load-bearing
   goes, and §6 protects two catches by name as non-negotiable.
2. **Enforce it at the real number and say why it moved.** Set the cap where the page actually
   sits, deliberately, with the reason written down. Cheap, and it concedes that the original 900
   was a guess — which it may have been.
3. **Count only what the cap was for.** The cap exists to stop the page becoming an essay. Counting
   `<main>` charges it for headings, figure captions and the artifact blocks §6 requires. A count
   over body prose only would measure the thing being limited.
4. **Split the page.** `CONTENT-RULES.md` §16 and `MAINTENANCE.md` §7 both say split rather than
   raise a cap, and that is what removed `/research`'s 110 KB exception. The case study and the
   caught-error list are separable from the method.
5. **Relabel §6's cap as advisory.** Recorded for completeness, and the weakest: it converts a
   breached hard rule into a satisfied soft one and changes nothing about the page.

Whichever is picked, the check goes into `tools/audit.sh` in the same change. A cap chosen and
still unenforced is the state this entry exists to end.

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

**The next substantive edit to this page has to split it, not shave it.** `CONTENT-RULES.md` §16 is
explicit that a page approaching the cap gets split rather than granted an exception — that is what
removed `/research`'s 110 KB allowance once the two theses became separate pages. The same seam is
available here: the finding and the two synthetic beds are the argument, while the pre-registered
predictions, the permission-route audit and the closing limitations read as a separable second page.

Recorded now because the failure mode is predictable: the next editor finds 140 bytes, shaves a
sentence to fit, and the page loses content to a byte budget instead of to a decision. Reproduce
with the `budgets` block of `bash tools/audit.sh`.
