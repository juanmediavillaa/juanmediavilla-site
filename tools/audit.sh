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
if grep -rnoE '<(link|script|img|iframe)[^>]*(src|href)="(https?:)?//[^"]*"' --include='*.html' .; then
  FAIL=1; else echo "  none"; fi

note "no infrastructure, secrets, identifiers or student data"
if grep -rniE '0x[0-9a-f]{6,}|s3565122|ssh://|[0-9]{1,3}(\.[0-9]{1,3}){3}|api[_-]?key|bearer ' \
     --include='*.html' --include='*.css' --include='*.csv' .; then
  FAIL=1; else echo "  none"; fi

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
    for m in re.finditer(r'<(h[123])[^>]*>(.*?)</\1>|<p class="card__stat">(.*?)</p>|<p class="oneline">(.*?)</p>', b, re.S):
        s = html.unescape(re.sub(r'<[^>]+>','',next(g for g in m.groups()[1:] if g))).strip()
        if NULL.search(s): print(f"  {f}: {s[:70]}"); bad += 1
print("  none" if not bad else f"  {bad} found")
sys.exit(1 if bad else 0)
PY

note "budgets"
python3 - <<'PY' || FAIL=1
import pathlib, re, sys
css = pathlib.Path('style.css').stat().st_size
js  = pathlib.Path('app.js').stat().st_size
figs = {p.name: p.stat().st_size for p in pathlib.Path('figures').glob('*.svg')}
bad = 0
for f in sorted(pathlib.Path('.').glob('**/index.html')):
    if 'pre-registration' in str(f): continue
    s = f.read_text(); h = len(s.encode())
    used = sum(figs.get(m+'.svg', 0) for m in re.findall(r'figures/([\w-]+)\.svg', s))
    used += sum(pathlib.Path('assets', m).stat().st_size for m in re.findall(r'assets/([\w.-]+)', s))
    markup, total = h + css, h + css + used + js
    cap = 400*1024 if str(f) == 'index.html' else 600*1024
    flag = ''
    if markup > 90*1024: flag += ' MARKUP OVER'; bad += 1
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
