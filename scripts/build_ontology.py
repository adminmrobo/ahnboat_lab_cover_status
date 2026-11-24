#!/usr/bin/env python3
"""공개 콘텐츠 페이지의 지식 색인(kg-raw)을 모아 분야별 온톨로지 지도 데이터 data/ontology.json 을 만든다.

  python3 scripts/build_ontology.py            # GitHub에서 받아 만든다 (Actions에서 매일)
  python3 scripts/build_ontology.py --repos-dir DIR   # 로컬 저장소 사본(<DIR>/<저장소>/)으로 만든다

읽는 것: data/repos.json(어느 페이지에 #kg가 있는지), data/catalog.json(공개 콘텐츠와 분야),
        data/content_domains.json(콘텐츠 → 학문 분야),
        스킬 저장소 ahnboat_lab_explainer의 data/domains.json·backbone_*.json(학문 분야 등록부와 뼈대)
공개 카탈로그에 있는 저장소만 넣는다. 표준 라이브러리만 쓴다.

분야는 두 가지다.
  fields  — 콘텐츠 분류(서버랙 8개). 노드의 c
  domains — 학문 분야(등록부 18개). 노드의 d. 노드 자신의 domain → 뼈대 주제(broader·이름 맞춤) → 콘텐츠의 주 분야 순으로 정한다.
뼈대 주제와 이름이 맞는 노드는 data/crosswalk.json에 후보로 남긴다(다시 걸기용, ai-lab-retrofit 15장).
"""
import html
import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request

OWNER = "adminmrobo"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(DATA, "ontology.json")
KG_RAW = re.compile(r'<script[^>]*\bid\s*=\s*["\']kg-raw["\'][^>]*>(.*?)</script>', re.S | re.I)
TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.S | re.I)
KEEP_TYPES = {"Concept", "Method", "Term", "Metric", "Dataset", "Account", "Standard", "Identity", "Theory",
              "BioAnalogue", "Assumption", "Distribution", "Indicator", "Framework",
              "Definition", "Theorem", "Axiom", "Structure", "Estimator"}   # 지식 개념만 지도에 넣는다 (주장·퀴즈·실험·한계·문헌 등은 뺀다)
MAX_LABEL = 60
MAX_DEF = 110
SKILL_REPO = "ahnboat_lab_explainer"
TAXO_CACHE = os.path.join(DATA, "taxonomy_cache.json")   # 스킬 저장소를 못 읽을 때 쓰는 마지막 사본
XWALK = os.path.join(DATA, "crosswalk.json")


def load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def fetch_raw(repo, branch, path):
    url = "https://raw.githubusercontent.com/%s/%s/%s/%s" % (OWNER, repo, branch, urllib.parse.quote(path))
    r = urllib.request.Request(url, headers={"User-Agent": "ahnboat-ontology"})
    try:
        with urllib.request.urlopen(r, timeout=60) as resp:
            return resp.read().decode("utf-8", "replace")
    except Exception:
        return None


def local_reader(repos_dir):
    def read(repo, branch, path):
        p = subprocess.run(["git", "-C", os.path.join(repos_dir, repo), "show", "HEAD:" + path], capture_output=True)
        return p.stdout.decode("utf-8", "replace") if p.returncode == 0 else None
    return read


def page_paths(url, pages_url):
    rel = urllib.parse.unquote(url.split("#")[0][len(pages_url):]) or "index.html"
    if rel.endswith("/"):
        rel += "index.html"
    return [rel, "docs/" + rel]


def short(s, n):
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def label(lbl):
    if isinstance(lbl, dict):
        ko = lbl.get("ko") or next(iter(lbl.values()), "")
        return short(ko, MAX_LABEL), short(lbl.get("en") or "", MAX_LABEL)
    return short(lbl, MAX_LABEL), ""


def norm_name(s):
    s = re.sub(r"\([^)]*\)", "", str(s or "")).lower()
    return re.sub(r"[\s·\-–—_,./'’\"“”:;!?]+", "", s)


def name_keys(label):
    """주제 이름의 맞춤 열쇠: 전체, 괄호 안, '·'로 나눈 조각(3글자 이상)"""
    out = set()
    for v in (label.get("ko"), label.get("en")):
        if not v:
            continue
        out.add(norm_name(v))
        for m in re.findall(r"\(([^)]*)\)", v):
            if len(norm_name(m)) >= 3:
                out.add(norm_name(m))
    return {k for k in out if len(k) >= 2}


