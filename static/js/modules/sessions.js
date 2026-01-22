// 세션 모듈: 기록 목록/필터/이름 변경/삭제/불러오기.
window.App.registerModule((ctx) => {
    const { dom, state } = ctx;

    /**
     * 새 대화를 시작하도록 UI/상태를 초기화한다.
     */
    ctx.sessions.startNewChat = function startNewChat() {
        if (!dom.chatWindow) return;
        dom.chatWindow.innerHTML = `
            <div class="message-wrapper">
                <div class="ai-message">
                    <p class="message-sender">코딩 AI 도우미</p>
                    <p>안녕하세요! ${state.currentUsername}님, 새로운 대화를 시작합니다. 무엇이든 물어보세요! 😊</p>
                </div>
            </div>`;

        state.currentSessionId = null;
        ctx.sessions.updateInputState(true);

        if (dom.userInput) {
            dom.userInput.value = '';
            ctx.ui.adjustTextareaHeight(dom.userInput);
            dom.userInput.focus();
        }
        document.querySelectorAll('#chat-history-list li a.active').forEach(el => {
            el.classList.remove('active');
        });

        if (ctx.files.clearAllPreviews) ctx.files.clearAllPreviews();
        if (ctx.sidebar.closeSidebarMobile) ctx.sidebar.closeSidebarMobile();
        if (ctx.canvas.closeCanvas) ctx.canvas.closeCanvas();

        ctx.provider.updateProviderUI();
    };

    /**
     * 선택된 페르소나의 세션 목록을 가져와 사이드바에 렌더링한다.
     * @param {string} roleKey - 역할 키
     */
    ctx.sessions.fetchHistory = async function fetchHistory(roleKey) {
        if (!dom.historyListContainer) return;
        dom.historyListContainer.innerHTML = '<li><a href="#">불러오는 중...</a></li>';
        if (!dom.modelSelector || dom.modelSelector.selectedIndex === -1) return;

        const selectedRoleName = dom.modelSelector.options[dom.modelSelector.selectedIndex].text;
        if (dom.historyTitle) dom.historyTitle.textContent = `${selectedRoleName} 대화 목록`;

        try {
            const response = await fetch(`/api/get_chat_history?role=${roleKey}`);
            if (!response.ok) throw new Error('Failed to fetch history');

            const data = await response.json();
            dom.historyListContainer.innerHTML = '';

            if (data.length === 0) {
                dom.historyListContainer.innerHTML = '<li><a href="#">기록 없음</a></li>';
            }

            data.forEach(item => {
                const li = document.createElement('li');
                const isOwner = (item.username === state.currentUsername);
                const showActions = isOwner || state.isAdmin;

                const lockIcon = isOwner ? '' : '<span style="font-size:0.8em; margin-right:4px;">🔒</span>';
                const ownerLabel = isOwner ? '' : `<span style="font-size:0.75em; color:#9CA3AF; margin-left:4px;">(${item.username})</span>`;

                const menuBtnHtml = showActions ?
                    `<button class="history-menu-btn" data-session-id="${item.id}" data-title="${item.title}" title="옵션">⋮</button>`
                    : '';

                li.innerHTML = `
                    <a href="#" data-session-id="${item.id}" title="${item.title}" class="${isOwner ? 'my-session' : 'other-session'}">
                        ${lockIcon}<span class="history-item-title">${item.title}</span>${ownerLabel}
                    </a>
                    ${menuBtnHtml}
                `;
                dom.historyListContainer.appendChild(li);
            });

            ctx.sessions.filterChatHistory();

        } catch (error) {
            console.error("Failed to fetch chat history:", error);
            dom.historyListContainer.innerHTML = '<li><a href="#">오류 발생</a></li>';
        }
    };

    /**
     * 검색어 + 내 대화만 보기 필터를 적용한다.
     */
    ctx.sessions.filterChatHistory = function filterChatHistory() {
        if (!dom.historyListContainer) return;
        const searchTerm = dom.searchInput ? dom.searchInput.value.toLowerCase() : "";
        const items = dom.historyListContainer.getElementsByTagName('li');

        Array.from(items).forEach(item => {
            const link = item.querySelector('a');
            if (!link) return;

            const text = link.textContent.toLowerCase();
            const matchesSearch = text.includes(searchTerm);

            const isMySession = link.classList.contains('my-session');
            const matchesFilter = state.isMyChatFilterActive ? isMySession : true;

            if (matchesSearch && matchesFilter) {
                item.style.display = '';
            } else {
                item.style.display = 'none';
            }
        });
    };

    /**
     * 세션 메시지를 불러오고 입력 가능 여부를 갱신한다.
     * @param {string|number} sessionId - 세션 ID
     * @param {HTMLElement|null} clickedElement - 클릭된 링크
     */
    ctx.sessions.loadChatSession = async function loadChatSession(sessionId, clickedElement) {
        document.querySelectorAll('#chat-history-list li a.active').forEach(el => {
            el.classList.remove('active');
        });
        if (clickedElement) {
            clickedElement.classList.add('active');
        }
        if (ctx.sidebar.closeSidebarMobile) ctx.sidebar.closeSidebarMobile();
        if (ctx.canvas.closeCanvas) ctx.canvas.closeCanvas();

        dom.chatWindow.innerHTML = `
            <div class="message-wrapper">
                <div class="ai-message">
                    <p class="message-sender">코딩 AI 도우미</p>
                    <p>대화 내용을 불러오는 중입니다...</p>
                </div>
            </div>`;

        try {
            const response = await fetch(`/api/get_session/${sessionId}`);
            if (!response.ok) throw new Error('Failed to load session');

            const data = await response.json();
            const messages = data.messages;
            const ownerUsername = data.owner_username;

            const isMySession = (ownerUsername === state.currentUsername);

            dom.chatWindow.innerHTML = '';
            messages.forEach(msg => {
                ctx.messages.addMessage(msg.text, msg.sender, null, msg.username, msg.image_path);
            });
            state.currentSessionId = sessionId;

            ctx.sessions.updateInputState(isMySession, ownerUsername);
            if (ctx.files.clearAllPreviews) ctx.files.clearAllPreviews();

        } catch (error) {
            console.error("Failed to load session:", error);
            dom.chatWindow.innerHTML = `
                <div class="message-wrapper">
                    <div class="ai-message">
                        <p class="message-sender">오류</p>
                        <p>대화 내용을 불러오는 데 실패했습니다.</p>
                    </div>
                </div>`;
            state.currentSessionId = null;
        }
    };

    /**
     * 소유자/관리자 여부에 따라 입력창을 활성/비활성화한다.
     * @param {boolean} isEditable - 편집 가능 여부
     * @param {string} ownerName - 소유자 이름
     */
    ctx.sessions.updateInputState = function updateInputState(isEditable, ownerName) {
        const sendBtn = document.getElementById('send-button');
        const uploadBtn = document.querySelector('.file-upload-button');

        if (isEditable) {
            dom.userInput.disabled = false;
            dom.userInput.placeholder = "AI에게 질문을 입력하세요... (Shift+Enter로 줄바꿈)";
            dom.userInput.style.backgroundColor = "transparent";
            if (sendBtn) {
                sendBtn.disabled = false;
                sendBtn.style.backgroundColor = "#EC4899";
                sendBtn.style.cursor = "pointer";
            }
            if (uploadBtn) uploadBtn.style.pointerEvents = "auto";
        } else {
            dom.userInput.disabled = true;
            dom.userInput.placeholder = `🔒 ${ownerName}님의 대화입니다. (읽기 전용)`;
            dom.userInput.style.backgroundColor = "#F3F4F6";
            dom.userInput.value = "";
            if (sendBtn) {
                sendBtn.disabled = true;
                sendBtn.style.backgroundColor = "#9CA3AF";
                sendBtn.style.cursor = "not-allowed";
            }
            if (uploadBtn) uploadBtn.style.pointerEvents = "none";
        }
        ctx.ui.adjustTextareaHeight(dom.userInput);
    };

    /**
     * 세션을 삭제하고 UI를 갱신한다.
     * @param {string|number} sessionId - 세션 ID
     */
    ctx.sessions.deleteChatSession = async function deleteChatSession(sessionId) {
        if (!confirm(`정말 이 대화방을 삭제하시겠습니까?\n이 작업은 되돌릴 수 없습니다.`)) {
            return;
        }
        try {
            const response = await fetch(`/api/delete_session/${sessionId}`, { method: 'POST' });
            if (!response.ok) throw new Error('Failed to delete session');
            const data = await response.json();
            if (data.success) {
                const targetBtn = document.querySelector(`.history-menu-btn[data-session-id="${sessionId}"]`);
                if (targetBtn) targetBtn.closest('li').remove();

                if (String(state.currentSessionId) === String(sessionId)) {
                    ctx.sessions.startNewChat();
                }
            } else {
                alert("삭제 실패: " + (data.error || "알 수 없는 오류"));
            }
        } catch (error) {
            console.error("Failed to delete session:", error);
            alert("삭제 중 서버 오류가 발생했습니다.");
        }
    };

    /**
     * 세션 제목을 변경한다.
     * @param {string|number} sessionId - 세션 ID
     * @param {string} currentTitle - 현재 제목
     */
    ctx.sessions.renameChatSession = async function renameChatSession(sessionId, currentTitle) {
        const newTitle = prompt("변경할 대화 주제를 입력하세요:", currentTitle);
        if (newTitle === null || newTitle.trim() === "") return;
        if (newTitle === currentTitle) return;

        try {
            const response = await fetch(`/api/rename_session/${sessionId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ new_title: newTitle.trim() })
            });

            if (!response.ok) throw new Error('Failed to rename session');
            const data = await response.json();

            if (data.success) {
                const selectedRoleKey = dom.modelSelector.value;
                ctx.sessions.fetchHistory(selectedRoleKey);
            } else {
                alert("이름 변경 실패: " + (data.error || "알 수 없는 오류"));
            }
        } catch (error) {
            console.error("Failed to rename session:", error);
            alert("이름 변경 중 서버 오류가 발생했습니다.");
        }
    };

    // 페르소나 변경: 대화 초기화 및 기록 갱신.
    if (dom.modelSelector) {
        dom.modelSelector.addEventListener('change', () => {
            const selectedRoleKey = dom.modelSelector.value;
            ctx.sessions.startNewChat();
            ctx.sessions.fetchHistory(selectedRoleKey);
            if (ctx.provider.fetchPersonaRestrictions) {
                ctx.provider.fetchPersonaRestrictions(selectedRoleKey)
                    .finally(() => ctx.provider.updateProviderUI());
            } else {
                ctx.provider.updateProviderUI();
            }
        });
    }

    // 새 채팅 버튼.
    if (dom.newChatButton) {
        dom.newChatButton.addEventListener('click', () => {
            ctx.sessions.startNewChat();
        });
    }

    // 현재 파일 버튼: 세션/전체 모드.
    if (dom.openCurrentFilesBtn) {
        dom.openCurrentFilesBtn.addEventListener('click', () => {
            if (state.currentSessionId) {
                ctx.files.openFileModal(state.currentSessionId, false);
            } else {
                ctx.files.openFileModal(null, true);
            }
        });
    }

    // 내 대화만 보기 토글.
    if (dom.myChatFilterBtn) {
        dom.myChatFilterBtn.addEventListener('click', () => {
            state.isMyChatFilterActive = !state.isMyChatFilterActive;

            if (state.isMyChatFilterActive) {
                dom.myChatFilterBtn.classList.add('active');
                if (dom.searchInput) dom.searchInput.placeholder = "내 채팅 기록 검색...";
            } else {
                dom.myChatFilterBtn.classList.remove('active');
                if (dom.searchInput) dom.searchInput.placeholder = "채팅 기록 검색...";
            }

            ctx.sessions.filterChatHistory();
        });
    }

    // 검색 입력 이벤트.
    if (dom.searchInput) {
        dom.searchInput.addEventListener('input', ctx.sessions.filterChatHistory);
    }

    // 기록 목록 클릭: 세션 열기 또는 메뉴 표시.
    if (dom.historyListContainer) {
        dom.historyListContainer.addEventListener('click', (e) => {
            const menuBtn = e.target.closest('.history-menu-btn');
            if (menuBtn) {
                e.preventDefault();
                e.stopPropagation();

                const sessionId = menuBtn.dataset.sessionId;
                const title = menuBtn.dataset.title;
                state.activeSessionId = sessionId;
                state.activeSessionTitle = title;

                const rect = menuBtn.getBoundingClientRect();

                dom.contextMenu.style.top = `${rect.bottom + window.scrollY + 5}px`;
                dom.contextMenu.style.left = `${rect.right - 120 + window.scrollX}px`;
                dom.contextMenu.classList.add('show');
                return;
            }

            const link = e.target.closest('a');
            if (link && link.dataset.sessionId) {
                e.preventDefault();
                const sessionId = link.dataset.sessionId;
                ctx.sessions.loadChatSession(sessionId, link);
                return;
            }
        });
    }

    // 컨텍스트 메뉴 동작(이름 변경/삭제).
    dom.contextMenu.addEventListener('click', (e) => {
        e.stopPropagation();

        if (e.target.closest('.ctx-edit-btn')) {
            ctx.sessions.renameChatSession(state.activeSessionId, state.activeSessionTitle);
            dom.contextMenu.classList.remove('show');
        }

        if (e.target.closest('.ctx-delete-btn')) {
            ctx.sessions.deleteChatSession(state.activeSessionId);
            dom.contextMenu.classList.remove('show');
        }
    });

    // 외부 클릭 시 컨텍스트 메뉴 닫기.
    window.addEventListener('click', () => {
        dom.contextMenu.classList.remove('show');
    });

    // 초기 로딩 시 기록 불러오기.
    if (dom.modelSelector) {
        const initialRoleKey = dom.modelSelector.value;
        ctx.sessions.fetchHistory(initialRoleKey);
    }
});
