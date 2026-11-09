#!/usr/bin/env python3
"""adminmrobo 공개 저장소의 표지·장면 그림 현황을 모아 data/repos.json 에 쓴다.

표준 라이브러리만 쓴다.

  GITHUB_TOKEN=... python3 scripts/scan_repos.py          # GitHub API로 수집 (Actions에서 매일 실행)
  python3 scripts/scan_repos.py --local --list LIST --repos-dir DIR
                                                           # 로컬 저장소 사본(git clone)으로 같은 형식을 만든다

토큰이 없으면 경고만 하고 기존 data/repos.json 을 그대로 둔다.
"""
import argparse
import base64
import datetime as dt
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

OWNER = "adminmrobo"
SELF_REPO = "ahnboat_lab_cover_status"
EXCLUDE_PREFIX = "newsreporter_"
EXCLUDE_NAMES = {"adminmrobo", "ahnboat_homepage_manual"}  # 프로필 저장소, 관리자용 매뉴얼(비밀번호 잠금 — 홈페이지·검색·지도에 내보내지 않음)
API = "https://api.github.com"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(DATA, "repos.json")

IMG_RE = re.compile(r"\.(png|jpe?g|webp|gif|avif)$", re.I)
# 파일 이름(확장자 앞)에 낱말로 들어간 것만 잡는다. logo·blog 같은 낱말 속 'og'는 제외.
ROLE_RE = re.compile(r"(?:^|[_\-.])(cover|og|hero|thumb)(?=$|[_\-.\d])|^(sc)_", re.I)
ROLE_ORDER = {"cover": 0, "og": 1, "hero": 2, "thumb": 3, "banner": 4, "scene": 5, "outro": 6}
MAX_COVERS = 80


def today():
    kst = dt.timezone(dt.timedelta(hours=9))
    return dt.datetime.now(kst).date().isoformat()


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def redraw_index():
    """redraw.json → {repo: [그림 id, ...]} (같은 그림의 크기별 사본은 한 장으로 센다)."""
    idx, first_thumb = {}, {}
    for item in load_json(os.path.join(DATA, "redraw.json"), []):
        for t in item.get("targets", []):
            repo = t.get("repo")
            if not repo:
                continue
            ids = idx.setdefault(repo, [])
            if item["id"] not in ids:
                ids.append(item["id"])
            if repo not in first_thumb or (item.get("priority") == "P1" and first_thumb[repo][1] != "P1"):
                first_thumb[repo] = (item["id"], item.get("priority"))
    return idx, {r: v[0] for r, v in first_thumb.items()}


def series_from_redraw():
    """그림의 첫 번째 반영 위치(원본 저장소)를 기준으로 저장소 → 시리즈 이름을 고른다."""
    votes = {}
    for item in load_json(os.path.join(DATA, "redraw.json"), []):
        s = item.get("series_ko")
        targets = [t for t in item.get("targets", []) if t.get("repo")]
        if not s or "공용" in s or not targets:
            continue
        v = votes.setdefault(targets[0]["repo"], {})
        v[s] = v.get(s, 0) + 1
    return {r: max(v, key=v.get) for r, v in votes.items()}


def guess_covers(paths):
    out = []
    for p in paths:
        if not IMG_RE.search(p) or "/archive/" in "/" + p:
            continue
        stem = os.path.splitext(os.path.basename(p))[0]
        m = ROLE_RE.search(stem)
        if not m:
            continue
        role = (m.group(1) or "scene").lower()
        out.append({"path": p, "role": role, "estimated": True})
    out.sort(key=lambda c: (ROLE_ORDER.get(c["role"], 9), c["path"].count("/"), c["path"]))
    return out[:MAX_COVERS]


def covers_from_manifest(man):
    out = []
    for it in man.get("items", []):
        emb = it.get("embedded_in")
        if isinstance(emb, list):
            emb = emb[0] if emb else None
        c = {"path": it.get("path") or (emb and "%s#%s" % (emb, it.get("key", ""))) or "",
             "role": it.get("role", "")}
        for k in ("id", "size", "characters", "robot", "status"):
            if it.get(k) is not None:
                c[k] = it[k]
        out.append(c)
    return out


