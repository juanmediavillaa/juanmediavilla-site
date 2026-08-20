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
if grep -rniE '0x[0-9a-f]{6,}|s3565122|ssh://|[0-9]{1,3}(\.[0-9]{1,3}){3}|api[_-]?key|bearer |secret[_-]?key|access[_-]?token' \
     --include='*.html' --include='*.css' --include='*.csv' --include='*.py' --include='*.yml' --exclude-dir=.git .; then
  FAIL=1; else echo "  none"; fi

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
    for href in re.findall(r'href="([^"]+)"', text):
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

note "no retired figures"
if grep -rnoE '(\+?665 nats|17,349|0\.939|0\.0585|236 GB|118 GB)' --include='*.html' .; then
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
