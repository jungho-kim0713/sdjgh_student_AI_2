// 공급사 선택 모듈: 공급사 선택/제한 처리.
window.App.registerModule((ctx) => {
    const { dom, state } = ctx;
    // 제한 시 대체 우선순위(요청한 순서).
    const PROVIDER_PRIORITY = ['google', 'anthropic', 'openai', 'xai'];

    // 모델 선택 state 초기화
    state.currentModelId = null;
    state.allowedModelsByProvider = {};
    state.modelNames = {};

    /**
     * 현재 공급사를 변경하고 UI 활성 상태를 갱신한다.
     * @param {string} provider - 공급사 키(openai|anthropic|google)
     */
    ctx.provider.setProvider = function setProvider(provider) {
        state.currentProvider = provider;
        const option = document.querySelector(`.provider-option[data-provider="${provider}"]`);
        if (option) {
            const selectedIconSrc = option.querySelector('img').src;
            if (dom.currentProviderIcon) dom.currentProviderIcon.src = selectedIconSrc;

            dom.providerOptions.forEach(opt => opt.classList.remove('active'));
            option.classList.add('active');
        }
    };

    /**
     * 현재 공급사가 제한이면 대체 공급사로 전환한다.
     */
    ctx.provider.checkAndFallbackProvider = function checkAndFallbackProvider() {
        const personaRestricted = state.personaProviderRestrictions || {};
        let isCurrentRestricted = (state.providerStatuses[state.currentProvider] === 'restricted');

        if (personaRestricted[state.currentProvider]) {
            isCurrentRestricted = true;
        }

        if (isCurrentRestricted) {
            let nextProvider = null;

            for (const p of PROVIDER_PRIORITY) {
                if (state.providerStatuses[p] !== 'restricted' && !personaRestricted[p]) {
                    nextProvider = p;
                    break;
                }
            }

            if (nextProvider && nextProvider !== state.currentProvider) {
                console.log(`⚠️ ${state.currentProvider} is restricted. Switching to ${nextProvider}`);
                ctx.provider.setProvider(nextProvider);
            }
        }
    };

    /**
     * 서버에서 공급사 상태를 가져와 드롭다운 UI를 갱신한다.
     */
    ctx.provider.updateProviderUI = async function updateProviderUI() {
        try {
            const response = await fetch(`/api/get_provider_status?t=${Date.now()}`);
            if (response.ok) {
                state.providerStatuses = await response.json();
            }
        } catch (e) { console.error("Provider status fetch error:", e); }

        const personaRestricted = state.personaProviderRestrictions || {};

        dom.providerOptions.forEach(option => {
            const provider = option.dataset.provider;
            let isRestricted = (state.providerStatuses[provider] === 'restricted');

            if (personaRestricted[provider]) {
                isRestricted = true;
            }

            if (isRestricted) {
                option.classList.add('restricted');
                option.setAttribute('title', '(현재 사용할 수 없습니다.)');
                option.style.display = 'none';
            } else {
                option.classList.remove('restricted');
                option.removeAttribute('title');
                option.style.display = '';
            }
        });

        ctx.provider.checkAndFallbackProvider();
        ctx.provider.updateModelSelector();
    };

    /**
     * 페르소나 제한 정보 + 허용 모델 목록을 서버에서 가져온다.
     */
    ctx.provider.fetchPersonaRestrictions = async function fetchPersonaRestrictions(roleKey) {
        try {
            const response = await fetch(`/api/get_persona_provider_restrictions?role_key=${encodeURIComponent(roleKey)}&t=${Date.now()}`);
            if (!response.ok) throw new Error('Failed to fetch persona restrictions');
            const data = await response.json();
            state.personaProviderRestrictions = {
                google: !!data.restrict_google,
                anthropic: !!data.restrict_anthropic,
                openai: !!data.restrict_openai,
                xai: !!data.restrict_xai
            };
            // 허용 모델 목록 + 한글 이름 저장
            state.allowedModelsByProvider = data.allowed_models || {};
            state.modelNames = data.model_names || {};
        } catch (e) {
            console.error("Persona restriction fetch error:", e);
            state.personaProviderRestrictions = { google: false, anthropic: false, openai: false, xai: false };
            state.allowedModelsByProvider = {};
            state.modelNames = {};
        }
    };

    /**
     * 현재 공급사의 허용 모델 목록으로 모델 선택 드롭다운을 갱신한다.
     * 모델이 1개 이하면 드롭다운을 숨긴다.
     */
    ctx.provider.updateModelSelector = function updateModelSelector() {
        const wrapper = document.getElementById('model-id-wrapper');
        const selector = document.getElementById('model-id-selector');
        if (!wrapper || !selector) return;

        const provider = state.currentProvider;

        // 공급사 자체가 제한된 경우 모델 드롭다운도 숨김
        if (state.personaProviderRestrictions?.[provider]) {
            wrapper.style.display = 'none';
            return;
        }

        const list = (state.allowedModelsByProvider || {})[provider] || [];

        if (list.length <= 1) {
            // 모델 1개 이하: 드롭다운 숨기고 state만 설정
            wrapper.style.display = 'none';
            state.currentModelId = list[0] || null;
            return;
        }

        // 모델 2개 이상: 드롭다운 표시
        selector.innerHTML = list.map(id => {
            const name = (state.modelNames || {})[id] || id;
            return `<option value="${id}">${name}</option>`;
        }).join('');

        // 이전 선택 유지 or 첫 번째로 초기화
        if (state.currentModelId && list.includes(state.currentModelId)) {
            selector.value = state.currentModelId;
        } else {
            selector.value = list[0];
            state.currentModelId = list[0];
        }
        wrapper.style.display = 'block';
    };

    // 초기 상태 동기화.
    ctx.provider.fetchPersonaRestrictions(dom.modelSelector ? dom.modelSelector.value : 'general')
        .finally(() => ctx.provider.updateProviderUI());

    // 드롭다운 열기/닫기.
    if (dom.currentProviderBtn) {
        dom.currentProviderBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            if (dom.providerMenu) dom.providerMenu.classList.toggle('show');
            dom.currentProviderBtn.classList.toggle('open', dom.providerMenu.classList.contains('show'));
        });
    }

    // 외부 클릭 시 드롭다운 닫기.
    window.addEventListener('click', (e) => {
        if (dom.providerDropdown && !dom.providerDropdown.contains(e.target)) {
            if (dom.providerMenu) dom.providerMenu.classList.remove('show');
            if (dom.currentProviderBtn) dom.currentProviderBtn.classList.remove('open');
        }
    });

    // 공급사 선택 클릭 처리.
    dom.providerOptions.forEach(option => {
        option.addEventListener('click', () => {
            if (option.classList.contains('restricted')) return;

            const selectedProvider = option.dataset.provider;
            ctx.provider.setProvider(selectedProvider);
            ctx.provider.updateModelSelector(); // 공급사 변경 시 모델 목록 갱신

            if (dom.providerMenu) dom.providerMenu.classList.remove('show');
            if (dom.currentProviderBtn) dom.currentProviderBtn.classList.remove('open');
        });
    });

    // 모델 선택 드롭다운 change 이벤트
    const modelIdSelector = document.getElementById('model-id-selector');
    if (modelIdSelector) {
        modelIdSelector.addEventListener('change', (e) => {
            state.currentModelId = e.target.value;
        });
    }
});
