#!/usr/bin/env python3
"""GitHub Pages용 정적 스냅샷 빌더.
server.py의 수집 함수를 재사용해 모든 탭 데이터를 JSON으로 저장하고,
핫링크가 막힌 썸네일(인스타/틱톡/트위터 CDN)은 내려받아 로컬 파일로 바꿉니다.
GitHub Actions가 1시간마다 실행해 결과를 GitHub Pages로 배포합니다.
사용: python3 collect.py [출력폴더=_site]
"""
import hashlib
import json
import os
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

import server

OUT = sys.argv[1] if len(sys.argv) > 1 else "_site"
PERIODS = ("day", "week", "month")
IMG_LIMIT = 400  # 스냅샷당 내려받는 썸네일 최대 개수
# 수집이 실패(0개)한 소스는 이전 배포 스냅샷을 재사용합니다
PAGES_BASE = os.environ.get("PAGES_BASE", "https://lmorejh.github.io/daily-trend-viewer/")

# static_shim.js의 SLUG와 반드시 일치해야 합니다 (파일명에 쓸 영문 슬러그)
CATEGORY_SLUGS = {
    "전체": "all", "AI": "ai", "먹방": "mukbang", "뷰티/패션": "beauty",
    "브이로그": "vlog", "예능/코미디": "fun", "영화/드라마": "movie",
    "테크/IT": "tech", "지식/교육": "edu", "여행": "travel", "동물": "animal",
}


