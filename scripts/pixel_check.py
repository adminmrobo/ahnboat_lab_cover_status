#!/usr/bin/env python3
"""그림 점검 — 각 저장소 페이지에 '픽셀 깨짐 보정 코드(px-fix)'가 들어 있는지 매번 확인한다.

깨짐의 원인: 그림에 image-rendering:pixelated(각진 픽셀)를 걸어 둔 채, 화면에서 원본과
딱 떨어지지 않는 배율로 키우거나 줄여 보이면 픽셀 크기가 들쭉날쭉해져 깨져 보인다.
보정 코드(px-fix v1)가 있으면 실제 표시 배율이 2배 이상인 그림만 각진 픽셀로 두고 나머지는 부드럽게 그린다.

판정(페이지마다)
  ok      : 보정 코드가 있다
  need    : 보정 코드는 없고, 그 페이지나 같은 저장소의 CSS·JS에 pixelated(또는 crisp-edges)가 있다 → 깨질 수 있음
  clear   : 둘 다 없다(각진 픽셀을 쓰지 않음)
조각 파일(<head>·<body> 없는 HTML)과 조립 원본 폴더(build·scripts·tools·old_skill 등)는 건너뛴다.

  GITHUB_TOKEN=... HUB_KEY=... python3 scripts/pixel_check.py      # Actions: 바뀐 저장소·파일만 다시 받는다
  python3 scripts/pixel_check.py --local DIR                         # 로컬 사본(DIR/저장소이름)으로 같은 검사

결과: data/pixel_audit.json (HUB_KEY가 있으면 data/pixel_audit.json.enc로 잠그고 평문은 지운다)
기록(history)·기준점(baseline)은 사람이 적은 그대로 두고, 상태(state)·요약(summary)만 새로 쓴다.
"""
import argparse
import datetime as dt
import json
import os
import re
import sys
import concurrent.futures as cf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
PLAIN = os.path.join(DATA, "pixel_audit.json")
ENC = PLAIN + ".enc"

FIX_MARK = "px-fix v1"
PIX_WORDS = ("pixelated", "crisp-edges")
SKIP_DIRS = {"build", "scripts", "tools", "node_modules", "old_skill", ".github", "templates", "src", "_src"}
EXAMPLES = 5


def today():
    return dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d")


def skip_path(p):
    parts = p.split("/")
    return any(x in SKIP_DIRS or x.startswith(".") for x in parts[:-1])


PAGE_RE = re.compile(r"<(?:head|body|html)[\s>]", re.I)


def is_page(text):
    return bool(PAGE_RE.search(text[:20000]))


def has_pix(text):
    t = text.lower()
    return any(w in t for w in PIX_WORDS)


def load_prev(key):
    if key and os.path.exists(ENC):
        import hubcrypt
        try:
            return json.loads(hubcrypt.decrypt(open(ENC, "rb").read(), key))
        except Exception as e:  # 키가 바뀌었으면 평문 기준점부터 다시
            print("잠긴 기록을 풀지 못함:", e)
    if os.path.exists(PLAIN):
        return json.load(open(PLAIN, encoding="utf-8"))
    return {}


def judge_repo(files, read):
    """files: [(path, sha)] 중 HTML·CSS·JS. read(path, sha) -> text. 반환: 저장소 결과 + 파일 메모."""
    memo = {}
    side_pix = False
    for p, sha in files:
        if p.endswith((".css", ".js")):
            t = read(p, sha)
            f = has_pix(t) if t is not None else False
            memo[p] = {"sha": sha, "pix": f}
            side_pix = side_pix or f
    pages = need = ok = 0
    need_pages = []
    for p, sha in files:
        if not p.endswith((".html", ".htm")):
            continue
        t = read(p, sha)
        if t is None:
            continue
        if not is_page(t):
            memo[p] = {"sha": sha, "frag": True}
            continue
        fix = FIX_MARK in t
        pix = has_pix(t)
        memo[p] = {"sha": sha, "fix": fix, "pix": pix}
        pages += 1
        if fix:
            ok += 1
        elif pix or side_pix:
            need += 1
            need_pages.append(p)
    status = "need" if need else ("ok" if ok else "clear")
    return {"status": status, "pages": pages, "fixed_pages": ok, "need_pages": need,
            "need_examples": sorted(need_pages)[:EXAMPLES]}, memo


