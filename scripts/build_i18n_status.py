#!/usr/bin/env python3
"""번역 현황 — 공개 콘텐츠(data/catalog.json)를 언어별로 얼마나 옮겼는지 data/i18n_status.json 에 쓴다.

번역률(언어 L) = 공개 콘텐츠마다 min(1, L 페이지 수 / 한국어 페이지 수) 의 평균
  - 다 옮긴 콘텐츠는 1, 일부만 옮긴 콘텐츠는 옮긴 페이지 비율, 한국어만 있으면 0
  - 페이지 수는 표지 현황 수집(scan_repos.py)이 실제 파일에서 센 값(repos.json i18n.pages)
홈페이지 헤드(top.html)의 언어 버튼 아래와 관리실(admin.html)이 이 파일을 읽는다.
번역 요청 대기열(data/translate_queue.json)에서 끝난 요청은 여기서 '완료'로 표시한다.
"""
import datetime as dt
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
LANGS = ["ko", "en", "zh", "ja", "uz", "ru", "vi"]


def load(name, default):
    try:
        with open(os.path.join(DATA, name), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def repo_of(url):
    m = re.search(r"github\.com/[^/]+/([^/?#]+)", url or "") or re.search(r"https://[^.]+\.github\.io/([^/?#]+)", url or "")
    return m.group(1) if m else None


def main():
    repos = {e["repo"]: e for e in load("repos.json", [])}
    cat = load("catalog.json", {})
    seen, rows = set(), []
    for it in cat.get("items", []):
        name = repo_of(it.get("repo_url")) or repo_of(it.get("site_url"))
        if not name or name in seen or name not in repos:
            continue
        seen.add(name)
        rows.append(repos[name])
    targets = LANGS[1:]
    acc = {l: 0.0 for l in targets}
    full = {l: 0 for l in targets}
    part = {l: 0 for l in targets}
    states = {"all": 0, "some": 0, "ko": 0}
    for e in rows:
        pages = ((e.get("i18n") or {}).get("pages")) or {}
        base = pages.get("ko") or max(pages.values() or [0]) or 0
        done = nfull = 0
        for l in targets:
            n = pages.get(l, 0)
            r = min(1.0, n / base) if base else (1.0 if n else 0.0)
            acc[l] += r
            if r >= 1:
                full[l] += 1
                done += 1
                nfull += 1
            elif r > 0:
                part[l] += 1
                done += 1
        states["all" if nfull == len(targets) else "some" if done else "ko"] += 1
    n = len(rows) or 1
    out = {
        "updated": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M KST"),
        "rule": "공개 콘텐츠마다 min(1, 그 언어 페이지 수 / 한국어 페이지 수)의 평균",
        "contents": len(rows),
        "states": states,
        "langs": {"ko": {"rate": 1.0, "full": len(rows), "partial": 0}},
    }
    for l in targets:
        out["langs"][l] = {"rate": round(acc[l] / n, 4), "full": full[l], "partial": part[l]}
    # 번역 요청 대기열: 이미 그 언어가 다 있는 요청은 '완료'로
    q = load("translate_queue.json", None)
    if q and isinstance(q.get("requests"), list):
        changed = False
        for r in q["requests"]:
            e = repos.get(r.get("repo"))
            if not e or r.get("status") == "done":
                continue
            pages = ((e.get("i18n") or {}).get("pages")) or {}
            base = pages.get("ko") or 0
            if base and all(pages.get(l, 0) >= base for l in r.get("langs", [])):
                r["status"] = "done"
                r["done_at"] = out["updated"][:10]
                changed = True
        if changed:
            with open(os.path.join(DATA, "translate_queue.json"), "w", encoding="utf-8") as f:
                f.write(json.dumps(q, ensure_ascii=False, indent=1) + "\n")
    with open(os.path.join(DATA, "i18n_status.json"), "w", encoding="utf-8") as f:
        f.write(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
    print("번역 현황:", {l: "%.1f%%" % (v["rate"] * 100) for l, v in out["langs"].items()}, out["states"])


if __name__ == "__main__":
    main()
