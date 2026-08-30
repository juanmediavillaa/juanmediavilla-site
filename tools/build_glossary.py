#!/usr/bin/env python3
"""Build /glossary from a single term list, and verify every anchor is real.

The glossary is generated rather than hand-written so that the inline <dfn>
links scattered across the site can be checked against one authoritative set of
anchors. `--check` fails if any page links to a glossary anchor that does not
exist, or if a term is defined here but never used anywhere.

Standard library only. Run:  python3 tools/build_glossary.py [--check]
"""

from __future__ import annotations

import argparse
import html
import pathlib
import re
import sys

SITE = pathlib.Path(__file__).resolve().parent.parent
OUT = SITE / "glossary" / "index.html"

# The favicon is an inline data: URI, so it costs no request and matches the
# hand-written pages exactly. Keep it identical to the one in those pages.
ICON = ("data:image/svg+xml,%3Csvg%20xmlns='http://www.w3.org/2000/svg'%20viewBox='0%200%2064%2064'"
        "%3E%3Crect%20width='64'%20height='64'%20rx='13'%20fill='%234F46E5'/%3E%3Ctext%20x='32'%20"
        "y='45'%20font-family='Helvetica,Arial,sans-serif'%20font-size='33'%20font-weight='700'%20"
        "fill='%23ffffff'%20text-anchor='middle'%3EJM%3C/text%3E%3C/svg%3E")

