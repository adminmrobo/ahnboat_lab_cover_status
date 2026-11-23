#!/usr/bin/env python3
"""'Reon Ahn Page 지식 노드 현황' 데이터를 만든다 (growth.html이 읽는다).

  python3 scripts/build_growth.py                 # Actions에서 build_ontology.py 다음에 실행
  python3 scripts/build_growth.py --relayout      # 배치를 처음부터 다시 계산 (모양을 새로 잡고 싶을 때만)

읽는 것
  data/ontology.json       공개 콘텐츠의 지식 노드(개념·방법·지표 등)와 관계, 노드가 나오는 페이지
  data/growth_dates.json   페이지별 첫 공개 시각 기록 (없는 페이지만 새로 찾는다)
  data/growth_layout.json  지난번 노드 좌표 (있던 노드는 제자리, 새 노드만 자리를 잡는다)
만드는 것
  data/growth.json         화면용 데이터 (노드·관계·페이지·기간 해석 숫자: 이번 주 → 없으면 이번 달 → 없으면 이번 분기)
  data/growth_dates.json, data/growth_layout.json  (위 두 기록을 갱신)

페이지의 첫 공개 시각 = 그 HTML 파일이 해설 저장소에 처음 커밋된 시각.
처음 보는 페이지가 있는 저장소만 기록만 받는 방식(--filter=blob:none)으로 잠깐 받아 본다.
필요한 패키지: networkx, numpy
"""
import argparse
import json
import math
import os
import random
import subprocess
import sys
import tempfile
import urllib.parse
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

import networkx as nx
import numpy as np

OWNER = "adminmrobo"
KST = timezone(timedelta(hours=9))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
P_ONTO = os.path.join(DATA, "ontology.json")
P_DATES = os.path.join(DATA, "growth_dates.json")
P_LAYOUT = os.path.join(DATA, "growth_layout.json")
P_OUT = os.path.join(DATA, "growth.json")


