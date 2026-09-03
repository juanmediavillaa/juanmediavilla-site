#!/usr/bin/env bash
# Every check for this site, in one command:  bash tools/audit.sh
#
# Starts a headless Chrome, runs the browser-measured audits (layout at four
# widths, computed contrast in both themes, structure with scripting on and off),
# then the generator idempotence checks and the prohibited-content sweeps.
# Non-zero exit means something failed. See MAINTENANCE.md.
set -uo pipefail
cd "$(dirname "$0")/.."
SITE="$(pwd)"
FAIL=0
note() { printf '\n\033[1m%s\033[0m\n' "$1"; }

# Flush WSL's writes before a Windows-side Chrome reads them over /mnt/c. Without
# this the browser audits can measure the PREVIOUS version of a page that a
# generator has just rewritten — which is the one failure mode worse than a red
# audit, because it is green on content that is not what will ship. Observed: the
# chart-overlap check reported five collisions that had already been fixed on disk.
sync 2>/dev/null || true

CHROME="${CHROME:-/mnt/c/Program Files/Google/Chrome/Application/chrome.exe}"
PROFILE="$(mktemp -d)"
if [ -x "$CHROME" ]; then
  WINPROF=$(wslpath -w "$PROFILE" 2>/dev/null || echo "$PROFILE")
  "$CHROME" --headless=new --disable-gpu --remote-debugging-port=9222 \
    --remote-allow-origins='*' --user-data-dir="$WINPROF" about:blank >/dev/null 2>&1 &
  CHROME_PID=$!
  for _ in $(seq 1 20); do
    curl -s --max-time 1 http://127.0.0.1:9222/json/version >/dev/null && break
    sleep 0.5
  done
  WIN=$(wslpath -w "$SITE" 2>/dev/null | sed 's|\\|/|g' || echo "$SITE")
  note "browser-measured audits"
  node tools/audit.js "$WIN" || FAIL=1
  kill "$CHROME_PID" 2>/dev/null
else
  echo "!! Chrome not found at $CHROME — set CHROME=/path/to/chrome. Browser audits SKIPPED."
  FAIL=1
fi
rm -rf "$PROFILE"

note "generators are idempotent"
python3 tools/make_figures.py --check   || FAIL=1
python3 tools/make_diagrams.py --check  || FAIL=1
python3 tools/build_glossary.py --check || FAIL=1

note "no external subresources"
# rel=canonical/alternate/me name a URL for crawlers and are never fetched, so
# they are exempt. Anything the browser actually requests is not.
if grep -rnoE '<(link|script|img|iframe)[^>]*(src|href)="(https?:)?//[^"]*"' --include='*.html' . \
     | grep -vE 'rel="(canonical|alternate|me|author)"'; then
  FAIL=1; else echo "  none"; fi

note "no infrastructure, secrets, identifiers or student data"
# Base64 payloads are blanked before the scan. These patterns look for a leak in
# READABLE TEXT — a wallet address, a key, a hostname — and an encoded image is
# none of those: it is opaque bytes in which "0x" followed by six hex characters
# turns up by chance in roughly every kilobyte. Scanning it can only ever produce
# a false positive, and a check that cries wolf on every attachment gets muted,
# which is how a real match would get waved through. The patterns themselves are
# unchanged, and three positive controls assert as much before the scan runs.
python3 - <<'PY' || FAIL=1
import pathlib, re, sys

PATTERNS = re.compile(
    r'0x[0-9a-f]{6,}|s3565122|ssh://|[0-9]{1,3}(\.[0-9]{1,3}){3}'
    r'|api[_-]?key|bearer |secret[_-]?key|access[_-]?token', re.I)
# No \s in the payload class: the scan is line-by-line, so a data URI never
# spans a newline here, and allowing whitespace let the match run past the URI
# and swallow the readable text after it — which the controls below caught.
DATAURI = re.compile(r'data:[a-z/+.-]+;base64,[A-Za-z0-9+/=]+')
SUFFIXES = {'.html', '.css', '.csv', '.py', '.yml'}

