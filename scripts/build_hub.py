#!/usr/bin/env python3
"""콘텐츠 현황판 DB를 만든다 (표준 라이브러리만 사용).

사람이 고치는 표  : data/hub.csv          (엑셀로 열어 고친 뒤 CSV로 저장)
자동으로 채우는 값: data/repos.json       (scan_repos.py가 매일 모음)
만드는 파일      : data/hub.json          (관리용 현황판이 읽음 · 저장소에는 잠긴 hub.json.enc 만 올라감)
                   data/catalog.json      (공개 카탈로그가 읽음 · 공개 항목만)
                   data/servers.csv       (랩타운 지하 1층 서버실이 읽음 · 공개 항목만)
hub.csv·hub.json 평문은 커밋하지 않는다. 잠그고 푸는 일은 hub_secure.py·hubcrypt.py가 한다.

- repos.json에 있는데 hub.csv에 없는 새 저장소는 hub.csv 맨 아래에 '미분류'로 덧붙인다.
  공개대상여부는 '검토'로 두어, 사람이 분류하기 전에는 서버실·카탈로그에 나오지 않는다.
- 외국어팩·온톨로지 현황(WIP / PROGRESS / DONE)과 콘텐츠 존재 여부는 자동으로 정한다.
"""
import csv, datetime as dt, io, json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
OWNER = "adminmrobo"
EXCLUDE_PREFIX = "newsreporter_"
EXCLUDE_NAMES = {"adminmrobo", "ahnboat_homepage_manual"}  # 관리자용 매뉴얼은 현황판·카탈로그에 넣지 않음
LANGS_FULL = 7  # 한국어 + en·zh·ja·uz·ru·vi

COLS = ["저장소", "제목", "주요내용", "콘텐츠_카테고리_대분류", "콘텐츠_카테고리_중분류", "콘텐츠_카테고리_소분류",
        "공개대상여부", "연구실_시리즈_적용대상_여부", "외국어팩대상_여부", "온톨로지_적용대상_여부", "순서", "외부링크", "비고"]
EXT = "외부:"  # GitHub 밖 실적(논문·특허·저서·사업)은 저장소 칸을 '외부:이름'으로 적는다
SERVER_LANGS = ["en", "zh", "ja", "uz", "ru"]


def load_json(p, d):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return d


def read_csv(p):
    raw = open(p, "rb").read()
    for enc in ("utf-8-sig", "cp949"):
        try:
            text = raw.decode(enc); break
        except UnicodeDecodeError:
            continue
    rows = list(csv.DictReader(io.StringIO(text)))
    return [{k.strip(): (v or "").strip() for k, v in r.items() if k} for r in rows]


