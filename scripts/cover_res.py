#!/usr/bin/env python3
"""표지 해상도 점검 — 저장소마다 대표 표지(카드 썸네일의 원본)의 실제 픽셀 크기를 재서 저해상도를 가려낸다.

대표 표지는 make_thumbs.py가 고른 그림(thumbs/repos/_index.json 의 src)이다.
  manifest:경로 · og:경로 · name:경로 · file:경로 · redraw:Rxxx:경로  → 저장소 안 그림 파일
  embedded:페이지.html[#hero]                                       → 그 페이지에 박힌(base64) 그림
cover_manifest.json 에 적힌 표지 크기(repos.json covers[].size)도 함께 세어 둔다.

판정 (가로 픽셀 기준, 홈페이지 카드·첫 화면이 1200px 안팎으로 보이기 때문)
  ok    : 가로 1200 이상
  warn  : 960 ~ 1199  (작은 화면에서는 괜찮지만 큰 화면·공유 미리보기에서 흐릴 수 있음)
  low   : 960 미만     → 저해상도
  none  : 대표 표지를 찾지 못함

결과: data/cover_res.json  {"updated", "rule", "summary", "repos": {저장소: {...}}}
대표 그림(src)과 저장소 수정 시각(pushed_at)이 그대로면 다시 받지 않는다.

  python3 scripts/cover_res.py                    # 원본 파일을 GitHub에서 받아 잰다 (Actions)
  python3 scripts/cover_res.py --repos-dir DIR    # 로컬 사본이 있으면 먼저 쓴다
  python3 scripts/cover_res.py --all              # 모두 다시
"""
import argparse
import base64
import datetime as dt
import io
import json
import os
import re
import struct
import sys
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(DATA, "cover_res.json")
INDEX = os.path.join(ROOT, "thumbs", "repos", "_index.json")
OWNER = "adminmrobo"
OK_W, WARN_W = 1200, 960
URI_RE = re.compile(r"data:image/(?:png|jpe?g|webp|gif);base64,([A-Za-z0-9+/=]+)")


def load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def dims(b):
    """그림 머리글만 읽어 (가로, 세로). Pillow 없이 PNG·JPEG·WebP·GIF."""
    if not b or len(b) < 30:
        return None
    if b[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", b[16:24])
    if b[:6] in (b"GIF87a", b"GIF89a"):
        return struct.unpack("<HH", b[6:10])
    if b[:4] == b"RIFF" and b[8:12] == b"WEBP":
        k = b[12:16]
        if k == b"VP8X":
            return (1 + int.from_bytes(b[24:27], "little"), 1 + int.from_bytes(b[27:30], "little"))
        if k == b"VP8 ":
            w, h = struct.unpack("<HH", b[26:30])
            return (w & 0x3FFF, h & 0x3FFF)
        if k == b"VP8L":
            v = int.from_bytes(b[21:25], "little")
            return ((v & 0x3FFF) + 1, ((v >> 14) & 0x3FFF) + 1)
    if b[:2] == b"\xff\xd8":
        i = 2
        while i + 9 < len(b):
            if b[i] != 0xFF:
                i += 1
                continue
            m = b[i + 1]
            if m in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                h, w = struct.unpack(">HH", b[i + 5:i + 9])
                return (w, h)
            if m in (0xD8, 0x01) or 0xD0 <= m <= 0xD7:
                i += 2
                continue
            i += 2 + struct.unpack(">H", b[i + 2:i + 4])[0]
    return None


def fetch(repo, branch, path, repos_dir=None):
    if repos_dir:
        p = os.path.join(repos_dir, repo, path)
        if os.path.isfile(p):
            with open(p, "rb") as f:
                return f.read()
    url = "https://raw.githubusercontent.com/%s/%s/%s/%s" % (OWNER, repo, branch or "main", urllib.parse.quote(path))
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "ahnboat-cover-res"}), timeout=60) as r:
            return r.read()
    except Exception:
        return None


def embedded(html, hero):
    """페이지에 박힌 큰 그림 — make_thumbs.py와 같은 규칙(첫 화면 그림 먼저, 없으면 첫 가로 그림)."""
    first = None
    for m in URI_RE.finditer(html):
        if len(m.group(1)) < 20000:
            continue
        try:
            d = dims(base64.b64decode(m.group(1)[:65536]))
        except Exception:
            d = None
        if not d or d[0] < 480:
            continue
        near = html[max(0, m.start() - 300):m.start()].lower()
        if ("hero" in near or "cover" in near) and d[0] >= d[1]:
            return d
        if first is None and 1.05 <= d[0] / max(d[1], 1) <= 4:
            first = d
    return first


def grade(w):
    if not w:
        return "none"
    return "ok" if w >= OK_W else "warn" if w >= WARN_W else "low"


def measure(repo, branch, src, repos_dir):
    if not src:
        return None, None
    kind, _, rest = src.partition(":")
    if kind == "redraw":
        rest = rest.partition(":")[2]
    path = rest
    if kind == "embedded" or ".htm" in path.split("#")[0][-6:]:
        page = path.split("#")[0]
        b = fetch(repo, branch, page, repos_dir)
        return (embedded(b.decode("utf-8", "ignore"), "#hero" in path) if b else None), page
    path = path.split("#")[0]
    return dims(fetch(repo, branch, path, repos_dir)), path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repos-dir")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    repos = load(os.path.join(DATA, "repos.json"), [])
    idx = load(INDEX, {})
    prev = load(OUT, {}).get("repos", {})
    out = {}
    for e in repos:
        name = e["repo"]
        t = idx.get(name) or {}
        src = t.get("src")
        p = prev.get(name)
        if p and not a.all and p.get("src") == src and p.get("pushed_at") == e.get("pushed_at") and p.get("w") is not None:
            rec = dict(p)
        else:
            d, path = measure(name, e.get("default_branch"), src, a.repos_dir)
            rec = {"src": src, "path": path, "w": d[0] if d else 0, "h": d[1] if d else 0, "pushed_at": e.get("pushed_at")}
        # cover_manifest.json 에 적힌 표지 크기
        decl = [c for c in e.get("covers") or [] if c.get("role") in ("cover", "og", "hero") and c.get("size")]
        rec["declared"] = len(decl)
        rec["declared_low"] = sum(1 for c in decl if (c["size"][0] or 0) < WARN_W)
        rec["grade"] = grade(rec.get("w"))
        out[name] = rec
    summ = {}
    for r in out.values():
        summ[r["grade"]] = summ.get(r["grade"], 0) + 1
    kst = dt.timezone(dt.timedelta(hours=9))
    doc = {"updated": dt.datetime.now(kst).strftime("%Y-%m-%d %H:%M KST"),
           "rule": {"ok": "가로 %d px 이상" % OK_W, "warn": "가로 %d~%d px" % (WARN_W, OK_W - 1), "low": "가로 %d px 미만" % WARN_W,
                    "none": "대표 표지 없음"},
           "summary": summ, "repos": dict(sorted(out.items(), key=lambda x: x[0].lower()))}
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(json.dumps(doc, ensure_ascii=False, indent=1) + "\n")
    print("표지 해상도:", summ)


if __name__ == "__main__":
    main()
