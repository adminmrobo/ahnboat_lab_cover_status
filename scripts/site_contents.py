#!/usr/bin/env python3
"""사이트 콘텐츠 목록 만들기 — ahnboat.xyz(워드프레스) 글·페이지 + GitHub 해설 콘텐츠 + 포트폴리오 + 일정.

결과
  SITE_CONTENTS.md          사람이 읽는 목록(저장소 맨 위)
  data/site_contents.json   같은 내용을 기계가 읽는 형식으로

외부 라이브러리 없이 표준 라이브러리만 쓴다. 한 곳을 못 읽어도 나머지는 만든다.
"""
import csv, html, io, json, os, re, sys, urllib.request, urllib.error, xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.environ.get("SITE_URL", "https://ahnboat.xyz").rstrip("/")
LABTOWN_CSV = os.environ.get("LABTOWN_CSV", "https://raw.githubusercontent.com/adminmrobo/ahn_boat_lab_town/main/projects.csv")
KST = timezone(timedelta(hours=9))
UA = {"User-Agent": "ahnboat-site-contents/1.0 (+https://github.com/adminmrobo/ahnboat_lab_cover_status)"}


def get(url, timeout=30):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(), dict(r.headers)


def text(s):
    s = html.unescape(re.sub(r"<[^>]+>", " ", s or ""))
    return re.sub(r"\s+", " ", s).strip()


def wp_list(kind):
    """워드프레스 REST API로 글(posts)·페이지(pages) 전부 읽기."""
    out, page = [], 1
    fields = "id,date,modified,link,title,excerpt,categories,tags,parent,status"
    while True:
        url = f"{SITE}/wp-json/wp/v2/{kind}?per_page=100&page={page}&_fields={fields}"
        try:
            body, hdr = get(url)
        except urllib.error.HTTPError as e:
            if e.code == 400 and page > 1:  # 마지막 쪽을 넘김
                break
            raise
        rows = json.loads(body)
        if not rows:
            break
        for r in rows:
            out.append({
                "id": r.get("id"),
                "title": text((r.get("title") or {}).get("rendered")),
                "link": r.get("link"),
                "date": (r.get("date") or "")[:10],
                "modified": (r.get("modified") or "")[:10],
                "excerpt": text((r.get("excerpt") or {}).get("rendered"))[:200],
                "categories": r.get("categories") or [],
                "parent": r.get("parent") or 0,
            })
        total = int(hdr.get("X-WP-TotalPages") or hdr.get("x-wp-totalpages") or 1)
        if page >= total:
            break
        page += 1
    return out


def wp_categories():
    try:
        body, _ = get(f"{SITE}/wp-json/wp/v2/categories?per_page=100&_fields=id,name")
        return {c["id"]: text(c["name"]) for c in json.loads(body)}
    except Exception:
        return {}


def wp_sitemap():
    """REST API가 막혔을 때: 워드프레스 기본 사이트맵에서 주소만 모은다."""
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    body, _ = get(f"{SITE}/wp-sitemap.xml")
    urls = []
    for loc in ET.fromstring(body).findall(".//s:loc", ns):
        sub, _ = get(loc.text)
        for u in ET.fromstring(sub).findall(".//s:url", ns):
            urls.append({"link": u.findtext("s:loc", "", ns), "modified": (u.findtext("s:lastmod", "", ns) or "")[:10]})
    return urls


