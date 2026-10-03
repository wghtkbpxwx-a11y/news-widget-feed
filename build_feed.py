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
    entries = root.findall(".//item") or root.findall(".//a:entry", NS) or root.findall(".//{http://purl.org/rss/1.0/}item")
    for e in entries:
        def g(tag, ns=None):
            x = e.find(tag, ns) if ns else e.find(tag)
            if x is None and not ns and not tag.startswith("{"): x = e.find("{http://purl.org/rss/1.0/}" + tag)
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
        out.append({"title": title, "url": link.strip(), "ts": date, "source": src or feed["name"], "category": feed["category"], "section": feed.get("section", feed["category"]), "feed": feed["name"]})
    return out

def quality_filter(items, cfg):
    """Drop blocked (low-quality / clickbait / spam) sources and clickbait-style titles. Config-driven."""
    bs = [b.lower() for b in cfg.get("blocked_sources", [])]
    bp = [re.compile(p, re.I) for p in cfg.get("blocked_title_patterns", [])]
    out = []
    for i in items:
        src = i["source"].lower()
        if any(b in src for b in bs): continue
        if any(p.search(i["title"]) for p in bp): continue
        out.append(i)
    return out

def norm_tokens(t):
    return set(w for w in re.findall(r"[a-z0-9']+", t.lower()) if len(w) > 2)

def dedupe(items, thr=0.6):
    kept, seen_urls = [], set()
    for it in items:  # items pre-sorted by score desc
        u = re.sub(r"[?#].*$", "", it["url"])
        if u in seen_urls: continue
        tk = norm_tokens(it["title"])
        dup = False
        for k in kept:
            kt = k["_tk"]
            if tk and kt and len(tk & kt) / len(tk | kt) >= thr:
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

def espn_scores(league, url, cfg, tz, now):
    d = json.loads(fetch(url))
    fav = set(cfg["favorite_teams"].get(league, []))
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
        link = next((l["href"] for l in ev.get("links", []) if "summary" in l.get("rel", [])), url)
        isfav = bool({aa, ha} & fav)
        out.append({"league": league, "text": txt, "url": link, "_p": 0 if isfav else 1, "fav": isfav, "_t": start.timestamp() if start else 0, "_state": state})
    return out

def load_players(cfg):
    fc = cfg.get("fantasy", {})
    if not fc.get("enabled"): return []
    import os
    base = os.path.dirname(os.path.abspath(__file__))
    path = os.environ.get("FANTASY_PLAYERS_FILE") or os.path.join(base, fc["players_file"])
    try: return json.load(open(path))["players"]
    except Exception: return []

def fantasy_feeds(cfg, players):
    """Google News queries (public) for roster players: injury/news batches. Names come from the local file only."""
    fc = cfg.get("fantasy", {}); n = fc.get("query_batch_size", 6); feeds = []
    from urllib.parse import quote_plus
    for sport in ("NHL", "NFL"):
        names = [p["name"] for p in players if p["sport"] == sport and not p["name"].endswith("defense")]
        for i in range(0, len(names), n):
            q = "(" + " OR ".join(f'"{x}"' for x in names[i:i+n]) + ") (injury OR injured OR out OR questionable OR practice OR lineup OR waiver) when:2d"
            feeds.append({"name": f"GN Fantasy {sport} {i//n+1}", "category": "Fantasy", "section": "Teams", "url": "https://news.google.com/rss/search?q=" + quote_plus(q) + "&hl=en-CA&gl=CA&ceid=CA:en"})
    return feeds

