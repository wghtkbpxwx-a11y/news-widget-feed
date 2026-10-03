// Dave's News + Sports — Scriptable LARGE widget
// Reads feed.json (built daily by build_feed.py). Public news only; no logins, no keys.
// Setup: see README.md. Only edit FEED_URL below.

const FEED_URL = "https://wghtkbpxwx-a11y.github.io/news-widget-feed/feed.json";   // <-- set to the published feed URL
const MAX_ITEMS = 7;          // headlines shown (large widget fits 7 comfortably)
const STALE_HOURS = 36;       // show "stale" marker if feed older than this
const REFRESH_MINUTES = 30;   // ask iOS to refresh this often (iOS decides the real timing)
const CACHE_FILE = "news-widget-cache.json";

const COLORS = {
  bg: new Color("#0d1117"), card: new Color("#161b22"), text: new Color("#e6edf3"),
  dim: new Color("#8b949e"), warn: new Color("#f0883e"),
  cat: {
    "Pharmacy": new Color("#3fb950"), "Hockey": new Color("#58a6ff"), "Football": new Color("#d29922"),
    "Tesla/EV": new Color("#f85149"), "BC": new Color("#a371f7"), "AI": new Color("#39c5cf"),
    "Music": new Color("#db61a2"), "Comedy": new Color("#ffa657")
  }
};
const TAGS = { "Pharmacy": "RX", "Hockey": "NHL", "Football": "NFL", "Tesla/EV": "EV", "BC": "BC", "AI": "AI", "Music": "MUSIC", "Comedy": "LOL" };

async function loadFeed() {
  const fm = FileManager.local();
  const path = fm.joinPath(fm.documentsDirectory(), CACHE_FILE);
  try {
    const req = new Request(FEED_URL + (FEED_URL.includes("?") ? "&" : "?") + "t=" + Date.now());
    req.timeoutInterval = 15;
    const feed = await req.loadJSON();
    if (!feed || !Array.isArray(feed.items)) throw new Error("bad feed");
    fm.writeString(path, JSON.stringify(feed));
    return { feed, cached: false };
  } catch (e) {
    if (fm.fileExists(path)) {
      return { feed: JSON.parse(fm.readString(path)), cached: true };
    }
    return { feed: null, cached: false, error: String(e) };
  }
}

function ageHours(iso) { return iso ? (Date.now() - new Date(iso).getTime()) / 3600000 : 999; }
function ago(iso) {
  const h = ageHours(iso);
  if (h < 1) return Math.max(1, Math.round(h * 60)) + "m";
  if (h < 24) return Math.round(h) + "h";
  return Math.round(h / 24) + "d";
}

function addText(parent, str, size, color, weight, lines) {
  const t = parent.addText(str);
  t.font = weight === "bold" ? Font.boldSystemFont(size) : (weight === "semi" ? Font.semiboldSystemFont(size) : Font.systemFont(size));
  t.textColor = color;
  if (lines) t.lineLimit = lines;
  return t;
}

async function buildWidget() {
  const w = new ListWidget();
  w.backgroundColor = COLORS.bg;
  w.setPadding(10, 12, 8, 12);
  w.refreshAfterDate = new Date(Date.now() + REFRESH_MINUTES * 60000);

  const { feed, cached, error } = await loadFeed();
  if (!feed) {
    addText(w, "News widget: no data yet", 14, COLORS.text, "bold");
    addText(w, "Set FEED_URL in the script and check your connection.\n" + (error || ""), 11, COLORS.dim, null, 4);
    return w;
  }

  // Header
  const head = w.addStack(); head.centerAlignContent();
  addText(head, "DAVE'S BRIEF", 11, COLORS.text, "bold");
  head.addSpacer();
  const stale = ageHours(feed.generated) > STALE_HOURS;
  const status = (stale ? "stale · " : (cached ? "offline · " : "")) + "updated " + ago(feed.generated) + " ago";
  addText(head, status, 9, (stale || cached) ? COLORS.warn : COLORS.dim);
  w.addSpacer(5);

  // Scores strip: 2 rows x 3, each cell tappable
  const scores = (feed.scores || []).slice(0, 6);
  if (scores.length) {
    const strip = w.addStack(); strip.layoutVertically();
    strip.backgroundColor = COLORS.card; strip.cornerRadius = 8; strip.setPadding(5, 7, 5, 7);
    for (let r = 0; r < 2; r++) {
      const row = strip.addStack(); row.centerAlignContent();
      const rowItems = scores.slice(r * 3, r * 3 + 3);
      if (!rowItems.length) continue;
      rowItems.forEach((s, i) => {
        const cell = row.addStack(); cell.centerAlignContent();
        if (s.url) cell.url = s.url;
        addText(cell, s.league + " ", 8, s.league === "NHL" ? COLORS.cat["Hockey"] : COLORS.cat["Football"], "bold");
        addText(cell, s.text, 9.5, COLORS.text, "semi", 1).minimumScaleFactor = 0.6;
        if (i < rowItems.length - 1) row.addSpacer();
      });
      if (r === 0 && scores.length > 3) strip.addSpacer(3);
    }
    w.addSpacer(6);
  }

  // Headlines, grouped by category (contiguous same-category items share one tag)
  let items = feed.items.slice(0, MAX_ITEMS);
  const order = [];
  items.forEach(i => { if (!order.includes(i.category)) order.push(i.category); });
  items.sort((a, b) => order.indexOf(a.category) - order.indexOf(b.category));

  let prevCat = null;
  items.forEach((it, idx) => {
    const row = w.addStack(); row.topAlignContent(); row.spacing = 6;
    row.url = it.url;
    const tagCol = row.addStack(); tagCol.size = new Size(34, 0);
    if (it.category !== prevCat) {
      addText(tagCol, TAGS[it.category] || it.category.toUpperCase().slice(0, 5), 8, COLORS.cat[it.category] || COLORS.dim, "bold", 1);
    }
    const body = row.addStack(); body.layoutVertically();
    addText(body, it.title, 11.5, COLORS.text, "semi", 2).minimumScaleFactor = 0.9;
    addText(body, it.source + (it.ts ? " · " + ago(it.ts) : ""), 8, COLORS.dim, null, 1);
    prevCat = it.category;
    if (idx < items.length - 1) w.addSpacer(3.5);
  });
  w.addSpacer();
  return w;
}

(async () => {
  const widget = await buildWidget();
  if (config.runsInWidget) {
    Script.setWidget(widget);
  } else {
    await widget.presentLarge();   // preview when you tap Run inside Scriptable
  }
  Script.complete();
})();
