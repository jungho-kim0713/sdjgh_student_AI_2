// 관리자/상태 모듈: 서비스 상태 토글 및 관리자 패널 관리.
window.App.registerModule((ctx) => {
    const { dom, state } = ctx;

    /**
     * 서비스 상태에 맞게 상단 상태 버튼 UI를 갱신한다.
     * @param {string} status - 'active' | 'inactive'
     */
    function updateStatusUI(status) {
        if (!dom.statusButton || !dom.statusText) return;
        if (status === 'active') {
            dom.statusButton.classList.remove('inactive');
            dom.statusButton.classList.add('active');
            dom.statusText.textContent = '사용 가능';
        } else {
            dom.statusButton.classList.remove('active');
            dom.statusButton.classList.add('inactive');
            dom.statusText.textContent = '사용 중지';
        }
    }

    /**
     * 앱 로딩 시 초기 서비스 상태를 가져온다.
     */
    async function fetchInitialStatus() {
        if (!dom.statusButton) return;
        try {
            const response = await fetch('/api/get_status');
            const data = await response.json();
            updateStatusUI(data.status);
        } catch (error) {
            console.error("Failed to fetch status:", error);
            updateStatusUI('active');
        }
    }

    // 상태 토글 클릭 핸들러(관리자 전용).
    if (dom.statusButton) {
        dom.statusButton.addEventListener('click', async () => {
            if (!state.isAdmin) { alert("관리자만 상태를 변경할 수 있습니다."); return; }
            try {
                const response = await fetch('/api/toggle_status', { method: 'POST' });
                if (response.ok) {
                    const data = await response.json();
                    updateStatusUI(data.status);
                } else if (response.status === 403) { alert("권한이 없습니다."); }
                else { alert("상태 변경 중 오류가 발생했습니다."); }
            } catch (error) {
                console.error("Failed to toggle status:", error);
                alert("서버와 통신 중 오류가 발생했습니다.");
            }
        });
    }

    // 페이지 로딩 시 상태 동기화.
    fetchInitialStatus();

    // 이하 로직은 관리자 전용.
    if (!state.isAdmin) return;

    // 관리자 모달 탭 전환 헬퍼.
    /**
     * 사용자 목록 뷰로 전환한다.
     */
    const showUserListView = () => {
        if (dom.adminUserListView) dom.adminUserListView.style.display = 'block';
        if (dom.adminModelConfigView) dom.adminModelConfigView.style.display = 'none';
        if (dom.adminUserHistoryView) dom.adminUserHistoryView.style.display = 'none';
        if (dom.navUserList) dom.navUserList.classList.add('active');
        if (dom.navModelConfig) dom.navModelConfig.classList.remove('active');
    };

    /**
     * 모델 설정 뷰로 전환한다.
     */
    const showModelConfigView = () => {
        if (dom.adminUserListView) dom.adminUserListView.style.display = 'none';
        if (dom.adminModelConfigView) dom.adminModelConfigView.style.display = 'block';
        if (dom.adminUserHistoryView) dom.adminUserHistoryView.style.display = 'none';
        if (dom.navUserList) dom.navUserList.classList.remove('active');
        if (dom.navModelConfig) dom.navModelConfig.classList.add('active');
    };

    /**
     * 사용자 기록 뷰로 전환한다.
     */
    const showUserHistoryView = () => {
        if (dom.adminUserListView) dom.adminUserListView.style.display = 'none';
        if (dom.adminModelConfigView) dom.adminModelConfigView.style.display = 'none';
        if (dom.adminUserHistoryView) dom.adminUserHistoryView.style.display = 'block';
        if (dom.navUserList) dom.navUserList.classList.remove('active');
        if (dom.navModelConfig) dom.navModelConfig.classList.remove('active');
    };

    // "고아 파일 정리" 버튼을 1회만 주입.
    if (dom.adminNav && !document.getElementById('btn-cleanup-files')) {
        const cleanupBtn = document.createElement('button');
        cleanupBtn.id = 'btn-cleanup-files';
        cleanupBtn.className = 'admin-nav-btn';
        cleanupBtn.style.color = '#B91C1C';
        cleanupBtn.innerHTML = '🧹 데이터 정리';
        dom.adminNav.appendChild(cleanupBtn);

        cleanupBtn.addEventListener('click', async () => {
            if (!confirm("⚠️ 주의: '연결 끊긴 파일(Orphaned Files)'을 모두 삭제하시겠습니까?\n\n(삭제된 대화방에 속해 있던 파일들이 영구적으로 삭제됩니다. 이 작업은 되돌릴 수 없습니다.)")) {
                return;
            }

            cleanupBtn.disabled = true;
            cleanupBtn.textContent = "정리 중...";

            try {
                const response = await fetch('/api/admin/cleanup_orphaned_files', { method: 'POST' });
                const result = await response.json();

                if (result.success) {
                    alert(`✅ 정리 완료!\n\n- 삭제된 파일 수: ${result.count}개\n- 확보된 용량: ${result.space_freed} MB`);
                } else {
                    alert("오류 발생: " + result.error);
                }
            } catch (err) {
                console.error(err);
                alert("서버 통신 오류가 발생했습니다.");
            } finally {
                cleanupBtn.disabled = false;
                cleanupBtn.innerHTML = '🧹 데이터 정리';
            }
        });
    }

    // 관리자 모달 열기 및 기본 뷰 로딩.
    if (dom.adminPanelButton) {
        dom.adminPanelButton.addEventListener('click', (e) => {
            e.stopPropagation();
            if (dom.adminModalOverlay) dom.adminModalOverlay.style.display = 'block';
            if (dom.adminModal) dom.adminModal.style.display = 'flex';
            showUserListView();
            loadAdminUserList();
        });
    }

    /**
     * 관리자 모달을 닫는다.
     */
    const closeModal = () => {
        if (dom.adminModalOverlay) dom.adminModalOverlay.style.display = 'none';
        if (dom.adminModal) dom.adminModal.style.display = 'none';
    };

    if (dom.adminModalCloseButton) dom.adminModalCloseButton.addEventListener('click', closeModal);
    if (dom.adminModalOverlay) dom.adminModalOverlay.addEventListener('click', closeModal);

    // 관리자 모달 탭 네비게이션.
    if (dom.navUserList) {
        dom.navUserList.addEventListener('click', () => {
            showUserListView();
            loadAdminUserList();
        });
    }
    if (dom.navModelConfig) {
        dom.navModelConfig.addEventListener('click', () => {
            showModelConfigView();
            loadModelConfig();
            loadProviderStatus();
        });
    }
    if (dom.adminBackToListBtn) dom.adminBackToListBtn.addEventListener('click', showUserListView);

    /**
     * 공급사 상태 테이블을 로드한다.
     */
    async function loadProviderStatus() {
        if (!dom.adminProviderStatusBody) return;
        try {
            dom.adminProviderStatusBody.innerHTML = '<tr><td colspan="3">상태를 불러오는 중...</td></tr>';
            const response = await fetch('/api/get_provider_status');
            if (!response.ok) throw new Error('Failed to fetch provider status');

            const statuses = await response.json();
            dom.adminProviderStatusBody.innerHTML = '';

            const providers = ['google', 'anthropic', 'openai'];

            providers.forEach(p => {
                const tr = document.createElement('tr');
                const status = statuses[p];
                const isActive = status === 'active';

                tr.innerHTML = `
                    <td><strong>${p.toUpperCase()}</strong></td>
                    <td>
                        <span class="status-badge ${isActive ? 'active' : 'restricted'}">
                            ${isActive ? 'Active (사용 가능)' : 'Restricted (제한됨)'}
                        </span>
                    </td>
                    <td>
                        <button class="btn-toggle-status ${isActive ? 'btn-danger' : 'btn-success'}" data-provider="${p}">
                            ${isActive ? '제한하기 (Disable)' : '활성화 (Enable)'}
                        </button>
                    </td>
                `;
                dom.adminProviderStatusBody.appendChild(tr);
            });

            document.querySelectorAll('.btn-toggle-status').forEach(btn => {
                btn.addEventListener('click', async (e) => {
                    const provider = e.target.dataset.provider;
                    await toggleProviderStatus(provider);
                });
            });

        } catch (error) {
            console.error(error);
            dom.adminProviderStatusBody.innerHTML = '<tr><td colspan="3">로드 실패</td></tr>';
        }
    }

    /**
     * 공급사 상태를 토글한다(서버 저장).
     * @param {string} provider - 공급사 키
     */
    async function toggleProviderStatus(provider) {
        try {
            const response = await fetch('/api/admin/toggle_provider_status', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ provider: provider })
            });
            if (response.ok) {
                loadProviderStatus();
                ctx.provider.updateProviderUI();
            } else {
                alert('상태 변경 실패');
            }
        } catch (error) {
            console.error(error);
            alert('서버 오류');
        }
    }

    /**
     * 페르소나별 모델 설정 테이블을 로드하고 변경 이벤트를 바인딩한다.
     */
    async function loadModelConfig() {
        if (!dom.adminModelConfigBody) return;
        try {
            dom.adminModelConfigBody.innerHTML = '<tr><td colspan="5">설정을 불러오는 중...</td></tr>';
            const response = await fetch('/api/admin/get_persona_config');
            if (!response.ok) throw new Error('Failed to fetch config');

            const data = await response.json();
            const personas = data.personas;
            const models = data.models;

            const modelsByProvider = { openai: [], anthropic: [], google: [] };
            for (const [mid, info] of Object.entries(models)) {
                if (modelsByProvider[info.provider]) {
                    modelsByProvider[info.provider].push({ id: mid, ...info });
                }
            }

            dom.adminModelConfigBody.innerHTML = '';

            personas.forEach(p => {
                const tr = document.createElement('tr');
                const createSelectCell = (provider, currentModelId) => {
                    let options = '';
                    modelsByProvider[provider].forEach(m => {
                        const selected = (m.id === currentModelId) ? 'selected' : '';
                        const priceTooltip = `입력 $${m.input_price} / 출력 $${m.output_price}`;
                        options += `<option value="${m.id}" ${selected} title="${priceTooltip}">${m.name}</option>`;
                    });
                    return `
                        <div class="model-select-wrapper" title="마우스를 올리면 가격이 보입니다">
                            <select class="model-select" data-role-key="${p.role_key}" data-target-provider="model_${provider}">
                                ${options}
                            </select>
                        </div>
                    `;
                };

                tr.innerHTML = `
                    <td><strong>${p.role_name}</strong><br><span style="font-size:0.8rem; color:#666;">(${p.role_key})</span></td>
                    <td>${createSelectCell('openai', p.model_openai)}</td>
                    <td>${createSelectCell('anthropic', p.model_anthropic)}</td>
                    <td>${createSelectCell('google', p.model_google)}</td>
                    <td>
                        <input type="number" class="token-input" data-role-key="${p.role_key}" value="${p.max_tokens}" style="width: 100%;">
                    </td>
                `;
                dom.adminModelConfigBody.appendChild(tr);
            });

            // 모델 선택 변경 저장.
            document.querySelectorAll('.model-select').forEach(select => {
                select.addEventListener('change', async (e) => {
                    const roleKey = e.target.dataset.roleKey;
                    const targetField = e.target.dataset.targetProvider;
                    const newValue = e.target.value;
                    await updateConfig(roleKey, { [targetField]: newValue });
                });
            });

            // 토큰 변경 저장.
            document.querySelectorAll('.token-input').forEach(input => {
                input.addEventListener('change', async (e) => {
                    const roleKey = e.target.dataset.roleKey;
                    await updateConfig(roleKey, { max_tokens: e.target.value });
                });
            });

            /**
             * 페르소나 설정 변경을 서버에 저장한다.
             * @param {string} roleKey - 역할 키
             * @param {object} updates - 변경 값
             */
            async function updateConfig(roleKey, updates) {
                try {
                    const payload = { role_key: roleKey, ...updates };
                    const res = await fetch('/api/admin/update_persona_config', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(payload)
                    });
                    if (!res.ok) throw new Error('Update failed');
                    console.log(`Updated config for ${roleKey}`);
                } catch (err) {
                    console.error(err);
                    alert("설정 저장 실패!");
                }
            }
        } catch (error) {
            console.error("Failed to load model config:", error);
            dom.adminModelConfigBody.innerHTML = '<tr><td colspan="5">설정 로드 실패.</td></tr>';
        }
    }

    /**
     * 관리자 사용자 목록 테이블을 로드한다.
     */
    async function loadAdminUserList() {
        if (!dom.adminUserListBody) return;
        try {
            dom.adminUserListBody.innerHTML = '<tr><td colspan="4">사용자 목록을 불러오는 중...</td></tr>';
            const response = await fetch('/api/admin/get_users');
            if (!response.ok) throw new Error('Failed to fetch users');

            const users = await response.json();
            dom.adminUserListBody.innerHTML = '';

            users.forEach(user => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td>${user.id}</td>
                    <td>${user.username}</td>
                    <td>${user.is_admin ? '<span class="admin-badge">Admin</span>' : 'User'}</td>
                    <td>
                        <div class="btn-group">
                            <button class="btn-secondary view-history-btn" data-user-id="${user.id}" data-username="${user.username}">기록 조회</button>
                            <button class="btn-danger delete-user-btn" data-user-id="${user.id}" data-username="${user.username}" ${user.username === state.currentUsername ? 'disabled' : ''}>삭제</button>
                        </div>
                    </td>
                `;
                dom.adminUserListBody.appendChild(tr);
            });
        } catch (error) {
            console.error("Failed to load users:", error);
            dom.adminUserListBody.innerHTML = '<tr><td colspan="4">사용자 목록 로드 실패</td></tr>';
        }
    }

    /**
     * 특정 사용자의 대화 기록을 로드한다.
     * @param {string|number} userId - 사용자 ID
     * @param {string} username - 사용자 이름
     */
    async function loadUserHistory(userId, username) {
        if (!dom.adminUserHistoryBody) return;
        try {
            if (dom.adminHistoryUsername) dom.adminHistoryUsername.textContent = username;
            dom.adminUserHistoryBody.innerHTML = '<tr><td colspan="5">대화 기록을 불러오는 중...</td></tr>';
            showUserHistoryView();

            const response = await fetch(`/api/admin/get_user_history/${userId}`);
            if (!response.ok) throw new Error('Failed to fetch user history');

            const data = await response.json();
            dom.adminUserHistoryBody.innerHTML = '';

            if (data.history.length === 0) {
                dom.adminUserHistoryBody.innerHTML = '<tr><td colspan="5">이 사용자의 대화 기록이 없습니다.</td></tr>';
                return;
            }

            data.history.forEach(session => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td>${session.id}</td>
                    <td>${session.title}</td>
                    <td>${session.role_name}</td>
                    <td>${session.timestamp}</td>
                    <td>
                        <button class="btn-secondary view-session-btn" data-session-id="${session.id}">대화 보기</button>
                    </td>
                `;
                dom.adminUserHistoryBody.appendChild(tr);
            });

        } catch (error) {
            console.error("Failed to load user history:", error);
            dom.adminUserHistoryBody.innerHTML = '<tr><td colspan="5">기록 로드 실패</td></tr>';
        }
    }

    // 사용자 목록 동작: 삭제 또는 기록 보기.
    if (dom.adminUserListBody) {
        dom.adminUserListBody.addEventListener('click', async (e) => {
            const target = e.target.closest('button');
            if (!target) return;

            const userId = target.dataset.userId;
            const username = target.dataset.username;

            if (target.classList.contains('delete-user-btn')) {
                if (!confirm(`[관리자] '${username}' (ID: ${userId}) 사용자를 정말 삭제하시겠습니까?\n이 사용자의 모든 대화 기록이 함께 삭제되며, 복구할 수 없습니다.`)) {
                    return;
                }
                try {
                    const response = await fetch('/api/admin/delete_user', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ user_id: parseInt(userId) })
                    });
                    const data = await response.json();
                    if (!response.ok || data.error) {
                        throw new Error(data.error || '삭제 실패');
                    }
                    alert(`'${data.username}' 사용자가 성공적으로 삭제되었습니다.`);
                    target.closest('tr').remove();
                } catch (error) {
                    console.error("Failed to delete user:", error);
                    alert("삭제 실패: " + error.message);
                }
            }

            if (target.classList.contains('view-history-btn')) {
                loadUserHistory(userId, username);
            }
        });
    }

    // 기록 테이블: 세션으로 이동.
    if (dom.adminUserHistoryBody) {
        dom.adminUserHistoryBody.addEventListener('click', (e) => {
            const target = e.target.closest('button.view-session-btn');
            if (!target) return;

            const sessionId = target.dataset.sessionId;
            const historyLink = document.querySelector(`#chat-history-list a[data-session-id='${sessionId}']`);
            if (ctx.sessions.loadChatSession) {
                ctx.sessions.loadChatSession(sessionId, historyLink);
            }
            closeModal();
        });
    }
});
