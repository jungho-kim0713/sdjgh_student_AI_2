// 페르소나 선택 모듈: 드롭다운 change 이벤트 처리만 담당.
// 목록 로드는 persona_visibility.js 가 단독 처리한다.
window.App.registerModule((ctx) => {
    const { dom, state } = ctx;

    const modelSelector = document.getElementById('model-selector');
    if (!modelSelector) return;

    // 서버 사이드 렌더링된 옵션이 있으면 즉시 state 초기화 (fetch 완료 전 전송 방지)
    if (modelSelector.options.length > 0) {
        state.currentRole = modelSelector.options[0].value;
    }

    // 페르소나 선택 변경 이벤트 핸들러
    modelSelector.addEventListener('change', (e) => {
        const selectedRole = e.target.value;
        state.currentRole = selectedRole;

        if (ctx.persona && ctx.persona.onPersonaChange) {
            ctx.persona.onPersonaChange(selectedRole);
        }
        if (ctx.provider && ctx.provider.checkAndFallbackProvider) {
            ctx.provider.checkAndFallbackProvider(false);
        }
    });
});
