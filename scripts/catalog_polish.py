#!/usr/bin/env python3
"""카드 다듬기 — 공개 카드에 빈 그림 · 빈 소개 · 깨진 글자가 나가지 않게 한다.

build_hub.py가 현황판 항목을 만든 직후 polish()를 부른다. 그래서 현황판(hub.json),
공개 카탈로그(catalog.json), 서버실(servers.csv)에 같은 결과가 들어간다.

  1. 글자: &#x27; · &amp; 같은 HTML 글자 표기를 실제 글자로 (제목·소개·분류·챕터)
  2. 제목: 비었거나 저장소 이름 그대로면 → data/catalog_fill.json의 title → 사이트 제목(title_ko)
  3. 소개: 비었거나 너무 짧으면(5자 이하) → catalog_fill.json의 summary → 첫 페이지 소개 문장(site_desc)
  4. 그림(저장소 콘텐츠만): 비었거나, 적힌 그림이 저장소에 없으면 →
     catalog_fill.json의 thumb → 그 중분류 그림 → 대분류 그림
     (외부 콘텐츠는 원래대로 그림 없이 얇은 띠 카드)

현황판의 값이 있으면 언제나 현황판 값이 우선이다. catalog_fill.json은 공개 평문(카드에 보이는 글뿐).

이미 만들어진 공개 파일만 바로 고칠 때:
  python3 scripts/catalog_polish.py      # data/catalog.json · data/servers.csv 다시 쓰기
"""
import csv
import html
import io
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
FILL = os.path.join(DATA, "catalog_fill.json")
THUMB_INDEX = os.path.join(ROOT, "thumbs", "repos", "_index.json")
ENT = re.compile(r"&(#[0-9]+|#x[0-9a-fA-F]+|[A-Za-z]{2,8});")
MIN_SUMMARY = 6


def _load(p, d):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return d


def unescape(t):
    if not isinstance(t, str) or "&" not in t:
        return t
    for _ in range(3):
        u = html.unescape(t)
        if u == t:
            break
        t = u
    return t


def repo_of(it):
    if it.get("repo"):
        return it["repo"]
    m = re.search(r"github\.com/[^/]+/([^/?#]+)", it.get("repo_url") or "")
    return m.group(1) if m else ""


def _clean_title(t):
    """'A — B (목차) — B' 처럼 뒤에 붙은 같은 말 반복을 줄인다."""
    t = unescape((t or "").strip())
    parts = [p.strip() for p in t.split(" — ")]
    if len(parts) >= 3 and parts[-1] and parts[-1] in parts[-2]:
        parts = parts[:-1]
    t = " — ".join(parts)
    return re.sub(r"\s*\((목차|index)\)\s*$", "", t)


def _local_ok(path):
    return bool(path) and (path.startswith("http") or os.path.exists(os.path.join(ROOT, path)))


def polish(items, repos_by_name, cats, mids, fill=None):
    """items(현황판 항목 또는 공개 카드)를 그 자리에서 고친다. 고친 칸 수를 돌려준다."""
    fill = _load(FILL, {}) if fill is None else fill
    fills = fill.get("items", fill)
    idx = _load(THUMB_INDEX, {})
    cat_img = {c.get("name"): c.get("image") for c in cats or []}
    mid_img = {(m.get("cat"), m.get("name")): m.get("image") for m in mids or []}
    n = 0
    for it in items:
        for k in ("title", "summary", "mid", "sub"):
            v = unescape(it.get(k))
            if v != it.get(k):
                it[k] = v
                n += 1
        for ch in it.get("chapters") or []:
            for k in ("title", "summary"):
                if isinstance(ch.get(k), str):
                    ch[k] = unescape(ch[k])
        repo = repo_of(it)
        f = fills.get(repo) or {}
        r = repos_by_name.get(repo) or {}
        # 제목
        t = (it.get("title") or "").strip()
        if not t or (repo and t == repo):
            nt = f.get("title") or _clean_title(r.get("title_ko") or r.get("site_title") or "")
            if nt:
                it["title"] = nt
                n += 1
        elif f.get("title"):
            pass
        # 소개
        s = (it.get("summary") or "").strip()
        if len(s) < MIN_SUMMARY:
            ns = f.get("summary") or unescape(r.get("site_desc") or "")
            if ns and len(ns) >= MIN_SUMMARY:
                it["summary"] = ns
                n += 1
        # 그림 (저장소 콘텐츠만)
        if it.get("kind", "repo") != "repo":
            continue
        th = it.get("thumb") or ""
        broken = (th.startswith("http") and "github.io/%s/" % repo in th
                  and repo in idx and not (idx.get(repo) or {}).get("src"))
        if th and not th.startswith("http") and not os.path.exists(os.path.join(ROOT, th)):
            broken = True
        if not th or broken:
            for cand in (f.get("thumb"), mid_img.get((it.get("cat"), it.get("mid"))), cat_img.get(it.get("cat"))):
                if cand and _local_ok(cand):
                    it["thumb"] = cand
                    n += 1
                    break
            else:
                if broken:
                    it["thumb"] = ""
    return n


