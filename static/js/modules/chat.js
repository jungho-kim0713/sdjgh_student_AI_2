// 채팅 입력 및 전송 흐름 모듈.
window.App.registerModule((ctx) => {
    const { dom, state } = ctx;

    // 입력 이벤트: 자동 높이 조절, 엔터 전송, 붙여넣기 파일 처리.
    if (dom.userInput) {
        dom.userInput.addEventListener('input', () => {
            ctx.ui.adjustTextareaHeight(dom.userInput);
        });

        dom.userInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                if (dom.chatForm) dom.chatForm.requestSubmit();
            }
        });

        dom.userInput.addEventListener('paste', (e) => {
            const items = (e.clipboardData || e.originalEvent.clipboardData).items;
            const newFiles = [];
            for (let i = 0; i < items.length; i++) {
                if (items[i].kind === 'file') {
                    const file = items[i].getAsFile();
                    if (file) {
                        newFiles.push(file);
                    }
                }
            }
            if (newFiles.length > 0) {
                ctx.files.handleFileSelect(newFiles);
            }
        });
    }

    // 입력창 확장/축소 토글.
    let isExpanded = false;
    if (dom.expandInputBtn) {
        dom.expandInputBtn.addEventListener('click', () => {
            isExpanded = !isExpanded;
            if (isExpanded) {
                dom.chatForm.classList.add('expanded-form');
                dom.userInput.classList.add('expanded-input');
                dom.expandInputBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M8 3v3a2 2 0 0 1-2 2H3m18 0h-3a2 2 0 0 1-2-2V3m0 18v-3a2 2 0 0 1 2-2h3M3 16h3a2 2 0 0 1 2 2v3"/></svg>`;
            } else {
                dom.chatForm.classList.remove('expanded-form');
                dom.userInput.classList.remove('expanded-input');
                dom.expandInputBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/></svg>`;
                ctx.ui.adjustTextareaHeight(dom.userInput);
            }
        });
    }

    /**
     * 응답 대기 중 로딩 메시지를 표시한다.
     */
    function addLoadingMessage() {
        const loadingHtml = `
            <div class="message-wrapper" id="loading-message-wrapper">
                <div class="ai-message">
                    <p class="message-sender">코딩 AI 도우미</p>
                    <div style="display: flex; align-items: center; gap: 4px;">
                        <div class="loading-spinner"></div>
                        <span>AI가 생각하는 중...</span>
                    </div>
                </div>
            </div>
        `;
        dom.chatWindow.insertAdjacentHTML('beforeend', loadingHtml);
        dom.chatWindow.scrollTop = dom.chatWindow.scrollHeight;
    }

    /**
     * 로딩 메시지를 제거한다.
     */
    function removeLoadingMessage() {
        const loadingElement = document.getElementById('loading-message-wrapper');
        if (loadingElement) {
            loadingElement.remove();
        }
    }

    /**
     * 메시지를 서버로 전송하고 응답을 렌더링한다.
     * @param {string} message - 전송할 메시지
     * @param {string|null} image - 이미지 경로/데이터
     * @param {string|number|null} sessionId - 세션 ID
     * @param {Array} fileIds - 업로드된 파일 ID 목록
     */
    async function sendMessageToServer(message, image, sessionId, fileIds = []) {
        const selectedModel = dom.modelSelector ? dom.modelSelector.value : 'general';
        addLoadingMessage();

        try {
            const response = await fetch('/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    session_id: sessionId,
                    message: message,
                    model: selectedModel,
                    provider: state.currentProvider,
                    image: image,
                    file_ids: fileIds
                }),
            });

            removeLoadingMessage();

            if (!response.ok) {
                let errorMessage = `서버 오류 (${response.status})`;
                try {
                    const errorData = await response.json();
                    if (errorData.error) {
                        errorMessage = errorData.error;
                    }
                } catch (e) {}
                throw new Error(errorMessage);
            }

            const data = await response.json();

            if (data.error) {
                ctx.messages.addMessage(data.error, 'ai', null, "오류", null);
                return;
            }

            let senderName = "AI 도우미";
            if (state.currentProvider === 'openai') senderName = "GPT";
            else if (state.currentProvider === 'google') senderName = "Gemini";
            else senderName = "Claude";

            ctx.messages.addMessage(data.response, 'ai', null, senderName, null);

            if (data.session_id && !state.currentSessionId) {
                state.currentSessionId = data.session_id;
                ctx.sessions.fetchHistory(selectedModel);
            }

            if (state.currentSessionId) {
                ctx.messages.extractCodeAndSaveFile(data.response, state.currentSessionId);
                if (data.response.includes("```")) {
                    const codeBlockRegex = /```(\w+)?\s*([\s\S]*?)```/;
                    const match = codeBlockRegex.exec(data.response);
                    if (match) {
                        ctx.canvas.openCanvas(match[2].trim(), match[1] || 'txt');
                    }
                }
            }
        } catch (error) {
            removeLoadingMessage();
            console.error('API Error:', error);
            ctx.messages.addMessage(`🚫 오류가 발생했습니다:\n${error.message}`, 'ai', null, "오류", null);
        }
    }

    // 폼 전송: 사용자 메시지 렌더링 → 파일 업로드 → 서버 전송.
    if (dom.chatForm) {
        dom.chatForm.addEventListener('submit', async (event) => {
            event.preventDefault();
            let messageText = dom.userInput.value.trim();
            const filesToSend = [...state.selectedFiles];

            if (!messageText && filesToSend.length === 0) return;

            let displayFile = null;
            if (filesToSend.length > 0) {
                const imgFile = filesToSend.find(f => f.type.startsWith('image/'));
                if (imgFile) displayFile = imgFile;
            }

            ctx.messages.addMessage(messageText, 'user', displayFile, state.currentUsername, null);

            dom.userInput.value = '';
            ctx.ui.adjustTextareaHeight(dom.userInput);
            ctx.files.clearAllPreviews();

            try {
                let finalMessage = messageText;
                let uploadedFileIds = [];

                if (filesToSend.length > 0) {
                    const loadingMessage = ctx.messages.addMessage(`파일 ${filesToSend.length}개를 업로드 및 분석 중입니다...`, 'ai', null, "System", null);

                    for (const file of filesToSend) {
                        const formData = new FormData();
                        formData.append('file', file);

                        try {
                            const uploadRes = await fetch('/api/upload_file', {
                                method: 'POST',
                                body: formData
                            });
                            const uploadData = await uploadRes.json();

                            if (uploadData.success) {
                                uploadedFileIds.push(uploadData.file_id);
                                if (uploadData.extracted_text && !file.type.startsWith('image/')) {
                                    finalMessage += `\n\n--- [첨부 파일: ${uploadData.filename}] ---\n${uploadData.extracted_text}\n----------------------------------\n`;
                                }
                            }
                        } catch (err) {
                            console.error(`File upload failed for ${file.name}:`, err);
                        }
                    }
                    loadingMessage.remove();
                }

                await sendMessageToServer(finalMessage, null, state.currentSessionId, uploadedFileIds);

            } catch (error) {
                console.error("Error during submit:", error);
                ctx.messages.addMessage("오류가 발생했습니다: " + error.message, 'ai', null, "오류", null);
            }
        });
    }
});