def load_json(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return json.load(f)


def main():
    now = datetime.now(KST)
    data = {"fetched_at": now.strftime("%Y-%m-%d %H:%M KST"), "site": SITE, "errors": []}

    # 1) 홈페이지(워드프레스)
    wp = {"source": "rest", "posts": [], "pages": [], "sitemap": []}
    try:
        cats = wp_categories()
        wp["posts"] = wp_list("posts")
        for p in wp["posts"]:
            p["categories"] = [cats.get(c, str(c)) for c in p["categories"]]
        wp["pages"] = wp_list("pages")
    except Exception as e:
        data["errors"].append(f"워드프레스 REST API 읽기 실패: {e}")
        try:
            wp["source"] = "sitemap"
            wp["sitemap"] = wp_sitemap()
        except Exception as e2:
            data["errors"].append(f"워드프레스 사이트맵 읽기 실패: {e2}")
    data["wordpress"] = wp

    # 2) GitHub 해설 콘텐츠(공개 카탈로그)·포트폴리오
    for key, rel in (("catalog", "data/catalog.json"), ("portfolio", "data/portfolio.json")):
        try:
            items = load_json(rel).get("items", [])
            data[key] = [{k: it.get(k, "") for k in ("title", "cat", "mid", "sub", "site_url", "repo_url", "link", "langs", "summary")} for it in items]
        except Exception as e:
            data[key] = []
            data["errors"].append(f"{rel} 읽기 실패: {e}")

    # 3) 일정(Lab Town projects.csv)
    try:
        body, _ = get(LABTOWN_CSV)
        rows = list(csv.DictReader(io.StringIO(body.decode("utf-8-sig"))))
        data["schedule"] = [{k: r.get(k, "") for k in ("상태", "카테고리", "프로젝트명", "프로젝트링크", "시작일", "완료일", "담당", "진행률", "비고")} for r in rows]
    except Exception as e:
        data["schedule"] = []
        data["errors"].append(f"일정(projects.csv) 읽기 실패: {e}")

    with open(os.path.join(ROOT, "data/site_contents.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")
    with open(os.path.join(ROOT, "SITE_CONTENTS.md"), "w", encoding="utf-8") as f:
        f.write(render(data))
    n = len(wp["posts"]) + len(wp["pages"]) + len(wp["sitemap"])
    print(f"홈페이지 {n} · 해설 {len(data['catalog'])} · 포트폴리오 {len(data['portfolio'])} · 일정 {len(data['schedule'])} · 오류 {len(data['errors'])}")


def esc(s):
    return str(s or "").replace("|", "\\|").replace("\n", " ")


def render(d):
    wp = d["wordpress"]
    L = [
        "# 사이트 콘텐츠 목록",
        "",
        f"ahnboat.xyz와 GitHub 해설 콘텐츠의 전체 목록입니다. 매일 오전·오후 자동으로 다시 만들고, Actions에서 수동으로도 돌릴 수 있습니다.",
        "",
        f"- 갱신: **{d['fetched_at']}**",
        f"- 홈페이지 글 {len(wp['posts'])} · 페이지 {len(wp['pages'])}" + (f" · 사이트맵 주소 {len(wp['sitemap'])}" if wp["sitemap"] else ""),
        f"- GitHub 해설 콘텐츠 {len(d['catalog'])} · 포트폴리오 {len(d['portfolio'])} · 일정 {len(d['schedule'])}",
        "- 기계용 원본: `data/site_contents.json`",
        "",
    ]
    if d["errors"]:
        L += ["> ⚠ 이번에 읽지 못한 곳", ""] + [f"> - {e}" for e in d["errors"]] + [""]

    L += ["## 1. 홈페이지 글 (ahnboat.xyz)", ""]
    if wp["posts"]:
        L += ["| 날짜 | 제목 | 분류 | 고친 날 |", "|---|---|---|---|"]
        for p in sorted(wp["posts"], key=lambda x: x["date"], reverse=True):
            L.append(f"| {p['date']} | [{esc(p['title'])}]({p['link']}) | {esc(', '.join(p['categories']))} | {p['modified']} |")
    elif wp["sitemap"]:
        L += ["REST API를 못 읽어 사이트맵 주소만 적습니다.", "", "| 고친 날 | 주소 |", "|---|---|"]
        L += [f"| {u['modified']} | {u['link']} |" for u in wp["sitemap"]]
    else:
        L.append("(읽지 못함)")
    L.append("")

    L += ["## 2. 홈페이지 페이지", ""]
    if wp["pages"]:
        L += ["| 제목 | 주소 | 고친 날 |", "|---|---|---|"]
        for p in sorted(wp["pages"], key=lambda x: x["title"]):
            L.append(f"| {esc(p['title']) or '(제목 없음)'} | {p['link']} | {p['modified']} |")
    else:
        L.append("(없음 또는 읽지 못함)")
    L.append("")

    L += ["## 3. GitHub 해설 콘텐츠 (공개 카탈로그)", ""]
    by = {}
    for it in d["catalog"]:
        by.setdefault(it["cat"] or "기타", []).append(it)
    for cat, items in by.items():
        L += [f"### {cat} ({len(items)})", "", "| 제목 | 중분류 | 주소 | 언어 |", "|---|---|---|---|"]
        for it in items:
            url = it["site_url"] or it["link"] or it["repo_url"]
            L.append(f"| {esc(it['title'])} | {esc(' / '.join(x for x in (it['mid'], it['sub']) if x))} | {url} | {' '.join(it['langs'] or [])} |")
        L.append("")

    L += ["## 4. 포트폴리오", "", "| 제목 | 분류 | 주소 |", "|---|---|---|"]
    for it in d["portfolio"]:
        L.append(f"| {esc(it['title'])} | {esc(it['cat'])} | {it['site_url'] or it['link']} |")
    L.append("")

    L += ["## 5. 일정 (Ahn-boat Lab Town)", "", "| 상태 | 프로젝트 | 담당 | 기간 | 진행률 | 비고 |", "|---|---|---|---|---|---|"]
    order = {"진행중": 0, "예정": 1, "완료": 2}
    for r in sorted(d["schedule"], key=lambda r: order.get(r["상태"].replace(" ", ""), 9)):
        name = f"[{esc(r['프로젝트명'])}]({r['프로젝트링크']})" if r["프로젝트링크"] else esc(r["프로젝트명"])
        span = " ~ ".join(x for x in (r["시작일"], r["완료일"]) if x)
        L.append(f"| {r['상태']} | {name} | {r['담당']} | {span} | {r['진행률']} | {esc(r['비고'])} |")
    L.append("")
    return "\n".join(L)


if __name__ == "__main__":
    sys.exit(main())
