/* GitHub Pages 정적 모드 심(shim).
   index.html은 그대로 두고, /api/* 호출을 수집된 JSON 파일로 돌려줍니다.
   collect.py가 이 파일을 사이트에 복사하고 index.html에 끼워 넣습니다. */
(() => {
  // collect.py의 CATEGORY_SLUGS와 반드시 일치해야 합니다
  const SLUG = {
    "전체": "all", "AI": "ai", "먹방": "mukbang", "뷰티/패션": "beauty",
    "브이로그": "vlog", "예능/코미디": "fun", "영화/드라마": "movie",
    "테크/IT": "tech", "지식/교육": "edu", "여행": "travel", "동물": "animal",
  };
  const jsonResp = obj => Promise.resolve(
    new Response(JSON.stringify(obj), { headers: { "Content-Type": "application/json" } }));

  const realFetch = window.fetch.bind(window);
  window.fetch = (input, init) => {
    const raw = typeof input === "string" ? input : input.url;
    if (!raw.startsWith("/api/")) return realFetch(input, init);
    const u = new URL(raw, location.href);
    const path = u.pathname;

    if (init && init.method === "POST") return jsonResp({ accounts: [] }); // 계정 관리는 정적 모드에서 비활성

    let target = null;
    if (path === "/api/categories") target = "data/categories.json";
    else if (path === "/api/videos") {
      if ((u.searchParams.get("q") || "").trim())
        return jsonResp({ videos: [], fetchedAt: Date.now() / 1000 });
      const cat = SLUG[u.searchParams.get("category") || "전체"] || "all";
      const period = u.searchParams.get("period") || "week";
      const shorts = u.searchParams.get("shorts") === "1" ? "1" : "0";
      target = `data/videos_${cat}_${period}_${shorts}.json`;
    }
    else if (path === "/api/ai") target = "data/ai.json";
    else if (path === "/api/reels") target = "data/reels.json";
    else if (path === "/api/x") target = "data/x.json";
    else if (path === "/api/threads") target = "data/threads.json";
    else if (path === "/api/tiktok") target = "data/tiktok.json";

    return target ? realFetch(target) : realFetch(input, init);
  };

  // /api/img?u=... 썸네일: collect.py가 내려받은 로컬 사본(img/...)으로 바꿉니다
  const fixImg = img => {
    const m = (img.getAttribute("src") || "").match(/^\/api\/img\?u=(.+)$/);
    if (!m) return;
    const decoded = decodeURIComponent(m[1]);
    if (decoded.startsWith("img/")) img.src = decoded;
    else img.style.display = "none"; // 로컬 사본이 없으면 숨김
  };
  new MutationObserver(muts => {
    for (const mu of muts) for (const n of mu.addedNodes) {
      if (n.nodeType !== 1) continue;
      if (n.tagName === "IMG") fixImg(n);
      if (n.querySelectorAll) n.querySelectorAll("img").forEach(fixImg);
    }
  }).observe(document.documentElement, { childList: true, subtree: true });

  // 실시간 전용 UI(검색·새로고침·계정 추가/삭제·좋아요 정렬)는 숨깁니다
  document.addEventListener("DOMContentLoaded", () => {
    const style = document.createElement("style");
    style.textContent =
      "#searchForm,#refreshBtn,.addbar,#vidSortMenu,.acc-chip button{display:none!important}" +
      "#updated{margin-left:auto}";
    document.head.appendChild(style);
    const badge = document.createElement("div");
    badge.textContent = "⏱ 1시간마다 자동 수집되는 스냅샷입니다";
    badge.style.cssText = "color:var(--muted);font-size:12px";
    document.getElementById("updated").after(badge);
  });
})();