def team_status(cfg, tz, now):
    """One compact line per favourite team: last result + next game (public NHL/ESPN schedule APIs)."""
    out = []
    names = cfg.get("favorite_team_names", {})
    def fmt_dt(dt):
        loc = dt.astimezone(tz); today = now.astimezone(tz).date()
        d = "Today" if loc.date() == today else loc.strftime("%a")
        return f'{d} {loc.strftime("%-I:%M %p")}'
    # NHL
    try:
        d = json.loads(fetch("https://api-web.nhle.com/v1/club-schedule-season/VAN/20262027"))
        last = next_ = None
        for g in d["games"]:
            st = parse_date(g["startTimeUTC"])
            if g["gameState"] in ("FINAL", "OFF"): last = g
            elif next_ is None: next_ = g
        def nhl_line(g):
            a, h = g["awayTeam"], g["homeTeam"]; van_home = h["abbrev"] == "VAN"
            opp = a if van_home else h
            vs, them = (h.get("score"), a.get("score")) if van_home else (a.get("score"), h.get("score"))
            return opp["abbrev"], vs, them, van_home
        e = {"league": "NHL", "team": names.get("NHL", "Canucks"), "last": None, "next": None}
        if last:
            o, vs, them, hm = nhl_line(last)
            e["last"] = f'{"W" if vs > them else "L"} {vs}-{them} {"vs" if hm else "@"} {o}'
        if next_:
            o, _, _, hm = nhl_line(next_); e["next"] = f'{"vs" if hm else "@"} {o} {fmt_dt(parse_date(next_["startTimeUTC"]))}'
        out.append(e)
    except Exception as ex:
        out.append({"league": "NHL", "team": "Canucks", "error": str(ex)[:80]})
    for lg, path, tid in (("NFL", "football/nfl", "sea"), ("CFL", "football/cfl", "79"), ("MLB", "baseball/mlb", "tor"), ("NBA", "basketball/nba", "tor")):
        e = {"league": lg, "team": names.get(lg, lg), "last": None, "next": None}
        try:
            d = json.loads(fetch(f"https://site.api.espn.com/apis/site/v2/sports/{path}/teams/{tid}/schedule"))
            abbr = d["team"]["abbreviation"]; last = next_ = None
            for ev in d.get("events", []):
                state = ev["competitions"][0]["status"]["type"]["state"]
                if state == "post": last = ev
                elif next_ is None: next_ = ev
            def line(ev, post):
                c = ev["competitions"][0]["competitors"]; me = next(x for x in c if x["team"]["abbreviation"] == abbr); op = next(x for x in c if x is not me)
                sc = lambda x: int(float((x.get("score") or {}).get("value", 0))) if isinstance(x.get("score"), dict) else int(float(x.get("score") or 0))
                hm = me.get("homeAway") == "home"
                if post: return f'{"W" if sc(me) > sc(op) else "L"} {sc(me)}-{sc(op)} {"vs" if hm else "@"} {op["team"]["abbreviation"]}'
                return f'{"vs" if hm else "@"} {op["team"]["abbreviation"]} {fmt_dt(parse_date(ev["date"]))}'
            if last: e["last"] = line(last, True)
            if next_: e["next"] = line(next_, False)
            try:
                t = json.loads(fetch(f"https://site.api.espn.com/apis/site/v2/sports/{path}/teams/{tid}"))["team"]
                rec = t.get("record", {}).get("items", [{}])[0].get("summary", "")
                if rec and rec != "0-0": e["record"] = rec
            except Exception: pass
            if not last and not next_:
                e["note"] = "Season over" if lg == "MLB" else "No free schedule feed - headlines only"
        except Exception as ex:
            e["error"] = str(ex)[:80]
        out.append(e)
    return out


STOP = set("the and for with from that this have has had are was were will after over into about amid says said new its their his her you your out not but who what when why how more than they them been being could would should may might also just all any can our off per via one two three".split())

def sig_tokens(t):
    return set(w.rstrip("'s") if w.endswith("'s") else w for w in re.findall(r"[a-z0-9']+", t.lower()) if (len(w) > 3 or re.search(r"\d", w)) and w not in STOP)

def kw_hits(text, weights):
    hits = {}
    for kw, w in weights.items():
        if re.search(r"(?<![a-z0-9])" + re.escape(kw) + r"(?![a-z0-9])", text): hits[kw] = w
    return hits

