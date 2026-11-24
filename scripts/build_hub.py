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
- 공개일: '공개일'(YYYY-MM-DD)이 기준일보다 늦으면 공개 대상이어도 카탈로그·서버실에 아직 나오지 않는다(예약 공개).
  기준일은 data/publish_settings.json — mode "fixed"면 관리실에서 저장한 기준일, "auto"면 빌드하는 날(한국 시간).
- 시리즈물: '시리즈물'=Y인 콘텐츠는 여러 챕터를 하나로 묶은 것. 챕터는 '상위시리즈'에 그 저장소 이름을 적은 줄로 두고
  (저장소 칸은 '<상위 저장소>/<파일>'), 공개 대상이면서 공개일이 지난 챕터만 상위 카드의 chapters 목록에 들어간다.
"""
import csv, datetime as dt, io, json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
OWNER = "adminmrobo"
EXCLUDE_PREFIX = "newsreporter_"
EXCLUDE_NAMES = {"adminmrobo", "ahnboat_homepage_manual"}  # 관리자용 매뉴얼은 현황판·카탈로그에 넣지 않음
LANGS_FULL = 7  # 한국어 + en·zh·ja·uz·ru·vi

COLS = ["저장소", "제목", "주요내용", "콘텐츠_카테고리_대분류", "콘텐츠_카테고리_중분류", "콘텐츠_카테고리_소분류",
        "공개대상여부", "연구실_시리즈_적용대상_여부", "외국어팩대상_여부", "온톨로지_적용대상_여부", "순서", "외부링크", "비고",
        "공개일", "시리즈물", "상위시리즈", "챕터", "주인장_저자_여부", "Articles_갈래", "저자_강의_여부"]
LECT_COL = "저자_강의_여부"  # Y면 Ahn's Articles & Presentations의 LECTURE(주인장이 직접 한 강의)에 나온다
OWNER_COL = "주인장_저자_여부"  # Y면 Ahn's Articles & Presentations(논문·발표·강연)에 나온다. 비우면 제외
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


def norm_date(v):
    """2026-11-17 · 2026.11.17 · 2026/11/17 · 20261117 → 2026-11-17. 비었거나 못 읽으면 ''."""
    d = re.sub(r"\D", "", str(v or ""))
    return "%s-%s-%s" % (d[:4], d[4:6], d[6:8]) if len(d) == 8 else ""


def base_date(settings, today):
    if (settings or {}).get("mode") == "fixed":
        return norm_date(settings.get("base_date")) or today
    return today


def chap_key(h, i):
    o = h.get("순서") or ""
    c = re.sub(r"\D", "", h.get("챕터") or "")
    return (int(o) if o.isdigit() else 1000 + i, int(c) if c else 0, h.get("저장소", ""))


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


def load_migration():
    """data/rack_migration.json: 랙 개편 옮기기 표. key(저장소 또는 제목) → 바꿀 분류·Articles 갈래."""
    mg = load_json(os.path.join(DATA, "rack_migration.json"), {})
    return mg.get("article_col") or "Articles_갈래", mg.get("moves") or []


def migrate(obj, keys, moves, fields, owner_k=None):
    """대분류가 from과 같은 항목만 새 분류로 옮긴다(한 번 옮기면 다시 건드리지 않음). 바뀌면 True."""
    cat_k, mid_k, sub_k, art_k = fields
    for mv in moves:
        if mv.get("key") not in keys or (obj.get(cat_k) or "미분류") != mv.get("from"):
            continue
        obj[cat_k] = mv.get("cat", obj.get(cat_k))
        if "mid" in mv:
            obj[mid_k] = mv["mid"]
        if "sub" in mv:
            obj[sub_k] = mv["sub"]
        if mv.get("article"):
            obj[art_k] = mv["article"]
            if owner_k:
                obj[owner_k] = "Y"
        return True
    return False


def apply_rules(obj, keys, rules, fields, pub_k=None):
    """상시 규칙(data/rack_migration.json → rules): 이름·제목이 pattern에 맞으면 대분류를 맞춘다. 바뀌면 True."""
    cat_k, mid_k, sub_k = fields
    for ru in rules:
        if not any(k and re.search(ru["pattern"], k, re.I) for k in keys):
            continue
        changed = False
        if (obj.get(cat_k) or "미분류") != ru["cat"]:
            obj[cat_k] = ru["cat"]
            obj[mid_k] = ru.get("mid", "")
            obj[sub_k] = ru.get("sub", "")
            changed = True
        if pub_k and ru.get("open") and (obj.get(pub_k) or "").strip() in ("", "검토"):
            obj[pub_k] = "Y"
            changed = True
        return changed
    return False


def rename_mid(obj, renames, fields):
    """중분류 이름 바꾸기(data/rack_migration.json → mid_renames). 바뀌면 True."""
    cat_k, mid_k, sub_k = fields
    for rn in renames:
        if obj.get(cat_k) == rn["cat"] and obj.get(mid_k) == rn["from"] and (not rn.get("from_sub") or obj.get(sub_k) == rn["from_sub"]):
            obj[mid_k] = rn["to"]
            return True
    return False


def main():
    hub_p = os.path.join(DATA, "hub.csv")
    rows = read_csv(hub_p) if os.path.exists(hub_p) else []
    meta = load_json(os.path.join(DATA, "hub_meta.json"), {})
    scan = load_json(os.path.join(DATA, "repos.json"), {})
    repos = scan.get("repos", scan) if isinstance(scan, dict) else scan
    by = {r["repo"]: r for r in repos}
    kst = dt.timezone(dt.timedelta(hours=9))
    today = dt.datetime.now(kst).date().isoformat()
    settings = load_json(os.path.join(DATA, "publish_settings.json"), {})
    BASE = base_date(settings, today)
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
    # 랙 개편: 옮기기 표대로 관리표(hub.csv) 자체의 분류를 고친다 → 관리실에서도 새 분류가 보인다
    ART_COL, MOVES = load_migration()
    row_fields = ("콘텐츠_카테고리_대분류", "콘텐츠_카테고리_중분류", "콘텐츠_카테고리_소분류", ART_COL)
    migrated = [r["저장소"] for r in rows if migrate(r, {r.get("저장소"), r.get("제목")}, MOVES, row_fields, OWNER_COL)]
    _mg = load_json(os.path.join(DATA, "rack_migration.json"), {})
    RULES, RENAMES = _mg.get("rules") or [], _mg.get("mid_renames") or []
    for r in rows:
        ch = apply_rules(r, [r.get("저장소"), r.get("제목")], RULES, row_fields[:3], "공개대상여부")
        ch = rename_mid(r, RENAMES, row_fields[:3]) or ch
        if ch and r["저장소"] not in migrated:
            migrated.append(r["저장소"])
    # 주인장 저자 칸이 생기기 전에 옮겨진 행: 옮기기 표에 갈래가 있고 저자 칸이 아직 비어 있으면 Y로 채운다
    # (관리실에서 체크를 끄면 'N'이 들어가므로 다시 채우지 않는다)
    arts = {mv["key"] for mv in MOVES if mv.get("article")}
    for r in rows:
        if not (r.get(OWNER_COL) or "").strip() and (r.get("저장소") in arts or r.get("제목") in arts):
            r[OWNER_COL] = "Y"
            if r["저장소"] not in migrated:
                migrated.append(r["저장소"])
    # 저자 강의: 옮기기 표에 lecture가 있고 칸이 비어 있으면 Y로 채운다 (관리실에서 끄면 'N')
    lects = {mv["key"] for mv in MOVES if mv.get("lecture")}
    for r in rows:
        if not (r.get(LECT_COL) or "").strip() and (r.get("저장소") in lects or r.get("제목") in lects):
            r[LECT_COL] = "Y"
            if r["저장소"] not in migrated:
                migrated.append(r["저장소"])
    if migrated:
        print("랙 개편으로 옮긴 행 %d개" % len(migrated))
    if added or migrated:  # 관리실에서 더한 칸(표준 칸 밖)도 지우지 않는다
        extra = []
        for r in rows:
            for k in r:
                if k and k not in COLS and k not in extra:
                    extra.append(k)
        write_csv(hub_p, COLS + extra, rows)

    def _img(o):  # 그림 파일이 아직 없으면 비워 둔다 (카드에는 색 상자가 보인다)
        o = dict(o)
        if o.get("image") and not os.path.exists(os.path.join(ROOT, o["image"])):
            o["image"] = ""
        return o
    cats = [_img(c) for c in meta.get("categories", [])]
    meta["mids"] = [_img(m) for m in meta.get("mids", [])]
    cat_order = {c["name"]: i for i, c in enumerate(cats)}
    items = []
    chaps = {}  # 상위 저장소 → [(정렬키, 챕터 행)]
    for i, h in enumerate(rows):
        if (h.get("상위시리즈") or "").strip():
            chaps.setdefault(h["상위시리즈"].strip(), []).append((chap_key(h, i), h))
    for i, h in enumerate(rows):
        if (h.get("상위시리즈") or "").strip():
            continue
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
            "release": norm_date(h.get("공개일")),
            "released": "Y" if (not norm_date(h.get("공개일")) or norm_date(h.get("공개일")) <= BASE) else "N",
            "series": "Y" if yes(h.get("시리즈물")) else "N",
            "order": int(h["순서"]) if (h.get("순서") or "").isdigit() else 1000 + i,
            # 주인장 저자(Y)만 Articles에 나온다. 갈래가 비면 '기타 논문·발표'
            "lecture": "Y" if yes(h.get(LECT_COL)) else "",
            "article": ((h.get(ART_COL) or "").strip() or "기타 논문·발표") if yes(h.get(OWNER_COL)) else "",
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
    item_fields = ("cat", "mid", "sub", "article")
    for it in items:
        migrate(it, {it["repo"], it["title"]}, MOVES, item_fields)
        apply_rules(it, [it["repo"], it["title"]], RULES, item_fields[:3])
        rename_mid(it, RENAMES, item_fields[:3])
    # 카드 다듬기: 깨진 글자(&#x27; 등) · 빈 소개 · 빈/없는 그림 보완 (scripts/catalog_polish.py, data/catalog_fill.json)
    import sys as _s0
    _s0.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import catalog_polish
    catalog_polish.polish(items, by, cats, meta.get("mids", []))
    # 시리즈 챕터: 상위 카드의 사이트 주소 + 파일 (외부링크에 주소가 있으면 그 주소)
    for it in items:
        if it["series"] != "Y":
            continue
        base_url = it["site_url"] or "https://%s.github.io/%s/" % (OWNER, it["repo"])
        if not base_url.endswith("/"):
            base_url += "/"
        lst = []
        for _, h in sorted(chaps.get(it["repo"], []), key=lambda x: x[0]):
            path = h["저장소"].split("/", 1)[1] if "/" in h["저장소"] else ""
            rd = norm_date(h.get("공개일"))
            pub = (h.get("공개대상여부") or "").strip()
            lst.append({"no": h.get("챕터", ""), "title": catalog_polish.unescape(h.get("제목") or path),
                        "summary": catalog_polish.unescape(h.get("주요내용", "")),
                        "url": _url(h.get("외부링크", "")) or base_url + path, "file": path, "release": rd,
                        "public": "Y" if yes(pub) else ("검토" if pub == "검토" else "N"),
                        "released": "Y" if (not rd or rd <= BASE) else "N"})
        it["chapters"] = lst
    items.sort(key=lambda x: (cat_order.get(x["cat"], 99), x["mid"], x["sub"], x["order"]))
    out = {"updated": today, "base_date": BASE, "base_mode": (settings or {}).get("mode") or "auto", "categories": cats, "mids": meta.get("mids", []), "hero": _img(meta["hero"]) if meta.get("hero") else {}, "items": items,
           "added_today": added}
    with open(os.path.join(DATA, "hub.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    # 공개 카탈로그용: 공개 대상이면서 콘텐츠가 있는 항목만, 화면에 필요한 칸만 (관리 메모·대상 여부는 넣지 않음)
    names = {c["name"] for c in cats}
    pub = [it for it in items if it["public"] == "Y" and it["exists"] == "Y" and it["released"] == "Y" and it["cat"] in names]
    keep = ["title", "summary", "cat", "mid", "sub", "kind", "repo_url", "site_url", "link", "langs", "thumb"]
    used = {(it["cat"], it["mid"] or "기타") for it in pub}  # 중분류가 빈 항목은 화면에서 '기타'로 묶인다
    # Ahn's Articles & Presentations: 랙과 상관없이 'Articles_갈래'가 있는 항목을 모은다 (data/views.json → articles.only = 갈래 묶음 이름)
    art_name = (load_json(os.path.join(DATA, "views.json"), {}).get("articles") or {}).get("only") or "논문 해설"
    used |= {(art_name, it["article"]) for it in pub if it.get("article")}
    lect_mid = (load_json(os.path.join(DATA, "views.json"), {}).get("articles") or {}).get("lecture_mid") or "강의"
    used |= {(art_name, lect_mid) for it in pub if it.get("lecture") == "Y"}

    def public_item(it):
        o = {k: it[k] for k in keep}
        if it.get("article"):
            o["article"] = it["article"]
        if it.get("lecture") == "Y":
            o["lecture"] = "Y"
        if it["series"] == "Y" and it.get("chapters"):
            allp = [c for c in it["chapters"] if c["public"] == "Y"]
            shown = [c for c in allp if c["released"] == "Y"]
            later = sorted(c["release"] for c in allp if c["released"] != "Y" and c["release"])
            o["series"] = {"total": len(allp), "open": len(shown),
                           "next": later[0] if later else "",
                           "chapters": [{k: c[k] for k in ("no", "title", "summary", "url", "release")} for c in shown]}
        return o
    catalog = {"updated": out["updated"], "categories": cats,
               "mids": [m for m in out["mids"] if (m.get("cat"), m.get("name")) in used],
               "hero": out["hero"], "items": [public_item(it) for it in pub]}
    # 중분류 카드가 hub_meta.json에 없으면(새 중분류) 그 갈래 콘텐츠의 표지로 카드 그림을 채운다 — 줄무늬 빈 카드 방지
    catalog["mids"] += catalog_polish.missing_mids(catalog["items"], catalog["mids"])
    # 시리즈 카드(data/series_cards.json): 한 저장소 안 여러 편을 장(챕터)별 소분류로 묶고 제목·소개·썸네일을 한 틀로
    import sys as _sys
    _sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import series_cards
    series_cards.apply(catalog["items"])
    with open(os.path.join(DATA, "catalog.json"), "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=1)

    # 서버실 servers.csv: 공개대상 Y이고 사이트가 있는 콘텐츠만, 대분류 순서대로 (랙 10개)
    tr = meta.get("server_translations", {})
    cols = ["카테고리", "제목", "내용소개", "해시태그", "생성일", "비고"]
    for base in ["카테고리", "제목", "내용소개", "해시태그", "비고"]:
        cols += ["%s_%s" % (base, l) for l in SERVER_LANGS]
    srows, first = [], set()
    for it in items:
        if it["public"] != "Y" or it["exists"] != "Y" or it["released"] != "Y":
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
