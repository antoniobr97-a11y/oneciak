#!/bin/bash
# Every check, in one command, on the local copy of the repo (its own server,
# started and stopped here). Exit code 0 only if everything passes.
# Run: tests/check.sh            (compares movements with https://oneciak.com/)
#      tests/check.sh --quick    (code only: lint and syntax, a few seconds)
set -u
cd "$(dirname "$0")/.."
LIVE="https://oneciak.com/"
export NODE_PATH=/opt/node22/lib/node_modules
OUT="${OUT:-$(mktemp -d)}"; mkdir -p "$OUT"; export OUT
fail=0
step() { local name="$1"; shift; printf '\n== %s\n' "$name"; local log="$OUT/$(echo "$name" | tr ' /' '__').log"; "$@" >"$log" 2>&1; local rc=$?; tail -n 4 "$log"; if [ $rc -ne 0 ]; then fail=1; echo "   >> NON PASSA (dettagli in $log)"; fi; }

# code: the design rules a machine can read, then syntax (a syntax error turns the whole site off)
step "regole nel codice" node tests/lint.js
python3 - > "$OUT/page.js" <<'PY'
import re
h = open('index.html').read()
print("\n".join(re.findall(r'<script(?![^>]*(?:src|ld\+json))[^>]*>(.*?)</script>', h, re.S)))
PY
step "sintassi della pagina" node --check "$OUT/page.js"
step "sintassi del server" bash -c 'for f in netlify/functions/*.js netlify/functions/_util/*.js tests/*.js; do node --check "$f" || exit 1; done; echo "tutti i file del server si leggono"'
[ "${1:-}" = "--quick" ] && { [ $fail -eq 0 ] && echo "TUTTO A POSTO (solo codice)" || echo "QUALCOSA NON PASSA"; exit $fail; }

# the site in a browser, on a server started here
PORT=8190; python3 -m http.server $PORT --bind 127.0.0.1 >"$OUT/server.log" 2>&1 & SRV=$!
trap 'kill $SRV 2>/dev/null' EXIT; sleep 1
L="http://127.0.0.1:$PORT/"
step "funzioni" node tests/functions.js "$L"
step "pagine" node tests/pages.js "$L"
step "regole di design" node tests/rules.js "$L"
step "pressione dei tasti" node tests/press.js "$L"
step "movimenti rispetto al sito vero" node tests/motion.js "$LIVE" "$L"
step "foto prima e dopo" node tests/shots.js "$LIVE" "$L"

printf '\n'; [ $fail -eq 0 ] && echo "TUTTO A POSTO" || echo "QUALCOSA NON PASSA: non pubblicare"
echo "Dettagli e foto: $OUT"
exit $fail