def write_json(name, obj):
    with open(os.path.join(OUT, "data", name), "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)


def collect_videos():
    def one(args):
        cat, period, shorts = args
        vids, fetched = server.get_videos(cat, period, shorts, force=False)
        return args, vids[:60], fetched

    jobs = [(c, p, s) for c in CATEGORY_SLUGS for p in PERIODS for s in (False, True)]
    with ThreadPoolExecutor(max_workers=3) as pool:
        for (cat, period, shorts), vids, fetched in pool.map(one, jobs):
            name = "videos_%s_%s_%s.json" % (CATEGORY_SLUGS[cat], period, "1" if shorts else "0")
            write_json(name, {"videos": vids, "fetchedAt": fetched})
    print("유튜브/쇼츠: %d개 조합 저장" % len(jobs))


def download_images(items, field):
    """items[*][field]의 CDN 이미지를 내려받고 값을 로컬 경로(img/...)로 바꿉니다."""
    urls = []
    for it in items:
        u = it.get(field) or ""
        if u.startswith("https://") and urlparse(u).netloc.lower().endswith(server.IMG_PROXY_ALLOW):
            urls.append(u)
    urls = list(dict.fromkeys(urls))[:IMG_LIMIT]

    def fetch(u):
        try:
            ctype, body = server.http_get(u, timeout=12)
        except Exception:
            return u, None
        ext = ".png" if "png" in ctype else ".webp" if "webp" in ctype else ".jpg"
        name = hashlib.sha1(u.encode()).hexdigest()[:16] + ext
        with open(os.path.join(OUT, "img", name), "wb") as f:
            f.write(body)
        return u, "img/" + name

    with ThreadPoolExecutor(max_workers=4) as pool:
        mapping = {u: local for u, local in pool.map(fetch, urls) if local}
    for it in items:
        u = it.get(field) or ""
        if u in mapping:
            it[field] = mapping[u]
    return len(mapping)


def carry_forward(name, items_key, current):
    """수집 결과가 비었으면 이전 배포 스냅샷과 커밋된 시드(seed/) 중 최신 것을 재사용합니다.
    (집 PC에서만 접근 가능한 소스(imginn 등)를 GitHub 서버가 못 가져올 때의 폴백)"""
    if current.get(items_key):
        return current
    prev = None
    try:
        _, body = server.http_get(PAGES_BASE + "data/" + name, timeout=15)
        prev = json.loads(body.decode("utf-8"))
    except Exception:
        pass
    seed = None
    try:
        with open(os.path.join(server.BASE_DIR, "seed", name), encoding="utf-8") as f:
            seed = json.load(f)
    except (OSError, json.JSONDecodeError):
        pass
    best, label = None, ""
    for cand, lab in ((prev, "이전 스냅샷"), (seed, "시드")):
        if cand and cand.get(items_key) and \
                (best is None or cand.get("fetchedAt", 0) > best.get("fetchedAt", 0)):
            best, label = cand, lab
    if not best:
        return current
    for it in best[items_key]:
        for fld in ("thumbnail", "media"):
            v = it.get(fld) or ""
            if not v.startswith("img/"):
                continue
            fname = v.split("/", 1)[1]
            dst = os.path.join(OUT, "img", fname)
            if os.path.exists(dst):
                continue
            seedfile = os.path.join(server.BASE_DIR, "seed", "img", fname)
            try:
                if os.path.exists(seedfile):
                    shutil.copy(seedfile, dst)
                else:
                    _, img = server.http_get(PAGES_BASE + v, timeout=15)
                    with open(dst, "wb") as fh:
                        fh.write(img)
            except Exception:
                it[fld] = ""
    print("  → %s: 이번 수집 실패, %s %d개 재사용" % (name, label, len(best[items_key])))
    return best


def build_site():
    base = server.BASE_DIR
    with open(os.path.join(base, "index.html"), encoding="utf-8") as f:
        html = f.read()
    # 메인 스크립트 앞에 정적 모드 심(shim)을 끼워 /api/* 호출을 JSON 파일로 돌립니다
    html = html.replace("<script>", '<script src="static_shim.js"></script>\n<script>', 1)
    with open(os.path.join(OUT, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)
    shutil.copy(os.path.join(base, "static_shim.js"), os.path.join(OUT, "static_shim.js"))
    open(os.path.join(OUT, ".nojekyll"), "w").close()


def main():
    assert set(CATEGORY_SLUGS) == {"전체", "AI", *server.CATEGORIES}, \
        "server.py 카테고리가 바뀌었습니다. CATEGORY_SLUGS를 갱신하세요."
    t0 = time.time()
    os.makedirs(os.path.join(OUT, "data"), exist_ok=True)
    os.makedirs(os.path.join(OUT, "img"), exist_ok=True)

    write_json("categories.json", {"categories": ["전체", "AI"] + list(server.CATEGORIES)})
    collect_videos()

    reels, accounts, fetched = server.get_reels(False)
    reels = reels[:80]
    n = download_images(reels, "thumbnail")
    data = carry_forward("reels.json", "reels",
                         {"reels": reels, "accounts": accounts, "fetchedAt": fetched})
    write_json("reels.json", data)
    print("릴스: %d개 (썸네일 %d개)" % (len(data["reels"]), n))

    posts, accounts, fetched = server.get_x_posts(False)
    n = download_images(posts, "media")
    data = carry_forward("x.json", "posts",
                         {"posts": posts, "accounts": accounts, "fetchedAt": fetched})
    write_json("x.json", data)
    print("X: %d개 (이미지 %d개)" % (len(data["posts"]), n))

    posts, accounts, fetched = server.get_threads_posts(False)
    n = download_images(posts, "media")
    data = carry_forward("threads.json", "posts",
                         {"posts": posts, "accounts": accounts, "fetchedAt": fetched})
    write_json("threads.json", data)
    print("스레드: %d개 (이미지 %d개)" % (len(data["posts"]), n))

    posts, accounts, fetched = server.get_tiktok(False)
    posts = posts[:100]
    n = download_images(posts, "thumbnail")
    data = carry_forward("tiktok.json", "posts",
                         {"posts": posts, "accounts": accounts, "fetchedAt": fetched})
    write_json("tiktok.json", data)
    print("틱톡: %d개 (썸네일 %d개)" % (len(data["posts"]), n))

    data, fetched = server.get_ai_data(False)
    write_json("ai.json", {**data, "fetchedAt": fetched})
    print("AI: 뉴스 %d건, 모델 %d개" % (len(data["news"]),
          len(data["models"]["latest"]) + len(data["models"]["trending"])))

    build_site()
    print("완료: %.0f초, 출력=%s" % (time.time() - t0, OUT))


if __name__ == "__main__":
    main()