def detect_must_know(items, cfg, now):
    """'Everyone must know' = same story covered by several DIFFERENT publishers and/or strong severity keywords.
    Pure public-headline logic; no names, no credentials."""
    mk = cfg.get("must_know", {})
    if not mk.get("enabled"): return []
    cutoff = timedelta(hours=mk.get("window_hours", 24))
    secs = set(mk.get("sections", []))
    sup = [re.compile(p, re.I) for p in mk.get("suppress_patterns", [])]
    pool = [i for i in items if i["ts"] and now - i["ts"] <= cutoff and i.get("section") in secs and not any(p.search(i["title"]) for p in sup)]
    # single-link clustering (union-find) on significant-token overlap
    for it in pool: it["_sig"] = sig_tokens(it["title"])
    par = list(range(len(pool)))
    def find(x):
        while par[x] != x: par[x] = par[par[x]]; x = par[x]
        return x
    for a_ in range(len(pool)):
        for b_ in range(a_ + 1, len(pool)):
            x, y = pool[a_]["_sig"], pool[b_]["_sig"]; inter = len(x & y)
            if not inter: continue
            if (inter >= 3 and inter / min(len(x), len(y)) >= 0.5) or inter / len(x | y) >= 0.4:
                par[find(a_)] = find(b_)
    groups = {}
    for idx, it in enumerate(pool): groups.setdefault(find(idx), []).append(it)
    clusters = [{"items": g} for g in groups.values()]
    out = []
    for c in clusters:
        pubs = {re.sub(r"[^a-z]", "", i["source"].lower()) for i in c["items"]}
        n = len(pubs)
        sev = {}
        for i in c["items"]: sev.update(kw_hits(i["title"].lower(), mk.get("severity", {})))
        sev_score = sum(sorted(sev.values(), reverse=True)[:3])
        ok = (sev_score >= 3 and n >= mk.get("min_sources_with_severity", 2)) or (n >= mk.get("min_sources_no_severity", 4) and sev_score >= 2) \
             or sev_score >= mk.get("strong_severity_single_source", 6)
        if not ok: continue
        best = max(c["items"], key=lambda i: (cfg.get("source_weight", {}).get(i["source"], 0), i["ts"]))
        out.append({"item": best, "members": [i["url"] for i in c["items"]], "sources": min(n, 99), "severity": round(sev_score, 1), "rank": sev_score + 1.5 * (n - 1) + 0.1 * best["score"],
                    "reason": ("multi-source" if n >= 2 else "alert") + (" + severity" if sev_score else "")})
    out.sort(key=lambda r: -r["rank"])
    return out[:mk.get("max_stories", 3)]

def prev_fantasy_items(path, cfg, now):
    """GitHub Action builds have no roster: carry over the last roster-based headlines so they are not wiped."""
    try: prev = json.load(open(path))
    except Exception: return [], None
    keep = []
    for i in prev.get("fantasy_items", []):
        t = parse_date(i.get("ts"))
        if t and now - t <= timedelta(hours=cfg["fantasy"].get("carryover_hours", 24)): keep.append(i)
    return keep, prev.get("fantasy_refreshed")

def tag_fantasy(items, players):
    """Mark items whose title mentions a rostered player (full name, or a unique distinctive last name)."""
    names = [p["name"].lower() for p in players if not p["name"].endswith("defense")]
    lasts = {}
    for n in names: lasts.setdefault(n.split()[-1], []).append(n)
    uniq_last = {l for l, v in lasts.items() if len(v) == 1 and len(l) >= 5}
    for i in items:
        tl = i["title"].lower()
        i["fantasy"] = any(n in tl for n in names) or any(re.search(r"\b" + re.escape(l) + r"\b", tl) for l in uniq_last) and i["category"] == "Fantasy"
    return names

