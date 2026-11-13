#!/usr/bin/env python3
"""오늘의 레포트 — GoatCounter 숫자를 조수 하루가 설명하는 메일로 보낸다.

하는 일
  1) GoatCounter API에서 어제(한국 시간) 방문·콘텐츠 클릭·유입 경로와 최근 30일 추이를 읽는다.
     + 저장소에 모아 둔 목록에서 콘텐츠 수·번역·온톨로지 적용 현황을 센다.
  2) 하루의 말풍선 해설을 만들고, 메일(HTML)을 보낸다. 같은 내용을 글자만 있는 파일(.md)로도 붙인다.
  3) 같은 숫자를 관리자 키로 잠가 data/report/ 에 남긴다(report.html이 풀어서 보여 준다).
     - 날짜.json.enc  그날 하루치 (일자별 조회용, 계속 쌓인다)
     - latest.json.enc 가장 최근 하루치
     - index.json      쌓인 날짜 목록 (날짜만 들어 있어 잠그지 않는다)
  4) 날짜별 파일이 비어 있는 지난 날(최대 30일)은 GoatCounter에서 다시 읽어 채운다(메일은 보내지 않는다).

환경 변수(GitHub Secrets)
  GOATCOUNTER_TOKEN   GoatCounter API 키 (통계 읽기)
  HUB_KEY             관리자 키 (레포트 데이터 잠금)
  GMAIL_ADDRESS       보내는/받는 Gmail 주소
  GMAIL_APP_PASSWORD  Gmail 앱 비밀번호
  REPORT_DAY          (선택) YYYY-MM-DD 로 날짜를 정해 다시 만들 때
  REPORT_SAMPLE       (선택) 예시 숫자 JSON 파일 경로 — API 없이 견본을 만들 때
  REPORT_OUT          (선택) 메일 HTML을 파일로도 저장할 경로
  REPORT_BACKFILL     (선택) 지난 날을 몇 일치까지 채울지 (기본 30, 0이면 채우지 않음)
"""
import datetime as dt
import json
import os
import re
import smtplib
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

SITE = "https://ahnboat.goatcounter.com"
PAGES = "https://adminmrobo.github.io/ahnboat_lab_cover_status/"
KST = dt.timezone(dt.timedelta(hours=9))
MENU = {"server": "Lab Server", "articles": "Articles", "portfolio": "Portfolio"}
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
REPORT_DIR = os.path.join(ROOT, "data", "report")
DAY_FILE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.json\.enc$")
LANGS = ["en", "zh", "ja", "uz", "ru", "vi"]
LANG_KO = {"en": "영어", "zh": "중국어", "ja": "일본어", "uz": "우즈베크어", "ru": "러시아어", "vi": "베트남어"}


# ---------------------------------------------------------------- GoatCounter
def api(path, **q):
    tok = os.environ.get("GOATCOUNTER_TOKEN", "")
    url = SITE + "/api/v0" + path + ("?" + urllib.parse.urlencode(q) if q else "")
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + tok,
                                               "Content-Type": "application/json",
                                               "User-Agent": "ahnboat-daily-report"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:400]
        print(f"GoatCounter {path} → {e.code}: {body}")
        raise


def daily_map(stats):
    """[{day, daily}, ...] → {YYYY-MM-DD: count}"""
    out = {}
    for s in stats or []:
        day = str(s.get("day", ""))[:10]
        if day:
            out[day] = out.get(day, 0) + int(s.get("daily") or 0)
    return out


def collect(day):
    d0 = day - dt.timedelta(days=29)
    w0 = day - dt.timedelta(days=6)
    iso = lambda x: x.isoformat() + "T00:00:00Z"
    end = (day + dt.timedelta(days=1)).isoformat() + "T00:00:00Z"
    tot = api("/stats/total", start=iso(d0), end=end)
    series = daily_map(tot.get("stats"))
    hits, after = [], None
    for _ in range(5):  # 최대 500개 경로
        q = dict(start=iso(w0), end=end, limit=100)
        if after:
            q["exclude_paths"] = after
        r = api("/stats/hits", **q)
        hits += r.get("hits") or []
        if not r.get("more"):
            break
        after = ",".join(str(h["path_id"]) for h in hits)
    try:
        refs = api("/stats/toprefs", start=iso(day), end=end, limit=10).get("stats") or []
    except Exception:
        refs = []
    return {"series": series, "hits": hits, "refs": refs}


