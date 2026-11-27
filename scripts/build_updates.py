#!/usr/bin/env python3
"""업데이트 이력 → 홈페이지 자동 공지.

하는 일 (표지 현황 수집 때마다, 카탈로그를 만든 뒤에 돈다)
  1) data/repos.json(저장소별 pushed_at·size_bytes)과 data/catalog.json(공개 콘텐츠)을 읽는다.
     공개 카탈로그에 오른 저장소만 본다 — 아직 공개일이 안 된 콘텐츠는 공지에 나오지 않는다.
  2) 지난번에 본 상태(data/updates.json의 state)와 비교해 이력(log)을 쌓는다.
       - 카탈로그에 처음 오른 저장소  → kind "new"     (그날 날짜, 크기 = 저장소 전체 용량)
       - pushed_at이 바뀐 저장소       → kind "update"  (push한 날짜, 크기 = 바뀐 용량의 절댓값)
     같은 날 같은 저장소가 여러 번 바뀌면 한 줄로 합친다(크기는 더한다).
  3) 이력에서 날짜마다 공지를 만든다 → data/notices_auto.csv (날짜, 제목, 링크, 표시)
       - 하루 이력이 많으면 용량이 큰 순서로 최대 4건(MAX_PER_DAY)만 공지로 만든다.
       - 아주 작은 수정(MIN_UPDATE_BYTES 미만)은 이력에는 남기되 공지로 만들지 않는다.
     손으로 쓰는 공지(data/notices.csv, 콘텐츠 관리실 '공지사항' 탭)는 건드리지 않는다.
     홈페이지(top.html)는 두 파일을 합쳐 최근 공지를 보여 준다.

처음 돌 때(state가 비어 있을 때)는 최근 BOOT_DAYS일 안에 push된 공개 저장소를
"update"로 기록해 공지 칸이 비지 않게 한다(크기 = 저장소 전체 용량).
"""
import csv
import datetime as dt
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
D = lambda *p: os.path.join(ROOT, "data", *p)
KST = dt.timezone(dt.timedelta(hours=9))

MAX_PER_DAY = 4          # 하루 공지 최대 건수 (용량이 큰 순서)
MIN_UPDATE_BYTES = 1024  # 이보다 작게 바뀐 업데이트는 공지로 만들지 않는다
KEEP_DAYS = 90           # 이력 보관 기간
NOTICE_DAYS = 30         # 자동 공지로 내보낼 기간
BOOT_DAYS = 7            # 처음 돌 때 거슬러 올라갈 기간


def load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def kst_date(iso):
    if not iso:
        return None
    try:
        t = dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None
    return t.astimezone(KST).date().isoformat()


def repo_of(url):
    m = re.match(r"https://github\.com/[^/]+/([^/?#]+)", url or "")
    return m.group(1) if m else None


def public_items():
    """공개 카탈로그의 저장소 → (제목, 링크). 한 저장소가 여러 줄이면 첫 줄."""
    out = {}
    for i in (load(D("catalog.json"), {}) or {}).get("items", []):
        if i.get("kind") != "repo":
            continue
        r = repo_of(i.get("repo_url"))
        if r and r not in out and i.get("title"):
            out[r] = {"title": i["title"], "link": i.get("site_url") or "https://adminmrobo.github.io/%s/" % r}
    return out


def notice_title(e):
    return ("새 콘텐츠 공개 — " if e["kind"] == "new" else "업데이트 — ") + e["title"]


def main():
    today = dt.datetime.now(KST).date()
    repos = {e["repo"]: e for e in load(D("repos.json"), [])}
    pub = public_items()
    old = load(D("updates.json"), {})
    state = old.get("state") or {}
    log = old.get("log") or []
    boot = not state
    idx = {(e["date"], e["repo"]): e for e in log}

    def add(date, repo, kind, size):
        info = pub[repo]
        e = idx.get((date, repo))
        if e:
            e["size"] += size
            if kind == "new":
                e["kind"] = "new"
            e["title"], e["link"] = info["title"], info["link"]
        else:
            e = {"date": date, "repo": repo, "kind": kind, "title": info["title"], "link": info["link"], "size": size}
            idx[(date, repo)] = e
            log.append(e)

    new_state = {}
    for repo in sorted(pub):
        r = repos.get(repo)
        if not r:
            continue
        pushed, size = r.get("pushed_at"), r.get("size_bytes")
        new_state[repo] = {"pushed_at": pushed, "size": size}
        prev = state.get(repo)
        if boot:
            d = kst_date(pushed)
            if d and (today - dt.date.fromisoformat(d)).days < BOOT_DAYS:
                add(d, repo, "update", size if size is not None else MIN_UPDATE_BYTES)
        elif prev is None:
            add(today.isoformat(), repo, "new", size or 0)
        elif pushed and pushed != prev.get("pushed_at"):
            if size is not None and prev.get("size") is not None:
                delta = abs(size - prev["size"])
            else:
                delta = MIN_UPDATE_BYTES  # 용량을 모르면 공지 기준선으로 둔다
            add(kst_date(pushed) or today.isoformat(), repo, "update", delta)
    # 비공개로 바뀌었거나 사라진 저장소는 상태에서 뺀다(다시 공개되면 '새 콘텐츠'로 잡힌다)

    cut = (today - dt.timedelta(days=KEEP_DAYS)).isoformat()
    log = sorted((e for e in log if e["date"] >= cut), key=lambda e: (-e["size"], e["repo"]))
    log.sort(key=lambda e: e["date"], reverse=True)  # 최근 날짜 먼저, 같은 날은 용량 큰 순서

    # 자동 공지: 날짜마다 용량 큰 순서로 최대 MAX_PER_DAY건
    ncut = (today - dt.timedelta(days=NOTICE_DAYS)).isoformat()
    by_day = {}
    for e in log:
        if e["date"] < ncut:
            continue
        if e["kind"] == "update" and e["size"] < MIN_UPDATE_BYTES:
            continue
        by_day.setdefault(e["date"], []).append(e)
    rows = []
    for day in sorted(by_day, reverse=True):
        for e in sorted(by_day[day], key=lambda e: (-e["size"], e["repo"]))[:MAX_PER_DAY]:
            rows.append([day, notice_title(e), e["link"], "Y"])
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["날짜", "제목", "링크", "표시"])
    w.writerows(rows)
    text = "﻿" + buf.getvalue()

    out = {
        "_guide": "업데이트 이력 — scripts/build_updates.py가 표지 현황 수집 때마다 만든다. state는 지난번에 본 공개 저장소의 "
                  "pushed_at·용량, log는 날짜별 이력(size는 바뀐 용량 바이트, new는 전체 용량). 홈페이지 자동 공지는 "
                  "data/notices_auto.csv (하루 최대 %d건, 용량 큰 순서, %d바이트 미만 수정은 제외)." % (MAX_PER_DAY, MIN_UPDATE_BYTES),
        "rules": {"max_per_day": MAX_PER_DAY, "min_update_bytes": MIN_UPDATE_BYTES, "keep_days": KEEP_DAYS,
                  "notice_days": NOTICE_DAYS},
        "log": log,
        "state": new_state,
    }
    with open(D("updates.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.write("\n")
    old_csv = open(D("notices_auto.csv"), encoding="utf-8").read() if os.path.exists(D("notices_auto.csv")) else None
    if text != old_csv:
        with open(D("notices_auto.csv"), "w", encoding="utf-8") as f:
            f.write(text)
    print("업데이트 이력 %d줄%s · 자동 공지 %d건" % (len(log), " (처음 기록)" if boot else "", len(rows)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
