// 파일 처리 모듈: 업로드 미리보기, 파일 모달, 드래그앤드롭.
window.App.registerModule((ctx) => {
    const { dom, state } = ctx;

    /**
     * 파일 모달을 연다(전체/세션 모드).
     * @param {string|null} sessionId - 세션 ID
     * @param {boolean} modeAll - 전체 모드 여부
     */
    ctx.files.openFileModal = function openFileModal(sessionId, modeAll = false) {
        const titleEl = dom.fileModal.querySelector('.file-modal-title');
        if (modeAll) {
            titleEl.textContent = "🗂️ 나의 파일 보관함 (전체)";
            ctx.files.fetchMyAllFiles();
        } else {
            titleEl.textContent = "📁 현재 채팅방 파일 목록";
            ctx.files.fetchSessionFiles(sessionId);
        }

        if (dom.fileModalOverlay) dom.fileModalOverlay.style.display = 'block';
        if (dom.fileModal) {
            dom.fileModal.style.display = 'flex';
            setTimeout(() => dom.fileModal.classList.add('show'), 10);
        }
    };

    /**
     * 파일 모달을 닫는다.
     */
    ctx.files.closeFileModal = function closeFileModal() {
        if (dom.fileModal) dom.fileModal.classList.remove('show');
        setTimeout(() => {
            if (dom.fileModalOverlay) dom.fileModalOverlay.style.display = 'none';
            if (dom.fileModal) dom.fileModal.style.display = 'none';
        }, 300);
    };

    /**
     * 내 모든 파일 목록을 불러와 렌더링한다.
     */
    ctx.files.fetchMyAllFiles = async function fetchMyAllFiles() {
        if (!dom.userFilesList || !dom.aiFilesList) return;
        dom.userFilesList.innerHTML = '<li class="loading-item">로딩 중...</li>';
        dom.aiFilesList.innerHTML = '<li class="loading-item">로딩 중...</li>';

        try {
            const response = await fetch('/api/get_my_files');
            if (!response.ok) throw new Error('Failed to fetch files');
            const files = await response.json();

            dom.userFilesList.innerHTML = '';
            dom.aiFilesList.innerHTML = '';

            const userFiles = files.filter(f => f.uploaded_by !== 'ai');
            const aiFiles = files.filter(f => f.uploaded_by === 'ai');

            /**
             * 파일 항목을 렌더링한다(공용).
             * @param {object} file - 파일 메타데이터
             * @returns {HTMLLIElement}
             */
            const renderFileItem = (file) => {
                const li = document.createElement('li');
                li.className = 'file-item';
                const icon = file.is_image ? '🖼️' : '📄';
                const sourceBadge = `<span style="display:block; font-size:0.75rem; color:#9CA3AF; margin-top:2px;">🔗 ${file.session_title}</span>`;

                li.innerHTML = `
                    <div class="file-info" style="align-items: flex-start; flex-direction: column; gap: 2px;">
                        <div style="display:flex; align-items:center; gap:5px; width:100%;">
                            ${icon}
                            <span class="file-name view-file-trigger" 
                                  data-file-id="${file.id}" 
                                  data-filename="${file.filename}" 
                                  data-is-image="${file.is_image}" 
                                  title="클릭하여 내용 확인">
                                ${file.filename}
                            </span>
                        </div>
                        ${sourceBadge}
                    </div>
                    <button class="download-file-btn" data-file-id="${file.id}" title="다운로드">💾</button>
                `;
                return li;
            };

            if (userFiles.length === 0) dom.userFilesList.innerHTML = '<li class="no-files-message">저장된 파일이 없습니다.</li>';
            else userFiles.forEach(f => dom.userFilesList.appendChild(renderFileItem(f)));

            if (aiFiles.length === 0) dom.aiFilesList.innerHTML = '<li class="no-files-message">저장된 파일이 없습니다.</li>';
            else aiFiles.forEach(f => dom.aiFilesList.appendChild(renderFileItem(f)));

        } catch (error) {
            console.error("Failed to fetch all files:", error);
            dom.userFilesList.innerHTML = '<li class="error-item">목록 로드 실패</li>';
            dom.aiFilesList.innerHTML = '<li class="error-item">목록 로드 실패</li>';
        }
    };

    /**
     * 특정 세션의 파일 목록을 불러와 렌더링한다.
     * @param {string|number} sessionId - 세션 ID
     */
    ctx.files.fetchSessionFiles = async function fetchSessionFiles(sessionId) {
        if (!dom.userFilesList || !dom.aiFilesList) return;
        dom.userFilesList.innerHTML = '<li class="loading-item">로딩 중...</li>';
        dom.aiFilesList.innerHTML = '<li class="loading-item">로딩 중...</li>';

        try {
            const response = await fetch(`/api/get_session_files/${sessionId}`);
            if (!response.ok) throw new Error('Failed to fetch files');
            const files = await response.json();

            dom.userFilesList.innerHTML = '';
            dom.aiFilesList.innerHTML = '';

            const userFiles = files.filter(f => f.uploaded_by !== 'ai');
            const aiFiles = files.filter(f => f.uploaded_by === 'ai');

            /**
             * 세션용 파일 항목을 렌더링한다(출처 배지 없음).
             * @param {object} file - 파일 메타데이터
             * @returns {HTMLLIElement}
             */
            const renderFileItem = (file) => {
                const li = document.createElement('li');
                li.className = 'file-item';

                const icon = file.is_image ? '🖼️' : '📄';
                li.innerHTML = `
                    <div class="file-info">
                        ${icon}
                        <span class="file-name view-file-trigger" 
                              data-file-id="${file.id}" 
                              data-filename="${file.filename}" 
                              data-is-image="${file.is_image}" 
                              title="클릭하여 내용 확인">
                            ${file.filename}
                        </span>
                    </div>
                    <button class="download-file-btn" data-file-id="${file.id}" title="다운로드">💾</button>
                `;
                return li;
            };

            if (userFiles.length === 0) dom.userFilesList.innerHTML = '<li class="no-files-message">업로드한 파일이 없습니다.</li>';
            else userFiles.forEach(f => dom.userFilesList.appendChild(renderFileItem(f)));

            if (aiFiles.length === 0) dom.aiFilesList.innerHTML = '<li class="no-files-message">생성된 파일이 없습니다.</li>';
            else aiFiles.forEach(f => dom.aiFilesList.appendChild(renderFileItem(f)));

        } catch (error) {
            console.error("Failed to fetch session files:", error);
            dom.userFilesList.innerHTML = '<li class="error-item">파일 목록 로드 실패</li>';
            dom.aiFilesList.innerHTML = '<li class="error-item">파일 목록 로드 실패</li>';
        }
    };

    if (dom.fileModalCloseBtn && !dom.fileModalCloseBtn.dataset.boundClick) {
        dom.fileModalCloseBtn.addEventListener('click', ctx.files.closeFileModal);
        dom.fileModalCloseBtn.dataset.boundClick = 'true';
    }
    if (dom.fileModalOverlay && !dom.fileModalOverlay.dataset.boundClick) {
        dom.fileModalOverlay.addEventListener('click', ctx.files.closeFileModal);
        dom.fileModalOverlay.dataset.boundClick = 'true';
    }

    // 모달 내부 클릭 위임(다운로드/보기).
    if (dom.fileModal && !dom.fileModal.dataset.boundClick) {
        dom.fileModal.addEventListener('click', async (e) => {
            const downloadButton = e.target.closest('.download-file-btn');
            if (downloadButton) {
                if (downloadButton.dataset.downloading === 'true') return;
                downloadButton.dataset.downloading = 'true';
                const fileId = downloadButton.dataset.fileId;
                window.open(`/api/download_file/${fileId}`, '_blank');
                setTimeout(() => {
                    delete downloadButton.dataset.downloading;
                }, 1000);
                return;
            }

            const viewTrigger = e.target.closest('.view-file-trigger');
            if (viewTrigger) {
                const fileId = viewTrigger.dataset.fileId;
                const filename = viewTrigger.dataset.filename;
                const isImage = viewTrigger.dataset.isImage === 'true';

                if (isImage) {
                    alert("이미지 파일은 캔버스에서 볼 수 없습니다. 우측의 다운로드 버튼을 이용해 확인해주세요.");
                    return;
                }

                document.body.style.cursor = 'wait';
                try {
                    const response = await fetch(`/api/view_file/${fileId}`);
                    if (!response.ok) throw new Error('파일 내용을 불러올 수 없습니다.');
                    const data = await response.json();
                    if (data.error) throw new Error(data.error);

                    const extension = filename.split('.').pop();
                    ctx.canvas.openCanvas(data.content, extension);
                    ctx.files.closeFileModal();
                } catch (error) {
                    console.error("File view error:", error);
                    alert("파일 내용을 불러오는 중 오류가 발생했습니다: " + error.message);
                } finally {
                    document.body.style.cursor = 'default';
                }
            }
        });
        dom.fileModal.dataset.boundClick = 'true';
    }

    /**
     * 선택된 파일과 미리보기를 초기화한다.
     */
    ctx.files.clearAllPreviews = function clearAllPreviews() {
        state.selectedFiles = [];
        if (dom.previewContainer) dom.previewContainer.innerHTML = '';
        if (dom.fileInput) dom.fileInput.value = '';
    };

    /**
     * 선택 목록에서 파일을 제거한다.
     * @param {number} index - 선택 배열 인덱스
     */
    ctx.files.removeFileFromSelection = function removeFileFromSelection(index) {
        state.selectedFiles.splice(index, 1);
        ctx.files.renderPreviews();
    };

    /**
     * 선택 목록에 파일을 추가하고 미리보기를 갱신한다.
     * @param {FileList|File[]} newFiles - 새 파일들
     */
    ctx.files.handleFileSelect = function handleFileSelect(newFiles) {
        if (!newFiles || newFiles.length === 0) return;
        state.selectedFiles = [...state.selectedFiles, ...Array.from(newFiles)];
        ctx.files.renderPreviews();
    };

    /**
     * 선택된 파일 미리보기를 렌더링한다.
     */
    ctx.files.renderPreviews = function renderPreviews() {
        if (!dom.previewContainer) return;
        dom.previewContainer.innerHTML = '';

        state.selectedFiles.forEach((file, index) => {
            const previewWrapper = document.createElement('div');
            previewWrapper.className = 'preview-item';

            if (file.type.startsWith('image/')) {
                const img = document.createElement('img');
                img.src = URL.createObjectURL(file);
                img.className = 'preview-image';
                previewWrapper.appendChild(img);
            } else {
                const fileIcon = document.createElement('div');
                fileIcon.style.cssText = "height: 60px; width: 60px; padding: 5px; border: 2px solid #E5E7EB; border-radius: 8px; background: #F9FAFB; display: flex; flex-direction: column; justify-content: center; align-items: center; font-size: 0.7rem; color: #374151; overflow: hidden; text-align: center; line-height: 1.2;";
                fileIcon.innerHTML = `<strong>FILE</strong><span>${file.name.length > 8 ? file.name.substring(0,5)+'...' : file.name}</span>`;
                previewWrapper.appendChild(fileIcon);
            }

            const removeBtn = document.createElement('button');
            removeBtn.className = 'remove-preview-button';
            removeBtn.textContent = '×';
            removeBtn.onclick = (e) => {
                e.preventDefault();
                ctx.files.removeFileFromSelection(index);
            };
            previewWrapper.appendChild(removeBtn);
            dom.previewContainer.appendChild(previewWrapper);
        });
    };

    // 파일 선택(change) 이벤트 처리.
    if (dom.fileInput) {
        dom.fileInput.addEventListener('change', () => {
            if (dom.fileInput.files.length > 0) ctx.files.handleFileSelect(dom.fileInput.files);
        });
    }

    /**
     * 페이지 기본 드래그 동작을 차단한다.
     * @param {Event} e - 드래그 이벤트
     */
    function preventDefaults(e) { e.preventDefault(); e.stopPropagation(); }
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dom.htmlTag.addEventListener(eventName, preventDefaults, false);
    });

    /**
     * 드래그 오버레이를 표시한다.
     */
    function showOverlay() { if (dom.dragOverlay) dom.dragOverlay.classList.add('visible'); }
    /**
     * 드래그 오버레이를 숨긴다.
     */
    function hideOverlay() { if (dom.dragOverlay) dom.dragOverlay.classList.remove('visible'); }

    // 중첩 dragenter/dragleave 카운트로 깜빡임 방지.
    let dragCounter = 0;
    dom.htmlTag.addEventListener('dragenter', (e) => {
        dragCounter++;
        if (e.dataTransfer.items && e.dataTransfer.items.length > 0) {
            showOverlay();
        }
    });
    dom.htmlTag.addEventListener('dragleave', () => {
        dragCounter--;
        if (dragCounter === 0) {
            hideOverlay();
        }
    });
    dom.htmlTag.addEventListener('drop', (e) => {
        dragCounter = 0;
        hideOverlay();
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files.length > 0) {
            ctx.files.handleFileSelect(files);
        }
    });
});
