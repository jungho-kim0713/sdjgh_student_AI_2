// 코드 캔버스 모듈: 생성된 코드를 사이드 패널에 표시한다.
window.App.registerModule((ctx) => {
    const { dom } = ctx;

    /**
     * 캔버스를 열고 코드/파일명을 표시한다.
     * @param {string} code - 표시할 코드
     * @param {string} rawLang - 언어 힌트(확장자 추정용)
     */
    ctx.canvas.openCanvas = function openCanvas(code, rawLang) {
        const lang = rawLang ? rawLang.toLowerCase() : 'text';
        let filename = "AI Generated Code";

        if (lang.includes('html')) filename = "index.html";
        else if (lang.includes('css')) filename = "style.css";
        else if (lang.includes('js') || lang.includes('javascript')) filename = "script.js";
        else if (lang.includes('py') || lang.includes('python')) filename = "app.py";
        else if (lang.includes('c')) filename = "main.c";
        else if (lang.includes('java')) filename = "Main.java";
        else if (lang.includes('md') || lang.includes('markdown')) filename = "README.md";
        else if (lang.includes('json')) filename = "data.json";

        // 캔버스 DOM이 없으면 중단.
        if (!dom.canvasCodeBlock || !dom.canvasFilename || !dom.codeCanvas) return;

        dom.canvasCodeBlock.textContent = code;
        dom.canvasFilename.textContent = filename;

        dom.canvasCodeBlock.className = '';
        dom.canvasCodeBlock.removeAttribute('data-highlighted');
        dom.canvasCodeBlock.classList.add(`language-${lang}`);

        // highlight.js가 있으면 구문 강조 적용.
        if (window.hljs) {
            window.hljs.highlightElement(dom.canvasCodeBlock);
        }

        dom.codeCanvas.classList.add('open');
        // 모바일에서는 사이드바를 닫아 캔버스가 보이게 한다.
        if (ctx.sidebar.closeSidebarMobile) ctx.sidebar.closeSidebarMobile();
    };

    /**
     * 캔버스를 닫고 크기 설정을 초기화한다.
     */
    ctx.canvas.closeCanvas = function closeCanvas() {
        if (dom.codeCanvas) {
            dom.codeCanvas.classList.remove('open');
            dom.codeCanvas.style.width = '';
        }
    };

    if (dom.canvasCloseBtn) {
        dom.canvasCloseBtn.addEventListener('click', ctx.canvas.closeCanvas);
    }

    // 복사 버튼: Clipboard API 우선, 실패 시 fallback 사용.
    if (dom.canvasCopyBtn) {
        dom.canvasCopyBtn.addEventListener('click', () => {
            const code = dom.canvasCodeBlock ? dom.canvasCodeBlock.textContent : '';
            if (navigator.clipboard && window.isSecureContext) {
                navigator.clipboard.writeText(code).then(() => {
                    alert("코드가 클립보드에 복사되었습니다!");
                }).catch(() => {
                    ctx.ui.fallbackCopyTextToClipboard(code);
                });
            } else {
                ctx.ui.fallbackCopyTextToClipboard(code);
            }
        });
    }

    // 캔버스 너비 드래그 리사이즈 로직.
    let isResizing = false;
    if (dom.canvasResizer) {
        dom.canvasResizer.addEventListener('mousedown', () => {
            isResizing = true;
            dom.canvasResizer.classList.add('resizing');
            document.body.style.cursor = 'ew-resize';
            document.body.style.userSelect = 'none';
        });

        document.addEventListener('mousemove', (e) => {
            if (!isResizing || !dom.codeCanvas) return;
            const newWidth = window.innerWidth - e.clientX;
            if (newWidth > 200 && newWidth < window.innerWidth * 0.8) {
                dom.codeCanvas.style.width = `${newWidth}px`;
            }
        });

        document.addEventListener('mouseup', () => {
            if (isResizing) {
                isResizing = false;
                dom.canvasResizer.classList.remove('resizing');
                document.body.style.cursor = '';
                document.body.style.userSelect = '';
            }
        });
    }
});