def title_from_html(text):
    m = re.search(r"<title[^>]*>(.*?)</title>", text or "", re.I | re.S)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else None


def h1_from_html(text):
    m = re.search(r"<h1[^>]*>(.*?)</h1>", text or "", re.I | re.S)
    if not m:
        return None
    t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", m.group(1))).strip()
    return t or None


# ---------------------------------------------------------------- 사이트 페이지: 온톨로지·번역
LANGS = ["ko", "en", "zh", "ja", "uz", "ru", "vi"]  # 언어팩 순서
LANG_ALIAS = {"zh-cn": "zh", "zh-hans": "zh", "zh-tw": "zh", "zh-hant": "zh", "cn": "zh", "jp": "ja", "kr": "ko"}
LANG_DIR = set(LANGS) | set(LANG_ALIAS)
LANG_SUFFIX_RE = re.compile(r"[._-](ko|en|zh|ja|uz|ru|vi|zh-cn|zh-hans|zh-tw)$", re.I)
HTML_LANG_RE = re.compile(r"<html[^>]*\blang\s*=\s*[\"']?([A-Za-z_-]+)", re.I)
KG_RE = re.compile(r"\bid\s*=\s*[\"']?kg[\"'\s>]", re.I)
EXPORT_RE = re.compile(r"\bid\s*=\s*[\"']?export[\"'\s>]", re.I)
# 사이트 페이지가 아닌 HTML (원본 소스·빌드 산출물·보관본 등)
SKIP_DIRS = {"src", "dist", "build", "overrides", "locked", "archive", "archives", "node_modules", "vendor",
             "templates", "template", "partials", "tools", "scripts", "test", "tests", "backup", "old"}
ONTO_RE = re.compile(r"(^|/)(KG_[^/]*\.json|[^/]*\.jsonld|[^/]*\.ttl|kg\.json|nodes\.csv|edges\.csv|backbone_[^/]*\.json)$", re.I)
README_RE = re.compile(r"^README[._-]([A-Za-z-]+)\.md$", re.I)
MAX_HTML = 40      # 저장소마다 내용을 받아 볼 HTML 수
MAX_HTML_BYTES = 40 * 1024 * 1024


def norm_lang(s):
    if not s:
        return None
    s = s.lower().replace("_", "-")
    if s in LANG_ALIAS:
        return LANG_ALIAS[s]
    base = s.split("-")[0]
    return LANG_ALIAS.get(base, base) if re.fullmatch(r"[a-z]{2,3}", base) else None


def lang_sort(codes):
    return sorted(set(codes), key=lambda c: (LANGS.index(c) if c in LANGS else 99, c))


def path_lang(p):
    """경로로 알 수 있는 번역판 언어: 언어 폴더(en/ …) 또는 파일 이름 끝(page.en.html, page_en.html, page-en.html)."""
    segs = p.split("/")
    for s in segs[:-1]:
        if s.lower() in LANG_DIR:
            return norm_lang(s)
    m = LANG_SUFFIX_RE.search(os.path.splitext(segs[-1])[0])
    return norm_lang(m.group(1)) if m else None


def site_root(paths, pages_path=None):
    """GitHub Pages가 내보내는 폴더. API로 알면 그대로, 모르면 맨 위에 index.html이 없고 docs/index.html이 있을 때 docs/."""
    if pages_path is not None:
        return pages_path.strip("/") + "/" if pages_path.strip("/") else ""
    s = set(paths)
    return "docs/" if "index.html" not in s and "docs/index.html" in s else ""


def site_pages(paths, root):
    out = []
    for p in paths:
        if not p.lower().endswith((".html", ".htm")) or (root and not p.startswith(root)):
            continue
        segs = p[len(root):].split("/")
        if any(s.lower() in SKIP_DIRS or s.startswith((".", "_")) for s in segs[:-1]):
            continue
        name = segs[-1].lower()
        if name == "404.html" or re.match(r"google[0-9a-f]+\.html$", name):
            continue
        out.append(p)
    return sorted(out)


