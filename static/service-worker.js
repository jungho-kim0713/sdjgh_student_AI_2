const CACHE_NAME = 'sdjgh-ai-v7';

// 앱 설치 시 미리 캐싱할 정적 자산
const PRECACHE_ASSETS = [
  '/static/images/logo.png',
];

// ---------------------------------------------------------------------------
// 설치: 정적 자산 사전 캐싱
// ---------------------------------------------------------------------------
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(PRECACHE_ASSETS))
      .then(() => self.skipWaiting())
  );
});

// ---------------------------------------------------------------------------
// 활성화: 이전 버전 캐시 삭제
// ---------------------------------------------------------------------------
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))
      )
    ).then(() => self.clients.claim())
  );
});

// ---------------------------------------------------------------------------
// Fetch 전략
//   - API / SSE 스트림 / 인증 경로 → 네트워크만 (캐시 안 함)
//   - 정적 자산 → 캐시 우선, 없으면 네트워크 후 캐시 저장
//   - 페이지 이동 요청 오프라인 → 캐시된 루트 반환
// ---------------------------------------------------------------------------
self.addEventListener('fetch', event => {
  const { request } = event;
  const url = new URL(request.url);

  // POST 요청 및 다른 출처 요청은 그냥 통과
  if (request.method !== 'GET' || url.origin !== self.location.origin) {
    return;
  }

  // API·SSE 경로는 항상 네트워크
  if (url.pathname.startsWith('/api/') ||
      url.pathname.startsWith('/stream') ||
      url.pathname.startsWith('/auth/') ||
      url.pathname === '/login' ||
      url.pathname === '/logout') {
    event.respondWith(fetch(request));
    return;
  }

  // 정적 자산: 캐시 우선
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(request).then(cached => {
        if (cached) return cached;
        return fetch(request).then(response => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then(cache => cache.put(request, clone));
          }
          return response;
        });
      })
    );
    return;
  }

  // 페이지 요청: 네트워크 우선, 오프라인 시 캐시 루트 반환
  event.respondWith(
    fetch(request).catch(() => caches.match('/') || caches.match(request))
  );
});