def load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save(path, obj, compact=False):
    with open(path, "w", encoding="utf-8") as f:
        if compact:
            json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
        else:
            json.dump(obj, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")


def page_key(url):
    return url.split("#")[0]


def page_file(url, repo):
    rel = urllib.parse.unquote(page_key(url).split("/%s/" % repo, 1)[-1])
    return rel or "index.html"


# ---------------------------------------------------------------- 1. 페이지 첫 공개 시각
def fill_dates(pages, dates):
    todo = defaultdict(list)
    for p in pages:
        if page_key(p["url"]) not in dates:
            todo[p["repo"]].append(p)
    if not todo:
        return 0
    found = 0
    with tempfile.TemporaryDirectory() as tmp:
        for repo, ps in sorted(todo.items()):
            d = os.path.join(tmp, repo)
            r = subprocess.run(["git", "clone", "-q", "--filter=blob:none", "--no-checkout",
                                "https://github.com/%s/%s" % (OWNER, repo), d],
                               capture_output=True, env=dict(os.environ, GIT_LFS_SKIP_SMUDGE="1"))
            if r.returncode != 0:
                print("  기록을 받지 못함:", repo, file=sys.stderr)
                continue
            first_any = subprocess.run(["git", "-C", d, "log", "--reverse", "--format=%aI"],
                                       capture_output=True, text=True).stdout.split()
            for p in ps:
                out = subprocess.run(["git", "-C", d, "log", "--diff-filter=A", "--reverse", "--format=%aI",
                                      "--", page_file(p["url"], repo)], capture_output=True, text=True).stdout.split()
                when = out[0] if out else (first_any[0] if first_any else None)
                if when:
                    dates[page_key(p["url"])] = when
                    found += 1
    return found


# ---------------------------------------------------------------- 2. 배치
def full_layout(nodes, edges, order):
    random.seed(7)
    G = nx.Graph()
    G.add_nodes_from(range(len(nodes)))
    G.add_edges_from(edges, weight=1.0)
    hub = {}
    for i, f in enumerate(order):
        ang = 2 * math.pi * i / len(order) - math.pi / 2
        hub[f] = (1.55 * math.cos(ang), 1.0 * math.sin(ang))
        G.add_node("H%d" % i)
        for j, n in enumerate(nodes):
            if n["cat"] == f:
                G.add_edge("H%d" % i, j, weight=0.06)
    pos0 = {j: (hub[n["cat"]][0] + random.gauss(0, .25), hub[n["cat"]][1] + random.gauss(0, .25))
            for j, n in enumerate(nodes)}
    for i, f in enumerate(order):
        pos0["H%d" % i] = hub[f]
    k = 0.05
    pos = nx.spring_layout(G, pos=pos0, fixed=["H%d" % i for i in range(len(order))],
                           k=k, iterations=150, weight="weight", seed=7)
    xy = np.array([pos[j] for j in range(len(nodes))])
    mean = xy.mean(axis=0)
    s = float(np.percentile(np.abs(xy[:, 0] - mean[0]), 99)) or 1.0
    xy = (xy - mean) / s
    hubs = {f: [(hub[f][0] - mean[0]) / s, (hub[f][1] - mean[1]) / s] for f in order}
    return xy, {"order": order, "hubs": hubs, "k": k / s}


def grow_layout(nodes, edges, prev):
    """있던 노드는 그대로 두고, 새 노드만 이웃 가까이에 놓은 뒤 조금 다듬는다."""
    random.seed(11)
    old = prev["pos"]
    hubs = prev["hubs"]
    nb = defaultdict(list)
    for a, b in edges:
        nb[a].append(b)
        nb[b].append(a)
    xy = np.zeros((len(nodes), 2))
    known = np.zeros(len(nodes), bool)
    for j, n in enumerate(nodes):
        if n["id"] in old:
            xy[j] = old[n["id"]]
            known[j] = True
    new = [j for j in range(len(nodes)) if not known[j]]
    if not new:
        return xy
    for j in new:
        near = [xy[m] for m in nb[j] if known[m]]
        base = np.mean(near, axis=0) if near else np.array(hubs[nodes[j]["cat"]])
        xy[j] = base + np.array([random.gauss(0, .04 if near else .15), random.gauss(0, .04 if near else .15)])
    G = nx.Graph()
    G.add_nodes_from(range(len(nodes)))
    G.add_edges_from(edges, weight=1.0)
    for i, f in enumerate(prev["order"]):
        G.add_node("H%d" % i)
        for j in new:
            if nodes[j]["cat"] == f:
                G.add_edge("H%d" % i, j, weight=0.06)
    pos0 = {j: tuple(xy[j]) for j in range(len(nodes))}
    for i, f in enumerate(prev["order"]):
        pos0["H%d" % i] = tuple(hubs[f])
    fixed = [j for j in range(len(nodes)) if known[j]] + ["H%d" % i for i in range(len(prev["order"]))]
    pos = nx.spring_layout(G, pos=pos0, fixed=fixed, k=prev["k"], iterations=60, weight="weight", seed=11)
    for j in new:
        xy[j] = pos[j]
    return xy


# ---------------------------------------------------------------- 3. 기간 숫자 (해석 문장 재료)
# 이번 주에 새 노드가 없으면 이번 달, 이번 달에도 없으면 이번 분기로 본다.
def _month_start(y, m):
    while m < 1:
        y, m = y - 1, m + 12
    while m > 12:
        y, m = y + 1, m - 12
    return datetime(y, m, 1, tzinfo=KST)


def period_bounds(kind, now):
    """(이번 기간 시작, 끝(제외), 지난 기간 시작, 묶음 시작 목록)"""
    k = now.astimezone(KST)
    if kind == "week":
        a = datetime(k.year, k.month, k.day, tzinfo=KST) - timedelta(days=k.weekday())
        b, pa = a + timedelta(days=7), a - timedelta(days=7)
        cuts = [a + timedelta(days=d) for d in range(7)]
    elif kind == "month":
        a, b, pa = _month_start(k.year, k.month), _month_start(k.year, k.month + 1), _month_start(k.year, k.month - 1)
        cuts, c = [], a
        while c < b:                      # 1일부터 7일씩 끊은 '몇째 주'
            cuts.append(c)
            c += timedelta(days=7)
    else:
        q0 = (k.month - 1) // 3 * 3 + 1
        a, b, pa = _month_start(k.year, q0), _month_start(k.year, q0 + 3), _month_start(k.year, q0 - 3)
        cuts = [_month_start(k.year, q0 + i) for i in range(3)]
    return a, b, pa, cuts


def period_stats(kind, nodes, edges, order, pages, now):
    a, b, pa, cuts = period_bounds(kind, now)
    ws, we, pws = a.timestamp(), b.timestamp(), pa.timestamp()
    cur = [j for j, n in enumerate(nodes) if ws <= n["t"] < we]
    prv = [j for j, n in enumerate(nodes) if pws <= n["t"] < ws]
    by = Counter(order.index(nodes[j]["cat"]) for j in cur)
    pby = Counter(order.index(nodes[j]["cat"]) for j in prv)
    curset = set(cur)
    cross, deg = Counter(), Counter()
    for x, y in edges:
        deg[x] += 1
        deg[y] += 1
        if (x in curset or y in curset) and nodes[x]["cat"] != nodes[y]["cat"]:
            fa, fb = sorted((order.index(nodes[x]["cat"]), order.index(nodes[y]["cat"])))
            cross[(fa, fb)] += 1
    top_link = list(cross.most_common(1)[0][0]) + [cross.most_common(1)[0][1]] if cross else None
    top_nodes = sorted(cur, key=lambda j: (-deg[j], nodes[j]["ko"]))[:2]
    edges_in = sum(1 for x, y in edges if ws <= max(nodes[x]["t"], nodes[y]["t"]) < we)
    bounds = [c.timestamp() for c in cuts] + [we]
    buckets = [[cuts[i].date().isoformat(), sum(1 for j in cur if bounds[i] <= nodes[j]["t"] < bounds[i + 1])]
               for i in range(len(cuts))]
    return {
        "kind": kind,
        "start": a.date().isoformat(),
        "end": b.date().isoformat(),          # 끝 날짜는 포함하지 않음
        "nodes": len(cur), "prev_nodes": len(prv),
        "by_field": [by.get(i, 0) for i in range(len(order))],
        "prev_by_field": [pby.get(i, 0) for i in range(len(order))],
        "top_link": top_link,
        "top_nodes": [[nodes[j]["ko"], nodes[j]["en"], deg[j]] for j in top_nodes],
        "pages": sum(1 for p in pages if ws <= p["t"] < we),
        "edges": edges_in,
        "buckets": buckets,
    }


def choose_period(nodes, edges, order, pages, now):
    for kind in ("week", "month", "quarter"):
        st = period_stats(kind, nodes, edges, order, pages, now)
        if st["nodes"] or kind == "quarter":
            return st


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--relayout", action="store_true", help="배치를 처음부터 다시 계산")
    ap.add_argument("--now", help="기준 시각(ISO, 시험용)")
    args = ap.parse_args()
    now = datetime.fromisoformat(args.now) if args.now else datetime.now(KST)

    onto = load(P_ONTO, None)
    if not onto or not onto.get("nodes"):
        print("ontology.json이 없거나 비어 있어 건너뜀")
        return
    dates = load(P_DATES, {})
    got = fill_dates(onto["pages"], dates)
    save(P_DATES, dates)

    pages = {}
    for p in onto["pages"]:
        when = dates.get(page_key(p["url"]))
        if when:
            pages[p["id"]] = dict(p, t=datetime.fromisoformat(when).timestamp())
    color = {f["cat"]: f["color"] for f in onto["fields"]}

    nodes, idx = [], {}
    for n in onto["nodes"]:
        pids = [x[0] for x in n.get("p", []) if x[0] in pages]
        if not pids:
            continue
        first = min(pids, key=lambda q: pages[q]["t"])
        cat = (n.get("c") or [pages[first]["cat"]])[0]
        if cat not in color:
            cat = pages[first]["cat"]
        if cat not in color:
            continue
        idx[n["id"]] = len(nodes)
        nodes.append({"id": n["id"], "ko": n.get("ko") or n.get("en") or n["id"].split("/")[-1],
                      "en": n.get("en") or n.get("ko") or n["id"].split("/")[-1],
                      "t": pages[first]["t"], "cat": cat, "page": first,
                      "dom": (n.get("d") or (pages[first].get("d") or ["ai"]))[0]})
    seen, edges = set(), []
    for a, b, _rel in onto["edges"]:
        if a in idx and b in idx and a != b:
            k = (min(idx[a], idx[b]), max(idx[a], idx[b]))
            if k not in seen:
                seen.add(k)
                edges.append(k)

    prev = load(P_LAYOUT, None)
    fields_now = sorted({n["cat"] for n in nodes})
    if args.relayout or not prev or not set(fields_now) <= set(prev.get("order", [])):
        # 분야 순서: 서로 이어진 관계가 많은 분야끼리 이웃하게
        fields = [f["cat"] for f in onto["fields"] if f["cat"] in fields_now]
        cross = Counter()
        for a, b in edges:
            ca, cb = nodes[a]["cat"], nodes[b]["cat"]
            if ca != cb:
                cross[(ca, cb)] += 1
                cross[(cb, ca)] += 1
        order = [fields[0]]
        while len(order) < len(fields):
            order.append(max((f for f in fields if f not in order), key=lambda f: cross[(order[-1], f)]))
        xy, lay = full_layout(nodes, edges, order)
        print("배치: 처음부터 계산")
    else:
        lay = {k: prev[k] for k in ("order", "hubs", "k")}
        xy = grow_layout(nodes, edges, prev)
        order = lay["order"]
        print("배치: 있던 노드는 제자리, 새 노드 %d개 자리 잡기" % sum(1 for n in nodes if n["id"] not in prev["pos"]))
    lay["pos"] = {n["id"]: [round(float(xy[j, 0]), 4), round(float(xy[j, 1]), 4)] for j, n in enumerate(nodes)}
    save(P_LAYOUT, lay, compact=True)

    deg = [0] * len(nodes)
    for a, b in edges:
        deg[a] += 1
        deg[b] += 1
    t0 = min(n["t"] for n in nodes)
    plist = sorted({n["page"] for n in nodes} | set(pages), key=lambda q: pages[q]["t"])
    pidx = {q: i for i, q in enumerate(plist)}
    out = {
        "t0": datetime.fromtimestamp(t0, KST).isoformat(),
        "built": now.astimezone(KST).isoformat(timespec="minutes"),
        "fields": [{"name": f, "color": color[f]} for f in order],
        "nodes": [[lay["pos"][n["id"]][0], lay["pos"][n["id"]][1], order.index(n["cat"]),
                   round((n["t"] - t0) / 86400, 4), deg[j], n["ko"], n["en"], pidx[n["page"]]]
                  for j, n in enumerate(nodes)],
        "edges": [list(e) for e in edges],
        "pages": [[pages[q]["title"], pages[q]["repo"], pages[q]["url"], round((pages[q]["t"] - t0) / 86400, 4),
                   order.index(pages[q]["cat"]) if pages[q]["cat"] in order else 0] for q in plist],
        "period": choose_period(nodes, edges, order, [pages[q] for q in plist], now),
    }
    # 학문 분야로 보기 (세 창 전체 보기의 '보는 기준'): 노드의 첫 학문 분야로 색·기간 통계를 한 벌 더
    doms = [d for d in (onto.get("domains") or []) if d.get("concepts")]
    if doms:
        dcode = [d["code"] for d in doms]
        nodes_d = [dict(n, cat=(n["dom"] if n["dom"] in dcode else dcode[0])) for n in nodes]
        pages_d = [dict(pages[q], cat=((pages[q].get("d") or [dcode[0]])[0])) for q in plist]
        out["domains"] = [{"name": d["ko"], "en": d["en"], "code": d["code"], "color": d["color"]} for d in doms]
        out["nd"] = [dcode.index(n["cat"]) for n in nodes_d]
        out["pd"] = [dcode.index(p["cat"]) if p["cat"] in dcode else 0 for p in pages_d]
        out["period_dom"] = period_stats(out["period"]["kind"], nodes_d, edges, dcode, pages_d, now)
    old = load(P_OUT, {})
    if {k: v for k, v in old.items() if k != "built"} == json.loads(json.dumps({k: v for k, v in out.items() if k != "built"})):
        print("지식 노드 자료 변화 없음 — growth.json 그대로 둠")
    else:
        save(P_OUT, out, compact=True)
    w = out["period"]
    print("지식 노드 %d · 관계 %d · 페이지 %d (새로 찾은 날짜 %d) · %s +%d"
          % (len(nodes), len(edges), len(plist), got, w["kind"], w["nodes"]))


if __name__ == "__main__":
    main()
