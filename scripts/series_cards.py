#!/usr/bin/env python3
"""시리즈 카드로 공개 카탈로그의 한 중분류를 '장(챕터)별'로 다시 묶는다 (표준 라이브러리만).

설정: data/series_cards.json  ·  카드: data/series/<시리즈>.json (시리즈 저장소의 catalog_cards.json 사본)
- build_hub.py가 catalog.json을 쓰기 직전에 apply(items)를 부른다.
- 혼자 돌리면(인자 없이) 지금 있는 data/catalog.json에 바로 반영한다 — 관리자 키 없이 카드만 고칠 때.
- --fetch 를 붙이면 각 시리즈의 source 주소에서 catalog_cards.json을 새로 받아 data/series/에 덮어쓴다.
"""
import json, os, sys, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")


def _load(p, d=None):
    try:
        with open(os.path.join(ROOT, p) if not os.path.isabs(p) else p, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return d


def fetch():
    cfg = _load("data/series_cards.json", {}) or {}
    for s in cfg.get("series", []):
        try:
            raw = urllib.request.urlopen(s["source"], timeout=20).read().decode("utf-8")
            json.loads(raw)
            with open(os.path.join(ROOT, s["cards"]), "w", encoding="utf-8") as f:
                f.write(raw)
            print("시리즈 카드 받음", s["name"])
        except Exception as e:  # 못 받으면 저장소에 있는 사본을 그대로 쓴다
            print("시리즈 카드 못 받음 (사본 사용)", s["name"], e)


def apply(items):
    cfg = _load("data/series_cards.json", {}) or {}
    for s in cfg.get("series", []):
        cards = _load(s["cards"])
        if not cards:
            continue
        groups = s["groups"]
        gidx = {}
        for gi, (gname, keys) in enumerate(groups):
            for k in keys:
                gidx[k] = gi
        rel_key = s.get("related_group", {})
        new = []
        for c in cards.get("items", []):
            gi = gidx.get(c["chap"], len(groups) - 1)
            new.append((gi, c["order"], c))
        for j, c in enumerate(cards.get("related", [])):
            gi = gidx.get(rel_key.get(c["kind"], c["chap"]), len(groups) - 1)
            new.append((gi, (0.5 if c["kind"] == "board" else 900 + j), c))
        new.sort(key=lambda x: (x[0], x[1]))
        built = [{"title": c["title"], "summary": c["summary"], "cat": s["cat"], "mid": s["mid"], "sub": groups[gi][0], "kind": "repo",
                  "repo_url": c["repo_url"], "site_url": c["site_url"], "link": "", "langs": c.get("langs", []), "thumb": c.get("thumb", "")}
                 for gi, _, c in new]
        urls = {b["site_url"] for b in built}
        pos = [i for i, it in enumerate(items) if it.get("cat") == s["cat"] and it.get("mid") == s["mid"]]
        at = pos[0] if pos else len(items)
        # 같은 중분류의 옛 항목은 카드로 바꾸고, 카드에 없는 항목(다른 저장소)은 카드 뒤에 그대로 둔다
        rest = [items[i] for i in pos if items[i].get("site_url") not in urls and not any(
            items[i].get("repo_url", "").rstrip("/") == b["repo_url"].rstrip("/") for b in built)]
        items[:] = [it for i, it in enumerate(items) if i not in set(pos)]
        items[at:at] = built + rest
    return items


if __name__ == "__main__":
    if "--fetch" in sys.argv:
        fetch()
    p = os.path.join(DATA, "catalog.json")
    cat = _load(p)
    n0 = len(cat["items"])
    apply(cat["items"])
    with open(p, "w", encoding="utf-8") as f:
        json.dump(cat, f, ensure_ascii=False, indent=1)
    print("catalog.json", n0, "→", len(cat["items"]), "항목")
