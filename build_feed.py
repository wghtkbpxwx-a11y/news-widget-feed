#!/usr/bin/env python3
"""Build feed.json for the Scriptable widget. Stdlib only, no credentials, public data only.
Usage: python3 build_feed.py [--config config.json] [--out feed.json]
"""
import argparse, json, math, re, sys, time, urllib.request, html
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

UA = "Mozilla/5.0 (compatible; DaveNewsWidget/1.0)"
NS = {"a": "http://www.w3.org/2005/Atom", "dc": "http://purl.org/dc/elements/1.1/"}

def fetch(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

def parse_date(s):
    if not s: return None
    s = s.strip()
    try:
        d = parsedate_to_datetime(s)
    except Exception:
        try: d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception: return None
    if d.tzinfo is None: d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc)

def clean(t):
    t = html.unescape(re.sub(r"<[^>]+>", "", t or ""))
    return re.sub(r"\s+", " ", t).strip()

def parse_feed(raw, feed):
    root = ET.fromstring(raw)
    out = []
    entries = root.findall(".//item") or root.findall(".//a:entry", NS)
    for e in entries:
        def g(tag, ns=None):
            x = e.find(tag, ns) if ns else e.find(tag)
            return x.text if x is not None and x.text else ""
        title = clean(g("title") or g("a:title", NS))
        link = g("link")
        if not link:
            l = e.find("a:link", NS)
            if l is not None: link = l.get("href", "")
        date = parse_date(g("pubDate") or g("a:published", NS) or g("a:updated", NS) or g("dc:date", NS))
        src = feed.get("source")
        se = e.find("source")
        if se is not None and se.text and not src:
            src = clean(se.text)
        # Google News titles: "Headline - Publisher"
        if "news.google.com" in feed["url"] and " - " in title:
            head, _, pub = title.rpartition(" - ")
            if head: title = head; src = src or pub
        if not title or not link: continue
        out.append({"title": title, "url": link.strip(), "ts": date, "source": src or feed["name"], "category": feed["category"], "feed": feed["name"]})
    return out

def norm_tokens(t):
    return set(w for w in re.findall(r"[a-z0-9']+", t.lower()) if len(w) > 2)

def dedupe(items):
    kept, seen_urls = [], set()
    for it in items:  # items pre-sorted by score desc
        u = re.sub(r"[?#].*$", "", it["url"])
        if u in seen_urls: continue
        tk = norm_tokens(it["title"])
        dup = False
        for k in kept:
            kt = k["_tk"]
            if tk and kt and len(tk & kt) / len(tk | kt) >= 0.6:
                dup = True; break
        if dup: continue
        it["_tk"] = tk; seen_urls.add(u); kept.append(it)
    return kept

def score_item(it, cfg, now):
    text = it["title"].lower()
    s = cfg["category_boost"].get(it["category"], 0)
    hits = []
    for kw, w in {**cfg["keywords"], **cfg.get("negative_keywords", {})}.items():
        if re.search(r"(?<![a-z0-9])" + re.escape(kw) + r"(?![a-z0-9])", text):
            s += w; hits.append(kw)
    s += cfg.get("source_weight", {}).get(it["source"], 0)
    if it["ts"]:
        age_h = max(0, (now - it["ts"]).total_seconds() / 3600)
        s += 4 * math.pow(0.5, age_h / cfg["recency_half_life_hours"])
    it["score"] = round(s, 2); it["hits"] = hits
    return s

def hhmm(dt, tz):
    return dt.astimezone(tz).strftime("%-I:%M %p")

def nhl_scores(cfg, tz, now):
    d = json.loads(fetch(cfg["nhl_scoreboard"]))
    today = now.astimezone(tz).strftime("%Y-%m-%d")
    games = []
    for day in d.get("gamesByDate", []):
        if day["date"] in (today,):
            games = day["games"]
    if not games:  # fall back to the focused date
        for day in d.get("gamesByDate", []):
            if day["date"] == d.get("focusedDate"): games = day["games"]
    fav = set(cfg["favorite_teams"].get("NHL", []))
    out = []
    for g in games:
        a, h = g["awayTeam"], g["homeTeam"]
        st = g.get("gameState", "")
        start = parse_date(g.get("startTimeUTC"))
        if st in ("FINAL", "OFF"):
            txt = f'{a["abbrev"]} {a.get("score","-")} @ {h["abbrev"]} {h.get("score","-")} F'
            if g.get("gameOutcome", {}).get("lastPeriodType") in ("OT", "SO"): txt += "/" + g["gameOutcome"]["lastPeriodType"]
        elif st in ("LIVE", "CRIT"):
            txt = f'{a["abbrev"]} {a.get("score",0)} @ {h["abbrev"]} {h.get("score",0)} LIVE'
        else:
            txt = f'{a["abbrev"]} @ {h["abbrev"]} {hhmm(start, tz) if start else ""}'
        pri = 0 if ({a["abbrev"], h["abbrev"]} & fav) else 1
        out.append({"league": "NHL", "text": txt, "url": "https://www.nhl.com" + g.get("gameCenterLink", ""), "_p": pri, "_t": start.timestamp() if start else 0})
    return out

