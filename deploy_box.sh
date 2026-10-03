#!/usr/bin/env bash
# Box-side refresh: builds feed.json WITH the private fantasy roster (read from files on this box) and pushes it.
# Run every 3h (e.g. via the box scheduler/routine). Roster names never enter the repo; only resulting headlines do.
# The GitHub Action also runs every 3h but has no roster, so it carries over the last roster headlines (<=24h).
set -euo pipefail
D=/workspace/news-widget-deploy
REPO=https://github.com/wghtkbpxwx-a11y/news-widget-feed.git
[ -d "$D/.git" ] || git clone -q "$REPO" "$D"
cd "$D"
git fetch -q origin && git reset -q --hard origin/main
python3 fantasy_players.py            # re-read rosters from /workspace (gitignored output)
python3 build_feed.py --out feed.json
python3 - <<'PY'
import json; f=json.load(open("feed.json"))
assert f["items"] and f["generated"] and "must_know" in f and "my_teams" in f, "bad feed"
PY
git config user.name "feed-bot"; git config user.email "feed-bot@users.noreply.github.com"
git add feed.json
if ! git diff --cached --quiet; then
  git commit -q -m "refresh feed (box, with roster) $(date -u +%FT%TZ)"
  git push -q origin main || { git pull -q --rebase -X theirs origin main && python3 build_feed.py --out feed.json && git add feed.json && git commit -q -m "refresh feed (box, retry)" && git push -q origin main; }
fi
echo "pushed $(git rev-parse --short HEAD)"
