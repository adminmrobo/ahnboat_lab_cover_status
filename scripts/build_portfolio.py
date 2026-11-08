#!/usr/bin/env python3
"""포트폴리오 목록을 만든다 (공개 정보만, 잠그지 않음).

사람이 고치는 표: data/portfolio.csv  (엑셀로 열어 고친 뒤 CSV UTF-8로 저장해 그대로 올림)
  칸: 대분류, 중분류, 제목, 소개, 링크, 이미지, 버튼글씨, 비고, 순서, 공개(Y/N)
  - 링크가 비면 카드에 '링크 준비 중'이 보인다.
  - 이미지는 https 주소나 사이트 안 경로. 비면 색 상자.
분야 설정: data/portfolio_meta.json (분야 순서·색·소개·색인어·그림, 갈래 소개)
만드는 파일: data/portfolio.json  (catalog.html?view=portfolio 가 읽음)
"""
import csv, datetime as dt, io, json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")


def read_csv(p):
    raw = open(p, "rb").read()
    for enc in ("utf-8-sig", "cp949"):
        try:
            text = raw.decode(enc); break
        except UnicodeDecodeError:
            continue
    return [{(k or "").strip(): (v or "").strip() for k, v in r.items()} for r in csv.DictReader(io.StringIO(text))]


def main():
    meta = json.load(open(os.path.join(DATA, "portfolio_meta.json"), encoding="utf-8"))
    cats = meta.get("categories", [])
    order = {c["name"]: k for k, c in enumerate(cats)}
    items = []
    for k, r in enumerate(read_csv(os.path.join(DATA, "portfolio.csv"))):
        if r.get("공개", "Y").upper() not in ("Y", "YES", "O", "예", ""):
            continue
        if not r.get("제목"):
            continue
        link = r.get("링크", "")
        items.append({"title": r["제목"], "summary": r.get("소개", ""), "cat": r.get("대분류", ""),
                      "mid": r.get("중분류", "") or r.get("대분류", ""), "sub": "",
                      "kind": "portfolio", "repo_url": "", "site_url": link if link.startswith("http") else "",
                      "link": link, "langs": [], "thumb": r.get("이미지", ""), "button": r.get("버튼글씨", ""),
                      "note": r.get("비고", ""),
                      "_o": (order.get(r.get("대분류", ""), 99), int(r["순서"]) if r.get("순서", "").isdigit() else 999, k)})
    items.sort(key=lambda x: x["_o"])
    for it in items:
        del it["_o"]
    kst = dt.timezone(dt.timedelta(hours=9))
    out = {"updated": dt.datetime.now(kst).date().isoformat(), "categories": cats, "mids": meta.get("mids", []),
           "hero": {}, "items": items}
    json.dump(out, open(os.path.join(DATA, "portfolio.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("포트폴리오 %d건" % len(items))


if __name__ == "__main__":
    main()
