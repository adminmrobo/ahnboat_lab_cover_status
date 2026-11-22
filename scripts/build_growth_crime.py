#!/usr/bin/env python3
"""'AI 범죄학 지식 노드 현황' 데이터를 만든다 (growth_crime.html이 읽는다).

  python3 scripts/build_growth_crime.py                    # Actions에서 build_growth.py 다음에 실행
  python3 scripts/build_growth_crime.py --relayout         # 배치를 처음부터 다시 계산
  python3 scripts/build_growth_crime.py --src 파일.json    # 받지 않고 로컬 crime_kg.json으로 (시험용)

읽는 것
  ai_crime_lab 저장소의 data/crime_kg.json  AI 범죄학(crime) 뼈대 13개 영역에 건 지식 노드·관계·페이지
  data/growth_crime_dates.json   페이지별 첫 공개 시각 기록 (없는 페이지만 새로 찾는다)
  data/growth_crime_layout.json  지난번 노드 좌표 (있던 노드는 제자리, 새 노드만 자리를 잡는다)
만드는 것
  data/growth_crime.json         화면용 데이터 (growth.json과 같은 틀 · 분야 = AI 범죄학 영역)
배치·기간 계산은 build_growth.py의 함수를 그대로 쓴다. 필요한 패키지: networkx, numpy
"""
import argparse
import json
import os
import sys
import urllib.request
from collections import Counter
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_growth as BG  # noqa: E402