def write_csv(p, cols, rows):
    with open(p, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def _url(s):
    m = re.search(r"https?://\S+", s or "")
    return m.group(0) if m else ""


def yes(v):
    return str(v).strip().upper() in ("Y", "YES", "O", "예", "네", "TRUE", "1")


def lang_status(target, r):
    if not target:
        return "-"
    i = (r or {}).get("i18n") or {}
    n = i.get("count") or 0
    if n >= LANGS_FULL and i.get("complete", True):
        return "DONE"
    if n > 1:
        return "PROGRESS"
    return "WIP"


def onto_status(target, r):
    if not target:
        return "-"
    s = ((r or {}).get("ontology") or {}).get("status")
    return {"full": "DONE", "partial": "PROGRESS"}.get(s, "WIP")


def main():
    hub_p = os.path.join(DATA, "hub.csv")
    rows = read_csv(hub_p) if os.path.exists(hub_p) else []
    meta = load_json(os.path.join(DATA, "hub_meta.json"), {})
    scan = load_json(os.path.join(DATA, "repos.json"), {})
    repos = scan.get("repos", scan) if isinstance(scan, dict) else scan
    by = {r["repo"]: r for r in repos}
    known = {r["저장소"] for r in rows}
    added = []
    for name in sorted(by):
        if name in known or name.startswith(EXCLUDE_PREFIX) or name in EXCLUDE_NAMES:
            continue
        r = by[name]
        rows.append({"저장소": name, "제목": r.get("title_ko") or r.get("site_title") or name,
                     "콘텐츠_카테고리_대분류": "미분류", "콘텐츠_카테고리_중분류": "", "콘텐츠_카테고리_소분류": "",
                     "공개대상여부": "검토", "연구실_시리즈_적용대상_여부": "", "외국어팩대상_여부": "",
                     "온톨로지_적용대상_여부": "", "비고": "새 저장소 · 분류 필요"})
        added.append(name)
    if added:
        write_csv(hub_p, COLS, rows)

    def _img(o):  # 그림 파일이 아직 없으면 비워 둔다 (카드에는 색 상자가 보인다)
        o = dict(o)
        if o.get("image") and not os.path.exists(os.path.join(ROOT, o["image"])):
            o["image"] = ""
        return o
    cats = [_img(c) for c in meta.get("categories", [])]
    meta["mids"] = [_img(m) for m in meta.get("mids", [])]
    cat_order = {c["name"]: i for i, c in enumerate(cats)}
    items = []
    for i, h in enumerate(rows):
        name = h["저장소"]
        ext = name.startswith(EXT)
        r = None if ext else by.get(name)
        public_repo = r is not None or name == "ahnboat_lab_cover_status"  # 공개 저장소만 수집됨
        has_site = bool(r and r.get("has_pages") is not False and r.get("pages_url"))
        exists = ext or bool(has_site and ((r.get("i18n") or {}).get("count") or r.get("site_title")))
        link = h.get("외부링크", "")
        lab = yes(h.get("연구실_시리즈_적용대상_여부"))
        lt = yes(h.get("외국어팩대상_여부"))
        ot = yes(h.get("온톨로지_적용대상_여부"))
        i18n = (r or {}).get("i18n") or {}
        pub = h.get("공개대상여부", "")
        items.append({
            "repo": name,
            "title": h.get("제목") or name,
            "summary": h.get("주요내용", ""),
            "cat": h.get("콘텐츠_카테고리_대분류") or "미분류",
            "mid": h.get("콘텐츠_카테고리_중분류") or "",
            "sub": h.get("콘텐츠_카테고리_소분류") or "",
            "public": "Y" if yes(pub) else ("검토" if pub == "검토" else "N"),
            "kind": "ext" if ext else "repo",
            "repo_url": "" if ext else "https://github.com/%s/%s" % (OWNER, name),
            "site_url": ((r or {}).get("pages_url") if has_site else "") or (_url(link) if ext else ""),
            "link": link,
            "visibility": "external" if ext else ("public" if public_repo else "private"),
            "exists": "Y" if exists else "N",
            "lab": "Y" if lab else "N",
            "lang_target": "Y" if lt else "N",
            "lang_status": lang_status(lt, r),
            "langs": i18n.get("langs") or [],
            "onto_target": "Y" if ot else "N",
            "onto_status": onto_status(ot, r),
            "thumb": (r or {}).get("thumb") or "",
            "pushed_at": (r or {}).get("pushed_at") or "",
            "note": h.get("비고", ""),
            "order": int(h["순서"]) if (h.get("순서") or "").isdigit() else 1000 + i,
        })
    # 옮긴 저장소·새로 넣을 저장소 (data/moved.json, hub.csv를 고치지 않아도 유지)
    mv = load_json(os.path.join(DATA, "moved.json"), {})
    for it in items:
        m = (mv.get("moved") or {}).get(it["repo"])
        if m:
            it.update({k: v for k, v in m.items() if k in ("site_url", "repo_url", "title", "langs", "summary")})
            it["exists"] = "Y"
        a = (mv.get("add") or {}).get(it["repo"])
        if a and it["cat"] == "미분류":
            it.update({k: v for k, v in a.items() if k in ("title", "summary", "cat", "mid", "sub", "order")})
            it["public"] = "Y"
            it["exists"] = "Y" if it["site_url"] or by.get(it["repo"]) else it["exists"]
            if not it["site_url"]:
                it["site_url"] = "https://%s.github.io/%s/" % (OWNER, it["repo"])
    items.sort(key=lambda x: (cat_order.get(x["cat"], 99), x["mid"], x["sub"], x["order"]))
    kst = dt.timezone(dt.timedelta(hours=9))
    out = {"updated": dt.datetime.now(kst).date().isoformat(), "categories": cats, "mids": meta.get("mids", []), "hero": _img(meta["hero"]) if meta.get("hero") else {}, "items": items,
           "added_today": added}
    with open(os.path.join(DATA, "hub.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    # 공개 카탈로그용: 공개 대상이면서 콘텐츠가 있는 항목만, 화면에 필요한 칸만 (관리 메모·대상 여부는 넣지 않음)
    names = {c["name"] for c in cats}
    pub = [it for it in items if it["public"] == "Y" and it["exists"] == "Y" and it["cat"] in names]
    keep = ["title", "summary", "cat", "mid", "sub", "kind", "repo_url", "site_url", "link", "langs", "thumb"]
    used = {(it["cat"], it["mid"]) for it in pub}
    catalog = {"updated": out["updated"], "categories": cats,
               "mids": [m for m in out["mids"] if (m.get("cat"), m.get("name")) in used],
               "hero": out["hero"], "items": [{k: it[k] for k in keep} for it in pub]}
    with open(os.path.join(DATA, "catalog.json"), "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=1)

    # 서버실 servers.csv: 공개대상 Y이고 사이트가 있는 콘텐츠만, 대분류 순서대로 (랙 10개)
    tr = meta.get("server_translations", {})
    cols = ["카테고리", "제목", "내용소개", "해시태그", "생성일", "비고"]
    for base in ["카테고리", "제목", "내용소개", "해시태그", "비고"]:
        cols += ["%s_%s" % (base, l) for l in SERVER_LANGS]
    srows, first = [], set()
    for it in items:
        if it["public"] != "Y" or it["exists"] != "Y":
            continue
        c = next((x for x in cats if x["name"] == it["cat"]), None)
        if c is None:
            continue
        t = tr.get(it["repo"], {})
        row = {"카테고리": it["cat"], "제목": it["title"], "내용소개": it["summary"],
               "해시태그": " ".join("#" + s.replace(" ", "") for s in [it["cat"], it["mid"], it["sub"]] if s),
               "생성일": "", "비고": it["link"] if it["kind"] == "ext" else it["site_url"]}
        if it["cat"] not in first:
            for l in SERVER_LANGS:
                row["카테고리_" + l] = (c.get("tr") or {}).get(l, "")
            first.add(it["cat"])
        for l in SERVER_LANGS:
            for base, key in (("제목", "title"), ("내용소개", "desc"), ("해시태그", "tags"), ("비고", "note")):
                if (t.get(l) or {}).get(key):
                    row["%s_%s" % (base, l)] = t[l][key]
        srows.append(row)
    write_csv(os.path.join(DATA, "servers.csv"), cols, srows)
    print("현황판 %d개, 서버실 %d개, 새 저장소 %d개 %s" % (len(items), len(srows), len(added), added or ""))


if __name__ == "__main__":
    main()
