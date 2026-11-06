#!/usr/bin/env python3
"""저장소마다 대표 표지를 골라 thumbs/repos/<저장소>.jpg 로 줄여 둔다. (Pillow 필요)

카드 썸네일은 "지금 사이트에 걸려 있는 그림"을 기준으로 한다. 저장소가 바뀌면
(pushed_at이 달라지면) 다시 만들고, 그대로면 건너뛴다. 무엇을 골랐는지는
thumbs/repos/_index.json 에 남긴다.

대표 그림을 고르는 순서
  1. cover_manifest.json 의 cover → og → hero 항목 (파일 또는 페이지에 박힌 그림)
  2. 주판봇 다시 그리기 목록(redraw.json)에서 이 저장소의 P1 그림 (표지·첫 화면)
  3. 첫 페이지(index.html)의 og:image
  4. 파일 이름에 cover · og · hero · thumb 가 들어간 그림 (없으면 sc_ 장면 그림)
  5. redraw.json 의 나머지(P2 본문 장면) 그림
  6. 페이지에 박힌(base64) 그림 — 첫 화면(hero·cover) 그림 먼저, 없으면 첫 가로 그림
  7. 저장소 안의 가로 그림 파일 (정사각·세로인 표정 그림은 제외)

  python3 scripts/make_thumbs.py --repos-dir DIR      # 저장소 사본이 있는 폴더에서
  python3 scripts/make_thumbs.py --fetch              # 바뀐 저장소만 받아서 (Actions에서 매일)
  python3 scripts/make_thumbs.py --fetch --all        # 모두 다시
"""
import argparse
import base64
import datetime as dt
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

from PIL import Image

OWNER = "adminmrobo"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
OUT_DIR = os.path.join(ROOT, "thumbs", "repos")
INDEX = os.path.join(OUT_DIR, "_index.json")
WIDTH = 480

IMG_RE = re.compile(r"\.(png|jpe?g|webp|gif|avif)$", re.I)
ROLE_RE = re.compile(r"(?:^|[_\-.])(cover|og|hero|thumb)(?=$|[_\-.\d])|^(sc)_", re.I)
ROLE_ORDER = {"cover": 0, "og": 1, "hero": 2, "thumb": 3, "sc": 4}
URI_RE = re.compile(r"data:image/(?:webp|png|jpe?g);base64,([A-Za-z0-9+/=]+)")
OG_RE = re.compile(r'property="og:image"\s+content="([^"]+)"')


def load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def open_img(data):
    try:
        im = Image.open(io.BytesIO(data))
        im.load()
        return im
    except Exception:
        return None


def read_bytes(repo_dir, rel):
    p = os.path.join(repo_dir, rel)
    if os.path.isfile(p):
        with open(p, "rb") as f:
            return f.read()
    return None


def key_token(key):
    """'img.hero-img', 'data-img=cover_05', 'SPR.sc_carpet' → 찾을 낱말."""
    key = (key or "").split(" (")[0]
    for pat in (r'data-img=\\?"?([\w\-]+)', r"SPR\.([\w\-]+)", r"\.([\w\-]+)$", r"([\w\-]+)$"):
        m = re.search(pat, key)
        if m:
            return m.group(1)
    return None


def embedded(repo_dir, page, key):
    raw = read_bytes(repo_dir, page)
    if not raw:
        return None
    text = raw.decode("utf-8", "ignore")
    tok = key_token(key)
    for m in URI_RE.finditer(text):
        if tok and tok in text[max(0, m.start() - 300):m.start()]:
            return base64.b64decode(m.group(1))
    return None


def from_item(repo_dir, it):
    """manifest 항목 또는 redraw target → (그림 바이트, 출처)."""
    path = it.get("path") or ""
    emb = it.get("embedded_in")
    if isinstance(emb, list):
        emb = emb[0] if emb else None
    if it.get("kind") in (None, "file") and path and IMG_RE.search(path):
        return read_bytes(repo_dir, path), path
    page = emb or path
    if page and it.get("key"):
        b = embedded(repo_dir, page, it["key"])
        if b:
            return b, "%s#%s" % (page, key_token(it["key"]))
    return None, None