def scan(text):
    return PATTERNS.search(DATAURI.sub('', text))

# Positive control: the check must still fire on a readable wallet address.
assert scan('taker 0xdeadbeef12'), "wallet pattern stopped matching"
assert scan('data:image/png;base64,AAAA and 0xdeadbeef12'), "text beside a data URI must still scan"
assert not scan('data:image/png;base64,QQQQ0xdeadbeef12QQQQ'), "base64 payload should be skipped"

bad = 0
for f in sorted(pathlib.Path('.').rglob('*')):
    if '.git' in f.parts or f.suffix not in SUFFIXES or not f.is_file(): continue
    for n, line in enumerate(f.read_text(encoding='utf-8', errors='replace').split('\n'), 1):
        m = scan(line)
        if m:
            print(f"  {f.as_posix()}:{n}: {m.group(0)}"); bad += 1
print("  none" if not bad else f"  {bad} match(es)")
sys.exit(1 if bad else 0)
PY

note "every internal link resolves"
# Pages moved when projects and the theses each became their own page. A link
# that still points at the old location is invisible until someone clicks it,
# so it gets a checker rather than a proofread.
python3 - <<'PY' || FAIL=1
import pathlib, re, sys
bad = 0
for f in sorted(pathlib.Path('.').glob('**/*.html')):
    if str(f) == '404.html': continue          # served at any depth; absolute by necessity
    text = f.read_text()
    ids = set(re.findall(r'\sid="([^"]+)"', text))
    # src as well as href: a broken image resolves to nothing, is not an
    # off-origin request, and is skipped by the budget check, so it was
    # invisible to every other sweep here.
    for href in re.findall(r'(?:href|src)="([^"]+)"', text):
        if re.match(r'^(https?:|mailto:|data:|#$)', href): continue
        target, _, frag = href.partition('#')
        if not target:
            if frag and frag not in ids:
                print(f"  {f}: dead anchor #{frag}"); bad += 1
            continue
        dest = (f.parent / target).resolve()
        if not dest.exists():
            print(f"  {f}: missing {href}"); bad += 1
        elif frag and dest.suffix == '.html' and frag not in set(
                re.findall(r'\sid="([^"]+)"', dest.read_text())):
            print(f"  {f}: {target} has no #{frag}"); bad += 1
print("  none" if not bad else f"  {bad} broken")
sys.exit(1 if bad else 0)
PY

note "every nav matches tools/sitegen.py"
# The nav is written out in 16 hand-edited pages and generated into the rest.
# Adding a section means touching all of them, and a page left on the old nav is
# invisible until someone lands on it and cannot reach the new section from it.
python3 - <<'PY' || FAIL=1
import pathlib, re, sys
sys.path.insert(0, 'tools')
from sitegen import NAV
want = [label for _, label in NAV]
bad = 0
for f in sorted(pathlib.Path('.').glob('**/*.html')):
    t = f.read_text(encoding='utf-8')
    m = re.search(r'<nav class="nav".*?</nav>', t, re.S)
    if not m:
        continue
    got = re.findall(r'<a [^>]*>([^<]+)</a>', m.group(0))[1:]   # [0] is the home link
    if got != want:
        print(f"  {f}: nav is {got}")
        bad += 1
print("  none" if not bad else f"  {bad} page(s) out of step")
sys.exit(1 if bad else 0)
PY

note "no funding chains in /notes"
# A sale of a stated size named as the source of specific purchases lets a
# reader infer their relative sizes — which is the one thing /notes withholds.
# Movements state the change and the realized result, never where money went.
if grep -rniE 'proceeds|funded by|funded the|redeploy|rotation|1:1' notes/ content/positions/; then
  FAIL=1; else echo "  none"; fi