def load_taxonomy(skill_dir):
    """학문 분야 등록부와 뼈대를 읽는다. 스킬 저장소 → 마지막 사본 순."""
    def rd(path):
        if skill_dir:
            try:
                with open(os.path.join(skill_dir, path), encoding="utf-8") as f:
                    return json.load(f)
            except (OSError, ValueError):
                return None
        t = fetch_raw(SKILL_REPO, "main", path)
        try:
            return json.loads(t) if t else None
        except ValueError:
            return None
    reg = rd("data/domains.json")
    if reg:
        files = sorted({d["backbone"] for d in reg["domains"] if d.get("backbone")} | {"data/backbone_bridge.json"})
        bbs = {f: rd(f) for f in files}
        if all(bbs.get(f) for f in files):
            taxo = {"domains": reg["domains"], "backbones": bbs}
            with open(TAXO_CACHE, "w", encoding="utf-8") as f:
                json.dump(taxo, f, ensure_ascii=False, separators=(",", ":"))
            return taxo
    print("학문 분야 등록부를 스킬 저장소에서 읽지 못해 마지막 사본을 씀", file=sys.stderr)
    return load(TAXO_CACHE, {"domains": [], "backbones": {}})


def topic_index(taxo):
    """뼈대 주제·영역 → (분야 코드 목록, 영역 id, 이름). 인공지능 뼈대는 영역별 렌즈(ml·dl 등)도 붙인다."""
    lens = {}
    for d in taxo["domains"]:
        for a in (d.get("backbone_areas") or []) + (d.get("backbone_areas_extra") or []):
            lens.setdefault(a, []).append(d["code"])
    owner = {}
    for d in taxo["domains"]:
        if d.get("backbone") and not d.get("backbone_areas"):
            owner[d["backbone"]] = d["code"]
    topics, keys = {}, {}
    for f, bb in taxo["backbones"].items():
        if not bb or "nodes" not in bb:
            continue
        code = owner.get(f)
        up = {e["s"]: e["o"] for e in bb.get("edges", []) if e.get("p") == "lab:broader"}
        for n in bb["nodes"]:
            area = n["id"] if n["type"] == "Area" else up.get(n["id"])
            ds = [code] if code else []
            for c in lens.get(area, []):
                if c not in ds:
                    ds.append(c)
            topics[n["id"]] = {"id": n["id"], "type": n["type"], "area": area, "d": ds,
                               "ko": n["label"].get("ko", ""), "en": n["label"].get("en", "")}
            if n["type"] == "Topic":
                for k in name_keys(n["label"]):
                    keys.setdefault(k, []).append(n["id"])
    return topics, keys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repos-dir")
    ap.add_argument("--skill-dir", help="스킬 저장소 사본(없으면 GitHub에서 읽음)")
    a = ap.parse_args()
    read = local_reader(a.repos_dir) if a.repos_dir else fetch_raw
    taxo = load_taxonomy(a.skill_dir)
    TOP, KEYS = topic_index(taxo)
    DOM = {d["code"]: d for d in taxo["domains"]}
    cdom = load(os.path.join(DATA, "content_domains.json"), {}).get("map", {})
    declared, linked = {}, {}   # 노드 → 페이지가 적은 domain, 페이지가 건 뼈대 주제

    catalog = load(os.path.join(DATA, "catalog.json"), {})
    repos = load(os.path.join(DATA, "repos.json"), [])
    cats = [c for c in catalog.get("categories", [])]
    public = {}
    for it in catalog.get("items", []):
        m = re.search(r"github\.com/%s/([^/?#]+)" % OWNER, it.get("repo_url") or "")
        if m and m.group(1) not in public:
            public[m.group(1)] = it

    pages, nodes, edges, missing = [], {}, {}, 0
    for r in repos:
        it = public.get(r["repo"])
        onto = r.get("ontology") or {}
        if not it or not onto.get("kg_links"):
            continue
        for link in onto["kg_links"]:
            url = link.split("#")[0]
            text = None
            for p in page_paths(url, r["pages_url"]):
                text = read(r["repo"], r.get("default_branch") or "main", p)
                if text and KG_RAW.search(text):
                    break
            m = KG_RAW.search(text or "")
            if not m:
                missing += 1
                continue
            try:
                kg = json.loads(m.group(1))
            except ValueError:
                missing += 1
                continue
            t = TITLE.search(text)
            pid = "P%03d" % len(pages)
            page = {"id": pid, "repo": r["repo"], "url": url, "cat": it["cat"],
                    "d": [c for c in cdom.get(r["repo"], []) if c in DOM],
                    "title": short(html.unescape(re.sub(r"<[^>]+>", "", t.group(1))) if t else r.get("site_title") or r["repo"], 80),
                    "content": it["title"], "n": 0}
            ids = set()
            for n in kg.get("nodes", []):
                if n.get("type") not in KEEP_TYPES or not n.get("id"):
                    continue
                ko, en = label(n.get("label"))
                if not ko:
                    continue
                d = n.get("definition")
                d = d.get("ko") if isinstance(d, dict) else d
                e = nodes.get(n["id"])
                if not e:
                    e = nodes[n["id"]] = {"id": n["id"], "t": n.get("type") or "Concept", "ko": ko, "en": en,
                                          "def": short(d, MAX_DEF), "p": [], "c": []}
                elif not e["def"] and d:
                    e["def"] = short(d, MAX_DEF)
                if pid not in [x[0] for x in e["p"]]:
                    e["p"].append([pid, n.get("anchor") or ""])
                if it["cat"] not in e["c"]:
                    e["c"].append(it["cat"])
                ids.add(n["id"])
                for dm in (n.get("domain") or []) if isinstance(n.get("domain"), list) else []:
                    if dm in DOM:
                        declared.setdefault(n["id"], [])
                        if dm not in declared[n["id"]]:
                            declared[n["id"]].append(dm)
            for ed in kg.get("edges", []):
                if (ed.get("p") or "").replace("lab:", "") == "broader" and ed.get("s") in ids and ed.get("o") in TOP:
                    linked.setdefault(ed["s"], set()).add(ed["o"])
                s, o = ed.get("s"), ed.get("o")
                if s in ids and o in ids and s != o:
                    k = (s, o)
                    if k not in edges:
                        edges[k] = [s, o, (ed.get("p") or "").replace("lab:", "")]
            page["n"] = len(ids)
            pages.append(page)

    # 학문 분야 정하기: 노드 자신의 domain + 뼈대 주제(페이지가 건 것 · 이름이 맞는 것) → 없으면 콘텐츠 주 분야
    PAGE = {p["id"]: p for p in pages}
    xw = []
    for n in nodes.values():
        tps = set(linked.get(n["id"], ()))
        auto = set()
        if n["id"] in TOP and TOP[n["id"]]["type"] == "Topic":
            tps.add(n["id"])
        for k in {norm_name(n["ko"]), norm_name(n["en"])}:
            for t in KEYS.get(k, []) if len(k) >= 2 else []:
                if t not in tps:
                    auto.add(t)
        cont, prim = [], []
        for pid, _ in n["p"]:
            for i, c in enumerate(PAGE[pid]["d"]):
                if c not in cont:
                    cont.append(c)
                if i == 0 and c not in prim:
                    prim.append(c)
        # 이름 맞춤은 그 개념이 나온 콘텐츠의 분야(와 상위 분야) 안에서만 믿는다.
        # 예: 신경망 페이지의 '가중치'가 표본조사 '가중치' 주제에 붙지 않게. 밖의 것은 후보 목록에만 낮은 확신으로.
        ok = set(cont) | set(declared.get(n["id"], [])) | {DOM[c].get("parent") for c in cont if c in DOM}
        weak = {t for t in auto if not set(TOP[t]["d"]) & ok}
        auto -= weak
        d = []
        for c in declared.get(n["id"], []):
            if c != "ai" and c not in d:
                d.append(c)
        for t in sorted(tps | auto):
            for c in TOP[t]["d"]:
                if c not in d:
                    d.append(c)
        for c in prim:                      # 콘텐츠의 주 분야는 늘 넣는다 (그 분야 렌즈에서 빠지지 않게)
            if c not in d:
                d.append(c)
        if not d:
            d = ["ai"] if "ai" in declared.get(n["id"], []) else []
        n["d"] = d
        if tps | auto:
            n["tp"] = sorted(tps | auto)
        for group, conf in ((auto, "mid"), (weak, "low")):
            if group:
                xw.append({"node": n["id"], "ko": n["ko"], "topics": sorted(group), "auto": True, "confidence": conf,
                           "pages": [PAGE[p]["repo"] + "/" + PAGE[p]["url"].rsplit("/", 1)[-1] for p, _ in n["p"]][:3]})

    # 학문 분야별 총계와 뼈대 커버리지
    domains = []
    for code, dm in DOM.items():
        ns = [n for n in nodes.values() if code in n["d"]]
        idn = {n["id"] for n in ns}
        es = [e for e in edges.values() if e[0] in idn and e[1] in idn]
        ps = {p for n in ns for p, _ in n["p"]}
        tps = [t for t in TOP.values() if t["type"] == "Topic" and code in t["d"]]
        hit = {}
        for n in ns:
            for t in n.get("tp", []):
                if code in TOP[t]["d"] and TOP[t]["type"] == "Topic":
                    hit[t] = hit.get(t, 0) + 1
        out_n = sum(1 for e in edges.values() if (e[0] in idn) != (e[1] in idn))
        domains.append({"code": code, "ko": dm["label"]["ko"], "en": dm["label"]["en"], "color": dm["color"],
                        "parent": dm.get("parent"), "concepts": len(ns), "relations": len(es), "bridges": out_n,
                        "pages": len(ps), "contents": len({PAGE[p]["repo"] for p in ps}),
                        "topics": len(tps), "covered": len(hit),
                        "top": [[t, TOP[t]["ko"], TOP[t]["en"], c] for t, c in sorted(hit.items(), key=lambda x: -x[1])[:12]],
                        "gaps": [[t["id"], t["ko"], t["en"]] for t in tps if t["id"] not in hit][:40]})

    # 분야별 총계
    redirect = dict(load(os.path.join(DATA, "content_domains.json"), {}).get("redirect", {}))
    for k, v in (load(os.path.join(DATA, "moved.json"), {}).get("moved") or {}).items():
        m = re.search(r"github\.com/%s/([^/?#]+)" % OWNER, v.get("repo_url") or "")
        if m:
            redirect.setdefault(k, m.group(1))
    indexed = {p["repo"] for p in pages}

    def item_repo(it):
        m = re.search(r"github\.com/%s/([^/?#]+)" % OWNER, it.get("repo_url") or "")
        r = m.group(1) if m else None
        return redirect.get(r, r)

    totals = []
    for c in cats:
        ps = [p for p in pages if p["cat"] == c["name"]]
        ns = [n for n in nodes.values() if c["name"] in n["c"]]
        es = [e for e in edges.values() if c["name"] in nodes[e[0]]["c"] and c["name"] in nodes[e[1]]["c"]]
        if not ps:
            continue
        # 콘텐츠 수는 홈페이지(카탈로그)와 같은 단위로 센다: 카탈로그 항목 가운데 지식 색인이 있는 저장소(옮긴 저장소는 새 주소)를 가리키는 것
        items = [it for it in catalog.get("items", []) if it.get("cat") == c["name"]]
        n_idx = sum(1 for it in items if item_repo(it) in indexed)
        totals.append({"cat": c["name"], "color": c.get("color") or "#888", "contents": n_idx or len({p["repo"] for p in ps}),
                       "listed": len(items),
                       "pages": len(ps), "concepts": len(ns), "relations": len(es)})
    shared = sum(1 for n in nodes.values() if len(n["c"]) > 1)
    out = {
        "updated": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d"),
        "summary": {"fields": len(totals), "contents": len({p["repo"] for p in pages}), "pages": len(pages),
                    "listed_indexed": sum(t["contents"] for t in totals), "listed": sum(t["listed"] for t in totals),
                    "concepts": len(nodes), "relations": len(edges), "shared": shared},
        "fields": totals,
        "domains": domains,
        "pages": pages,
        "nodes": list(nodes.values()),
        "edges": list(edges.values()),
    }
    out["summary"]["domains"] = sum(1 for d in domains if d["concepts"])
    out["summary"]["topic_linked"] = sum(1 for n in nodes.values() if n.get("tp"))
    xw_text = json.dumps({"note": "뼈대 주제와 이름이 맞는 노드(자동 후보). 사람이 보고 맞는 것만 해설 페이지 kg-raw에 broader로 옮긴다(ai-lab-retrofit 15-2).",
                          "count": len(xw), "items": sorted(xw, key=lambda x: x["node"])}, ensure_ascii=False, indent=0) + "\n"
    with open(XWALK, "w", encoding="utf-8") as f:
        f.write(xw_text)
    text = json.dumps(out, ensure_ascii=False, separators=(",", ":")) + "\n"
    old = None
    if os.path.exists(OUT):
        with open(OUT, encoding="utf-8") as f:
            old = f.read()
    # 날짜만 바뀐 경우는 쓰지 않는다
    if old and re.sub(r'"updated":"[^"]*"', "", old) == re.sub(r'"updated":"[^"]*"', "", text):
        print("data/ontology.json: 변경 없음")
        return 0
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(text)
    print("data/ontology.json: 분야 %d · 학문 분야 %d · 콘텐츠 %d · 페이지 %d · 개념 %d · 관계 %d · 뼈대에 걸린 개념 %d (받지 못한 페이지 %d)" % (
        len(totals), out["summary"]["domains"], out["summary"]["contents"], len(pages), len(nodes), len(edges),
        out["summary"]["topic_linked"], missing))
    return 0


if __name__ == "__main__":
    sys.exit(main())