def pick(repo, repo_dir, redraw):
    """(이미지, 출처 설명)을 돌려준다. 못 찾으면 (None, None)."""
    # 1. manifest
    man = load(os.path.join(repo_dir, "cover_manifest.json"), None)
    if man:
        items = sorted([i for i in man.get("items", []) if i.get("role") in ("cover", "og", "hero")],
                       key=lambda i: ROLE_ORDER[i["role"]])
        for it in items:
            b, src = from_item(repo_dir, it)
            im = b and open_img(b)
            if im:
                return im, "manifest:" + src
    # 2. redraw 목록의 P1 (표지·첫 화면, 지금은 모두 새 그림으로 반영됨)
    mine = []
    for x in redraw:
        for t in x.get("targets", []):
            if t.get("repo") == repo:
                mine.append((0 if x.get("priority") == "P1" else 1, x["id"], t))
    mine.sort(key=lambda m: (m[0], m[1]))

    def from_redraw(pri):
        for p, rid, t in mine:
            if p != pri:
                continue
            b, src = from_item(repo_dir, t)
            im = b and open_img(b)
            if im:
                return im, "redraw:%s:%s" % (rid, src)
        return None, None

    im, src = from_redraw(0)
    if im:
        return im, src
    index = read_bytes(repo_dir, "index.html") or b""
    html = index.decode("utf-8", "ignore")
    # 3. og:image
    m = OG_RE.search(html[:65536])
    if m and not m.group(1).startswith(("http:", "https:", "data:")):
        rel = m.group(1).lstrip("./")
        b = read_bytes(repo_dir, rel)
        im = b and open_img(b)
        if im:
            return im, "og:" + rel
    # 4. 파일 이름
    found = []
    for dp, dn, fn in os.walk(repo_dir):
        dn[:] = [d for d in dn if not d.startswith(".") and d not in ("archive", "node_modules")]
        for f in fn:
            if not IMG_RE.search(f):
                continue
            mm = ROLE_RE.search(os.path.splitext(f)[0])
            if mm:
                rel = os.path.relpath(os.path.join(dp, f), repo_dir)
                found.append((ROLE_ORDER[(mm.group(1) or mm.group(2)).lower()], rel.count(os.sep), rel))
    for _, _, rel in sorted(found):
        im = open_img(read_bytes(repo_dir, rel) or b"")
        if im and im.width >= 320:
            return im, "name:" + rel
    # 5. redraw 목록의 본문 장면
    im, src = from_redraw(1)
    if im:
        return im, src
    # 6. 페이지에 박힌 그림 (첫 페이지 먼저, 다음은 맨 위 폴더의 페이지 순서대로)
    roots = sorted(f for f in os.listdir(repo_dir) if f.endswith(".html") and f != "index.html")
    pages = (["index.html"] if index else []) + roots[:12]
    for page in pages:
        text = (read_bytes(repo_dir, page) or b"").decode("utf-8", "ignore")
        first = None
        for m in URI_RE.finditer(text):
            if len(m.group(1)) < 20000:  # 작은 아이콘·표정 그림은 건너뜀
                continue
            im = open_img(base64.b64decode(m.group(1)))
            if not im or im.width < 480:
                continue
            near = text[max(0, m.start() - 300):m.start()].lower()
            if ("hero" in near or "cover" in near) and im.width / im.height >= 1.0:
                return im, "embedded:%s#hero" % page  # 첫 화면 그림이 가장 확실하다
            if first is None and wide(im):
                first = im
        if first is not None:
            return first, "embedded:%s" % page
    # 7. 저장소 안의 가로 그림 파일 (정사각·세로인 표정 그림은 제외)
    files = []
    for dp, dn, fn in os.walk(repo_dir):
        dn[:] = [d for d in dn if not d.startswith(".") and d not in ("archive", "node_modules")]
        if os.path.relpath(dp, repo_dir).count(os.sep) > 2:
            continue
        files += [os.path.relpath(os.path.join(dp, f), repo_dir) for f in fn if IMG_RE.search(f)]
    for rel in sorted(files, key=lambda r: (r.count(os.sep), r)):
        im = open_img(read_bytes(repo_dir, rel) or b"")
        if wide(im, 600):
            return im, "file:" + rel
    return None, None


