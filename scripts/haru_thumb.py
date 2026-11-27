#!/usr/bin/env python3
"""하루의 실험실 막대 썸네일 규격으로 바꾸기 — docs/haru_thumb_spec.md

  python3 scripts/haru_thumb.py <원본 그림> <회차 번호 2자리>
  예) python3 scripts/haru_thumb.py ../haru_3d_classic_learning_model_01_lab/images/thumb_ep07.webp 07
  → thumbs/haru_lab/ep07.webp  (16:9 · 960×540 · WebP q82 · 가운데 기준 잘라 맞춤 · LANCZOS)
"""
import os, sys
from PIL import Image

W, H, Q, LIMIT = 960, 540, 82, 150 * 1024
src, no = sys.argv[1], sys.argv[2].zfill(2)
top = float(sys.argv[3]) if len(sys.argv) > 3 else 0.5   # 세로로 잘라낼 때 기준(0 위 · 0.5 가운데)
im = Image.open(src).convert("RGB")
w, h = im.size
if w / h > W / H:                      # 옆으로 길면 좌우를 자른다
    nw = round(h * W / H); x = (w - nw) // 2; im = im.crop((x, 0, x + nw, h))
else:                                  # 위아래로 길면 위아래를 자른다
    nh = round(w * H / W); y = round((h - nh) * top); im = im.crop((0, y, w, y + nh))
im = im.resize((W, H), Image.LANCZOS)
out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "thumbs", "haru_lab", "ep%s.webp" % no)
q = Q
while True:
    im.save(out, "WEBP", quality=q, method=6)
    if os.path.getsize(out) <= LIMIT or q <= 60:
        break
    q -= 6
print(out, im.size, os.path.getsize(out) // 1024, "KB", "q", q)