def readme_langs(paths, readme):
    """README의 언어 앵커(#ko, #en …)·id, README.en.md 같은 따로 된 파일."""
    found = set()
    for p in paths:
        m = README_RE.match(p)
        if m and norm_lang(m.group(1)) and m.group(1).lower() != "i18n":
            found.add(norm_lang(m.group(1)))
    if readme:
        for m in re.finditer(r"\]\(#([A-Za-z-]+)\)|\b(?:id|name)\s*=\s*[\"']([A-Za-z-]+)[\"']", readme):
            c = (m.group(1) or m.group(2) or "").lower()
            if c in LANG_DIR:
                found.add(norm_lang(c))
    if found:
        found.add("ko")
    return lang_sort(found) if len(found) > 1 else []


REFRESH_RE = re.compile(r"http-equiv\s*=\s*[\"']?refresh", re.I)


def not_a_page(t):
    """옮겨 가기만 하는 작은 페이지(meta refresh)와 <html> 없는 조각 파일(ep/…/body.html 등)은 페이지로 세지 않는다."""
    if REFRESH_RE.search(t[:4096]) and len(t) < 6000:
        return True
    return not re.search(r"<html|<!doctype", t[:4096], re.I)


def collect_site(paths, read, pages_url, blob_url, readme=None, pages_path=None, manifest=None, max_html=MAX_HTML):
    """사이트 페이지를 훑어 site_title·ontology·i18n·languages 를 만든다.

    read(path) → HTML 텍스트 또는 None. 원본 페이지(번역판이 아닌 것)를 먼저, index.html을 먼저 읽는다.
    """
    manifest = manifest or {}
    root = site_root(paths, pages_path)
    info = []
    for p in site_pages(paths, root):
        lang = path_lang(p)
        info.append({"path": p, "url": pages_url + urllib.parse.quote(p[len(root):]), "lang": lang, "translated": lang is not None})
    order = sorted(info, key=lambda i: (i["translated"], os.path.basename(i["path"]).split(".")[0] != "index",
                                        i["path"].count("/"), i["path"]))
    for i in (order if max_html is None else order[:max_html]):
        t = read(i["path"])
        if t is None:
            continue
        if not_a_page(t):
            i["skip"] = True
            if os.path.basename(i["path"]) == "index.html" and not i["translated"]:
                i["title"] = title_from_html(t)  # 첫 페이지가 옮겨 가기 페이지여도 제목은 사이트 제목으로 쓴다
            continue
        i["checked"] = True
        i["kg"] = bool(KG_RE.search(t))
        i["export"] = bool(EXPORT_RE.search(t))
        i["title"] = title_from_html(t) or h1_from_html(t)
        if not i["translated"]:
            m = HTML_LANG_RE.search(t[:8192])
            i["lang"] = norm_lang(m.group(1)) if m else None
    first = next((i for i in info if i["path"] == root + "index.html"), None)
    info = [i for i in info if not i.get("skip")]
    for i in info:
        i["lang"] = i["lang"] or "ko"

    # 사이트 제목: 첫 페이지(index.html) 제목, 없으면 첫 원본 페이지 제목
    base = [i for i in info if not i["translated"]]
    site_title = manifest.get("site_title") or (first or {}).get("title") \
        or next((i["title"] for i in order if not i["translated"] and i.get("title")), None)

    # 온톨로지: 원본 페이지 기준 (#kg 지식 색인, #export 온톨로지·서지 꾸러미) + 저장소 안 온톨로지 파일
    checked = [i for i in base if i.get("checked")]
    n_kg = sum(1 for i in checked if i["kg"])
    if checked and n_kg == len(checked):
        status = "full"
    elif n_kg:
        status = "partial"
    else:
        status = "none"
    files = [{"path": p, "url": blob_url + urllib.parse.quote(p)} for p in sorted(paths) if ONTO_RE.search(p) and "/archive/" not in "/" + p]
    ontology = {
        "status": status,
        "pages_with_kg": n_kg,
        "pages_total": len(base),
        "pages_checked": len(checked),
        "kg_links": [i["url"] + "#kg" for i in base if i.get("kg")],
        "export_links": [i["url"] + "#export" for i in base if i.get("export")],
        "files": files,
    }

    # 번역: 실제 파일 기준 언어별 페이지 수
    pages = {}
    links = {}
    for i in sorted(info, key=lambda i: (os.path.basename(i["path"]).split(".")[0] != "index", i["path"].count("/"), i["path"])):
        pages[i["lang"]] = pages.get(i["lang"], 0) + 1
        links.setdefault(i["lang"], i["url"])
    langs = lang_sort(pages)
    if not langs and manifest.get("languages"):
        langs = lang_sort(norm_lang(c) for c in manifest["languages"] if norm_lang(c))
    top = max(pages.values()) if pages else 0
    partial = [c for c in langs if c in pages and pages[c] < top]
    i18n = {
        "langs": langs,
        "count": len(langs),
        "pages": {c: pages[c] for c in langs if c in pages},
        "partial": partial,
        "complete": not partial,
        "readme_langs": readme_langs(paths, readme),
        "links": {c: links[c] for c in langs if c in links},
    }
    languages = {"codes": langs, "count": len(langs), "complete": not partial,
                 "pages_by_lang": i18n["pages"]}
    return {"site_title": site_title, "ontology": ontology, "i18n": i18n, "languages": languages}