def item_out(i, names=()):
    return {"title": i["title"], "source": i["source"], "url": i["url"],
            "ts": i["ts"].isoformat(timespec="seconds") if i["ts"] else None,
            "category": i["category"], "section": i.get("section"), "feed": i.get("feed"), "score": i["score"],
            "hits": [h for h in i["hits"] if h not in names]}  # never publish roster names

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.json"); ap.add_argument("--pool-out", default=None); ap.add_argument("--out", default="feed.json")
    args = ap.parse_args()
    cfg = json.load(open(args.config))
    tz = ZoneInfo(cfg.get("tz", "America/Vancouver"))
    now = datetime.now(timezone.utc)
    status = {}
    players = load_players(cfg)
    if players:
        cfg["feeds"] = cfg["feeds"] + fantasy_feeds(cfg, players)
        w = cfg["fantasy"].get("player_keyword_weight", 3.0)
        for p in players:
            if not p["name"].endswith("defense"): cfg["keywords"][p["name"].lower()] = w

    def run_feed(f):
        try: return f["name"], parse_feed(fetch(f["url"]), f), None
        except Exception as ex: return f["name"], [], str(ex)[:120]
    items = []
    with ThreadPoolExecutor(8) as ex:
        for name, its, err in ex.map(run_feed, cfg["feeds"]):
            status[name] = err or f"ok ({len(its)})"; items += its

    items = [i for i in items if sum(c.isascii() for c in i["title"]) / max(1, len(i["title"])) > 0.85]  # drop non-English
    items = quality_filter(items, cfg)
    max_age = timedelta(hours=cfg["max_age_hours"])
    items = [i for i in items if not i["ts"] or now - i["ts"] <= max_age]
    for i in items: score_item(i, cfg, now)
    items.sort(key=lambda i: -i["score"])
    # "Everyone must know": detected on the full pre-dedupe pool so multi-publisher coverage is visible
    mk = detect_must_know(items, cfg, now)
    mk_urls = {re.sub(r"[?#].*$", "", u) for m in mk for u in m["members"]}
    mk_tokens = [norm_tokens(m["item"]["title"]) for m in mk]
    pre = [i for i in dedupe(items, cfg.get('dedupe_similarity', 0.6)) if i["score"] > 0]
    names = tag_fantasy(pre, players) if players else []
    def is_mk(i):
        if re.sub(r"[?#].*$", "", i["url"]) in mk_urls: return True
        tk = norm_tokens(i["title"])
        return any(tk and k and len(tk & k) / len(tk | k) >= 0.4 for k in mk_tokens)
    items = [i for i in pre if not is_mk(i)]
    # Roster-based player news (names stay local; only headlines are published)
    fant_out, fant_refreshed = [], None
    fpath = args.out
    if players:
        fant = [i for i in items if i.get("fantasy")][:cfg["fantasy"].get("max_items", 3)]
        fant_out = [dict(item_out(i, names), fantasy=True) for i in fant]
        fant_refreshed = now.isoformat(timespec="seconds")
        items = [i for i in items if i not in fant]
        status["fantasy"] = f"roster read at build time: {len(fant_out)} player headlines"
    else:
        fant_out, fant_refreshed = prev_fantasy_items(fpath, cfg, now)
        fant_urls = {re.sub(r"[?#].*$", "", f["url"]) for f in fant_out}
        items = [i for i in items if re.sub(r"[?#].*$", "", i["url"]) not in fant_urls]
        status["fantasy"] = f"no roster on this runner: carried over {len(fant_out)} items from previous feed"

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
    jobs = [("NHL", lambda: nhl_scores(cfg, tz, now))] + [(lg, (lambda lg=lg, u=u: espn_scores(lg, u, cfg, tz, now))) for lg, u in cfg["espn_scoreboards"].items()]
    for lg, fn in jobs:
        try: scores += fn(); status[lg + " scores"] = "ok"
        except Exception as e: status[lg + " scores"] = str(e)[:120]
    # favourites first, then live, then by start time; keep both leagues represented
    scores.sort(key=lambda s: (s["_p"], s["_t"]))
    for s_ in scores:
        s_.setdefault("fav", s_["_p"] == 0)
    favs = [s_ for s_ in scores if s_["fav"]]
    n = cfg["scores_max"]; picked = favs[:n]
    lists = {lg: [s_ for s_ in scores if s_["league"] == lg and not s_["fav"]] for lg in ("NHL", "NFL", "MLB", "NBA", "CFL")}
    while len(picked) < n and any(lists.values()):
        for lst in lists.values():
            if lst and len(picked) < n: picked.append(lst.pop(0))
    picked.sort(key=lambda s: (s["_p"], s["_t"]))
    scores_out = [{k: v for k, v in s.items() if not k.startswith("_")} for s in picked]

    try: my_teams = team_status(cfg, tz, now); status["team status"] = "ok"
    except Exception as e: my_teams = []; status["team status"] = str(e)[:120]
    feed = {
        "generated": now.isoformat(timespec="seconds"),
        "generated_local": now.astimezone(tz).strftime("%a %b %-d, %-I:%M %p %Z"),
        "scores": scores_out,
        "my_teams": my_teams,
        "layout": "v2",
        "must_know": [dict(item_out(m["item"], ()), sources=m["sources"], severity=m["severity"], reason=m["reason"]) for m in mk],
        "fantasy_items": fant_out,
        "fantasy_refreshed": fant_refreshed,
        "items": [item_out(i, names) for i in sel],
        "_status": status,
    }
    if args.pool_out:
        json.dump({"generated_local": feed["generated_local"], "scores": scores_out, "my_teams": my_teams,
                   "all_scores": [{k: v for k, v in s.items() if not k.startswith("_")} for s in scores],
                   "pool": [item_out(i) for i in pre]}, open(args.pool_out, "w"), indent=1, ensure_ascii=False)
    json.dump(feed, open(args.out, "w"), indent=2, ensure_ascii=False)
    print(f"wrote {args.out}: {len(sel)} items, {len(scores_out)} scores")
    for k, v in status.items(): print(f"  {k}: {v}")

if __name__ == "__main__":
    main()
