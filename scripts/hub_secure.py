#!/usr/bin/env python3
"""잠긴 관리 데이터로 현황판을 다시 만들고, 다시 잠근다 (GitHub Actions에서 실행).

1) data/hub.csv.enc 를 관리자 키(HUB_KEY)로 풀어 data/hub.csv 를 만든다.
   (처음 한 번: 잠긴 파일이 없고 평문 data/hub.csv 만 있으면 그것을 그대로 쓴다.)
2) build_hub.py 로 hub.json(관리용), catalog.json·servers.csv(공개용)를 만든다.
3) hub.csv·hub.json 을 잠가 .enc 로 저장하고(내용이 같으면 그대로 둠) 평문은 지운다.
   평문 두 파일은 .gitignore 에 있어 커밋되지 않는다.
HUB_KEY 가 없으면 아무것도 바꾸지 않고 끝낸다(공개 파일도 그대로).
"""
import os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import hubcrypt  # noqa: E402

PLAIN = ["hub.csv", "hub.json"]


def main():
    key = os.environ.get("HUB_KEY", "")
    if not key:
        print("HUB_KEY 가 없어 현황판을 다시 만들지 않습니다.")
        return
    csv_p, enc_p = os.path.join(DATA, "hub.csv"), os.path.join(DATA, "hub.csv.enc")
    if os.path.exists(enc_p):
        open(csv_p, "wb").write(hubcrypt.decrypt(open(enc_p, "rb").read(), key))
    elif not os.path.exists(csv_p):
        raise SystemExit("data/hub.csv.enc 도, 평문 data/hub.csv 도 없습니다.")
    subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "build_hub.py")], check=True)
    for n in PLAIN:
        p = os.path.join(DATA, n)
        changed = hubcrypt.lock_if_changed(p, p + ".enc", key)
        print("%s.enc %s" % (n, "새로 잠금" if changed else "그대로"))
        os.remove(p)
        # 예전에 커밋된 평문이 있으면 저장소에서 뺀다(처음 한 번)
        subprocess.run(["git", "-C", ROOT, "rm", "-q", "--cached", "--ignore-unmatch", "data/" + n], check=True)


if __name__ == "__main__":
    main()