def pick_thumb(repo, pages_url, covers, og, redraw_thumb):
    local = "thumbs/repos/%s.jpg" % repo
    if os.path.exists(os.path.join(ROOT, local)):
        return local
    files = [c for c in covers if c.get("path") and "#" not in c["path"] and IMG_RE.search(c["path"])]
    files = [c["path"] for c in sorted(files, key=lambda c: (c["path"].count("/"), ROLE_ORDER.get(c["role"], 9)))]
    if og and not og.startswith("http") and og in files:
        return pages_url + og
    if files:
        return pages_url + files[0]
    if redraw_thumb:
        return "thumbs/%s.jpg" % redraw_thumb
    return None


def base_status(has_manifest, covers, redraw_count):
    if redraw_count:
        return "redraw"
    if has_manifest or covers:
        return "ok"
    return "unknown"


def make_entry(repo, branch, pushed_at, manifest, tree_paths, title, og, redraw, thumbs, series, prev, extra=None):
    pages_url = "https://%s.github.io/%s/" % (OWNER, repo)
    if manifest:
        covers = covers_from_manifest(manifest)
        series_ko = manifest.get("series_ko") or series.get(repo)
    else:
        covers = guess_covers(tree_paths or [])
        series_ko = series.get(repo)
    series_ko = series_ko or title or (prev or {}).get("series_ko") or repo
    ids = redraw.get(repo, [])
    e = {
        "repo": repo,
        "series_ko": series_ko,
        "title_ko": title or (prev or {}).get("title_ko"),
        "repo_url": "https://github.com/%s/%s" % (OWNER, repo),
        "pages_url": pages_url,
        "default_branch": branch,
        "pushed_at": pushed_at,
        "has_manifest": bool(manifest),
        "covers": covers,
        "redraw_count": len(ids),
        "redraw_ids": ids,
        "thumb": pick_thumb(repo, pages_url, covers, og, thumbs.get(repo)),
        "status": base_status(bool(manifest), covers, len(ids)),
        "checked_at": today(),
    }
    if extra:
        e.update(extra)
    return e