# ---------------------------------------------------------------- 콘텐츠 현황
def _load(rel):
    try:
        return json.load(open(os.path.join(ROOT, rel), encoding="utf-8"))
    except (OSError, ValueError):
        return None


def inventory():
    """저장소에 모아 둔 목록으로 콘텐츠 수·번역·온톨로지 현황을 센다 (없는 자료는 건너뜀)."""
    inv = {}
    sc = _load("data/site_contents.json")
    if sc:
        wp = sc.get("wordpress") or {}
        inv["posts"] = len(wp.get("posts") or [])
        inv["portfolio"] = len(sc.get("portfolio") or [])
        inv["list_at"] = sc.get("fetched_at", "")
    cat = _load("data/catalog.json")
    if cat:
        items = cat.get("items") or []
        repos = [x for x in items if x.get("kind") == "repo"]
        onto = _load("data/ontology.json") or {}
        tagged = {p.get("repo") for p in onto.get("pages") or []}
        inv["contents"] = len(items)
        inv["external"] = len(items) - len(repos)
        inv["korean"] = len(repos)
        full = part = 0
        by = {k: 0 for k in LANGS}
        todo_tr, todo_onto = [], []
        for x in repos:
            name = (x.get("repo_url") or "").rstrip("/").split("/")[-1]
            have = [k for k in LANGS if k in (x.get("langs") or [])]
            for k in have:
                by[k] += 1
            if len(have) == len(LANGS):
                full += 1
            elif have:
                part += 1
                todo_tr.append({"name": name, "title": x.get("title", ""), "missing": [k for k in LANGS if k not in have]})
            if name in tagged:
                inv["onto"] = inv.get("onto", 0) + 1
            else:
                todo_onto.append(name)
        inv.setdefault("onto", 0)
        inv.update({"tr_full": full, "tr_part": part, "tr_none": len(repos) - full - part,
                    "by_lang": by, "tr_partial_list": todo_tr[:20], "onto_todo": len(todo_onto)})
        s = onto.get("summary") or {}
        inv["concepts"] = s.get("concepts", 0)
    return inv


def previous(day):
    """하루 전 레포트를 풀어 콘텐츠 수를 비교한다 (키가 없거나 처음이면 빈 값).
    하루 전 날짜 파일이 있으면 그것을, 없으면 latest를 쓴다(같은 날 다시 돌려도 증감이 지워지지 않게)."""
    key = os.environ.get("HUB_KEY", "")
    path = day_path(day - dt.timedelta(days=1))
    if not os.path.exists(path):
        path = os.path.join(REPORT_DIR, "latest.json.enc")
    if not key or not os.path.exists(path):
        return {}
    try:
        sys.path.insert(0, HERE)
        from hubcrypt import decrypt
        old = json.loads(decrypt(open(path, "rb").read(), key).decode("utf-8"))
        if old.get("date", "") >= day.isoformat():
            return {}
        return old.get("inventory") or {}
    except Exception:
        return {}


# ---------------------------------------------------------------- 숫자 정리
def build(raw, day, with_inventory=True):
    ds = day.isoformat()
    prev = (day - dt.timedelta(days=1)).isoformat()
    days7 = [(day - dt.timedelta(days=k)).isoformat() for k in range(6, -1, -1)]
    days30 = [(day - dt.timedelta(days=k)).isoformat() for k in range(29, -1, -1)]
    series = raw["series"]
    pages, clicks = [], []
    for h in raw["hits"]:
        dm = daily_map(h.get("stats"))
        row = {"path": h.get("path", ""), "title": (h.get("title") or "").strip(),
               "day": dm.get(ds, 0), "week": [dm.get(x, 0) for x in days7]}
        row["week_sum"] = sum(row["week"])
        p = row["path"]
        if h.get("event") or p.startswith("click/"):
            parts = p.split("/", 2)
            row["menu"] = parts[1] if len(parts) > 2 else "기타"
            row["name"] = parts[2] if len(parts) > 2 else p
            clicks.append(row)
        else:
            pages.append(row)
    pages.sort(key=lambda r: (-r["day"], -r["week_sum"]))
    clicks.sort(key=lambda r: (-r["day"], -r["week_sum"]))
    menus = {}
    for c in clicks:
        m = menus.setdefault(c["menu"], {"day": 0, "week": 0})
        m["day"] += c["day"]
        m["week"] += c["week_sum"]
    pv = series.get(ds, sum(r["day"] for r in pages))
    pv_prev = series.get(prev, 0)
    week = [series.get(x, 0) for x in days7]
    last_week = sum(series.get(x, 0) for x in days30[16:23])
    rep = {
        "date": ds, "dow": "월화수목금토일"[day.weekday()],
        "generated": dt.datetime.now(KST).strftime("%Y-%m-%d %H:%M"),
        "pageviews": pv, "pageviews_prev": pv_prev,
        "clicks": sum(c["day"] for c in clicks),
        "week": [{"day": x, "count": c} for x, c in zip(days7, week)],
        "month": [{"day": x, "count": series.get(x, 0)} for x in days30],
        "week_total": sum(week), "last_week_total": last_week,
        "top_pages": pages[:10], "top_clicks": clicks[:15], "menus": menus,
        "refs": [{"name": (r.get("name") or "(직접 방문)"), "count": int(r.get("count") or 0)} for r in raw["refs"]][:8],
    }
    inv = inventory() if with_inventory else {}
    if inv:
        old = previous(day)
        inv["delta"] = {k: inv[k] - old[k] for k in ("contents", "posts", "tr_full", "onto")
                        if isinstance(inv.get(k), int) and isinstance(old.get(k), int) and inv[k] != old[k]}
    rep["inventory"] = inv
    rep.update(narrate(rep))
    return rep


