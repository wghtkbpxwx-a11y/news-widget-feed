// Dave Brief — Scriptable widget, layout V3 "Light editorial" (matches the Tesla dashboard palette).
// Large: Everyone Must Know banner + 5 headline rows + team ticker, filling the whole widget.
// Medium: banner + 2 headlines. Small: banner only. Light/dark follow the system (dark = "C" twin).
// Size adapts to the phone via Device.screenSize(); layout picked by config.widgetFamily.
// Reads ONLY feed.json (same single source as the dashboard). Public headlines; no logins, no keys.

const FEED_URL = "https://wghtkbpxwx-a11y.github.io/news-widget-feed/feed.json";
const STALE_HOURS = 8;        // feed is rebuilt every ~3h; warn if older than this
const REFRESH_MINUTES = 30;   // hint to iOS (iOS decides the real timing)
const CACHE_FILE = "news-widget-cache.json";

const DC = (l, d) => Color.dynamic(new Color(l), new Color(d));
const COL = {
  bg:    DC("#FFFFFF", "#080B10"),
  text:  DC("#0F1319", "#F4F6FB"),
  sub:   DC("#7A8494", "#6B7385"),
  t2:    DC("#4B5566", "#8B95A8"),
  div:   DC("#E7E9EC", "#1A1D22"),      // ~ rgba(12,16,22,.09) on white / rgba(255,255,255,.075) on near-black
  mint:  DC("#0D8F74", "#2AF5C4"),
  red:   new Color("#FF5A4F"),           // banner only
  redBg: DC("#FFEEED", "#2A1415"),       // ~ red at .10 on white / .12 on near-black
  warn:  new Color("#FF9F0A")
};

// ---- adaptive sizing --------------------------------------------------------------------
// Known iPhone widget sizes in points, keyed by portrait screen width; unknown/new phones use the ratio fallback
// (widget width ~ 0.846 x screen width; Large height ~ 1.048 x its width; Medium height ~ 0.467 x its width).
const KNOWN = { // screen width: [mediumW, mediumH, largeH]
  440: [364, 170, 382], 430: [364, 170, 382], 428: [364, 170, 382], 414: [360, 169, 379],
  402: [338, 158, 354], 393: [338, 158, 354], 390: [338, 158, 354], 375: [329, 155, 345], 320: [292, 141, 311]
};
function widgetSize(family) {
  let sw = 393;
  try { const s = Device.screenSize(); sw = Math.min(s.width, s.height); } catch (e) {}
  let k = KNOWN[Math.round(sw)];
  if (!k) { const w = Math.round(sw * 0.846); k = [w, Math.round(w * 0.467), Math.round(w * 1.048)]; }
  if (family === "small") { const d = Math.round(k[1]); return { w: d, h: d }; }
  if (family === "medium") return { w: k[0], h: k[1] };
  return { w: k[0], h: k[2] };
}

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
    if (fm.fileExists(path)) return { feed: JSON.parse(fm.readString(path)), cached: true };
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
function txt(parent, str, size, color, weight, lines) {
  const t = parent.addText(String(str));
  t.font = weight === "bold" ? Font.boldSystemFont(size) : (weight === "semi" ? Font.semiboldSystemFont(size) : (weight === "med" ? Font.mediumSystemFont(size) : Font.systemFont(size)));
  t.textColor = color;
  if (lines) { t.lineLimit = lines; t.minimumScaleFactor = 0.9; }
  return t;
}
function rule(parent, w) {   // hairline divider (not edge to edge: inset by widget padding)
  const r = parent.addStack(); r.size = new Size(w, 0.5); r.backgroundColor = COL.div; return r;
}

