#!/usr/bin/env python3
"""공개 콘텐츠 페이지의 지식 색인(kg-raw)을 모아 분야별 온톨로지 지도 데이터 data/ontology.json 을 만든다.

  python3 scripts/build_ontology.py            # GitHub에서 받아 만든다 (Actions에서 매일)
  python3 scripts/build_ontology.py --repos-dir DIR   # 로컬 저장소 사본(<DIR>/<저장소>/)으로 만든다

읽는 것: data/repos.json(어느 페이지에 #kg가 있는지), data/catalog.json(공개 콘텐츠와 분야)
공개 카탈로그에 있는 저장소만 넣는다. 표준 라이브러리만 쓴다.
"""
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
              "BioAnalogue", "Assumption"}   # 지식 개념만 지도에 넣는다 (주장·퀴즈·실험·한계·문헌 등은 뺀다)
MAX_LABEL = 60
MAX_DEF = 110


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repos-dir")
    a = ap.parse_args()
    read = local_reader(a.repos_dir) if a.repos_dir else fetch_raw

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
                    "title": short(re.sub(r"<[^>]+>", "", t.group(1)) if t else r.get("site_title") or r["repo"], 80),
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
            for ed in kg.get("edges", []):
                s, o = ed.get("s"), ed.get("o")
                if s in ids and o in ids and s != o:
                    k = (s, o)
                    if k not in edges:
                        edges[k] = [s, o, (ed.get("p") or "").replace("lab:", "")]
            page["n"] = len(ids)
            pages.append(page)

    # 분야별 총계
    totals = []
    for c in cats:
        ps = [p for p in pages if p["cat"] == c["name"]]
        ns = [n for n in nodes.values() if c["name"] in n["c"]]
        es = [e for e in edges.values() if c["name"] in nodes[e[0]]["c"] and c["name"] in nodes[e[1]]["c"]]
        if not ps:
            continue
        totals.append({"cat": c["name"], "color": c.get("color") or "#888", "contents": len({p["repo"] for p in ps}),
                       "pages": len(ps), "concepts": len(ns), "relations": len(es)})
    shared = sum(1 for n in nodes.values() if len(n["c"]) > 1)
    out = {
        "updated": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d"),
        "summary": {"fields": len(totals), "contents": len({p["repo"] for p in pages}), "pages": len(pages),
                    "concepts": len(nodes), "relations": len(edges), "shared": shared},
        "fields": totals,
        "pages": pages,
        "nodes": list(nodes.values()),
        "edges": list(edges.values()),
    }
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
    print("data/ontology.json: 분야 %d · 콘텐츠 %d · 페이지 %d · 개념 %d · 관계 %d (받지 못한 페이지 %d)" % (
        len(totals), out["summary"]["contents"], len(pages), len(nodes), len(edges), missing))
    return 0


if __name__ == "__main__":
    sys.exit(main())