def wide(im, min_w=480):
    return bool(im) and im.width >= min_w and 1.05 <= im.width / im.height <= 4


def save(im, repo):
    im = im.convert("RGB")
    im.thumbnail((WIDTH, WIDTH))
    os.makedirs(OUT_DIR, exist_ok=True)
    im.save(os.path.join(OUT_DIR, repo + ".jpg"), "JPEG", quality=82, optimize=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repos-dir", help="<저장소 이름>/ 사본이 있는 폴더")
    ap.add_argument("--fetch", action="store_true", help="바뀐 저장소만 git clone --depth 1 로 받아서 만든다")
    ap.add_argument("--all", action="store_true", help="바뀌지 않은 저장소도 다시 만든다")
    a = ap.parse_args()
    if not a.repos_dir and not a.fetch:
        ap.error("--repos-dir 또는 --fetch 가 필요합니다")

    repos = load(os.path.join(DATA, "repos.json"), [])
    redraw = load(os.path.join(DATA, "redraw.json"), [])
    idx = load(INDEX, {})
    tmp = tempfile.mkdtemp() if a.fetch else None
    made = kept = none = 0
    try:
        for e in repos:
            repo, pushed = e["repo"], e.get("pushed_at")
            old = idx.get(repo)
            if not a.all and old and pushed and old.get("pushed_at") == pushed:
                kept += 1
                continue
            if a.fetch:
                d = os.path.join(tmp, repo)
                r = subprocess.run(["git", "clone", "-q", "--depth", "1",
                                    "https://github.com/%s/%s.git" % (OWNER, repo), d], capture_output=True)
                if r.returncode != 0:
                    print("받기 실패", repo, file=sys.stderr)
                    continue
            else:
                d = os.path.join(a.repos_dir, repo)
                if not os.path.isdir(d):
                    continue
            im, src = pick(repo, d, redraw)
            if im:
                save(im, repo)
                idx[repo] = {"src": src, "pushed_at": pushed,
                             "made": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date().isoformat()}
                made += 1
            else:
                p = os.path.join(OUT_DIR, repo + ".jpg")
                if os.path.exists(p):
                    os.remove(p)
                idx[repo] = {"src": None, "pushed_at": pushed}
                none += 1
            if a.fetch:
                shutil.rmtree(d, ignore_errors=True)
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)
    live = {e["repo"] for e in repos}
    idx = {k: v for k, v in sorted(idx.items(), key=lambda kv: kv[0].lower()) if k in live}
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(INDEX, "w", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False, indent=1)
        f.write("\n")
    # 카드가 바로 새 썸네일을 쓰도록 repos.json 의 thumb 을 맞춘다
    changed = 0
    for e in repos:
        local = "thumbs/repos/%s.jpg" % e["repo"]
        if os.path.exists(os.path.join(ROOT, local)):
            want = local
        elif e.get("thumb") == local:
            ids = e.get("redraw_ids") or []
            want = "thumbs/%s.jpg" % ids[0] if ids else None
        else:
            continue
        if e.get("thumb") != want:
            e["thumb"] = want
            changed += 1
    if changed:
        with open(os.path.join(DATA, "repos.json"), "w", encoding="utf-8") as f:
            f.write(json.dumps(repos, ensure_ascii=False, indent=1) + "\n")
    print("썸네일 새로 %d · 그대로 %d · 대표 그림 없음 %d · 카드 연결 %d곳 바꿈" % (made, kept, none, changed))


if __name__ == "__main__":
    main()