def pct(a, b):
    return None if not b else round((a - b) * 100 / b)


def narrate(r):
    pv, pp = r["pageviews"], r["pageviews_prev"]
    ch = pct(pv, pp)
    if pv == 0:
        mood, head = "E09", "어제는 연구실이 조용했어요… 방문 기록이 없어요."
    elif ch is None:
        mood, head = "E01", f"어제 연구실 문이 {pv:,}번 열렸어요!"
    elif ch >= 30:
        mood, head = "E12", f"와아! 어제 {pv:,}번 열렸어요. 그저께보다 {ch}%나 늘었어요!"
    elif ch >= 5:
        mood, head = "E01", f"어제는 {pv:,}번 열렸어요. 그저께보다 {ch}% 늘었어요 ✨"
    elif ch > -5:
        mood, head = "E07", f"어제는 {pv:,}번, 그저께와 거의 같아요. 꾸준한 게 제일이죠!"
    else:
        mood, head = "E09", f"어제는 {pv:,}번… 그저께보다 {abs(ch)}% 줄었어요. 음, 다시 볼게요."
    lines = [head]
    wk, lw = r["week_total"], r["last_week_total"]
    wch = pct(wk, lw)
    if wk:
        lines.append(f"최근 7일 동안은 모두 {wk:,}번이에요" + (f", 지난주보다 {wch:+d}%." if wch is not None else "."))
    if r["top_clicks"] and r["top_clicks"][0]["day"]:
        c = r["top_clicks"][0]
        lines.append(f"어제 가장 많이 열린 콘텐츠는 「{c['title'] or c['name']}」({MENU.get(c['menu'], c['menu'])}, {c['day']}번)이에요!")
    elif r["top_clicks"]:
        c = r["top_clicks"][0]
        lines.append(f"어제는 콘텐츠 클릭이 없었어요. 이번 주 1등은 「{c['title'] or c['name']}」({c['week_sum']}번)이에요.")
    else:
        lines.append("콘텐츠 클릭 기록은 아직 쌓이는 중이에요. 내일부터 순위를 보여 드릴게요!")
    if r["menus"]:
        best = max(r["menus"].items(), key=lambda kv: (kv[1]["day"], kv[1]["week"]))
        lines.append(f"메뉴 중에서는 {MENU.get(best[0], best[0])}이(가) 제일 인기였어요.")
    if r["refs"]:
        lines.append(f"손님들은 주로 「{r['refs'][0]['name']}」에서 들어왔어요.")
    inv = r.get("inventory") or {}
    if inv.get("korean"):
        d = inv.get("delta") or {}
        new = f" 어제보다 {d['contents']:+d}개!" if d.get("contents") else ""
        lines.append(f"연구실 콘텐츠는 모두 {inv['contents']}개예요.{new} 해설 {inv['korean']}개 가운데 "
                     f"6개 언어 번역이 끝난 건 {inv['tr_full']}개, 온톨로지를 붙인 건 {inv['onto']}개예요.")
    lines.append("자세한 그래프는 ‘하루와 자세히 보기’에서 같이 봐요!")
    return {"mood": mood, "lines": lines}


