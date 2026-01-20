// 모듈 초기화를 위한 전역 레지스트리.
// 각 모듈은 공용 컨텍스트를 받는 초기화 함수를 등록한다.
window.App = window.App || {};
// 로드 순서대로 모듈 초기화 함수를 보관한다.
window.App.modules = [];
/**
 * 모듈 초기화 함수를 등록한다.
 * @param {(ctx: object) => void} initFn - 모듈 초기화 함수
 */
window.App.registerModule = function registerModule(initFn) {
    if (typeof initFn === 'function') {
        window.App.modules.push(initFn);
    }
};
/**
 * 등록된 모든 모듈을 공용 컨텍스트로 초기화한다.
 * @param {object} ctx - 공용 컨텍스트
 */
window.App.init = function initApp(ctx) {
    window.App.modules.forEach((initFn) => initFn(ctx));
};
