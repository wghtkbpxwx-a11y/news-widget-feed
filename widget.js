// Dave Brief — Scriptable widget, layout V2 (iOS "Liquid Glass" look): Everyone Must Know hero banner,
// 5 team chips, glass headline cards. Large + Medium (small = top story only).
// Reads feed.json from GitHub Pages. Public headlines only; no logins, no keys.
// Setup: see README.md. Only edit FEED_URL below if the feed moves.

const FEED_URL = "https://wghtkbpxwx-a11y.github.io/news-widget-feed/feed.json";
const STALE_HOURS = 8;        // feed is rebuilt every ~3h; warn if older than this
const REFRESH_MINUTES = 30;   // hint to iOS (iOS decides the real timing)
const CACHE_FILE = "news-widget-cache.json";

const C = (hex, a) => new Color(hex, a === undefined ? 1 : a);
const COL = {
  text: C("#F5F7FB"), dim: C("#9AA3B8"), warn: C("#FF9F0A"),
  glass: C("#FFFFFF", 0.10), glassHi: C("#FFFFFF", 0.16), edge: C("#FFFFFF", 0.20),
  hero: C("#BF5AF2", 0.22), heroEdge: C("#BF5AF2", 0.55), red: C("#FF453A"), yellow: C("#FFD60A"), green: C("#30D158")
};
// section/category -> label, SF Symbol, colour
const KIND = {
  Local: ["LOCAL", "mappin.and.ellipse", "#0A84FF"], National: ["CANADA", "flag.fill", "#FF453A"], World: ["WORLD", "globe", "#BF5AF2"],
  Health: ["HEALTH · RX", "pills.fill", "#30D158"], Money: ["MONEY", "dollarsign.circle.fill", "#64D2FF"],
  Fantasy: ["FANTASY", "waveform.path.ecg", "#FFD60A"], Teams: ["TEAMS", "sportscourt.fill", "#FF9F0A"],
  "Tesla/EV": ["TESLA", "bolt.fill", "#5AC8FA"], AI: ["AI", "sparkles", "#BF5AF2"], Tech: ["TECH", "bolt.fill", "#5AC8FA"]
};
const TEAM_STYLE = { Canucks: ["C", "#00B86B"], Seahawks: ["S", "#69BE28"], "BC Lions": ["L", "#FF8A1F"], "Blue Jays": ["J", "#2F7BFF"], Raptors: ["R", "#E5173F"] };
const TEAM_LEAGUE_LABEL = { NHL: "NHL", NFL: "NFL", CFL: "CFL", MLB: "MLB", NBA: "NBA" };

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
  t.font = weight === "bold" ? Font.boldSystemFont(size) : (weight === "semi" ? Font.semiboldSystemFont(size) : Font.systemFont(size));
  t.textColor = color;
  if (lines) { t.lineLimit = lines; t.minimumScaleFactor = 0.85; }
  return t;
}
function glass(parent, radius, pad, tint, edge) {
  const s = parent.addStack();
  s.backgroundColor = tint || COL.glass; s.cornerRadius = radius; s.borderWidth = 1; s.borderColor = edge || COL.edge;
  s.setPadding(pad[0], pad[1], pad[2], pad[3]);
  return s;
}
function symbol(parent, name, color, size) {
  const img = parent.addImage(SFSymbol.named(name).image);
  img.imageSize = new Size(size, size); img.tintColor = color;
  return img;
}
function badge(parent, name, hex, d) {
  const b = parent.addStack(); b.size = new Size(d, d); b.cornerRadius = d / 2; b.backgroundColor = C(hex, 0.22);
  b.borderWidth = 1; b.borderColor = C(hex, 0.45); b.centerAlignContent();
  symbol(b, name, C(hex), Math.round(d * 0.55));
  return b;
}
function kindOf(it) {
  if (it.fantasy || it.category === "Fantasy") return KIND.Fantasy;
  if (it.category === "Tesla/EV" || it.category === "AI") return KIND[it.category];
  if (it.section === "Tech") return KIND.Tech;
  if (it.section === "Teams") return [(it.category || "TEAMS").toUpperCase().slice(0, 6), "sportscourt.fill", "#FF9F0A"];
  return KIND[it.section] || KIND[it.category] || ["NEWS", "newspaper.fill", "#8E8E93"];
}

