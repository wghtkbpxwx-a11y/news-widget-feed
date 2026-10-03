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
