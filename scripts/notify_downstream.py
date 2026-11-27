#!/usr/bin/env python3
"""수집이 끝나면 온톨로지 피드·캐릭터 갤러리를 바로 다시 만들게 부른다 (GitHub Actions에서 실행).

토큰은 DISPATCH_TOKEN(Secrets)이 있으면 그것을, 없으면 콘텐츠 관리실에 등록한 토큰
(data/admin_vault.enc, 관리자 비밀번호 HUB_KEY로 잠김)을 쓴다. 토큰은 화면·기록에 남기지 않는다.
토큰에 두 저장소의 Actions 쓰기 권한이 없으면 건너뛴다 — 그래도 두 저장소가 15분마다
이 저장소의 새 커밋을 확인해 스스로 다시 만든다.
"""
import json, os, sys, urllib.error, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
TARGETS = ["ahnboat_ontology_feed", "ahnboat_lab_gallery"]


def token():
    t = os.environ.get("DISPATCH_TOKEN", "").strip()
    if t:
        return t, "DISPATCH_TOKEN"
    key, vp = os.environ.get("HUB_KEY", ""), os.path.join(ROOT, "data", "admin_vault.enc")
    if not key or not os.path.exists(vp):
        return "", ""
    try:
        import hubcrypt
        return json.loads(hubcrypt.decrypt(open(vp, "rb").read(), key)).get("token", ""), "관리실 토큰"
    except Exception as e:  # 열쇠가 다르거나 파일이 깨졌으면 건너뛴다
        print("관리실 토큰을 열지 못함: %s" % type(e).__name__)
        return "", ""


def main():
    t, src = token()
    if not t:
        print("부를 토큰 없음 — 피드·갤러리는 15분 안에 스스로 반영합니다.")
        return
    print("::add-mask::%s" % t)
    for repo in TARGETS:
        req = urllib.request.Request(
            "https://api.github.com/repos/adminmrobo/%s/actions/workflows/build.yml/dispatches" % repo,
            data=json.dumps({"ref": "main"}).encode(), method="POST",
            headers={"Authorization": "Bearer " + t, "Accept": "application/vnd.github+json",
                     "X-GitHub-Api-Version": "2022-11-28", "Content-Type": "application/json"})
        try:
            urllib.request.urlopen(req, timeout=30)
            print("%s: 바로 다시 만들기 시작 (%s)" % (repo, src))
        except urllib.error.HTTPError as e:
            why = "토큰에 이 저장소의 Actions 쓰기 권한 없음" if e.code in (403, 404) else "HTTP %d" % e.code
            print("%s: 부르지 못함 — %s. 15분 안에 스스로 반영합니다." % (repo, why))
        except Exception as e:
            print("%s: 부르지 못함 — %s" % (repo, type(e).__name__))


if __name__ == "__main__":
    main()
