// 페르소나 선택 모듈: 사용 가능한 페르소나를 동적으로 로드하고 선택 처리
window.App.registerModule((ctx) => {
    const { dom, state } = ctx;

    /**
     * 사용 가능한 페르소나 목록을 서버에서 가져와서 드롭박스에 채운다
     */
    async function loadAvailablePersonas() {
        try {
            const response = await fetch('/api/personas/available');
            const data = await response.json();

            if (!data.success || !data.personas) {
                console.error('페르소나 목록 로드 실패:', data.error);
                return;
            }

            const modelSelector = document.getElementById('model-selector');
            if (!modelSelector) {
                console.error('model-selector 요소를 찾을 수 없습니다');
                return;
            }

            // 기존 옵션 제거
            modelSelector.innerHTML = '';

            // 페르소나 목록을 드롭박스에 추가
            data.personas.forEach(persona => {
                const option = document.createElement('option');
                option.value = persona.role_key;
                option.textContent = `${persona.icon} ${persona.role_name}`;
                option.dataset.description = persona.description;
                option.dataset.useRag = persona.use_rag;
                modelSelector.appendChild(option);
            });

            // 첫 번째 페르소나 선택
            if (data.personas.length > 0) {
                const firstPersona = data.personas[0];
                state.currentRole = firstPersona.role_key;
                modelSelector.value = firstPersona.role_key;

                // 페르소나 변경 이벤트 트리거 (provider 체크 등을 위해)
                if (ctx.persona && ctx.persona.onPersonaChange) {
                    ctx.persona.onPersonaChange(firstPersona.role_key);
                }
            }

            console.log(`✅ ${data.personas.length}개의 페르소나 로드 완료`);

        } catch (error) {
            console.error('페르소나 목록 로드 중 오류:', error);
        }
    }

    /**
     * 페르소나 선택 변경 이벤트 핸들러 등록
     */
    function setupPersonaSelector() {
        const modelSelector = document.getElementById('model-selector');
        if (!modelSelector) return;

        modelSelector.addEventListener('change', (e) => {
            const selectedRole = e.target.value;
            state.currentRole = selectedRole;

            console.log(`페르소나 변경: ${selectedRole}`);

            // 페르소나 변경 시 필요한 로직 (예: provider 제한 체크)
            if (ctx.persona && ctx.persona.onPersonaChange) {
                ctx.persona.onPersonaChange(selectedRole);
            }

            // 프로바이더 제한 체크 및 폴백
            if (ctx.provider && ctx.provider.checkAndFallbackProvider) {
                ctx.provider.checkAndFallbackProvider(false);
            }
        });
    }

    // 초기화: 페르소나 목록 로드
    loadAvailablePersonas();
    setupPersonaSelector();

    // ctx.persona 네임스페이스에 함수 등록
    if (!ctx.persona) ctx.persona = {};
    ctx.persona.reload = loadAvailablePersonas;
});
