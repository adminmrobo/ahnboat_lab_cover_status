#!/usr/bin/env python3
"""(선택, 로컬 전용) 저장소 사본에서 대표 표지를 찾아 thumbs/repos/<저장소>.jpg 로 줄여 둔다.

Pillow 가 필요하다. 자동 수집(scan_repos.py)에는 필요 없다. 썸네일 파일이 있으면
scan_repos.py 가 그 파일을 대표 그림으로 쓰고, 없으면 사이트의 원본 그림 주소를 쓴다.

  python3 scripts/make_thumbs.py --repos-dir DIR && python3 scripts/scan_repos.py --local ...
"""
import argparse, json, os
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--repos-dir", required=True)
    ap.add_argument("--width", type=int, default=480); a = ap.parse_args()
    data = json.load(open(os.path.join(ROOT, "data", "repos.json"), encoding="utf-8"))
    os.makedirs(os.path.join(ROOT, "thumbs", "repos"), exist_ok=True)
    n = 0
    for e in data:
        t = e.get("thumb") or ""
        if not t.startswith(e["pages_url"]):
            continue
        src = os.path.join(a.repos_dir, e["repo"], t[len(e["pages_url"]):])
        if not os.path.isfile(src):
            continue
        try:
            im = Image.open(src); im.thumbnail((a.width, a.width)); im = im.convert("RGB")
        except Exception as ex:  # 손상·미지원 형식
            print("건너뜀", e["repo"], ex); continue
        im.save(os.path.join(ROOT, "thumbs", "repos", e["repo"] + ".jpg"), "JPEG", quality=82, optimize=True); n += 1
    print("썸네일 %d장" % n)

if __name__ == "__main__":
    main()