// ---- pieces ----
function header(w, feed, cached, size) {
  const h = w.addStack(); h.centerAlignContent();
  symbol(h, "star.fill", COL.text, size + 1); h.addSpacer(4);
  txt(h, "DAVE BRIEF", size, COL.text, "bold");
  h.addSpacer();
  const stale = ageHours(feed.generated) > STALE_HOURS;
  const when = feed.generated ? new Date(feed.generated).toLocaleString("en-CA", { weekday: "short", hour: "numeric", minute: "2-digit", timeZone: "America/Vancouver" }).replace(",", " •").replace(/\./g, "") + " PT" : "";
  txt(h, (stale ? "stale · " : (cached ? "offline · " : "")) + when, size - 2, (stale || cached) ? COL.warn : COL.dim);
}
function banner(parent, stories, big) {
  const b = glass(parent, 16, [8, 10, 8, 10], stories.length ? COL.hero : C("#30D158", 0.14), stories.length ? COL.heroEdge : C("#30D158", 0.4));
  b.layoutVertically();
  if (stories[0]) b.url = stories[0].url;
  const top = b.addStack(); top.centerAlignContent();
  const dot = top.addStack(); dot.size = new Size(6, 6); dot.cornerRadius = 3; dot.backgroundColor = stories.length ? COL.red : COL.green;
  top.addSpacer(5);
  txt(top, stories.length ? "EVERYONE MUST KNOW" : "ALL CLEAR", 9, stories.length ? C("#FFB4AE") : COL.green, "bold");
  top.addSpacer();
  if (stories.length) txt(top, stories.length + (stories.length === 1 ? " STORY" : " STORIES"), 8.5, COL.dim, "bold");
  b.addSpacer(3);
  if (!stories.length) { txt(b, "Nothing major right now.", 12, COL.text, "semi", 1); return b; }
  txt(b, stories[0].title, big ? 13.5 : 12.5, COL.text, "bold", big ? 3 : 4);
  stories.slice(1, 3).forEach(s => {
    b.addSpacer(3);
    const r = b.addStack(); r.centerAlignContent(); r.url = s.url;
    const d = r.addStack(); d.size = new Size(5, 5); d.cornerRadius = 2.5; d.backgroundColor = COL.yellow; r.addSpacer(5);
    txt(r, s.title, 10.5, C("#E6EAF5"), "semi", 1);
  });
  return b;
}
function chips(parent, teams, compact) {
  const row = parent.addStack(); row.centerAlignContent(); row.spacing = 4;
  (teams || []).slice(0, 5).forEach((t, i) => {
    const st = TEAM_STYLE[t.team] || [(t.team || "?")[0], "#8E8E93"];
    const chip = glass(row, 13, [3, 4, 3, 4], COL.glass, COL.edge); chip.centerAlignContent(); chip.spacing = 3;
    const d = compact ? 14 : 16;
    const logo = chip.addStack(); logo.size = new Size(d, d); logo.cornerRadius = d / 2; logo.backgroundColor = C(st[1], 0.9); logo.centerAlignContent();
    txt(logo, st[0], d * 0.55, C("#FFFFFF"), "bold");
    const col = chip.addStack(); col.layoutVertically();
    const l1 = t.last ? t.last.split(" ").slice(0, 2).join(" ") : (t.record || t.league || "—");
    const m = (t.next || "").match(/^(vs|@) (\S+) (.*)$/);
    const l2 = m ? m[3].replace(/ ?[AP]M$/, "").replace("Today", "Tdy") : (t.note === "Season over" ? "done" : (t.next || "headlines"));
    txt(col, l1, compact ? 7.5 : 8.5, COL.text, "bold", 1);
    txt(col, l2, compact ? 7 : 8, COL.dim, null, 1);
    if (i < 4) row.addSpacer();
  });
  return row;
}
function card(parent, it, lines, compact) {
  const k = kindOf(it);
  const c = glass(parent, 14, [6, 8, 6, 8], COL.glass, COL.edge); c.centerAlignContent(); c.spacing = 7; c.url = it.url;
  badge(c, k[1], k[2], compact ? 20 : 24);
  const body = c.addStack(); body.layoutVertically();
  txt(body, it.title, compact ? 10.5 : 11.5, COL.text, "semi", lines);
  const meta = body.addStack();
  txt(meta, k[0], 8, C(k[2]), "bold"); txt(meta, " • " + it.source + (it.ts ? " • " + ago(it.ts) : ""), 8, COL.dim, null, 1);
  return c;
}
// choose cards: roster headline first, then one per section for variety
function pickCards(feed, n, mkUrls) {
  const out = [];
  const fant = (feed.fantasy_items || [])[0];
  if (fant) out.push(fant);
  const used = new Set(out.map(i => i.section || i.category));
  const pool = (feed.items || []).filter(i => !mkUrls.has(i.url) && i.category !== "Fantasy");
  for (const it of pool) { if (out.length >= n) break; const s = it.section || it.category; if (used.has(s)) continue; used.add(s); out.push(it); }
  for (const it of pool) { if (out.length >= n) break; if (!out.includes(it)) out.push(it); }
  return out.slice(0, n);
}

