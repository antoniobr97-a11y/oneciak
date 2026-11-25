#!/bin/bash
# Publishes site files from the working branch to main, only after
# tests/check.sh passes, then waits until oneciak.com serves exactly the new
# files and runs the checks there. Only when Antonio has written "pubblica".
# Run: tests/publish.sh "message" file1 [file2 ...]
set -u
cd "$(dirname "$0")/.."
MSG="$1"; shift; FILES=("$@")
BRANCH=claude/website-completion-aesthetics-6wknns
[ "$(git branch --show-current)" = "$BRANCH" ] || { echo "Non sei sul branch di lavoro"; exit 1; }
[ -z "$(git status --porcelain -- "${FILES[@]}")" ] || { echo "Ci sono modifiche non salvate in questi file: salvale prima"; exit 1; }
tests/check.sh || { echo "STOP: i controlli non passano, niente pubblicazione"; exit 1; }
git fetch -q origin main || exit 1
git checkout -q -B main-publish origin/main
git checkout "$BRANCH" -- "${FILES[@]}"
if git diff --cached --quiet origin/main; then echo "STOP: niente da pubblicare (uguale a main)"; git checkout -q "$BRANCH"; exit 1; fi
git diff --cached --stat origin/main
git commit -q -m "$MSG" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01KB7uckaFEVRn4u848AoGXr" || { git checkout -q "$BRANCH"; exit 1; }
for t in 1 2 3 4; do git push -q origin main-publish:main && break; sleep $((t*2)); done
echo "Pubblicato: $(git log -1 --format=%h)"
git checkout -q "$BRANCH"
# the CDN can serve the old file with 200: wait until every published page is
# the new one. Netlify rewrites links ("/privacy.html" becomes '/privacy'),
# so lines holding a link are left out of the comparison.
for f in "${FILES[@]}"; do
  case "$f" in *.html|*.css|*.js) ;; *) continue;; esac
  case "$f" in netlify/*|tests/*) continue;; esac
  url="https://oneciak.com/${f%index.html}"
  for i in $(seq 1 40); do
    if diff -q <(curl -s "$url?x=$i$RANDOM" | grep -v 'href=') <(grep -v 'href=' "$f") >/dev/null; then echo "online: $f"; break; fi
    [ $i -eq 40 ] && { echo "ATTENZIONE: $f non è ancora quello nuovo dopo 6 minuti"; exit 1; }
    sleep 10
  done
done
export NODE_PATH=/opt/node22/lib/node_modules
echo "== prove sul sito vero"
node tests/functions.js https://oneciak.com/ | tail -3
node tests/pages.js https://oneciak.com/ | tail -3