# (slug, term, plain definition, worked example from my own results or None)
TERMS: list[tuple[str, str, str, str | None]] = [
    ("bootstrap", "Bootstrap (and why “clustered”)",
     "A way of asking how much an answer wobbles. You resample your own data thousands of times, "
     "recompute the result each time, and look at the spread. <b>Clustered</b> means resampling "
     "whole markets rather than individual trades, because two trades in the same market are not "
     "independent of each other. Treating them as independent would make a result look far more "
     "certain than it is.",
     "The strategy results use 2,000 clustered resamples with the market as the unit."),

    ("credible-interval", "Credible interval",
     "The range a true value plausibly sits in. It is an honesty device: it says how precise the "
     "estimate is <em>not</em>. Read one out loud rather than skipping it — “[3,256, 23,292]” "
     "means somewhere between about three thousand and twenty-three thousand, and no more precise "
     "than that.",
     None),

    ("dwell-time", "Dwell time",
     "How long the market stays in one mode before switching to the other.",
     "About 37 minutes in the quiet mode, about 8 minutes in the busy one."),

    ("friedman-test", "Friedman test",
     "A way of comparing several methods across many test cases at once, while allowing for the "
     "fact that some test cases are simply harder than others. It answers “is any of these "
     "genuinely better?” rather than “which scored highest?”.",
     "Across 22 people, six activity-recognition models gave p = 0.296 — the ranking between them "
     "is indistinguishable from noise."),

    ("hazard-rate", "Hazard rate",
     "The chance that something ends in the next minute, given that it has not ended yet. A rising "
     "hazard means the longer it has run, the sooner it will stop. A falling hazard means the "
     "opposite.",
     "Mine falls, from 0.325 to 0.167 per minute. The longer a burst of activity has already "
     "lasted, the more likely it is to keep going. Young bursts die young."),

    ("held-out", "Held out (out-of-sample)",
     "Tested on data the model never saw while it was being built. A model checked against the "
     "data it was fitted to will always look good; only held-out results tell you anything.",
     None),

    ("hawkes", "Hawkes process (self-exciting)",
     "A model where every event makes the next one more likely for a while — earthquakes and "
     "aftershocks. Nothing hidden is driving it. The activity is its own cause.",
     "The central question of my thesis was whether the market has a hidden mood that turns busy "
     "before the prices move, or whether price moves simply cause more price moves. The answer "
     "was the second."),

    ("isotonic-calibration", "Isotonic calibration",
     "Adjusting a model so its confidence means what it says: when it claims 70% confidence it is "
     "right about 70% of the time. A model can rank things well and still be badly calibrated.",
     None),

    ("lambda", "λ (lambda) — the rate",
     "How often something happens, in events per minute. Always readable as a waiting time: a rate "
     "of 1 per minute is one event every 60 seconds.",
     "The quiet mode runs at 0.041 moves per minute — one price move about every 25 minutes. The "
     "busy mode runs at 1.141 — one about every 53 seconds."),

    ("leave-one-out", "Leave-one-out",
     "Train on everything except one case, test on the case you left out, then repeat for every "
     "case in turn. Nothing is ever tested on itself.",
     "For the wearable-sensor work the unit left out is a person, which makes the question “does "
     "this work on someone it has never seen?” — the only question that matters for a product. "
     "For the market work the unit is a market."),

    ("macro-f1", "Macro-F1",
     "An accuracy score that treats a rare category as just as important as a common one. It stops "
     "a model scoring well by quietly ignoring everything unusual.",
     "It is the headline number in my BSc thesis, where six models scored between 0.843 and 0.880."),

    ("mmpp", "MMPP (Markov-modulated Poisson process)",
     "A model in which the market flips between a quiet mode and a busy mode, and you cannot see "
     "which mode it is in. You only see the price moves, and have to infer the mode from them — "
     "like working out whether a room is in a meeting or on a coffee break by listening through "
     "the door.",
     "Mine recovered a real quiet/busy split. It just could not use it to predict anything."),

    ("nats", "Nats (log-evidence)",
     "A unit of how unsurprised a model was by data it had never seen. Higher is better. The "
     "absolute number means little; the comparison between two models on the same data is the "
     "point.",
     "Partial pooling improved this on all 34 of 34 markets, by a total of 11,400 nats."),

    ("nav", "NAV and unitization",
     "A fund’s total value, divided into units — like shares in a fund. Put money in and you are "
     "issued units at today’s price; take money out and units are redeemed at today’s price. "
     "Everything else in a fund-accounting system exists to keep that arithmetic exactly right.",
     None),

    ("order-book", "Order book, and L2 depth",
     "The list of buy and sell offers resting at each price, waiting to be filled. <b>L2 depth</b> "
     "is how much is stacked up at each level. It says where the pressure is, which a single "
     "quoted price does not.",
     "My historical data does not contain it. One strategy needed it, so it refused to run rather "
     "than substitute a rough stand-in — which is why its result is “not applicable” instead of a "
     "number."),

    ("p-value", "p-value",
     "If there were genuinely no effect at all, how often would pure luck alone produce a result "
     "at least this good? A small p-value means luck is an unlikely explanation. A large one means "
     "there is nothing here.",
     "My strategies came out at p = 0.498, 0.601 and 0.613. The first is a coin flip; none is "
     "evidence of anything."),

    ("partial-pooling", "Partial pooling (hierarchical model)",
     "Letting each market learn from all the other markets instead of being estimated alone. A "
     "market with barely any data borrows the shape of the typical market, so its estimate is "
     "sensible rather than wild. See also <a href=\"#shrinkage\">shrinkage</a>.",
     "It improved held-out prediction on every one of 34 markets."),

    ("point-process", "Point process",
     "The branch of maths for “when do things happen in time” — earthquakes, buses, price moves. "
     "You model the timing of events rather than their size.",
     None),

    ("poisson", "Poisson process",
     "The simplest point process: events arrive at random, at a steady average rate, and each one "
     "is independent of the last. It is the baseline that more interesting models have to beat.",
     None),

    ("pre-registration", "Pre-registration",
     "Writing down exactly what you are going to test, and what would count as success, "
     "<em>before</em> you look at the answer — and committing it to version control so the "
     "timestamp proves the order. It is what stops you moving the goalposts after seeing the "
     "result, because moving them afterwards would be visible in the history.",
     "My thesis carries 14 pre-registered components. It is the reason I can report that my own "
     "primary test failed rather than quietly re-cutting the measurement until something passed."),

    ("prediction-market", "Prediction market",
     "A market where you buy a contract that pays $1 if some event happens and nothing if it does "
     "not. A contract trading at 63¢ means the crowd collectively thinks there is roughly a 63% "
     "chance. The price is the forecast.",
     None),

    ("repricing", "Repricing event",
     "A moment when the market’s price actually moves. The raw material of this whole project is "
     "not what the price is, but when it changes.",
     None),

    ("self-supervised", "Self-supervised learning",
     "Let a model learn the structure of a mountain of unlabelled data first, then fine-tune it on "
     "the small labelled set you actually have. Labels are expensive; raw data usually is not.",
     "Three of the six models I benchmarked work this way."),

    ("shrinkage", "Shrinkage",
     "How hard a <a href=\"#partial-pooling\">pooled model</a> pulls a noisy estimate toward the "
     "group average. Estimates built on very little data should be pulled hard; estimates built on "
     "a lot should barely move.",
     "Mine pulls the data-poor markets 40.5 times harder than the data-rich ones, which is exactly "
     "the behaviour you want."),

    ("truncation", "Truncation artifact",
     "A measurement error caused by which cases you were able to see in the first place. If you "
     "only survey people who have already been at a party for twenty minutes, you will conclude "
     "that nobody ever leaves early — not because it is true, but because the early leavers were "
     "never in your sample.",
     "This is exactly what happened to me. A model said bursts of activity get more likely to end "
     "as they age. It was an artifact of only counting bursts above a minimum length, so I "
     "rejected it and rebuilt the result without that floor."),

    ("walk-forward", "Walk-forward testing",
     "Only ever train on the past and test on the future, stepping forward through time. It is the "
     "honest way to test a trading idea, because it never lets the model see information that "
     "would not have existed yet.",
     None),

    ("weibull", "Weibull",
     "A standard mathematical shape for how the risk of something ending changes as it gets older. "
     "Its shape parameter says whether that risk rises or falls with age.",
     "Mine came out saying the risk rises. That was a "
     "<a href=\"#truncation\">truncation artifact</a>, and the corrected result says the opposite."),

    ("xgboost", "XGBoost",
     "A pile of simple decision rules, each one built to correct the mistakes of the ones before "
     "it. Well understood, unfashionable, and often extremely hard to beat.",
     "In my benchmark it was statistically tied with a transformer that took eighteen times longer "
     "to train — about 23 minutes against about 7 hours."),

    ("average-precision", "Average precision",
     "A score for how well a model <em>ranks</em> rare events. Sort everything by the model's "
     "confidence, walk down the list, and at each step ask what fraction of what you have flagged "
     "so far was real. Average precision is the area under the curve that traces. A model that "
     "ranks at random scores the base rate itself, so the base rate is the number to compare "
     "against. It is blind to the probabilities: a model that is right about the order but wrong "
     "about every number scores identically to a perfectly calibrated one.",
     "On the second synthetic bed the best admissible model scored 0.3971 against a base rate of "
     "0.0206 — ranking fraud about nineteen times better than chance."),

    ("target-leakage", "Target leakage",
     "Information about the answer smuggled into the inputs. A column counts as leakage when its "
     "value did not exist yet at the moment the prediction is for — it is a fact about what "
     "happened next. A model using one scores brilliantly and is worth nothing, because at the "
     "moment a real decision has to be made the column is blank.",
     "A settlement column planted in a synthetic bed was worth +0.2231 average precision on its "
     "own — more than every improvement that project's whole search found, added together."),
]


