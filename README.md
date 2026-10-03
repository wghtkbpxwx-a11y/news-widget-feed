# Dave's News + Sports Widget (iPhone, Large)

Free. No accounts, no API keys, public headlines only.

**Pieces**
- `build_feed.py` + `config.json` → builds `feed.json` (≤12 ranked items + score strip)
- GitHub Actions (`.github/workflows/refresh.yml`) rebuilds it every 3 hours and publishes via GitHub Pages
- `widget.js` → Scriptable script that draws the Large widget from the feed URL

## Setup on your iPhone (about 3 minutes)
1. App Store → install **Scriptable** (free, by Simon B. Støvring).
2. Open this on your phone and copy the whole script:  
   https://raw.githubusercontent.com/wghtkbpxwx-a11y/news-widget-feed/main/widget.js  
   (tap the page, Select All, Copy)
3. Scriptable → **+** (top right) → paste → tap the name at the top → rename to `Dave Brief` → **Done**.
4. Tap ▶ **Run** once. A large preview should appear with scores and headlines.
5. Home screen → long-press empty space → **+** → search **Scriptable** → choose the **Large** (third) size → **Add Widget**.
6. Long-press the new widget → **Edit Widget** → **Script: Dave Brief** → **When Interacting: Open URL** (or Run Script) → tap outside.
   - Tapping a headline row opens that article; tapping a score opens the game page.
7. Feed URL is already set in the script:  
   `https://wghtkbpxwx-a11y.github.io/news-widget-feed/feed.json`

If offline, the widget shows the last cached feed and an orange "offline" marker. If the feed is >36 h old it shows "stale".

## Change what you see
Edit `config.json` (keywords + weights, `favorite_teams`, feeds, `max_items`, `max_per_category`). Run `python3 build_feed.py` locally to test, or edit it on github.com and click **Actions → refresh-feed → Run workflow**.
Favorite teams use abbreviations, e.g. `"NHL": ["VAN"]`, `"NFL": ["SEA"]`.

## Run locally
    python3 build_feed.py          # needs Python 3.9+, no packages
    node --check widget.js         # syntax check
    node test_widget_mock.js       # smoke test against mock Scriptable API

## Notes
- GitHub pauses scheduled workflows after 60 days of no repo activity; the bot's own commits normally keep it alive, but if the widget says "stale", press Run workflow once.
- Everything is public: the repo (incl. config.json interest keywords) and feed.json are visible to anyone with the link.


## Oct 2 2026 draft update (NOT live - awaiting Dave's layout choice)
- config.json: teams = Canucks, Seahawks, BC Lions, Blue Jays, Raptors; Music/Comedy removed; new Local/National/World/Money/Health/Teams/Tech sections.
- `mockups/` holds three layout mockups (A scores-first, B headlines+chips, C sections) rendered from real data (`make_mockups.py`, `render.sh`).
- `topic-picker.html` is the interactive topic chooser.
- `FANTASY_TODO.md` documents fantasy-player ingestion (read-only; rosters stay out of the public repo).
- `build_feed.py --pool-out FILE` dumps every scored item for mockups/analysis; feed.json now also has `my_teams` (last result + next game).


## V2 layout (Oct 2 2026) — live
- `widget.js` = V2 "glass" layout: **Everyone Must Know** banner (≤3 stories), 5 team chips (last result / next game), glass headline cards. Large, Medium and Small sizes (Medium = hero + 2 cards + chips; Small = top story).
- **Everyone Must Know** (`must_know` in feed.json, rules in `config.json → must_know`): same story covered by several *different* publishers in the last 24h plus severity keywords (emergency, evacuation, war, election result, disaster, alerts…). Sports/tech never qualify. If nothing qualifies the banner says "ALL CLEAR".
- **Fantasy roster headlines** (`fantasy_items`): built on the box only. Roster names are read from files on the box at build time (`fantasy_players.py` → gitignored `fantasy_players.local.json`) and are never written to the repo or feed.json; only the resulting headlines are published.
- **Who refreshes what:** `deploy_box.sh` (box, with roster) builds + pushes every 3h. The GitHub Action (no roster) also runs every 3h and carries over the last roster headlines (≤24h) from the previous feed.json, so it can't wipe them. If the box stops, roster headlines age out after 24h and everything else keeps updating.
- Source blocklist (Daily Hive/Buzz, gossip, crypto, entertainment, clickbait) lives in `config.json → blocked_sources / blocked_title_patterns`.
- Smoke test: `node test_widget_mock.js feed.json large|medium|small`.