async function buildWidget() {
  const w = new ListWidget();
  const g = new LinearGradient();
  g.colors = [C("#1A2347"), C("#0A0E1D"), C("#14102E")]; g.locations = [0, 0.55, 1]; g.startPoint = new Point(0, 0); g.endPoint = new Point(1, 1);
  w.backgroundGradient = g;
  w.refreshAfterDate = new Date(Date.now() + REFRESH_MINUTES * 60000);
  const family = config.widgetFamily || "large";

  const { feed, cached, error } = await loadFeed();
  if (!feed) {
    txt(w, "Dave Brief: no data yet", 14, COL.text, "bold");
    txt(w, "Check your connection.\n" + (error || ""), 11, COL.dim, null, 4);
    return w;
  }
  const mk = feed.must_know || [];
  const mkUrls = new Set(mk.map(s => s.url));

  if (family === "small") {
    w.setPadding(10, 10, 10, 10);
    header(w, feed, cached, 9); w.addSpacer(4);
    banner(w, mk.slice(0, 1), false);
    return w;
  }
  if (family === "medium") {
    w.setPadding(9, 11, 8, 11);
    header(w, feed, cached, 10); w.addSpacer(4);
    const mid = w.addStack(); mid.spacing = 6; mid.topAlignContent();
    const left = mid.addStack(); left.layoutVertically(); left.size = new Size(165, 0);
    const lb = glass(left, 16, [8, 9, 8, 9], mk.length ? COL.hero : C("#30D158", 0.14), mk.length ? COL.heroEdge : C("#30D158", 0.4));
    lb.layoutVertically(); if (mk[0]) lb.url = mk[0].url;
    const t = lb.addStack(); t.centerAlignContent();
    const d = t.addStack(); d.size = new Size(6, 6); d.cornerRadius = 3; d.backgroundColor = mk.length ? COL.red : COL.green; t.addSpacer(4);
    txt(t, mk.length ? "EVERYONE MUST KNOW" : "ALL CLEAR", 8, mk.length ? C("#FFB4AE") : COL.green, "bold");
    lb.addSpacer(3);
    txt(lb, mk.length ? mk[0].title : "Nothing major right now.", 11.5, COL.text, "bold", 4);
    if (mk.length > 1) { lb.addSpacer(2); txt(lb, "+" + (mk.length - 1) + " more • tap to open", 8, C("#FFB84D"), "semi", 1); }
    const right = mid.addStack(); right.layoutVertically(); right.spacing = 5;
    pickCards(feed, 2, mkUrls).forEach(it => card(right, it, 2, true));
    w.addSpacer(4);
    chips(w, feed.my_teams, true);
    return w;
  }
  // large
  w.setPadding(12, 12, 10, 12);
  header(w, feed, cached, 11); w.addSpacer(6);
  banner(w, mk, true); w.addSpacer(6);
  chips(w, feed.my_teams, false); w.addSpacer(6);
  const cards = pickCards(feed, mk.length >= 2 ? 3 : 4, mkUrls);
  cards.forEach((it, i) => { card(w, it, 2, false); if (i < cards.length - 1) w.addSpacer(5); });
  w.addSpacer();
  return w;
}

(async () => {
  const widget = await buildWidget();
  if (config.runsInWidget) Script.setWidget(widget);
  else await widget.presentLarge();   // preview when you tap Run inside Scriptable
  Script.complete();
})();