# ---------------------------------------------------------------- 메일
def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;"))


def bars(rows, key, label, maxw=260, color="#8f74ef"):
    top = max([r[key] for r in rows] + [1])
    out = []
    for r in rows:
        w = max(4, round(r[key] * maxw / top)) if r[key] else 0
        out.append(
            f'<tr><td style="padding:3px 8px 3px 0;font-size:13px;color:#1f2224;white-space:nowrap">{esc(label(r))}</td>'
            f'<td style="padding:3px 0;width:100%"><div style="height:14px;width:{w}px;background:{color};border-radius:7px;display:inline-block;vertical-align:middle"></div>'
            f'<span style="font-size:12px;color:#5f6663;margin-left:6px">{r[key]:,}</span></td></tr>')
    return "".join(out)


def email_html(r):
    face = PAGES + f"thumbs/report/haru_{r['mood']}.png"
    week_rows = [{"d": w["day"][5:].replace("-", "."), "c": w["count"]} for w in r["week"]]
    wk = bars(week_rows, "c", lambda x: x["d"], color="#8f74ef")
    clicks = [c for c in r["top_clicks"] if c["day"]][:5] or r["top_clicks"][:5]
    ckey = "day" if any(c["day"] for c in clicks) else "week_sum"
    ck = bars(clicks, ckey, lambda x: (x["title"] or x["name"])[:22], color="#d9668f") if clicks else \
        '<tr><td style="font-size:13px;color:#5f6663">아직 클릭 기록이 없어요.</td></tr>'
    menu_cells = "".join(
        f'<td style="padding:6px;text-align:center"><div style="border:2px solid #1f2224;border-radius:12px;padding:8px 4px;background:#fff">'
        f'<div style="font-size:11px;color:#5f6663;font-family:monospace">{esc(MENU.get(k, k))}</div>'
        f'<div style="font-size:20px;font-weight:700">{v["day"]:,}</div><div style="font-size:11px;color:#5f6663">7일 {v["week"]:,}</div></div></td>'
        for k, v in sorted(r["menus"].items(), key=lambda kv: -kv[1]["week"])[:3]) or \
        '<td style="font-size:13px;color:#5f6663;padding:6px">메뉴별 클릭은 기록이 쌓이면 보여 드려요.</td>'
    talk = "".join(f'<p style="margin:0 0 6px;font-size:14px;line-height:1.55">💬 {esc(t)}</p>' for t in r["lines"][1:-1])
    ch = pct(r["pageviews"], r["pageviews_prev"])
    chs = "" if ch is None else (f'<span style="color:{"#1f9e66" if ch >= 0 else "#c0392b"};font-weight:700">{ch:+d}%</span>')
    card = 'border:2px solid #1f2224;border-radius:16px;background:#ffffff;padding:16px 18px;margin:0 0 14px'
    inv_card = inventory_html(r.get("inventory") or {}, card)
    return f"""<!doctype html><html><body style="margin:0;padding:0;background:#f3f1ec">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f3f1ec"><tr><td align="center" style="padding:20px 10px">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;font-family:'Apple SD Gothic Neo','Malgun Gothic','Noto Sans KR',sans-serif;color:#1f2224">
<tr><td style="padding:0 0 10px"><span style="display:inline-block;font-family:monospace;font-size:11px;letter-spacing:.1em;border:1.5px solid #1f2224;border-radius:99px;padding:3px 10px;background:#fff">AHNBOAT LAB · DAILY REPORT</span>
<div style="font-size:24px;font-weight:700;margin-top:6px">오늘의 레포트 <span style="font-size:15px;color:#5f6663;font-weight:500">{esc(r['date'])} ({esc(r['dow'])}) 기준</span></div></td></tr>
<tr><td style="{card};background:#fbfaf7">
<table role="presentation" width="100%"><tr>
<td width="120" valign="top"><img src="{face}" width="110" alt="조수 하루" style="display:block;border:2px solid #1f2224;border-radius:12px;background:#dfeaf6"></td>
<td valign="middle" style="padding-left:12px"><div style="font-size:12px;color:#6b4fd6;font-weight:700;font-family:monospace">조수 하루</div>
<div style="background:#fff;border:2px solid #1f2224;border-radius:14px;padding:10px 14px;font-size:16px;font-weight:700;line-height:1.45;margin-top:4px">{esc(r['lines'][0])}</div></td>
</tr></table></td></tr>
<tr><td><table role="presentation" width="100%" cellspacing="0" cellpadding="0"><tr>
<td width="33%" style="padding:0 6px 14px 0"><div style="{card};margin:0;text-align:center"><div style="font-size:12px;color:#5f6663">어제 방문</div><div style="font-size:26px;font-weight:700">{r['pageviews']:,}</div><div style="font-size:12px">{chs}</div></div></td>
<td width="33%" style="padding:0 3px 14px"><div style="{card};margin:0;text-align:center"><div style="font-size:12px;color:#5f6663">콘텐츠 클릭</div><div style="font-size:26px;font-weight:700">{r['clicks']:,}</div><div style="font-size:12px;color:#5f6663">어제</div></div></td>
<td width="33%" style="padding:0 0 14px 6px"><div style="{card};margin:0;text-align:center"><div style="font-size:12px;color:#5f6663">최근 7일</div><div style="font-size:26px;font-weight:700">{r['week_total']:,}</div><div style="font-size:12px;color:#5f6663">방문</div></div></td>
</tr></table></td></tr>
<tr><td style="{card}"><div style="font-weight:700;margin-bottom:6px">📈 최근 7일 방문</div><table role="presentation" width="100%">{wk}</table></td></tr>
<tr><td style="{card}"><div style="font-weight:700;margin-bottom:6px">🏆 많이 열린 콘텐츠 {'(어제)' if ckey == 'day' else '(최근 7일)'}</div><table role="presentation" width="100%">{ck}</table></td></tr>
<tr><td><table role="presentation" width="100%"><tr>{menu_cells}</tr></table></td></tr>
{inv_card}<tr><td style="{card};background:#fbfaf7">{talk}</td></tr>
<tr><td align="center" style="padding:6px 0 18px"><a href="{PAGES}report.html" style="display:inline-block;background:#e0a92a;color:#1f2224;text-decoration:none;font-weight:700;border:2px solid #1f2224;border-radius:12px;padding:11px 20px">🔎 하루와 자세히 보기</a>
<div style="font-size:12px;color:#5f6663;margin-top:8px">자세히 보기 페이지는 관리자 키로 열립니다.</div></td></tr>
<tr><td style="font-size:11px;color:#8a8f8c;text-align:center;padding-bottom:10px">AHNBOAT LAB · {esc(r['generated'])} 자동 발송</td></tr>
</table></td></tr></table></body></html>"""