def nfl_scores(cfg, tz, now):
    d = json.loads(fetch(cfg["nfl_scoreboard"]))
    fav = set(cfg["favorite_teams"].get("NFL", []))
    out = []
    for ev in d.get("events", []):
        c = ev["competitions"][0]
        teams = {t["homeAway"]: t for t in c["competitors"]}
        a, h = teams["away"], teams["home"]
        aa, ha = a["team"]["abbreviation"], h["team"]["abbreviation"]
        state = ev["status"]["type"]["state"]
        start = parse_date(ev.get("date"))
        if state == "post": txt = f'{aa} {a.get("score","-")} @ {ha} {h.get("score","-")} F'
        elif state == "in": txt = f'{aa} {a.get("score",0)} @ {ha} {h.get("score",0)} {ev["status"]["type"].get("shortDetail","LIVE")}'
        else: txt = f'{aa} @ {ha} {start.astimezone(tz).strftime("%a %-I:%M %p") if start else ""}'
        link = next((l["href"] for l in ev.get("links", []) if "summary" in l.get("rel", [])), "https://www.espn.com/nfl/scoreboard")
        pri = 0 if ({aa, ha} & fav) else 1
        out.append({"league": "NFL", "text": txt, "url": link, "_p": pri, "_t": start.timestamp() if start else 0, "_state": state})
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.json"); ap.add_argument("--out", default="feed.json")
    args = ap.parse_args()
    cfg = json.load(open(args.config))
    tz = ZoneInfo(cfg.get("tz", "America/Vancouver"))
    now = datetime.now(timezone.utc)
    status = {}

    def run_feed(f):
        try: return f["name"], parse_feed(fetch(f["url"]), f), None
        except Exception as ex: return f["name"], [], str(ex)[:120]
    items = []
    with ThreadPoolExecutor(8) as ex:
        for name, its, err in ex.map(run_feed, cfg["feeds"]):
            status[name] = err or f"ok ({len(its)})"; items += its

    items = [i for i in items if sum(c.isascii() for c in i["title"]) / max(1, len(i["title"])) > 0.85]  # drop non-English
    max_age = timedelta(hours=cfg["max_age_hours"])
    items = [i for i in items if not i["ts"] or now - i["ts"] <= max_age]
    for i in items: score_item(i, cfg, now)
    items.sort(key=lambda i: -i["score"])
    items = [i for i in dedupe(items) if i["score"] > 0]

    # Selection: round 1 = best item of each category (variety), round 2 = best remaining under per-category cap.
    # Output order = selection order, so a widget showing only the first N still gets variety.
    sel, counts = [], {}
    cats = []
    for i in items:
        if i["category"] not in cats: cats.append(i["category"])  # categories ordered by their best item
    for c in cats:
        best = next(i for i in items if i["category"] == c)
        sel.append(best); counts[c] = 1
    for i in items:
        if len(sel) >= cfg["max_items"]: break
        if i in sel or counts.get(i["category"], 0) >= cfg["max_per_category"]: continue
        sel.append(i); counts[i["category"]] = counts.get(i["category"], 0) + 1
    sel = sel[:cfg["max_items"]]

    scores = []
    for fn, lg in ((nhl_scores, "NHL"), (nfl_scores, "NFL")):
        try: scores += fn(cfg, tz, now); status[lg + " scores"] = "ok"
        except Exception as e: status[lg + " scores"] = str(e)[:120]
    # favourites first, then live, then by start time; keep both leagues represented
    scores.sort(key=lambda s: (s["_p"], s["_t"]))
    nhl = [s for s in scores if s["league"] == "NHL"]; nfl = [s for s in scores if s["league"] == "NFL"]
    n = cfg["scores_max"]; picked = []
    while len(picked) < n and (nhl or nfl):
        for lst in (nhl, nfl):
            if lst and len(picked) < n: picked.append(lst.pop(0))
    picked.sort(key=lambda s: (s["_p"], s["_t"]))
    scores_out = [{k: v for k, v in s.items() if not k.startswith("_")} for s in picked]

    feed = {
        "generated": now.isoformat(timespec="seconds"),
        "generated_local": now.astimezone(tz).strftime("%a %b %-d, %-I:%M %p %Z"),
        "scores": scores_out,
        "items": [{"title": i["title"], "source": i["source"], "url": i["url"],
                   "ts": i["ts"].isoformat(timespec="seconds") if i["ts"] else None,
                   "category": i["category"], "score": i["score"], "hits": i["hits"]} for i in sel],
        "_status": status,
    }
    json.dump(feed, open(args.out, "w"), indent=2, ensure_ascii=False)
    print(f"wrote {args.out}: {len(sel)} items, {len(scores_out)} scores")
    for k, v in status.items(): print(f"  {k}: {v}")

if __name__ == "__main__":
    main()
