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
        updateBulkButtons();
    };

    /**
     * 체크박스 선택 수에 따라 일괄 버튼 UI 갱신.
     */
    function updateBulkButtons() {
        const checkedCount = document.querySelectorAll('.user-select-checkbox:checked').length;
        const container = document.getElementById('bulk-actions-container');
        if (!container) return;

        if (dom.navUserList && dom.navUserList.classList.contains('active')) {
            container.style.display = 'flex';
            const btnApprove = document.getElementById('btn-bulk-approve');
            const btnDelete = document.getElementById('btn-bulk-delete');
            if (checkedCount >= 2) {
                if (btnApprove) btnApprove.style.display = 'inline-block';
                if (btnDelete) btnDelete.style.display = 'inline-block';
            } else {
                if (btnApprove) btnApprove.style.display = 'none';
                if (btnDelete) btnDelete.style.display = 'none';
            }
        } else {
            container.style.display = 'none';
        }
    }

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

        if (!document.getElementById('bulk-actions-container')) {
            const bulkContainer = document.createElement('div');
            bulkContainer.id = 'bulk-actions-container';
            bulkContainer.style.display = 'none';
            bulkContainer.style.alignItems = 'center';
            bulkContainer.style.gap = '8px';
            bulkContainer.style.marginLeft = 'auto'; // 우측에 밀착
            bulkContainer.innerHTML = `
                <button id="btn-bulk-approve" class="btn-success btn-sm" style="display: none; padding: 4px 8px; font-size: 0.8rem;">일괄 승인</button>
                <button id="btn-bulk-delete" class="btn-danger btn-sm" style="display: none; padding: 4px 8px; font-size: 0.8rem;">일괄 삭제</button>
            `;
            dom.adminNav.appendChild(bulkContainer);

            document.getElementById('btn-bulk-approve').onclick = async () => {
                const checked = document.querySelectorAll('.user-select-checkbox:checked');
                if (checked.length === 0) return;
                const ids = Array.from(checked).map(cb => parseInt(cb.dataset.userId));
                if (!confirm(`선택한 ${ids.length}명의 사용자를 일괄 승인 처리하시겠습니까?`)) return;
                try {
                    const res = await fetch('/api/admin/bulk_approve_users', {
                        method: 'POST', headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ user_ids: ids })
                    });
                    if (res.ok) { alert('✅ 일괄 승인 완료'); loadAdminUserList(); }
                } catch (e) { console.error(e); }
            };

            document.getElementById('btn-bulk-delete').onclick = async () => {
                const checked = document.querySelectorAll('.user-select-checkbox:checked');
                if (checked.length === 0) return;
                const ids = Array.from(checked).map(cb => parseInt(cb.dataset.userId));
                if (!confirm(`⚠️ 선택한 ${ids.length}명의 사용자를 부속 기록과 함께 영구 삭제하시겠습니까?`)) return;
                try {
                    const res = await fetch('/api/admin/bulk_delete_users', {
                        method: 'POST', headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ user_ids: ids })
                    });
                    if (res.ok) { alert('✅ 일괄 삭제 완료'); loadAdminUserList(); }
                } catch (e) { console.error(e); }
            };
        }
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

    // 교사 패널 버튼 클릭 시 페르소나 관리 화면으로 이동
    if (dom.teacherPanelButton) {
        console.log('✅ 교사 패널 버튼 이벤트 리스너 등록됨');
        dom.teacherPanelButton.addEventListener('click', (e) => {
            console.log('🎯 교사 패널 버튼 클릭됨');
            e.preventDefault();
            e.stopPropagation();
            console.log('➡️ /admin/persona로 이동 중...');
            window.location.href = '/admin/persona';
        });
    } else {
        console.log('❌ 교사 패널 버튼을 찾을 수 없음');
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
            // loadModelConfig(); // 제거됨 - 중복 기능
            loadProviderStatus();
            loadProviderModels();
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

            const providers = ['google', 'anthropic', 'openai', 'xai'];
            const tr = document.createElement('tr');
            providers.forEach(p => {
                const status = statuses[p];
                const isActive = status === 'active';
                tr.innerHTML += `
                    <td>
                        <div class="provider-status-cell">
                            <div class="provider-name">${p.toUpperCase()}</div>
                            <select class="provider-status-select" data-provider="${p}">
                                <option value="active" ${isActive ? 'selected' : ''}>사용 가능</option>
                                <option value="restricted" ${!isActive ? 'selected' : ''}>제한하기</option>
                            </select>
                        </div>
                    </td>
                `;
            });
            dom.adminProviderStatusBody.appendChild(tr);

            document.querySelectorAll('.provider-status-select').forEach(select => {
                select.addEventListener('change', async (e) => {
                    const provider = e.target.dataset.provider;
                    const status = e.target.value;
                    await setProviderStatus(provider, status);
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
    async function setProviderStatus(provider, status) {
        try {
            const response = await fetch('/api/admin/set_provider_status', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ provider: provider, status: status })
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
     * 공급사 모델 설정 로드 및 이벤트 바인딩
     */
    async function loadProviderModels() {
        const providers = ['openai', 'anthropic', 'google', 'xai'];

        // 1. 각 공급사의 상태 로드 (이미 loadProviderStatus()에서 처리됨)

        // 2. 각 공급사별로 모델 리스트 로드
        for (const provider of providers) {
            await loadModelsForProvider(provider);
        }

        // 3. 라디오 버튼 이벤트 리스너
        providers.forEach(provider => {
            const radios = document.querySelectorAll(`input[name="provider-${provider}-status"]`);
            radios.forEach(radio => {
                radio.addEventListener('change', async (e) => {
                    const status = e.target.value;
                    const modelsSection = document.getElementById(`${provider}-models-section`);

                    if (status === 'active') {
                        modelsSection.style.display = 'block';
                    } else {
                        modelsSection.style.display = 'none';
                    }

                    // 공급사 상태 저장
                    await setProviderStatus(provider, status);
                });
            });
        });

        // 4. 저장 버튼 이벤트 리스너
        const saveBtn = document.getElementById('save-provider-models-btn');
        if (saveBtn) {
            saveBtn.addEventListener('click', async () => {
                await saveAllProviderModels();
            });
        }
    }

    /**
     * 특정 공급사의 모델 리스트 로드
     */
    async function loadModelsForProvider(provider) {
        const loadingDiv = document.getElementById(`${provider}-models-loading`);
        const listDiv = document.getElementById(`${provider}-models-list`);
        const lastUpdateSpan = document.getElementById(`${provider}-last-update`);

        if (!loadingDiv || !listDiv) return;

        try {
            // 1. 사용 가능한 모든 모델 조회 (메타데이터 포함)
            const availableResponse = await fetch(`/api/admin/available_models/${provider}`);
            const availableData = await availableResponse.json();

            if (!availableData.models) {
                throw new Error('모델 리스트를 가져올 수 없습니다.');
            }

            // 2. 현재 활성화된 모델 조회
            const enabledResponse = await fetch(`/api/admin/enabled_models/${provider}`);
            const enabledData = await enabledResponse.json();
            const enabledModels = enabledData.enabled_models || [];

            // 3. 모델 순서 조회
            const orderResponse = await fetch(`/api/admin/model_order/${provider}`);
            const orderData = await orderResponse.json();
            const modelOrder = orderData.model_order || [];

            // 4. 순서에 따라 모델 정렬
            const sortedModels = [...availableData.models].sort((a, b) => {
                const indexA = modelOrder.indexOf(a.id);
                const indexB = modelOrder.indexOf(b.id);
                if (indexA === -1 && indexB === -1) return 0;
                if (indexA === -1) return 1;
                if (indexB === -1) return -1;
                return indexA - indexB;
            });

            // 5. UI 생성 (메타데이터 포함)
            let html = '';

            sortedModels.forEach(model => {
                const isChecked = enabledModels.includes(model.id) ? 'checked' : '';
                const inputPrice = model.input_price ? `$${model.input_price}/M` : '';
                const outputPrice = model.output_price ? `$${model.output_price}/M` : '';
                const description = model.description || '';

                html += `
                    <div class="model-item" draggable="true" data-model-id="${model.id}">
                        <span class="drag-handle">⋮⋮</span>
                        <input type="checkbox"
                               name="${provider}-model"
                               value="${model.id}"
                               ${isChecked}>
                        <div class="model-info">
                            <div class="model-name">${model.name}</div>
                            ${inputPrice || outputPrice ? `
                            <div class="model-metadata">
                                ${inputPrice ? `<span class="model-price">📥 ${inputPrice}</span>` : ''}
                                ${outputPrice ? `<span class="model-price">📤 ${outputPrice}</span>` : ''}
                            </div>
                            ` : ''}
                            ${description ? `<div class="model-description">${description}</div>` : ''}
                        </div>
                    </div>
                `;
            });

            listDiv.innerHTML = html;
            loadingDiv.style.display = 'none';
            listDiv.style.display = 'block';

            // 6. 드래그 앤 드롭 이벤트 리스너 등록
            initDragAndDrop(listDiv, provider);

            // 7. 마지막 업데이트 시간 표시
            if (lastUpdateSpan) {
                loadLastUpdateTime(provider, lastUpdateSpan);
            }

        } catch (error) {
            console.error(`${provider} 모델 로드 실패:`, error);
            loadingDiv.innerHTML = `<p style="color: red;">모델 로드 실패: ${error.message}</p>`;
        }
    }

    /**
     * 모든 공급사의 선택된 모델 저장 (순서 포함)
     */
    async function saveAllProviderModels() {
        const providers = ['openai', 'anthropic', 'google', 'xai'];
        let successCount = 0;

        for (const provider of providers) {
            try {
                // 1. 체크된 모델들 수집
                const checkboxes = document.querySelectorAll(`input[name="${provider}-model"]:checked`);
                const enabledModels = Array.from(checkboxes).map(cb => cb.value);

                // 2. 모델 순서 수집 (드래그로 재정렬된 순서)
                const listDiv = document.getElementById(`${provider}-models-list`);
                const modelItems = listDiv.querySelectorAll('.model-item');
                const modelOrder = Array.from(modelItems).map(item => item.dataset.modelId);

                // 3. 활성화된 모델 저장
                const enabledResponse = await fetch('/api/admin/enabled_models', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        provider: provider,
                        enabled_models: enabledModels
                    })
                });

                const enabledResult = await enabledResponse.json();

                // 4. 모델 순서 저장
                const orderResponse = await fetch('/api/admin/model_order', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        provider: provider,
                        model_order: modelOrder
                    })
                });

                const orderResult = await orderResponse.json();

                if (enabledResult.success && orderResult.success) {
                    successCount++;
                } else {
                    console.error(`${provider} 저장 실패:`, enabledResult.error || orderResult.error);
                }
            } catch (error) {
                console.error(`${provider} 저장 중 오류:`, error);
            }
        }

        if (successCount === providers.length) {
            alert('✅ 모든 공급사의 모델 설정이 저장되었습니다.');
        } else {
            alert(`⚠️ ${successCount}/${providers.length}개 공급사 저장 완료. 일부 실패가 있습니다.`);
        }
    }

    /**
     * 드래그 앤 드롭 기능 초기화
     */
    function initDragAndDrop(listDiv, provider) {
        const items = listDiv.querySelectorAll('.model-item');

        items.forEach(item => {
            item.addEventListener('dragstart', (e) => {
                item.classList.add('dragging');
                e.dataTransfer.effectAllowed = 'move';
                e.dataTransfer.setData('text/html', item.innerHTML);
            });

            item.addEventListener('dragend', (e) => {
                item.classList.remove('dragging');
            });

            item.addEventListener('dragover', (e) => {
                e.preventDefault();
                const draggingItem = listDiv.querySelector('.dragging');
                if (draggingItem && draggingItem !== item) {
                    const rect = item.getBoundingClientRect();
                    const midpoint = rect.top + rect.height / 2;
                    if (e.clientY < midpoint) {
                        listDiv.insertBefore(draggingItem, item);
                    } else {
                        listDiv.insertBefore(draggingItem, item.nextSibling);
                    }
                }
            });

            item.addEventListener('dragenter', (e) => {
                e.preventDefault();
                item.classList.add('drag-over');
            });

            item.addEventListener('dragleave', (e) => {
                item.classList.remove('drag-over');
            });

            item.addEventListener('drop', (e) => {
                e.preventDefault();
                item.classList.remove('drag-over');
            });
        });
    }

    /**
     * 마지막 업데이트 시간 표시
     */
    async function loadLastUpdateTime(provider, spanElement) {
        try {
            const key = `last_model_update_${provider}`;
            const response = await fetch(`/api/admin/system_config/${key}`);
            if (response.ok) {
                const data = await response.json();
                const lastUpdate = new Date(data.value);
                const timeAgo = getTimeAgo(lastUpdate);
                spanElement.textContent = `마지막 업데이트: ${timeAgo}`;
            }
        } catch (error) {
            console.error('마지막 업데이트 시간 조회 실패:', error);
        }
    }

    /**
     * 시간차 계산 (예: "2시간 전")
     */
    function getTimeAgo(date) {
        const seconds = Math.floor((new Date() - date) / 1000);
        const intervals = {
            '년': 31536000,
            '개월': 2592000,
            '일': 86400,
            '시간': 3600,
            '분': 60
        };

        for (const [unit, secondsInUnit] of Object.entries(intervals)) {
            const interval = Math.floor(seconds / secondsInUnit);
            if (interval >= 1) {
                return `${interval}${unit} 전`;
            }
        }
        return '방금 전';
    }

    // refreshModels를 전역 함수로 등록 (HTML onclick에서 사용)
    window.refreshModels = async function (provider) {
        const btn = event.target;
        btn.disabled = true;
        btn.textContent = '⏳';

        try {
            const response = await fetch(`/api/admin/refresh_models/${provider}`, {
                method: 'POST'
            });

            const result = await response.json();

            if (result.success) {
                // 새로운 모델이 발견되었으면 알림
                if (result.new_models && result.new_models.length > 0) {
                    alert(`✨ 새로운 모델 발견:\n${result.new_models.join(', ')}\n\n체크박스를 활성화하여 사용할 수 있습니다.`);
                } else {
                    alert('✅ 모델 리스트가 최신 상태입니다.');
                }

                // UI 다시 로드
                await loadModelsForProvider(provider);
            } else {
                alert(`❌ 새로고침 실패: ${result.error}`);
            }
        } catch (error) {
            console.error('새로고침 오류:', error);
            alert('❌ 새로고침 중 오류가 발생했습니다.');
        } finally {
            btn.disabled = false;
            btn.textContent = '🔄';
        }
    };


    /**
     * 관리자 사용자 목록 테이블을 로드한다. (정렬 기능 및 UI 개선)
     */
    async function loadAdminUserList() {
        if (!dom.adminUserListBody) return;
        try {
            dom.adminUserListBody.innerHTML = '<tr><td colspan="6">사용자 목록을 불러오는 중...</td></tr>';
            const response = await fetch('/api/admin/get_users');
            if (!response.ok) throw new Error('Failed to fetch users');

            let users = await response.json();
            // 검색 필터링용 캐싱
            ctx._adminAllUsers = users;

            // 정렬 상태 초기화 (최대 3개 기준)
            if (!ctx.adminSortState) {
                ctx.adminSortState = [{ key: 'username', dir: 'asc' }];
            }

            // 다중 정렬 로직 적용
            users.sort((a, b) => {
                for (const criteria of ctx.adminSortState) {
                    const key = criteria.key;
                    const dir = criteria.dir === 'asc' ? 1 : -1;
                    let valA = a[key] ?? '';
                    let valB = b[key] ?? '';

                    if (typeof valA === 'string') valA = valA.toLowerCase();
                    if (typeof valB === 'string') valB = valB.toLowerCase();

                    if (valA < valB) return -1 * dir;
                    if (valA > valB) return 1 * dir;
                }
                return 0;
            });

            dom.adminUserListBody.innerHTML = '';

            users.forEach(user => {
                const tr = document.createElement('tr');

                // Role Select
                const roleCell = user.is_admin
                    ? '<span class="admin-badge">admin</span>'
                    : `<select class="user-role-select" data-user-id="${user.id}">
                            <option value="user" ${user.role === 'user' ? 'selected' : ''}>user</option>
                            <option value="teacher" ${user.role === 'teacher' ? 'selected' : ''}>teacher</option>
                        </select>`;

                // Email (CSS에서 넓게 잡음)
                const emailCell = user.email || '-';

                // Approval Icon (Toggle 방식)
                let approvalIcon = '';
                if (user.is_admin) {
                    approvalIcon = '<span class="status-icon status-approved" title="관리자">✅</span>';
                } else {
                    if (user.is_approved) {
                        approvalIcon = `<span class="status-icon status-approved toggle-approval-btn" data-user-id="${user.id}" data-approved="true" title="승인됨 (클릭하여 승인 취소)">✅</span>`;
                    } else {
                        approvalIcon = `<span class="status-icon status-unapproved toggle-approval-btn" data-user-id="${user.id}" data-approved="false" title="미승인 (클릭하여 승인)">❌</span>`;
                    }
                }

                // 이름과 이메일 분리하여 이름만 가져오기
                const displayName = user.username.includes('/') ? user.username.split('/')[0] : user.username;

                tr.innerHTML = `
                    <td style="text-align: center;"><input type="checkbox" class="user-select-checkbox" data-user-id="${user.id}"></td>
                    <td style="text-align: center;">${user.id}</td>
                    <td>${displayName}</td>
                    <td style="font-size: 0.85rem; width: 100%; word-break: break-all;">${emailCell}</td>
                    <td style="text-align: center;">${approvalIcon}</td>
                    <td style="text-align: center;">${roleCell}</td>
                    <td style="text-align: center;">
                        <div class="btn-group" style="justify-content: center;">
                            <button class="btn-secondary btn-xs view-history-btn" data-user-id="${user.id}" data-username="${user.username}">기록</button>
                            <button class="btn-danger btn-xs delete-user-btn" data-user-id="${user.id}" data-username="${user.username}" ${user.username === state.currentUsername ? 'disabled' : ''}>삭제</button>
                            ${!user.is_admin ? `<button class="btn-warning btn-xs reset-password-btn" data-user-id="${user.id}" data-username="${displayName}">🔑</button>` : ''}
                        </div>
                    </td>
                `;
                dom.adminUserListBody.appendChild(tr);
            });

            const selectAllCheck = document.getElementById('selectAllUsers');
            if (selectAllCheck) {
                selectAllCheck.checked = false;
                selectAllCheck.onchange = (e) => {
                    const checkboxes = document.querySelectorAll('.user-select-checkbox');
                    checkboxes.forEach(cb => cb.checked = e.target.checked);
                    updateBulkButtons();
                };
            }

            const userCheckboxes = Array.from(document.querySelectorAll('.user-select-checkbox'));
            let lastCheckedIndex = null;
            userCheckboxes.forEach((cb, index) => {
                cb.addEventListener('click', (e) => {
                    if (e.shiftKey && lastCheckedIndex !== null) {
                        const start = Math.min(lastCheckedIndex, index);
                        const end = Math.max(lastCheckedIndex, index);
                        
                        for (let i = start; i <= end; i++) {
                            userCheckboxes[i].checked = cb.checked;
                        }
                    }
                    lastCheckedIndex = index;
                });
                cb.addEventListener('change', updateBulkButtons);
            });
            updateBulkButtons();

            // 헤더 클릭 이벤트 (정렬) - 최초 1회만 등록
            const thead = document.querySelector('.admin-table thead');
            if (thead && !thead.dataset.sortInitialized) {
                thead.dataset.sortInitialized = 'true';

                // 헤더에 sortKey 데이터 속성 주입 (0번은 체크박스라 제외)
                const headers = thead.querySelectorAll('th');
                if (headers.length >= 6) {
                    headers[1].dataset.sortKey = 'id';
                    headers[2].dataset.sortKey = 'username';
                    headers[3].dataset.sortKey = 'email';
                    headers[4].dataset.sortKey = 'is_approved';
                    headers[5].dataset.sortKey = 'role';
                }

                thead.addEventListener('click', (e) => {
                    // Prevent sort if clicking on the checkbox or its cell
                    if (e.target.tagName.toLowerCase() === 'input') return;

                    const th = e.target.closest('th');
                    if (!th || !th.dataset.sortKey) return;

                    const key = th.dataset.sortKey;

                    // 정렬 상태 업데이트
                    const existingIndex = ctx.adminSortState.findIndex(s => s.key === key);

                    if (existingIndex !== -1) {
                        // 이미 존재: asc -> desc -> remove
                        const currentDir = ctx.adminSortState[existingIndex].dir;
                        if (currentDir === 'asc') {
                            ctx.adminSortState[existingIndex].dir = 'desc';
                        } else {
                            ctx.adminSortState.splice(existingIndex, 1); // Remove
                        }
                    } else {
                        // 새 키: 맨 앞에 추가 (최대 3개 유지)
                        ctx.adminSortState.unshift({ key: key, dir: 'asc' });
                        if (ctx.adminSortState.length > 3) ctx.adminSortState.pop();
                    }

                    // 기본 정렬(username ASC) 유지 (비어있으면)
                    if (ctx.adminSortState.length === 0) {
                        ctx.adminSortState.push({ key: 'username', dir: 'asc' });
                    }

                    loadAdminUserList(); // 재렌더링
                });
            }

            // 헤더 UI 업데이트 (화살표 표시)
            const headers = document.querySelectorAll('.admin-table thead th');
            headers.forEach(th => {
                const key = th.dataset.sortKey;
                let indicator = th.querySelector('.sort-indicator');
                if (!indicator) {
                    indicator = document.createElement('span');
                    indicator.className = 'sort-indicator';
                    th.appendChild(indicator);
                }

                const sortState = ctx.adminSortState.find(s => s.key === key);
                if (sortState) {
                    const order = ctx.adminSortState.indexOf(sortState) + 1;
                    const arrow = sortState.dir === 'asc' ? '▲' : '▼';
                    indicator.textContent = `${arrow}${order}`;
                    indicator.classList.add('active');
                } else {
                    indicator.textContent = '';
                    indicator.classList.remove('active');
                }
            });

            // 정렬 재렌더링 후 현재 검색어 재적용
            if (typeof window.filterAdminUserList === 'function') {
                window.filterAdminUserList();
            }

        } catch (error) {
            console.error("Failed to load users:", error);
            dom.adminUserListBody.innerHTML = '<tr><td colspan="6">사용자 목록 로드 실패: ' + error.message + '</td></tr>';
        }
    }

    /**
     * 사용자 검색 필터 (이름 또는 이메일)
     * HTML의 oninput="filterAdminUserList()"에서 호출
     */
    window.filterAdminUserList = function() {
        const query = (document.getElementById('adminUserSearch')?.value || '').toLowerCase().trim();
        const allUsers = ctx._adminAllUsers || [];
        const rows = dom.adminUserListBody?.querySelectorAll('tr') || [];

        if (!query) {
            rows.forEach(r => r.style.display = '');
            return;
        }

        rows.forEach(row => {
            const username = (row.querySelector('td:nth-child(3)')?.textContent || '').toLowerCase();
            const email    = (row.querySelector('td:nth-child(4)')?.textContent || '').toLowerCase();
            row.style.display = (username.includes(query) || email.includes(query)) ? '' : 'none';
        });
    };

    // 사용자 목록 동작: 승인 토글, 삭제, 기록 보기, 비밀번호 초기화 (이벤트 위임)
    if (dom.adminUserListBody) {
        dom.adminUserListBody.addEventListener('click', async (e) => {
            const target = e.target.closest('.toggle-approval-btn, .delete-user-btn, .view-history-btn, .reset-password-btn');
            if (!target) return;

            const userId = target.dataset.userId;
            const username = target.dataset.username;

            // 1. 승인 토글
            if (target.classList.contains('toggle-approval-btn')) {
                const isApproved = target.dataset.approved === 'true';
                const newStatus = !isApproved;

                try {
                    const response = await fetch('/api/admin/approve_user', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ user_id: userId, is_approved: newStatus })
                    });
                    if (response.ok) {
                        loadAdminUserList(); // UI Refresh
                    } else {
                        alert('변경 실패');
                    }
                } catch (err) {
                    console.error(err);
                }
                return;
            }

            // 2. 사용자 삭제
            if (target.classList.contains('delete-user-btn')) {
                if (!confirm(`[관리자] '${username}' (ID: ${userId}) 사용자를 삭제하시겠습니까?`)) return;
                try {
                    const response = await fetch('/api/admin/delete_user', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ user_id: parseInt(userId) })
                    });
                    if (response.ok) {
                        alert('삭제 완료');
                        target.closest('tr').remove();
                    } else {
                        alert('삭제 실패');
                    }
                } catch (error) {
                    console.error(error);
                }
                return;
            }

            // 3. 기록 조회
            if (target.classList.contains('view-history-btn')) {
                loadUserHistory(userId, username);
                return;
            }

            // 4. 비밀번호 초기화
            if (target.classList.contains('reset-password-btn')) {
                showPasswordResetModal(userId, username);
            }
        });
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

    // 사용자 역할 변경.
    if (dom.adminUserListBody) {
        dom.adminUserListBody.addEventListener('change', async (e) => {
            const target = e.target;
            if (!target.classList.contains('user-role-select')) return;
            const userId = target.dataset.userId;
            const newRole = target.value;
            try {
                const response = await fetch('/api/admin/update_user_role', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ user_id: parseInt(userId), role: newRole })
                });
                if (!response.ok) {
                    throw new Error('역할 변경 실패');
                }
            } catch (error) {
                console.error(error);
                alert("역할 변경 실패");
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

    /**
     * 비밀번호 초기화 모달 표시
     */
    function showPasswordResetModal(userId, username) {
        const existing = document.getElementById('pw-reset-modal');
        if (existing) existing.remove();

        const modal = document.createElement('div');
        modal.id = 'pw-reset-modal';
        modal.style.cssText = `
            position: fixed; top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(0,0,0,0.5); z-index: 9999;
            display: flex; align-items: center; justify-content: center;
        `;
        modal.innerHTML = `
            <div style="background: white; border-radius: 12px; padding: 28px; width: 360px; box-shadow: 0 8px 32px rgba(0,0,0,0.2);">
                <h3 style="margin: 0 0 8px 0; font-size: 1.1rem;">🔑 비밀번호 초기화</h3>
                <p style="margin: 0 0 16px 0; color: #666; font-size: 0.9rem;">${username} 사용자의 비밀번호를 초기화합니다.</p>
                <div style="margin-bottom: 12px;">
                    <label style="font-size: 0.85rem; color: #555; display: block; margin-bottom: 4px;">새 비밀번호 (비워두면 자동 생성)</label>
                    <input id="pw-reset-input" type="text" placeholder="직접 입력하거나 비워두세요"
                        style="width: 100%; padding: 8px 12px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 0.95rem; box-sizing: border-box;">
                </div>
                <div style="display: flex; gap: 8px; justify-content: flex-end;">
                    <button id="pw-reset-cancel" style="padding: 8px 16px; border: 1px solid #d1d5db; border-radius: 6px; background: white; cursor: pointer;">취소</button>
                    <button id="pw-reset-confirm" style="padding: 8px 16px; border: none; border-radius: 6px; background: #f59e0b; color: white; font-weight: bold; cursor: pointer;">초기화</button>
                </div>
                <div id="pw-reset-result" style="display:none; margin-top: 14px; padding: 10px 14px; background: #f0fdf4; border: 1px solid #86efac; border-radius: 6px; font-size: 0.9rem;"></div>
            </div>
        `;

        document.body.appendChild(modal);

        document.getElementById('pw-reset-cancel').onclick = () => modal.remove();
        modal.addEventListener('click', (e) => { if (e.target === modal) modal.remove(); });

        document.getElementById('pw-reset-confirm').onclick = async () => {
            const pw = document.getElementById('pw-reset-input').value.trim();
            const btn = document.getElementById('pw-reset-confirm');
            btn.disabled = true;
            btn.textContent = '처리중...';

            try {
                const res = await fetch('/api/admin/reset_password', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ user_id: parseInt(userId), password: pw })
                });
                const data = await res.json();
                if (data.success) {
                    const resultDiv = document.getElementById('pw-reset-result');
                    resultDiv.style.display = 'block';
                    resultDiv.innerHTML = `✅ 초기화 완료! 새 비밀번호: <strong style="font-family: monospace; font-size: 1rem;">${data.new_password}</strong>`;
                    btn.style.display = 'none';
                    document.getElementById('pw-reset-cancel').textContent = '닫기';
                } else {
                    alert(data.error || '초기화 실패');
                    btn.disabled = false;
                    btn.textContent = '초기화';
                }
            } catch (err) {
                console.error(err);
                btn.disabled = false;
                btn.textContent = '초기화';
            }
        };
    }

    /**
     * 공급사별 모델 목록 접기/펴기 토글
     * @param {string} provider - 'openai' | 'anthropic' | 'google' | 'xai'
     */
    window.toggleProviderModels = function (provider) {
        const section = document.querySelector(`.provider-section[data-provider="${provider}"]`);
        const toggleBtn = section.querySelector('.btn-toggle-models');
        const toggleIcon = toggleBtn.querySelector('.toggle-icon');
        const toggleText = toggleBtn.querySelector('.toggle-text');

        // 토글 상태 변경
        section.classList.toggle('collapsed');
        toggleBtn.classList.toggle('collapsed');

        // 버튼 텍스트 및 아이콘 업데이트
        if (section.classList.contains('collapsed')) {
            toggleText.textContent = '펴기';
            toggleIcon.textContent = '🔼';
        } else {
            toggleText.textContent = '접기';
            toggleIcon.textContent = '🔽';
        }
    };
});