def inventory_html(inv, card):
    if not inv.get("korean"):
        return ""
    d = inv.get("delta") or {}
    dl = lambda k: (f' <span style="color:#1f9e66;font-weight:700">{d[k]:+d}</span>' if d.get(k) else "")
    n = inv["korean"]

    def row(label, done, extra=""):
        w = round(done * 260 / n) if n else 0
        return (f'<tr><td style="padding:3px 8px 3px 0;font-size:13px;white-space:nowrap">{label}</td>'
                f'<td style="padding:3px 0;width:100%"><div style="width:260px;height:14px;background:#ece9e1;border-radius:7px;display:inline-block;vertical-align:middle">'
                f'<div style="width:{w}px;height:14px;background:#2f9e8f;border-radius:7px"></div></div>'
                f'<span style="font-size:12px;color:#5f6663;margin-left:6px">{done}/{n}{extra}</span></td></tr>')
    langs = " · ".join(f"{LANG_KO[k]} {v}" for k, v in (inv.get("by_lang") or {}).items())
    return (f'<tr><td style="{card}"><div style="font-weight:700;margin-bottom:6px">🗂 콘텐츠 현황</div>'
            f'<div style="font-size:13px;color:#5f6663;margin-bottom:8px">전체 {inv["contents"]}개{dl("contents")}'
            f' (해설 {n} · 외부 {inv.get("external", 0)}) · 홈페이지 글 {inv.get("posts", 0)}개{dl("posts")}</div>'
            f'<table role="presentation" width="100%">'
            + row("한국어", n)
            + row("번역 6개 언어", inv["tr_full"], f' · 일부 {inv["tr_part"]} · 없음 {inv["tr_none"]}')
            + row("온톨로지", inv["onto"])
            + f'</table><div style="font-size:12px;color:#5f6663;margin-top:6px">{esc(langs)}</div></td></tr>\n')


