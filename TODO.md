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
