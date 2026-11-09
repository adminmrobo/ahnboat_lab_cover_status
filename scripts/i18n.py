#!/usr/bin/env python3
"""홈페이지(ahnboat.xyz에 들어가는 GitHub 페이지) 다국어 사전.

사전은 data/i18n/site.json — {"str": {한국어 원문: {en: …, zh: …, ja: …, uz: …, ru: …, vi: …}}}
페이지(i18n.js)는 화면에 쓰는 한국어 문장을 그대로 열쇠로 찾아 바꾼다. 사전에 없으면 한국어를 보여 준다.

  python3 scripts/i18n.py collect [projects.csv]   번역이 필요한 한국어 문장을 모아 data/i18n/work/todo.json 으로
  python3 scripts/i18n.py pack                     todo.json → 언어별 번역 묶음 data/i18n/work/{L}_001.json (언어팩 형식)
  python3 scripts/i18n.py merge                    data/i18n/work/{L}_001.out.json 을 site.json 에 합치고 검사
  python3 scripts/i18n.py missing                  언어별로 아직 번역되지 않은 문장 수
"""
import csv, io, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = lambda *p: os.path.join(ROOT, "data", *p)
LANGS = ["en", "zh", "ja", "uz", "ru", "vi"]
HANGUL = re.compile(r"[가-힣]")


def load(p, default=None):
    try:
        return json.load(open(p, encoding="utf-8"))
    except FileNotFoundError:
        return default


def csv_rows(p):
    t = open(p, "rb").read()
    try:
        t = t.decode("utf-8-sig")
    except UnicodeDecodeError:
        t = t.decode("cp949")
    return list(csv.DictReader(io.StringIO(t)))


def collect(projects=None):
    S = []

    def add(x):
        if isinstance(x, list):
            for y in x:
                add(y)
        elif isinstance(x, str):
            x = x.strip()
            if x and HANGUL.search(x) and x not in S:
                S.append(x)

    ui = load(D("i18n", "ui_strings.json"), {})
    for k, v in ui.items():
        if not k.startswith("_"):
            add(v)
    for src in ("catalog.json", "portfolio.json"):
        d = load(D(src), {})
        for c in d.get("categories", []):
            add([c.get("name"), c.get("desc")]); add(c.get("keywords", []))
        for m in d.get("mids", []):
            add([m.get("name"), m.get("desc")]); add(m.get("keywords", []))
        add((d.get("hero") or {}).get("desc"))
        for i in d.get("items", []):
            add([i.get("title"), i.get("summary"), i.get("sub"), i.get("mid"), i.get("note"), i.get("button")])
            if i.get("kind") == "ext" and i.get("link"):
                add(re.sub(r"\s*·?\s*https?://\S+", "", i["link"]).strip())
    views = load(D("views.json"), {})
    for k, v in views.items():
        if k.startswith("_") or not isinstance(v, dict):
            continue
        for f in ("root_label", "unit", "foot", "soon_desc", "random_label", "page_title"):
            add(v.get(f))
        add((v.get("hero") or {}).get("desc"))
        add(list((v.get("mid_alias") or {}).values()))
        for mi in (v.get("mid_info") or {}).values():
            add(mi.get("desc")); add(mi.get("keywords", []))
    if os.path.exists(D("notices.csv")):
        for r in csv_rows(D("notices.csv")):
            add(r.get("제목"))
    if projects and os.path.exists(projects):
        for r in csv_rows(projects):
            add([r.get("프로젝트명"), r.get("카테고리")])
    site = load(D("i18n", "site.json"), {"str": {}})
    todo = [s for s in S if any(not (site["str"].get(s) or {}).get(L) for L in LANGS)]
    os.makedirs(D("i18n", "work"), exist_ok=True)
    json.dump(todo, open(D("i18n", "work", "todo.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(f"모은 문장 {len(S)}개 · 번역할 것 {len(todo)}개 · 글자 {sum(len(s) for s in todo):,}")


def pack(rules_dir=None):
    todo = load(D("i18n", "work", "todo.json"), [])
    gl = load(D("i18n", "glossary.json"), {})
    rules = open(D("i18n", "rules.md"), encoding="utf-8").read()
    site = load(D("i18n", "site.json"), {"str": {}})
    for L in LANGS:
        units = {f"u{n+1:04d}": s for n, s in enumerate(todo) if not (site["str"].get(s) or {}).get(L)}
        lr = os.path.join(rules_dir, f"{L}.md") if rules_dir else None
        extra = open(lr, encoding="utf-8").read() if lr and os.path.exists(lr) else ""
        g = {k: v[L] for k, v in gl.items() if L in v}
        json.dump({"rules": rules + "\n\n" + extra, "glossary": g, "units": units},
                  open(D("i18n", "work", f"{L}_001.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(L, len(units))


def check(src, out):
    probs = []
    ph = lambda s: sorted(re.findall(r"\{\d+\}", s))
    nums = lambda s: sorted(re.findall(r"\d+(?:\.\d+)?", s))
    if ph(src) != ph(out):
        probs.append("자리표시")
    if HANGUL.search(re.sub(r"한국어|商船|안\s*\(Ahn|상선", "", out)):
        probs.append("한글 남음")
    if nums(src) != nums(out) and not re.search(r"[가-힣]만|\d+\s*(?:개|편|건)", src):
        probs.append("숫자")
    return probs


def merge():
    todo = load(D("i18n", "work", "todo.json"), [])
    site = load(D("i18n", "site.json"), {"v": 1, "langs": ["ko"] + LANGS, "str": {}})
    bad = 0
    for L in LANGS:
        pk = load(D("i18n", "work", f"{L}_001.json"), {})
        out = load(D("i18n", "work", f"{L}_001.out.json"), None)
        if out is None:
            print(L, "번역 파일 없음"); continue
        miss = 0
        for uid, ko in (pk.get("units") or {}).items():
            tr = (out.get(uid) or "").strip()
            if not tr:
                miss += 1; continue
            p = check(ko, tr)
            if "자리표시" in p or "한글 남음" in p:
                bad += 1; print(f"  [{L}] {uid} {p}: {ko[:40]} → {tr[:60]}"); continue
            site["str"].setdefault(ko, {})[L] = tr
        print(L, "합침", len(pk.get("units") or {}) - miss, "· 빠짐", miss)
    site["str"] = {k: v for k, v in site["str"].items()}
    json.dump(site, open(D("i18n", "site.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print("문제", bad)


def missing():
    todo = load(D("i18n", "work", "todo.json"), [])
    site = load(D("i18n", "site.json"), {"str": {}})
    for L in LANGS:
        print(L, sum(1 for s in todo if not (site["str"].get(s) or {}).get(L)))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "collect":
        collect(sys.argv[2] if len(sys.argv) > 2 else None)
    elif cmd == "pack":
        pack(sys.argv[2] if len(sys.argv) > 2 else None)
    elif cmd == "merge":
        merge()
    elif cmd == "missing":
        missing()
    else:
        print(__doc__)
