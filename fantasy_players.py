#!/usr/bin/env python3
"""Build fantasy_players.local.json from roster files already on this box. READ-ONLY.
Never logs into Yahoo/Sleeper. Output is gitignored (Dave's rosters stay out of the public repo).
Sources (if present): /workspace/david_roster.json (football, Sleeper-style export),
/workspace/fantasy/data-*-<league>.md (hockey roster tables, section 1 only).
Add names by hand via extra_players.txt (one per line: Name, TEAM, SPORT)."""
import json, re, glob, os
OUT = os.path.join(os.path.dirname(__file__), "fantasy_players.local.json")
players = []
fb = "/workspace/david_roster.json"
if os.path.exists(fb):
    for v in json.load(open(fb)).values():
        if v.get("full_name"):
            players.append({"name": v["full_name"], "team": v.get("team"), "sport": "NFL", "pos": v.get("position"), "status": v.get("injury_status"), "src": "david_roster.json"})
        elif v.get("position") == "DEF":
            players.append({"name": v.get("team", "") + " defense", "team": v.get("team"), "sport": "NFL", "pos": "DEF", "status": None, "src": "david_roster.json"})
for fn in sorted(glob.glob("/workspace/fantasy/data-*.md")):
    if "allteams" in fn: continue
    league = re.sub(r"^data-[\d-]+-|\.md$", "", os.path.basename(fn))
    txt = open(fn).read().split("\n## 2.")[0]
    for line in txt.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 4 and re.fullmatch(r"(Active|BN|IR\+?|C|LW|RW|D|G|Util)(?: \(Util\))?", cells[0]) and re.fullmatch(r"[A-Z]{2,3}", cells[2]):
            note = cells[4] if len(cells) > 4 else ""
            st = "IR" if "IR" in note else None
            players.append({"name": cells[1], "team": cells[2], "sport": "NHL", "pos": cells[3], "status": st, "src": league})
extra = os.path.join(os.path.dirname(__file__), "extra_players.txt")
if os.path.exists(extra):
    for l in open(extra):
        p = [x.strip() for x in l.split(",")]
        if len(p) >= 3 and not l.startswith("#"):
            players.append({"name": p[0], "team": p[1], "sport": p[2], "pos": None, "status": None, "src": "manual"})
seen, uniq = set(), []
for p in players:
    k = (p["name"].lower(), p["sport"])
    if k not in seen: seen.add(k); uniq.append(p)
json.dump({"players": uniq}, open(OUT, "w"), indent=1)
print(f"wrote {OUT}: {len(uniq)} players ({sum(p['sport']=='NFL' for p in uniq)} NFL, {sum(p['sport']=='NHL' for p in uniq)} NHL)")
