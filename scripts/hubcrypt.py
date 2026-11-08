#!/usr/bin/env python3
"""관리용 데이터를 관리자 키로 잠그고 푼다.

형식(JSON 한 덩어리, 현황판 페이지의 브라우저 코드와 같은 방식):
  {"v":1, "alg":"AES-256-GCM", "kdf":"PBKDF2-SHA256", "iter":310000,
   "salt":"<base64 16바이트>", "iv":"<base64 12바이트>", "ct":"<base64 암호문+인증태그>"}

- 키는 사람이 정한 문장(관리자 키)에서 PBKDF2로 만든다. 키가 틀리면 풀리지 않는다(인증 태그 불일치).
- 사용: hubcrypt.py enc <평문> <잠긴파일>   /   hubcrypt.py dec <잠긴파일> <평문>
  관리자 키는 환경 변수 HUB_KEY 에서 읽는다.
"""
import base64, json, os, sys

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

ITER = 310000


def _key(passphrase, salt, it=ITER):
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=it)
    return kdf.derive(passphrase.encode("utf-8"))


def encrypt(data: bytes, passphrase: str) -> bytes:
    salt, iv = os.urandom(16), os.urandom(12)
    ct = AESGCM(_key(passphrase, salt)).encrypt(iv, data, None)
    b = lambda x: base64.b64encode(x).decode()
    return json.dumps({"v": 1, "alg": "AES-256-GCM", "kdf": "PBKDF2-SHA256", "iter": ITER,
                       "salt": b(salt), "iv": b(iv), "ct": b(ct)}).encode()


def decrypt(blob: bytes, passphrase: str) -> bytes:
    o = json.loads(blob)
    d = base64.b64decode
    return AESGCM(_key(passphrase, d(o["salt"]), int(o["iter"]))).decrypt(d(o["iv"]), d(o["ct"]), None)


def lock_if_changed(plain_path, enc_path, passphrase):
    """평문이 잠긴 파일의 내용과 같으면 그대로 둔다(매번 새 암호문이 생겨 커밋이 쌓이는 것을 막음)."""
    data = open(plain_path, "rb").read()
    if os.path.exists(enc_path):
        try:
            if decrypt(open(enc_path, "rb").read(), passphrase) == data:
                return False
        except Exception:
            pass
    open(enc_path, "wb").write(encrypt(data, passphrase))
    return True


def main():
    key = os.environ.get("HUB_KEY", "")
    if not key:
        raise SystemExit("HUB_KEY 가 없습니다.")
    mode, src, dst = sys.argv[1:4]
    if mode == "enc":
        open(dst, "wb").write(encrypt(open(src, "rb").read(), key))
    elif mode == "dec":
        open(dst, "wb").write(decrypt(open(src, "rb").read(), key))
    else:
        raise SystemExit("enc 또는 dec")


if __name__ == "__main__":
    main()