# ---------------------------------------------------------------- GitHub API
class Api:
    def __init__(self, token):
        self.token = token
        self.calls = 0

    def req(self, path, raw=False, limit=None):
        url = path if path.startswith("http") else API + path
        r = urllib.request.Request(url)
        r.add_header("Authorization", "Bearer " + self.token)
        r.add_header("Accept", "application/vnd.github.raw" if raw else "application/vnd.github+json")
        r.add_header("X-GitHub-Api-Version", "2022-11-28")
        r.add_header("User-Agent", SELF_REPO + "-scan")
        self.calls += 1
        try:
            with urllib.request.urlopen(r, timeout=60) as resp:
                body = resp.read(limit) if limit else resp.read()
                link = resp.headers.get("Link", "")
        except urllib.error.HTTPError as e:
            if e.code in (404, 409):  # 없음 / 빈 저장소
                return None, ""
            raise
        if raw:
            return body.decode("utf-8", "replace"), link
        return json.loads(body.decode("utf-8")), link

    def list_repos(self):
        url, out = "/users/%s/repos?per_page=100&type=owner" % OWNER, []
        while url:
            page, link = self.req(url)
            out.extend(page or [])
            m = re.search(r'<([^>]+)>;\s*rel="next"', link or "")
            url = m.group(1) if m else None
        return out


def raw_file(repo, branch, path):
    """공개 저장소 파일을 raw.githubusercontent.com 에서 받는다 (API 호출 수에 들어가지 않음)."""
    url = "https://raw.githubusercontent.com/%s/%s/%s/%s" % (OWNER, repo, branch, urllib.parse.quote(path))
    r = urllib.request.Request(url, headers={"User-Agent": SELF_REPO + "-scan"})
    try:
        with urllib.request.urlopen(r, timeout=60) as resp:
            return resp.read(MAX_HTML_BYTES).decode("utf-8", "replace")
    except (urllib.error.URLError, OSError):
        return None


def keep_repo(name, fork=False, private=False):
    return not (name.startswith(EXCLUDE_PREFIX) or name == SELF_REPO or name in EXCLUDE_NAMES or fork or private)


def scan_api(token):
    api = Api(token)
    redraw, thumbs = redraw_index()
    series = series_from_redraw()
    prev = {e["repo"]: e for e in load_json(OUT, [])}
    out = []
    for r in sorted(api.list_repos(), key=lambda r: r["name"].lower()):
        name = r["name"]
        if not keep_repo(name, r.get("fork"), r.get("private")):
            continue
        branch = r.get("default_branch") or "main"
        manifest = None
        text, _ = api.req("/repos/%s/%s/contents/cover_manifest.json?ref=%s" % (OWNER, name, branch), raw=True)
        if text:
            try:
                manifest = json.loads(text)
            except ValueError:
                print("  ! %s: cover_manifest.json 형식 오류" % name, file=sys.stderr)
        tree, _ = api.req("/repos/%s/%s/git/trees/%s?recursive=1" % (OWNER, name, branch))
        all_paths = [t["path"] for t in (tree or {}).get("tree", []) if t.get("type") == "blob"]
        head, _ = api.req("/repos/%s/%s/contents/index.html?ref=%s" % (OWNER, name, branch), raw=True, limit=65536)
        og = None
        if head:
            m = re.search(r'property="og:image"\s+content="([^"]+)"', head)
            og = m.group(1) if m else None
        readme, _ = api.req("/repos/%s/%s/contents/README.md?ref=%s" % (OWNER, name, branch), raw=True)
        pages_path = None
        if r.get("has_pages"):
            try:
                pg, _ = api.req("/repos/%s/%s/pages" % (OWNER, name))
                pages_path = ((pg or {}).get("source") or {}).get("path")
            except urllib.error.HTTPError:
                pages_path = None
        site = collect_site(all_paths, lambda p, n=name, b=branch: raw_file(n, b, p),
                            "https://%s.github.io/%s/" % (OWNER, name),
                            "https://github.com/%s/%s/blob/%s/" % (OWNER, name, branch), readme, pages_path, manifest)
        site["has_pages"] = bool(r.get("has_pages"))
        out.append(make_entry(name, branch, r.get("pushed_at"), manifest, None if manifest else all_paths,
                              title_from_html(head), og, redraw, thumbs, series, prev.get(name), site))
        print("  %-55s %s" % (name, out[-1]["status"]))
    print("API 호출 %d회, 저장소 %d개" % (api.calls, len(out)))
    return out