// ---- pieces -----------------------------------------------------------------------------
function banner(parent, stories, s, lines) {
  const b = parent.addStack(); b.layoutHorizontally(); b.topAlignContent();
  b.backgroundColor = stories.length ? COL.redBg : DC("#E8F7F2", "#0C2420");
  b.cornerRadius = 14; b.setPadding(7 * s, 10 * s, 7 * s, 10 * s);
  if (stories[0]) b.url = stories[0].url;
  const dotWrap = b.addStack(); dotWrap.setPadding(4 * s, 0, 0, 0);
  const dot = dotWrap.addStack(); dot.size = new Size(6, 6); dot.cornerRadius = 3; dot.backgroundColor = stories.length ? COL.red : COL.mint;
  b.addSpacer(9 * s);
  const col = b.addStack(); col.layoutVertically();
  txt(col, stories.length ? "EVERYONE MUST KNOW" : "ALL CLEAR", 9.5 * s, stories.length ? COL.red : COL.mint, "bold");
  col.addSpacer(1);
  txt(col, stories.length ? stories[0].title : "Nothing major right now.", 12 * s, COL.text, "semi", stories.length ? lines : 1);
  b.addSpacer();           // keep text left-aligned, full width
  return b;
}
function row(parent, it, s, h, lines, w) {
  const r = parent.addStack(); r.layoutVertically(); r.centerAlignContent(); r.url = it.url;
  if (h) r.size = new Size(w, h);
  txt(r, it.title, 12.5 * s, COL.text, "semi", lines);
  r.addSpacer(2);
  txt(r, it.source + (it.ts ? " · " + ago(it.ts) : ""), 10.5 * s, COL.sub, "med", 1);
  return r;
}
function tickerText(t) {
  const m = (t.next || "").match(/^(vs|@) (\S+) (.*)$/);
  if (m) return m[3].replace(/ ?[AP]M$/, "") + " " + (m[1] === "@" ? "@" : "") + m[2];
  const l = (t.last || "").match(/^([WLT]) (\d+)-(\d+) (?:vs|@) (\S+)/);
  if (l) return l[1] + " " + l[2] + "–" + l[3] + " " + l[4];
  return null;
}
function ticker(parent, teams, s, w, extra) {
  const items = (teams || []).map(t => ({ name: t.team, text: tickerText(t) })).filter(x => x.text).slice(0, 3);
  const r = parent.addStack(); r.centerAlignContent(); r.size = new Size(w, 14 * s);
  items.forEach((x, i) => {
    const t = r.addStack(); t.centerAlignContent();
    txt(t, x.name, 10.5 * s, COL.mint, "semi"); t.addSpacer(4);
    txt(t, x.text, 10.5 * s, COL.t2, null, 1);
    if (i < items.length - 1) r.addSpacer();
  });
  if (extra) { r.addSpacer(); txt(r, extra, 9 * s, COL.warn, "semi"); }
  return r;
}
// choose rows: roster headline first, then one per section for variety
function pickCards(feed, n, mkUrls) {
  const out = [];
  const fant = (feed.fantasy_items || [])[0];
  const used = new Set();
  const pool = (feed.items || []).filter(i => !mkUrls.has(i.url) && i.category !== "Fantasy");
  for (const it of pool) { if (out.length >= n) break; const sec = it.section || it.category; if (used.has(sec)) continue; used.add(sec); out.push(it); }
  for (const it of pool) { if (out.length >= n) break; if (!out.includes(it)) out.push(it); }
  if (fant && n >= 3) out.splice(Math.min(2, out.length), 0, fant);   // roster headline sits 3rd, not first
  else if (fant && out.length >= n) out[n - 1] = fant;
  return out.slice(0, n);
}

async function buildWidget() {
  const w = new ListWidget();
  w.backgroundColor = COL.bg;
  w.refreshAfterDate = new Date(Date.now() + REFRESH_MINUTES * 60000);
  const family = config.widgetFamily || "large";
  const sz = widgetSize(family);
  const s = Math.max(0.85, Math.min(1.2, sz.w / 364));       // type scale relative to the 364pt reference
  const padX = 16 * s, padT = 13 * s, padB = 11 * s;
  const innerW = sz.w - 2 * padX;

  const { feed, cached, error } = await loadFeed();
  if (!feed) {
    w.setPadding(padT, padX, padB, padX);
    txt(w, "Dave Brief: no data yet", 14, COL.text, "bold");
    txt(w, "Check your connection.\n" + (error || ""), 11, COL.sub, null, 4);
    return w;
  }
  const mk = feed.must_know || [];
  const mkUrls = new Set(mk.map(x => x.url));
  const stale = ageHours(feed.generated) > STALE_HOURS;
  const flag = stale ? "stale" : (cached ? "offline" : "");

  if (family === "small") {
    w.setPadding(10, 10, 10, 10);
    banner(w, mk.slice(0, 1), 0.85, 5);
    return w;
  }
  if (family === "medium") {
    w.setPadding(10 * s, padX, 8 * s, padX);
    banner(w, mk.slice(0, 1), s, 2);
    w.addSpacer();
    const picks = pickCards(feed, 2, mkUrls);
    picks.forEach((it, i) => { row(w, it, s, 0, 1, innerW); if (i < picks.length - 1) { w.addSpacer(); rule(w, innerW); w.addSpacer(); } });
    w.addSpacer();
    return w;
  }
  // large: fill the whole widget — banner, N equal rows, ticker
  w.setPadding(padT, padX, padB, padX);
  banner(w, mk.slice(0, 1), s, 2);
  const bannerH = 54 * s, tickerH = 14 * s + 16 * s;          // estimates (banner 2 lines / ticker + rule + gap)
  const n = sz.h >= 340 ? 5 : 4;
  const rowH = Math.max(34, (sz.h - padT - padB - bannerH - tickerH - 3) / n);
  w.addSpacer(3);
  const picks = pickCards(feed, n, mkUrls);
  picks.forEach((it, i) => {
    row(w, it, s, rowH, 2, innerW);
    if (i < picks.length - 1) rule(w, innerW);
  });
  w.addSpacer();
  rule(w, innerW); w.addSpacer(8 * s);
  ticker(w, feed.my_teams, s, innerW, flag);
  return w;
}

(async () => {
  const widget = await buildWidget();
  if (config.runsInWidget) Script.setWidget(widget);
  else await widget.presentLarge();   // preview when you tap Run inside Scriptable
  Script.complete();
})();