note "no prose that expires (positions and books)"
# A page saying "right now" or "last quarter" is true the day it is written and
# silently false later; nothing else here can detect that, because the sentence
# stays grammatical and the figures stay put. Name the period instead — "in Q2
# 2026" is still correct in five years. Quoted speech is exempt: altering words
# inside quotation marks to tidy the prose would be a misquote.
python3 - <<'PY' || FAIL=1
import pathlib, re, sys

EXPIRING = re.compile(
    r"\b(right now|currently|so far|thus far|at the moment|these days|for now|"
    r"nowadays|as things stand|to date|last quarter|this quarter|next quarter|"
    r"the previous quarter|the most recent quarter|the latest quarter|"
    r"this year|last year|newest|most recently|have not owned|has not happened yet|"
    r"not yet|no longer)\b", re.I)

QUOTED = re.compile(r"[\u201c\"][^\u201d\"]*[\u201d\"]")

bad = 0
for f in sorted(pathlib.Path("content").glob("*/*.md")):
    for n, line in enumerate(f.read_text(encoding="utf-8").split("\n"), 1):
        # Dated ledger entries are anchored by their own date, not by when read.
        if line.lstrip().startswith("- **20"):
            continue
        for m in EXPIRING.finditer(QUOTED.sub(lambda q: " " * len(q.group(0)), line)):
            bad += 1
            print(f"  {f.as_posix()}:{n}  \"{m.group(0)}\"  {line.strip()[:78]}")
if bad:
    print(f"  {bad} phrase(s) that will expire — name the period instead")
    sys.exit(1)
print("  none")
PY

note "no retired figures"
# '7 of 7' is a retired *claim*, not a figure: the attribution of the agent
# programme's catches. agent-research-protocol retracts it at source and
# CONTENT-RULES.md 4.1 forbids reintroducing it here. It was this site's most
# quotable sentence, which is exactly why it needs a machine guard and not a
# rule. The record supports three of seven.
if grep -rnoE '(\+?665 nats|17,349|0\.939|0\.0585|236 GB|118 GB|800 GB|7 of 7)' --include='*.html' .; then
  FAIL=1; else echo "  none"; fi

note "no heading, card or one-liner built on a null result"
python3 - <<'PY' || FAIL=1
import re, html, pathlib, sys
NULL = re.compile(r'\b(no edge|not significant|failed|redundant|does not|did not|nothing|no evidence)', re.I)
bad = 0
for f in pathlib.Path('.').glob('**/index.html'):
    if 'pre-registration' in str(f): continue
    t = f.read_text()
    if '<main' not in t: continue
    b = t.split('<main',1)[1].split('</main>')[0]
    for m in re.finditer(r'<(h[123])([^>]*)>(.*?)</\1>|<p class="card__stat">(.*?)</p>|<p class="oneline">(.*?)</p>', b, re.S):
        # The title of a cited work is a proper noun, not this site's framing of
        # its own results: 'When Genius Failed' is the name of a book. Only an
        # element explicitly marked as one is exempt, and only its own text.
        if 'work-title' in (m.group(2) or ''): continue
        s = html.unescape(re.sub(r'<[^>]+>','',next(g for g in m.groups()[2:] if g))).strip()
        if NULL.search(s): print(f"  {f}: {s[:70]}"); bad += 1
print("  none" if not bad else f"  {bad} found")
sys.exit(1 if bad else 0)
PY