# ---------------------------------------------------------------- 로컬 사본
def git(repo_dir, *args):
    p = subprocess.run(["git", "-c", "core.quotePath=false", "-C", repo_dir] + list(args), capture_output=True)
    return p.stdout.decode("utf-8", "replace") if p.returncode == 0 else None


def scan_local(list_file, repos_dir):
    with open(list_file, encoding="utf-8") as f:
        names = f.read().split()
    redraw, thumbs = redraw_index()
    series = series_from_redraw()
    prev = {e["repo"]: e for e in load_json(OUT, [])}
    out = []
    for name in sorted(dict.fromkeys(names), key=str.lower):
        if not keep_repo(name):
            continue
        d = os.path.join(repos_dir, name)
        has_copy = git(d, "rev-parse", "HEAD") is not None
        if not has_copy:
            out.append(make_entry(name, None, None, None, [], None, None, redraw, thumbs, series, prev.get(name),
                                  {"local_copy": False, "site_title": None, "ontology": None, "i18n": None,
                                   "languages": None, "note": "로컬 사본 없음 (빈 저장소이거나 받기 실패) — 다음 API 수집 때 채워짐"}))
            continue
        ref = git(d, "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
        branch = ref.strip().split("/", 1)[1] if ref and "/" in ref else (git(d, "rev-parse", "--abbrev-ref", "HEAD") or "main").strip()
        pushed = (git(d, "log", "-1", "--format=%cI") or "").strip() or None
        manifest = None
        mt = git(d, "show", "HEAD:cover_manifest.json")
        if mt:
            try:
                manifest = json.loads(mt)
            except ValueError:
                pass
        all_paths = (git(d, "ls-tree", "-r", "--name-only", "HEAD") or "").splitlines()
        html = git(d, "show", "HEAD:index.html") or ""
        m = re.search(r'property="og:image"\s+content="([^"]+)"', html[:65536])
        site = collect_site(all_paths, lambda p, d=d: git(d, "show", "HEAD:" + p),
                            "https://%s.github.io/%s/" % (OWNER, name),
                            "https://github.com/%s/%s/blob/%s/" % (OWNER, name, branch),
                            git(d, "show", "HEAD:README.md"), None, manifest, max_html=None)
        site["local_copy"] = True
        out.append(make_entry(name, branch, pushed, manifest, None if manifest else all_paths,
                              title_from_html(html[:65536]), m.group(1) if m else None, redraw, thumbs, series,
                              prev.get(name), site))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--local", action="store_true", help="GitHub API 대신 로컬 저장소 사본으로 만든다")
    ap.add_argument("--list", help="--local: 저장소 이름 목록 파일 (공백·줄바꿈 구분)")
    ap.add_argument("--repos-dir", help="--local: <이름>/ 저장소 사본이 있는 폴더")
    a = ap.parse_args()
    if a.local:
        if not (a.list and a.repos_dir):
            ap.error("--local 에는 --list 와 --repos-dir 가 필요합니다")
        data = scan_local(a.list, a.repos_dir)
    else:
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            print("경고: GITHUB_TOKEN 이 없어 수집하지 않습니다. 기존 data/repos.json 을 그대로 둡니다.", file=sys.stderr)
            return 0
        try:
            data = scan_api(token)
        except (urllib.error.URLError, OSError, ValueError) as e:
            print("오류: GitHub API 호출 실패 (%s). 기존 data/repos.json 을 그대로 둡니다." % e, file=sys.stderr)
            return 1
        if not data:
            print("경고: 저장소를 하나도 받지 못해 기존 파일을 유지합니다.", file=sys.stderr)
            return 1
    text = json.dumps(data, ensure_ascii=False, indent=1) + "\n"
    old = None
    if os.path.exists(OUT):
        with open(OUT, encoding="utf-8") as f:
            old = f.read()
    if text != old:
        os.makedirs(DATA, exist_ok=True)
        with open(OUT, "w", encoding="utf-8") as f:
            f.write(text)
    counts = {}
    for e in data:
        counts[e["status"]] = counts.get(e["status"], 0) + 1
    print("data/repos.json: 저장소 %d개 %s%s" % (len(data), counts, "" if text != old else " (변경 없음)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