def text_report(r):
    """메일에 붙이는 글자만 있는 레포트 (.md)."""
    L = [f"# 오늘의 레포트 — {r['date']} ({r['dow']}) 기준", "", f"만든 때: {r['generated']} KST", "",
         "## 하루의 한마디", ""] + [f"- {t}" for t in r["lines"][:-1]]
    ch = pct(r["pageviews"], r["pageviews_prev"])
    wch = pct(r["week_total"], r["last_week_total"])
    L += ["", "## 방문·클릭", "",
          f"- 어제 방문: {r['pageviews']:,}" + (f" (그저께 대비 {ch:+d}%)" if ch is not None else ""),
          f"- 어제 콘텐츠 클릭: {r['clicks']:,}",
          f"- 최근 7일 방문: {r['week_total']:,}" + (f" (지난주 대비 {wch:+d}%)" if wch is not None else ""),
          "", "| 날짜 | 방문 |", "|---|---|"] + [f"| {w['day']} | {w['count']:,} |" for w in r["week"]]
    L += ["", "## 많이 열린 콘텐츠", "", "| 콘텐츠 | 메뉴 | 어제 | 7일 |", "|---|---|---|---|"]
    L += [f"| {(c['title'] or c['name']).replace('|', '/')} | {MENU.get(c['menu'], c['menu'])} | {c['day']} | {c['week_sum']} |"
          for c in r["top_clicks"]] or ["| (아직 클릭 기록 없음) | | | |"]
    L += ["", "## 많이 본 페이지", "", "| 페이지 | 어제 | 7일 |", "|---|---|---|"]
    L += [f"| {(p['title'] or p['path']).replace('|', '/')} | {p['day']} | {p['week_sum']} |" for p in r["top_pages"]]
    if r["refs"]:
        L += ["", "## 들어온 곳", ""] + [f"- {x['name']}: {x['count']}" for x in r["refs"]]
    inv = r.get("inventory") or {}
    if inv.get("korean"):
        n, d = inv["korean"], inv.get("delta") or {}
        L += ["", "## 콘텐츠 현황", "",
              f"- 전체 콘텐츠: {inv['contents']}개 (해설 {n} · 외부 {inv.get('external', 0)})" + (f" — 어제보다 {d['contents']:+d}" if d.get("contents") else ""),
              f"- 홈페이지 글: {inv.get('posts', 0)}개 · 포트폴리오 {inv.get('portfolio', 0)}건",
              f"- 지식 색인 개념: {inv.get('concepts', 0):,}개", "",
              "| 체크 | 완료 | 일부 | 없음 |", "|---|---|---|---|",
              f"| 한국어 콘텐츠 | {n} | – | – |",
              f"| 번역(6개 언어) | {inv['tr_full']} | {inv['tr_part']} | {inv['tr_none']} |",
              f"| 온톨로지 적용 | {inv['onto']} | – | {inv['onto_todo']} |", "",
              "언어별: " + " · ".join(f"{LANG_KO[k]} {v}" for k, v in inv["by_lang"].items())]
        if inv.get("tr_partial_list"):
            L += ["", "### 번역이 일부만 된 콘텐츠", ""]
            L += [f"- {x['name']} — 빠진 언어: {', '.join(LANG_KO[k] for k in x['missing'])}" for x in inv["tr_partial_list"]]
    return "\n".join(L) + "\n"


def send(r, html):
    user = os.environ.get("GMAIL_ADDRESS", "").strip()
    pw = os.environ.get("GMAIL_APP_PASSWORD", "").replace(" ", "")
    if not user or not pw:
        print("메일 설정(GMAIL_ADDRESS·GMAIL_APP_PASSWORD)이 없어 메일은 보내지 않았습니다.")
        return False
    msg = MIMEMultipart("mixed")
    body = MIMEMultipart("alternative")
    msg["Subject"] = f"[오늘의 레포트] {r['date']} · 방문 {r['pageviews']:,} · 클릭 {r['clicks']:,}"
    msg["From"] = formataddr(("조수 하루 (AHNBOAT LAB)", user))
    msg["To"] = user
    body.attach(MIMEText("\n".join(r["lines"]) + f"\n\n자세히 보기: {PAGES}report.html", "plain", "utf-8"))
    body.attach(MIMEText(html, "html", "utf-8"))
    msg.attach(body)
    att = MIMEApplication(text_report(r).encode("utf-8"), _subtype="octet-stream")
    att.add_header("Content-Disposition", "attachment", filename=f"daily_report_{r['date']}.md")
    msg.attach(att)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=60) as s:
        s.login(user, pw)
        s.sendmail(user, [user], msg.as_string())
    print("메일을 보냈습니다.")
    return True