def missing_mids(items, mids):
    """공개 콘텐츠가 쓰는 (대분류, 중분류) 가운데 중분류 카드 정보가 없는 것 → 자동 카드.
    그림은 그 갈래의 첫 저장소 표지(로컬 파일), 소개는 비워 둔다. hub_meta.json에 적으면 그쪽이 쓰인다."""
    have = {(m.get("cat"), m.get("name")) for m in mids or []}
    out, seen = [], set()
    for it in items:
        key = (it.get("cat"), it.get("mid") or "기타")
        if key in have or key in seen:
            continue
        seen.add(key)
        grp = [i for i in items if (i.get("cat"), i.get("mid") or "기타") == key]
        img = next((i["thumb"] for i in grp if i.get("thumb") and not i["thumb"].startswith("http")
                    and "thumbs/cats/" not in i["thumb"] and os.path.exists(os.path.join(ROOT, i["thumb"]))), "")
        if not img:
            img = next((i["thumb"] for i in grp if i.get("thumb")), "")
        out.append({"cat": key[0], "name": key[1], "id": "", "desc": "", "keywords": [], "image": img, "auto": True})
    return out


def _repos():
    scan = _load(os.path.join(DATA, "repos.json"), [])
    repos = scan.get("repos", scan) if isinstance(scan, dict) else scan
    return {r["repo"]: r for r in repos}


def main():
    by = _repos()
    cat_p = os.path.join(DATA, "catalog.json")
    cat = _load(cat_p, None)
    if cat:
        n = polish(cat["items"], by, cat.get("categories"), cat.get("mids"))
        with open(cat_p, "w", encoding="utf-8") as f:
            json.dump(cat, f, ensure_ascii=False, indent=1)
        print("catalog.json %d칸 고침" % n)
        # 서버실 목록: 같은 제목·소개로
        srv_p = os.path.join(DATA, "servers.csv")
        if os.path.exists(srv_p):
            with open(srv_p, encoding="utf-8-sig") as f:
                text = f.read()
            rows = list(csv.DictReader(io.StringIO(text)))
            cols = list(rows[0].keys()) if rows else []
            by_url = {(i.get("site_url") or i.get("link") or ""): i for i in cat["items"]}
            m = 0
            for row in rows:
                for k in ("제목", "내용소개"):
                    v = unescape(row.get(k))
                    if v != row.get(k):
                        row[k] = v
                        m += 1
                i = by_url.get(row.get("비고") or "")
                if i:
                    if not (row.get("내용소개") or "").strip() and i.get("summary"):
                        row["내용소개"] = i["summary"]
                        m += 1
                    if row.get("제목") != i.get("title") and re.fullmatch(r"[\w\-]+", row.get("제목") or ""):
                        row["제목"] = i["title"]
                        m += 1
            with open(srv_p, "w", encoding="utf-8-sig", newline="") as f:
                w = csv.DictWriter(f, fieldnames=cols)
                w.writeheader()
                w.writerows(rows)
            print("servers.csv %d칸 고침" % m)


if __name__ == "__main__":
    main()
