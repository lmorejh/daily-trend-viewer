#!/usr/bin/env python3
"""릴스 시드 갱신 스크립트 (집 PC에서 실행).
imginn은 GitHub 서버(데이터센터 IP)를 차단하므로, 웹 버전의 릴스 데이터는
이 스크립트로 수집해 seed/에 저장한 뒤 커밋·푸시해서 공급합니다.
사용: python3 update_seed.py  (또는 시드갱신-릴스.bat 더블클릭)
"""
import hashlib
import json
import os
from urllib.parse import urlparse

import server

SEED = os.path.join(server.BASE_DIR, "seed")
IMG = os.path.join(SEED, "img")


def main():
    reels, accounts, fetched = server.get_reels(True)
    reels = reels[:80]
    if not reels:
        print("릴스 수집 실패(0개) — 시드를 덮어쓰지 않고 종료합니다.")
        return 1
    os.makedirs(IMG, exist_ok=True)
    for f in os.listdir(IMG):
        os.remove(os.path.join(IMG, f))
    saved = 0
    for r in reels:
        u = r.get("thumbnail") or ""
        if not (u.startswith("https://")
                and urlparse(u).netloc.lower().endswith(server.IMG_PROXY_ALLOW)):
            r["thumbnail"] = ""
            continue
        try:
            ctype, body = server.http_get(u, timeout=12)
        except Exception:
            r["thumbnail"] = ""
            continue
        ext = ".png" if "png" in ctype else ".webp" if "webp" in ctype else ".jpg"
        name = hashlib.sha1(u.encode()).hexdigest()[:16] + ext
        with open(os.path.join(IMG, name), "wb") as fh:
            fh.write(body)
        r["thumbnail"] = "img/" + name
        saved += 1
    with open(os.path.join(SEED, "reels.json"), "w", encoding="utf-8") as f:
        json.dump({"reels": reels, "accounts": accounts, "fetchedAt": fetched},
                  f, ensure_ascii=False)
    print("릴스 %d개, 썸네일 %d개 시드 저장 완료" % (len(reels), saved))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
