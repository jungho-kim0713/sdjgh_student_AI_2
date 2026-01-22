// 페르소나 가시성 모듈: 역할 제한에 따라 드롭다운 필터링.
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
            dom.modelSelector.innerHTML = '';

            personas.forEach((p) => {
                const option = document.createElement('option');
                option.value = p.role_key;
                option.textContent = p.role_name;
                dom.modelSelector.appendChild(option);
            });

            const hasCurrent = personas.some(p => p.role_key === currentValue);
            dom.modelSelector.value = hasCurrent ? currentValue : personas[0].role_key;

            if (ctx.sessions.fetchHistory) {
                ctx.sessions.fetchHistory(dom.modelSelector.value);
            }
            if (ctx.provider.fetchPersonaRestrictions) {
                ctx.provider.fetchPersonaRestrictions(dom.modelSelector.value)
                    .finally(() => ctx.provider.updateProviderUI());
            } else if (ctx.provider.updateProviderUI) {
                ctx.provider.updateProviderUI();
            }
        } catch (error) {
            console.error("Failed to load persona visibility:", error);
        }
    }

    loadPersonaOptions();
});
