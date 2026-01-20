// 공급사 선택 모듈: 공급사 선택/제한 처리.
window.App.registerModule((ctx) => {
    const { dom, state } = ctx;
    // 제한 시 대체 우선순위.
    const PROVIDER_PRIORITY = ['google', 'anthropic', 'openai'];

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
     * @param {boolean} isImageGen - 이미지 생성 모드 여부
     */
    ctx.provider.checkAndFallbackProvider = function checkAndFallbackProvider(isImageGen) {
        let isCurrentRestricted = (state.providerStatuses[state.currentProvider] === 'restricted');

        if (isImageGen && state.currentProvider !== 'google') {
            isCurrentRestricted = true;
        }

        if (isCurrentRestricted) {
            let nextProvider = null;

            if (isImageGen) {
                nextProvider = 'google';
            } else {
                for (const p of PROVIDER_PRIORITY) {
                    if (state.providerStatuses[p] !== 'restricted') {
                        nextProvider = p;
                        break;
                    }
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
            const response = await fetch('/api/get_provider_status');
            if (response.ok) {
                state.providerStatuses = await response.json();
            }
        } catch (e) { console.error("Provider status fetch error:", e); }

        const currentPersona = dom.modelSelector ? dom.modelSelector.value : 'general';
        const isImageGen = (currentPersona === 'ai_illustrator');

        dom.providerOptions.forEach(option => {
            const provider = option.dataset.provider;
            let isRestricted = (state.providerStatuses[provider] === 'restricted');

            if (isImageGen) {
                if (provider !== 'google') {
                    isRestricted = true;
                }
            }

            if (isRestricted) {
                option.classList.add('restricted');
                option.setAttribute('title', '(현재 사용할 수 없습니다.)');
                option.style.pointerEvents = 'none';
            } else {
                option.classList.remove('restricted');
                option.removeAttribute('title');
                option.style.pointerEvents = 'auto';
            }
        });

        ctx.provider.checkAndFallbackProvider(isImageGen);
    };

    // 초기 상태 동기화.
    ctx.provider.updateProviderUI();

    // 드롭다운 열기/닫기.
    if (dom.currentProviderBtn) {
        dom.currentProviderBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            if (dom.providerMenu) dom.providerMenu.classList.toggle('show');
        });
    }

    // 외부 클릭 시 드롭다운 닫기.
    window.addEventListener('click', (e) => {
        if (dom.providerDropdown && !dom.providerDropdown.contains(e.target)) {
            if (dom.providerMenu) dom.providerMenu.classList.remove('show');
        }
    });

    // 공급사 선택 클릭 처리.
    dom.providerOptions.forEach(option => {
        option.addEventListener('click', () => {
            if (option.classList.contains('restricted')) return;

            const selectedProvider = option.dataset.provider;
            ctx.provider.setProvider(selectedProvider);

            if (dom.providerMenu) dom.providerMenu.classList.remove('show');
        });
    });
});