def run_local(base, prev_state):
    import subprocess
    state = {}
    for name in sorted(os.listdir(base)):
        d = os.path.join(base, name)
        if not os.path.isdir(os.path.join(d, ".git")):
            continue
        out = subprocess.run(["git", "-C", d, "ls-files", "-s"], capture_output=True, text=True).stdout
        files = []
        for line in out.splitlines():
            meta, p = line.split("\t", 1)
            if p.endswith((".html", ".htm", ".css", ".js")) and not skip_path(p):
                files.append((p, meta.split()[1]))

        def read(p, sha, d=d):
            try:
                return open(os.path.join(d, p), encoding="utf-8", errors="ignore").read()
            except OSError:
                return None
        res, _ = judge_repo(files, read)
        res["pushed_at"] = None
        state[name] = res
    return state


def run_api(token, prev_state, prev_memo):
    import scan_repos as S
    repos = json.load(open(os.path.join(DATA, "repos.json"), encoding="utf-8"))
    api = S.Api(token)
    state, memo_all = {}, {}

    def work(r):
        name, branch, pushed = r["repo"], r.get("default_branch") or "main", r.get("pushed_at")
        old = prev_state.get(name)
        if old and old.get("pushed_at") == pushed and name in prev_memo:
            return name, old, prev_memo[name]
        tree, _ = api.req("/repos/%s/%s/git/trees/%s?recursive=1" % (S.OWNER, name, branch))
        files = [(t["path"], t["sha"]) for t in (tree or {}).get("tree", [])
                 if t.get("type") == "blob" and t["path"].endswith((".html", ".htm", ".css", ".js"))
                 and not skip_path(t["path"])]
        pm = prev_memo.get(name, {})
        cache = {}

        def read(p, sha):
            m = pm.get(p)
            if m and m.get("sha") == sha:   # 바뀌지 않은 파일은 지난 판정으로 대신한다
                if m.get("frag"):
                    return ""
                return (FIX_MARK if m.get("fix") else "") + (" pixelated" if m.get("pix") else "") + " <head>"
            if p not in cache:
                b = S.raw_file(name, branch, p)
                cache[p] = b.decode("utf-8", "ignore") if isinstance(b, (bytes, bytearray)) else b
            return cache[p]
        res, memo = judge_repo(files, read)
        res["pushed_at"] = pushed
        return name, res, memo

    with cf.ThreadPoolExecutor(8) as ex:
        for name, res, memo in ex.map(work, repos):
            state[name], memo_all[name] = res, memo
    return state, memo_all


def summarize(state):
    c = {"ok": 0, "need": 0, "clear": 0}
    for v in state.values():
        c[v["status"]] += 1
    return {"repos": len(state), "ok": c["ok"], "need": c["need"], "clear": c["clear"],
            "need_pages": sum(v["need_pages"] for v in state.values())}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--local")
    ap.add_argument("--lock-only", action="store_true", help="검사 없이 남은 평문만 잠근다(검사가 실패했을 때)")
    a = ap.parse_args()
    key = os.environ.get("HUB_KEY", "")
    if a.lock_only:
        if key and os.path.exists(PLAIN):
            import hubcrypt
            hubcrypt.lock_if_changed(PLAIN, ENC, key)
            os.remove(PLAIN)
            print("평문 그림 점검 기록을 잠금")
        return
    prev = load_prev(key)
    prev_state = prev.get("state", {})
    if a.local:
        state, memo = run_local(a.local, prev_state), prev.get("memo", {})
    else:
        tok = os.environ.get("GITHUB_TOKEN", "")
        if not tok:
            print("GITHUB_TOKEN 이 없어 그림 점검을 건너뜁니다.")
            if key and os.path.exists(PLAIN):
                import hubcrypt
                hubcrypt.lock_if_changed(PLAIN, ENC, key)
                os.remove(PLAIN)
            return
        state, memo = run_api(tok, prev_state, prev.get("memo", {}))
    out = dict(prev)
    summ = summarize(state)
    if summ != prev.get("summary") or state != prev_state:
        out["checked_on"] = today()      # 결과가 바뀐 날만 적는다(매번 커밋이 쌓이지 않게)
        hist = out.setdefault("history", [])
        if not hist or hist[-1].get("summary") != summ:
            hist.append({"date": today(), "kind": "auto", "title": "자동 점검", "summary": summ})
    out["summary"], out["state"], out["memo"] = summ, state, memo
    os.makedirs(DATA, exist_ok=True)
    with open(PLAIN, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, sort_keys=True)
    if key:
        import hubcrypt
        print("pixel_audit.json.enc", "새로 잠금" if hubcrypt.lock_if_changed(PLAIN, ENC, key) else "그대로")
        os.remove(PLAIN)
    print(json.dumps(summ, ensure_ascii=False))


if __name__ == "__main__":
    main()
