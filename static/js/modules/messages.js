// 메시지 렌더링 및 코드 추출 로직.
window.App.registerModule((ctx) => {
    const { dom } = ctx;

    /**
     * 마크다운 코드 블록을 미리보기 블록으로 변환한다.
     * @param {string} html - 마크다운 변환 결과 HTML
     * @returns {string} 변환된 HTML
     */
    ctx.messages.processCodeBlocksInHtml = function processCodeBlocksInHtml(html) {
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = html;
        const preTags = tempDiv.querySelectorAll('pre');

        preTags.forEach(pre => {
            const codeTag = pre.querySelector('code');
            if (!codeTag) return;
            const className = codeTag.className || '';
            const langMatch = className.match(/language-(\w+)/);
            const lang = langMatch ? langMatch[1] : 'text';
            const codeContent = codeTag.textContent;

            const previewBlock = document.createElement('div');
            previewBlock.className = 'code-preview-block';

            const header = document.createElement('div');
            header.className = 'code-preview-header';
            header.innerHTML = `
                <span>${lang}</span>
                <button class="open-canvas-btn" data-code="${encodeURIComponent(codeContent)}" data-lang="${lang}">Canvas에서 보기</button>
            `;

            const content = document.createElement('div');
            content.className = 'code-preview-content';
            content.textContent = codeContent;

            previewBlock.appendChild(header);
            previewBlock.appendChild(content);

            pre.replaceWith(previewBlock);
        });

        return tempDiv.innerHTML;
    };

    /**
     * 채팅 메시지 버블을 렌더링한다.
     * 텍스트/이미지/복사 버튼을 지원한다.
     * @param {string} text - 메시지 텍스트
     * @param {string} sender - 'user' 또는 'ai'
     * @param {File|null} imageFile - 업로드 이미지 파일
     * @param {string} username - 표시할 사용자명
     * @param {string|null} imagePath - 서버 이미지 경로
     * @returns {HTMLElement|null} 생성된 메시지 래퍼
     */
    ctx.messages.addMessage = function addMessage(text, sender, imageFile, username, imagePath) {
        if (!dom.chatWindow) return null;
        const messageWrapper = document.createElement('div');
        messageWrapper.className = `message-wrapper ${sender}`;
        const messageBubble = document.createElement('div');
        messageBubble.className = `${sender}-message`;

        const senderName = (sender === 'ai') ? (username || "AI 도우미") : (username || "User");

        if (sender === 'ai') {
            messageBubble.innerHTML = `<p class="message-sender">${senderName}</p>`;
        }

        if (imageFile) {
            const imgPreview = document.createElement('img');
            imgPreview.src = URL.createObjectURL(imageFile);
            imgPreview.className = "message-image";
            messageBubble.appendChild(imgPreview);
        }
        if (imagePath) {
            const imgPreview = document.createElement('img');
            imgPreview.src = imagePath;
            imgPreview.className = "message-image";
            messageBubble.appendChild(imgPreview);
        }

        if (text) {
            let contentHtml = '';
            const originalText = text;

            if (sender === 'ai') {
                const rawHtml = window.marked.parse(text);
                contentHtml = ctx.messages.processCodeBlocksInHtml(rawHtml);
            } else {
                contentHtml = `<p>${text.replace(/\n/g, '<br>')}</p>`;
            }

            const textDiv = document.createElement('div');
            textDiv.className = 'message-content';
            textDiv.innerHTML = contentHtml;
            messageBubble.appendChild(textDiv);

            // 원본 텍스트를 복사하는 버튼.
            const copyBtn = document.createElement('button');
            copyBtn.className = 'copy-msg-btn';
            copyBtn.title = '텍스트 복사';
            copyBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>`;

            copyBtn.addEventListener('click', (e) => {
                e.stopPropagation();

                const textToCopy = originalText;

                if (navigator.clipboard && window.isSecureContext) {
                    navigator.clipboard.writeText(textToCopy).then(onCopySuccess).catch(() => fallbackCopy(textToCopy));
                } else {
                    fallbackCopy(textToCopy);
                }

                // 성공 표시 아이콘을 잠깐 보여준다.
                function onCopySuccess() {
                    copyBtn.classList.add('copied');
                    copyBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>`;

                    setTimeout(() => {
                        copyBtn.classList.remove('copied');
                        copyBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>`;
                    }, 2000);
                }

                // 숨은 textarea로 복사하는 fallback.
                function fallbackCopy(txt) {
                    const ta = document.createElement("textarea");
                    ta.value = txt;
                    ta.style.position = "fixed";
                    ta.style.left = "-9999px";
                    document.body.appendChild(ta);
                    ta.focus();
                    ta.select();
                    try {
                        document.execCommand('copy');
                        onCopySuccess();
                    } catch (err) {
                        alert("복사에 실패했습니다.");
                    }
                    document.body.removeChild(ta);
                }
            });

            messageBubble.prepend(copyBtn);
        }

        messageWrapper.appendChild(messageBubble);
        dom.chatWindow.appendChild(messageWrapper);
        dom.chatWindow.scrollTop = dom.chatWindow.scrollHeight;

        return messageWrapper;
    };

    /**
     * 언어 ID를 파일 확장자로 매핑한다.
     * @param {string} language - 언어 ID
     * @returns {string} 확장자
     */
    ctx.messages.getFileExtension = function getFileExtension(language) {
        const map = {
            'python': '.py', 'javascript': '.js', 'js': '.js', 'html': '.html',
            'css': '.css', 'c': '.c', 'cpp': '.cpp', 'java': '.java',
            'json': '.json', 'markdown': '.md', 'md': '.md', 'txt': '.txt'
        };
        return map[language] || '.txt';
    };

    /**
     * 코드 블록을 추출해 서버에 파일로 저장한다.
     * @param {string} aiResponse - AI 응답 텍스트
     * @param {string|number} sessionId - 세션 ID
     */
    ctx.messages.extractCodeAndSaveFile = async function extractCodeAndSaveFile(aiResponse, sessionId) {
        const codeBlockRegex = /```(\w+)?\s*([\s\S]*?)```/g;
        let match;
        let fileIndex = 1;

        while ((match = codeBlockRegex.exec(aiResponse)) !== null) {
            const language = match[1] || 'txt';
            const codeContent = match[2].trim();
            if (!codeContent) continue;

            const extension = ctx.messages.getFileExtension(language.toLowerCase());
            const suggestedFilename = `ai_code_${sessionId}_${fileIndex}${extension}`;
            fileIndex++;

            try {
                await fetch('/api/save_ai_file', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        session_id: sessionId,
                        content: codeContent,
                        filename: suggestedFilename
                    })
                });
            } catch (error) {
                console.error("Error saving AI file:", error);
            }
        }
    };

    // 미리보기 블록의 "캔버스 열기" 클릭 위임 처리.
    if (dom.chatWindow) {
        dom.chatWindow.addEventListener('click', (e) => {
            if (e.target.classList.contains('open-canvas-btn')) {
                const code = decodeURIComponent(e.target.dataset.code);
                const lang = e.target.dataset.lang;
                ctx.canvas.openCanvas(code, lang);
            }
        });
    }
});
