// UI 유틸 모듈(주로 DOM 업데이트만 수행).
window.App.registerModule((ctx) => {
    /**
     * textarea 높이를 내용에 맞게 자동 조절한다.
     * @param {HTMLTextAreaElement} el - 대상 textarea
     */
    ctx.ui.adjustTextareaHeight = function adjustTextareaHeight(el) {
        if (!el) return;
        el.style.height = 'auto';
        el.style.height = `${el.scrollHeight}px`;
    };

    /**
     * Clipboard API가 없을 때 숨은 textarea로 복사한다.
     * @param {string} text - 복사할 텍스트
     */
    ctx.ui.fallbackCopyTextToClipboard = function fallbackCopyTextToClipboard(text) {
        const textArea = document.createElement("textarea");
        textArea.value = text;
        textArea.style.position = "fixed";
        textArea.style.left = "-9999px";
        textArea.style.top = "0";
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        try {
            const successful = document.execCommand('copy');
            if (successful) alert("코드가 클립보드에 복사되었습니다!");
            else alert("복사에 실패했습니다. 직접 드래그해서 복사해주세요.");
        } catch (err) {
            alert("이 브라우저는 복사 기능을 지원하지 않습니다.");
        }
        document.body.removeChild(textArea);
    };

    /**
     * 이미지 라이트박스를 열어 원본 크기로 표시한다.
     * @param {string} src - 이미지 URL
     */
    ctx.ui.openImageLightbox = function openImageLightbox(src) {
        const lightbox = document.getElementById('image-lightbox');
        const img = document.getElementById('lightbox-img');
        if (!lightbox || !img) return;
        img.src = src;
        lightbox.style.display = 'flex';
        document.body.style.overflow = 'hidden';
    };

    // 라이트박스 닫기: 오버레이 클릭 또는 × 버튼
    document.addEventListener('click', (e) => {
        const lightbox = document.getElementById('image-lightbox');
        if (!lightbox) return;
        if (e.target === lightbox || e.target.id === 'lightbox-close-btn') {
            lightbox.style.display = 'none';
            document.body.style.overflow = '';
        }
    });

    // ESC 키로 라이트박스 닫기
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            const lightbox = document.getElementById('image-lightbox');
            if (lightbox && lightbox.style.display !== 'none') {
                lightbox.style.display = 'none';
                document.body.style.overflow = '';
            }
        }
    });
});