REPO = "ai_crime_lab"
SRC = "https://raw.githubusercontent.com/%s/%s/main/data/crime_kg.json" % (BG.OWNER, REPO)
P_DATES = os.path.join(BG.DATA, "growth_crime_dates.json")
P_LAYOUT = os.path.join(BG.DATA, "growth_crime_layout.json")
P_OUT = os.path.join(BG.DATA, "growth_crime.json")
# 영역 색 — 13개 영역을 갈래별 색조로 (기초·경제=갈색, 게임=주황, 공격 수법=붉은 계열, 감시=분홍, 대응·제도=초록·청록, 개인·미래·현장=파랑·보라)
COLOR = {
    "lab:area/ai-crime-basics": "#a0703c", "lab:area/crime-economics": "#c9952f", "lab:area/crime-games": "#e07b39",
    "lab:area/synthetic-media": "#d6453d", "lab:area/social-engineering": "#e0607e", "lab:area/automated-attacks": "#b04a8c",
    "lab:area/financial-crime": "#f2b134", "lab:area/surveillance-privacy": "#c77dd6", "lab:area/detection-response": "#2fa37a",
    "lab:area/institutions-policy": "#2a9bb5", "lab:area/personal-defense": "#4f8be8", "lab:area/future-threats": "#8a7cf0",
    "lab:area/field-verification": "#9aa8b8",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--relayout", action="store_true")
    ap.add_argument("--src")
    ap.add_argument("--now")
    a = ap.parse_args()
    now = datetime.fromisoformat(a.now) if a.now else datetime.now(BG.KST)
    try:
        if a.src:
            K = BG.load(a.src, None)
        else:
            req = urllib.request.Request(SRC, headers={"User-Agent": "ahnboat-growth-crime"})
            with urllib.request.urlopen(req, timeout=60) as r:
                K = json.loads(r.read().decode("utf-8"))
    except Exception as e:  # 못 받으면 지난번 결과를 그대로 둔다
        print("crime_kg.json을 받지 못해 건너뜀:", e)
        return
    if not K or not K.get("nodes"):
        print("crime_kg.json이 비어 있어 건너뜀")
        return

    site = K["site"]
    area_ko = {x["id"]: x["ko"] for x in K["areas"]}
    raw_pages = [{"id": p["file"], "repo": REPO, "url": site + p["file"], "title": p["title"],
                  "cat": None} for p in K["pages"]]
    dates = BG.load(P_DATES, {})
    BG.fill_dates(raw_pages, dates)
    BG.save(P_DATES, dates)
    pages = {}
    for p in raw_pages:
        when = dates.get(BG.page_key(p["url"]))
        if when:
            pages[p["id"]] = dict(p, t=datetime.fromisoformat(when).timestamp())

    nodes, idx = [], {}
    for n in K["nodes"]:
        fs = [f for f in n["files"] if f in pages]
        if not fs or n["area"] not in area_ko:
            continue
        first = min(fs, key=lambda q: pages[q]["t"])
        idx[n["id"]] = len(nodes)
        nodes.append({"id": n["id"], "ko": n["ko"], "en": n.get("en") or n["ko"], "t": pages[first]["t"],
                      "cat": area_ko[n["area"]], "page": first})
    for p in pages.values():  # 페이지의 분야 = 그 페이지 노드에서 가장 많은 영역
        c = Counter(x["cat"] for x in nodes if x["page"] == p["id"])
        p["cat"] = c.most_common(1)[0][0] if c else None
    seen, edges = set(), []
    for s, o, _ in K["edges"]:
        if s in idx and o in idx and s != o:
            k = (min(idx[s], idx[o]), max(idx[s], idx[o]))
            if k not in seen:
                seen.add(k)
                edges.append(k)

    fields_all = [area_ko[x["id"]] for x in K["areas"]]
    fields_now = [f for f in fields_all if any(n["cat"] == f for n in nodes)]
    prev = BG.load(P_LAYOUT, None)
    if a.relayout or not prev or not set(fields_now) <= set(prev.get("order", [])):
        xy, lay = BG.full_layout(nodes, edges, fields_now)   # 영역 순서 = 뼈대 순서 (기초 → 미래·현장)
        print("배치: 처음부터 계산")
    else:
        lay = {k: prev[k] for k in ("order", "hubs", "k")}
        xy = BG.grow_layout(nodes, edges, prev)
        print("배치: 새 노드 %d개 자리 잡기" % sum(1 for n in nodes if n["id"] not in prev["pos"]))
    order = lay["order"]
    lay["pos"] = {n["id"]: [round(float(xy[j, 0]), 4), round(float(xy[j, 1]), 4)] for j, n in enumerate(nodes)}
    BG.save(P_LAYOUT, lay, compact=True)

    deg = [0] * len(nodes)
    for x, y in edges:
        deg[x] += 1
        deg[y] += 1
    t0 = min(n["t"] for n in nodes)
    plist = sorted({n["page"] for n in nodes}, key=lambda q: pages[q]["t"])
    pidx = {q: i for i, q in enumerate(plist)}
    color = {area_ko[k]: v for k, v in COLOR.items() if k in area_ko}
    out = {
        "domain": "crime",
        "map": K.get("map", ""),
        "t0": datetime.fromtimestamp(t0, BG.KST).isoformat(),
        "built": now.astimezone(BG.KST).isoformat(timespec="minutes"),
        "fields": [{"name": f, "color": color.get(f, "#999")} for f in order],
        "nodes": [[lay["pos"][n["id"]][0], lay["pos"][n["id"]][1], order.index(n["cat"]),
                   round((n["t"] - t0) / 86400, 4), deg[j], n["ko"], n["en"], pidx[n["page"]]]
                  for j, n in enumerate(nodes)],
        "edges": [list(e) for e in edges],
        "pages": [[pages[q]["title"], pages[q]["repo"], pages[q]["url"], round((pages[q]["t"] - t0) / 86400, 4),
                   order.index(pages[q]["cat"]) if pages[q]["cat"] in order else 0] for q in plist],
        "period": BG.choose_period(nodes, edges, order, [pages[q] for q in plist], now),
    }
    BG.save(P_OUT, out, compact=True)
    print("growth_crime.json: 노드 %d · 관계 %d · 페이지 %d · 영역 %d" % (len(nodes), len(edges), len(plist), len(order)))


if __name__ == "__main__":
    main()