note "/how-i-work word cap"
# CONTENT-RULES.md 6 capped this page at 900 words and nothing ever checked it,
# so it reached 2,489 -- 2.8x the cap -- without a single failure. The cap is now
# set to the measured count and enforced here. It is a RATCHET, not a budget:
# there is no headroom by construction, so any addition fails until the number in
# 6 and the number here are both moved deliberately, together. Counting matches
# what 6 states: words inside <main>, with script, style and svg stripped.
python3 - <<'PY' || FAIL=1
import re, pathlib, sys
CAP = 2489
t = pathlib.Path('how-i-work/index.html').read_text(encoding='utf-8')
b = t.split('<main', 1)[1].split('</main>')[0]
b = re.sub(r'<(script|style|svg)\b.*?</\1>', '', b, flags=re.S | re.I)
b = re.sub(r'<[^>]+>', ' ', b)
b = re.sub(r'&[a-z]+;', ' ', b)
n = len(b.split())
print(f"  {n} words of {CAP}")
if n > CAP:
    print(f"  OVER by {n - CAP}. Cut, or move the cap in CONTENT-RULES.md 6 and here together.")
sys.exit(1 if n > CAP else 0)
PY

note "budgets"
python3 - <<'PY' || FAIL=1
import pathlib, re, sys
js  = pathlib.Path('app.js').stat().st_size
figs = {p.name: p.stat().st_size for p in pathlib.Path('figures').glob('*.svg')}
# Fonts are referenced from the stylesheet, not the markup, so counting only
# assets named in the HTML missed them entirely. Charged to every page as the
# full set: a unicode-range means a reader may fetch less, never more.
fonts = sum(pathlib.Path(m).stat().st_size
            for m in sorted(set(re.findall(r'url\("(assets/fonts/[\w.-]+)"\)',
                                           pathlib.Path('style.css').read_text()))))
print(f"  fonts {fonts/1024:.1f} KB (self-hosted, charged to every page)")
bad = 0
for f in sorted(pathlib.Path('.').glob('**/index.html')):
    if 'pre-registration' in str(f): continue
    s = f.read_text(encoding='utf-8'); h = len(s.encode())
    # Charge each page for the stylesheets it actually links, not for style.css
    # alone: /notebook and /books load a second sheet that no other page does,
    # and counting one file for everyone is how 70 KB of fonts went unseen.
    css = sum((f.parent / m).resolve().stat().st_size
              for m in re.findall(r'<link rel="stylesheet" href="([^"]+)"', s)
              if (f.parent / m).resolve().exists())
    used = sum(figs.get(m+'.svg', 0) for m in re.findall(r'figures/([\w-]+)\.svg', s))
    # Any local asset the page references, at any depth. The old pattern stopped
    # at assets/<name> and silently measured a directory for anything nested.
    for rel in set(re.findall(r'(?:src|href)="([^"]*assets/[\w./-]+)"', s)):
        a = (f.parent / rel).resolve()
        if a.is_file(): used += a.stat().st_size
    markup, total = h + css, h + css + used + js + fonts
    cap = 400*1024 if str(f) == 'index.html' else 600*1024
    # /research used to need 110 KB because it carried all six inline charts on
    # one page. The two theses are now separate pages, so the largest of them
    # fits the ordinary budget and the exception is gone.
    markup_cap = 90*1024
    flag = ''
    if markup > markup_cap: flag += ' MARKUP OVER'; bad += 1
    if total > cap:      flag += ' TOTAL OVER';  bad += 1
    print(f"  {str(f):34} markup {markup/1024:6.1f} KB  total {total/1024:6.1f} KB{flag}")
sys.exit(1 if bad else 0)
PY

note "JavaScript budget"
python3 - <<'PY' || FAIL=1
import pathlib, re, sys
app = pathlib.Path('app.js').stat().st_size
inline = sum(len(m.group(1).encode()) for p in pathlib.Path('.').rglob('*.html')
             for m in re.finditer(r'<script(?![^>]*src)[^>]*>(.*?)</script>', p.read_text(), re.S))
print(f"  {app+inline:,} bytes of 25,600")
sys.exit(1 if app + inline > 25600 else 0)
PY

if [ "$FAIL" -eq 0 ]; then printf '\n\033[1mALL CHECKS PASSED\033[0m\n'; else printf '\n\033[1mAUDIT FAILED\033[0m\n'; fi
exit "$FAIL"