def render() -> str:
    entries, letters = [], []
    for slug, term, plain, mine in sorted(TERMS, key=lambda t: t[1].lower()):
        first = term[0].upper()
        if first not in letters:
            letters.append(first)
        mine_html = f'\n      <p class="mine">{mine}</p>' if mine else ""
        entries.append(
            f'    <div class="gterm" id="{slug}">\n'
            f"      <h2>{term}</h2>\n"
            f"      <p>{plain}</p>{mine_html}\n"
            f"    </div>"
        )
    nav = "".join(f'<li><a href="#{s}">{html.escape(t)}</a></li>'
                  for s, t, _p, _m in sorted(TERMS, key=lambda t: t[1].lower()))
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Glossary — Juan Mediavilla</title>
<meta name="description" content="Every technical term used on this site, defined in plain words, with the number from my own work as the example.">
<link rel="canonical" href="https://juanmediavilla.com/glossary/">
<script>try{{var t=localStorage.getItem('theme');if(t&&t!=='system')document.documentElement.setAttribute('data-theme',t)}}catch(e){{}}</script>
<link rel="stylesheet" href="../style.css">
<link rel="icon" href="{ICON}">
</head>
<body>
<a class="skip" href="#main">Skip to content</a>

<nav class="nav" aria-label="Primary">
  <div class="wrap">
    <a class="nav__home" href="../index.html">Juan Mediavilla</a>
    <a href="../projects/index.html">Projects</a>
    <a href="../research/index.html">Research</a>
    <a href="../notes/index.html">Notes</a>
    <a href="../how-i-work/index.html">How I Work</a>
    <a href="../about/index.html">About</a>
    <span data-theme-slot></span>
  </div>
</nav>

<main id="main">
  <header class="head">
    <div class="wrap">
      <h1>Glossary</h1>
      <p class="standfirst">
        Every technical term this site uses, in plain words. Where a term has a number attached to
        it in my own work, that number is the example.
      </p>
      <ul class="gloss-nav">{nav}</ul>
    </div>
  </header>

  <div class="wrap">
{chr(10).join(entries)}
  </div>
</main>

<footer class="foot">
  <div class="wrap">
    <p>Juan Mediavilla · London · <a href="../index.html">Home</a> · <a href="../projects/index.html">Projects</a> · <a href="../research/index.html">Research</a> · <a href="../notes/index.html">Notes</a> · <a href="../how-i-work/index.html">How I Work</a> · <a href="../about/index.html">About</a> · <a href="../cv/index.html">CV</a></p>
  </div>
</footer>

<script src="../app.js"></script>
</body>
</html>
"""


def check() -> int:
    slugs = {t[0] for t in TERMS}
    problems, used = [], set()
    for page in sorted(SITE.rglob("*.html")):
        if page == OUT:
            continue
        for m in re.finditer(r'href="[^"]*glossary/index\.html#([\w-]+)"', page.read_text(encoding='utf-8')):
            used.add(m.group(1))
            if m.group(1) not in slugs:
                problems.append(f"{page.relative_to(SITE)} links to missing anchor #{m.group(1)}")
    for orphan in sorted(slugs - used):
        problems.append(f"term '{orphan}' is defined but linked from no page")
    for p in problems:
        print(f"  ! {p}", file=sys.stderr)
    print(f"  {len(TERMS)} terms, {len(used)} distinct anchors linked, {len(problems)} problem(s)")
    return 1 if problems else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(), encoding='utf-8', newline='\n')
    print(f"  wrote {OUT.relative_to(SITE)} ({len(render()):,} bytes, {len(TERMS)} terms)")
    return check() if args.check else 0


if __name__ == "__main__":
    sys.exit(main())
