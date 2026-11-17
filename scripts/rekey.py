#!/usr/bin/env python3
"""관리자 키를 바꿀 때, 예전 키로 잠긴 파일을 새 키로 다시 잠근다 (GitHub Actions에서 실행).

환경 변수
  HUB_KEY      지금 쓰는 관리자 키 (새 키). Actions에서는 secrets.ADMIN_PASSWORD가 있으면 그 값, 없으면 secrets.HUB_KEY.
  HUB_KEY_OLD  예전 관리자 키 (secrets.HUB_KEY).

data/*.enc 와 data/report/*.enc 중 새 키로 풀리지 않고 예전 키로 풀리는 파일만 새 키로 다시 잠근다.
두 키가 같거나 하나라도 없으면 아무것도 하지 않는다. 관리실 열쇠 보관함(admin_vault.enc)은 건드리지 않는다.
"""
import glob, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hubcrypt  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def opens(blob, key):
    try:
        hubcrypt.decrypt(blob, key)
        return True
    except Exception:
        return False


def main():
    new, old = os.environ.get("HUB_KEY", ""), os.environ.get("HUB_KEY_OLD", "")
    if not new or not old or new == old:
        print("키를 바꾸지 않습니다 (새 키가 없거나 예전 키와 같음).")
        return
    files = sorted(glob.glob(os.path.join(ROOT, "data", "*.enc")) + glob.glob(os.path.join(ROOT, "data", "report", "*.enc")))
    moved = 0
    for p in files:
        if os.path.basename(p) == "admin_vault.enc":
            continue
        blob = open(p, "rb").read()
        if opens(blob, new):
            continue
        try:
            data = hubcrypt.decrypt(blob, old)
        except Exception:
            print("어느 키로도 풀리지 않음:", os.path.relpath(p, ROOT))
            continue
        open(p, "wb").write(hubcrypt.encrypt(data, new))
        moved += 1
    print("새 관리자 키로 다시 잠근 파일 %d개" % moved)


if __name__ == "__main__":
    main()
