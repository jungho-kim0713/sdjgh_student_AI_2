// 앱 엔트리: 컨텍스트를 만들고 모듈을 초기화한다.
document.addEventListener('DOMContentLoaded', () => {
    // 공용 컨텍스트 생성(DOM 캐시 + 상태 + 모듈 네임스페이스).
    const ctx = window.App.createContext();

    // marked.js(마크다운 렌더러) 옵션 설정.
    if (window.marked) {
        window.marked.setOptions({
            breaks: true,
            gfm: true,
            headerIds: false,
            mangle: false
        });
    }

    // 등록 순서대로 모듈 초기화 실행.
    window.App.init(ctx);
});
