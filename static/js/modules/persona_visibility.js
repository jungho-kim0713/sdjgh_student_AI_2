// 페르소나 가시성 모듈: 권한에 맞는 페르소나 목록을 드롭다운에 채운다.
// /api/get_persona_visibility 하나만 사용 (학생 배정, 교사 배정, allow_user/teacher 모두 반영).
window.App.registerModule((ctx) => {
    const { dom, state } = ctx;

    if (!dom.modelSelector || state.isAdmin) return;

    async function loadPersonaOptions() {
        try {
            const response = await fetch('/api/get_persona_visibility');
            if (!response.ok) throw new Error('Failed to fetch persona visibility');
            const data = await response.json();
            const personas = data.personas || [];

            if (personas.length === 0) return;

            const currentValue = dom.modelSelector.value;
            dom.modelSelector.innerHTML = personas.map(p =>
                `<option value="${p.role_key}" data-use-rag="${p.use_rag}" data-description="${p.description || ''}">${p.icon || '🤖'} ${p.role_name}</option>`
            ).join('');

            const hasCurrent = personas.some(p => p.role_key === currentValue);
            const selectedValue = hasCurrent ? currentValue : personas[0].role_key;
            dom.modelSelector.value = selectedValue;
            state.currentRole = selectedValue;

            if (ctx.sessions && ctx.sessions.fetchHistory) {
                ctx.sessions.fetchHistory(selectedValue);
            }
            if (ctx.provider && ctx.provider.fetchPersonaRestrictions) {
                ctx.provider.fetchPersonaRestrictions(selectedValue)
                    .finally(() => ctx.provider.updateProviderUI && ctx.provider.updateProviderUI());
            } else if (ctx.provider && ctx.provider.updateProviderUI) {
                ctx.provider.updateProviderUI();
            }
        } catch (error) {
            console.error("Failed to load persona visibility:", error);
        }
    }

    loadPersonaOptions();

    // 외부에서 재로드 가능하도록 등록
    if (!ctx.persona) ctx.persona = {};
    ctx.persona.reload = loadPersonaOptions;
});