def day_path(day):
    return os.path.join(REPORT_DIR, (day if isinstance(day, str) else day.isoformat()) + ".json.enc")


def saved_days():
    if not os.path.isdir(REPORT_DIR):
        return []
    return sorted(m.group(1) for m in (DAY_FILE.match(f) for f in os.listdir(REPORT_DIR)) if m)


def write_index():
    """쌓인 날짜 목록 — report.html의 날짜 고르기가 읽는다 (날짜만 들어 있다)."""
    days = saved_days()
    json.dump({"days": days, "updated": dt.datetime.now(KST).strftime("%Y-%m-%d %H:%M")},
              open(os.path.join(REPORT_DIR, "index.json"), "w", encoding="utf-8"), ensure_ascii=False)
    return days


def lock(r):
    """하루치를 날짜 파일로 잠가 남긴다. 가장 최근 날짜이면 latest도 함께 바꾼다."""
    key = os.environ.get("HUB_KEY", "")
    if not key:
        print("HUB_KEY가 없어 레포트 데이터는 남기지 않았습니다.")
        return False
    sys.path.insert(0, HERE)
    from hubcrypt import encrypt
    os.makedirs(REPORT_DIR, exist_ok=True)
    blob = encrypt(json.dumps(r, ensure_ascii=False).encode("utf-8"), key)
    open(day_path(r["date"]), "wb").write(blob)
    days = write_index()
    if r["date"] >= days[-1]:
        open(os.path.join(REPORT_DIR, "latest.json.enc"), "wb").write(blob)
    print(f"{r['date']} 레포트 데이터를 잠가 저장했습니다.")
    return True


def backfill(r, day):
    """날짜 파일이 없는 지난 날을 GoatCounter에서 다시 읽어 채운다.
    방문 기록이 처음 생긴 날부터만 채우고, 콘텐츠 현황은 그날 값을 알 수 없어 넣지 않는다. 메일은 보내지 않는다."""
    limit = int(os.environ.get("REPORT_BACKFILL", "30") or 0)
    if limit <= 0 or not os.environ.get("HUB_KEY") or not os.environ.get("GOATCOUNTER_TOKEN"):
        return 0
    first = next((m["day"] for m in r["month"] if m["count"]), None)
    if not first:
        return 0
    n = 0
    for k in range(1, limit):
        d = day - dt.timedelta(days=k)
        if d.isoformat() < first:
            break
        if os.path.exists(day_path(d)):
            continue
        try:
            time.sleep(1)  # GoatCounter 요청 한도를 넘지 않게 천천히
            old = build(collect(d), d, with_inventory=False)
        except Exception as e:
            print(f"{d} 지난 기록을 읽지 못해 여기서 멈춥니다: {e}")
            break
        old["backfilled"] = True
        lock(old)
        n += 1
    if n:
        print(f"지난 {n}일치 레포트를 채웠습니다.")
    return n


def main():
    if os.environ.get("REPORT_DAY"):
        day = dt.date.fromisoformat(os.environ["REPORT_DAY"])
    else:
        day = (dt.datetime.now(KST) - dt.timedelta(days=1)).date()
    if os.environ.get("REPORT_SAMPLE"):
        raw = json.load(open(os.environ["REPORT_SAMPLE"], encoding="utf-8"))
    else:
        if not os.environ.get("GOATCOUNTER_TOKEN"):
            raise SystemExit("GOATCOUNTER_TOKEN 이 없습니다.")
        raw = collect(day)
    r = build(raw, day)
    html = email_html(r)
    if os.environ.get("REPORT_OUT"):
        open(os.environ["REPORT_OUT"], "w", encoding="utf-8").write(html)
        open(os.environ["REPORT_OUT"] + ".json", "w", encoding="utf-8").write(json.dumps(r, ensure_ascii=False, indent=1))
        open(os.environ["REPORT_OUT"] + ".md", "w", encoding="utf-8").write(text_report(r))
    print(f"{r['date']}: 방문 {r['pageviews']} · 클릭 {r['clicks']} · 표정 {r['mood']}")
    if lock(r) and not os.environ.get("REPORT_SAMPLE"):
        backfill(r, day)
    send(r, html)


if __name__ == "__main__":
    main()
