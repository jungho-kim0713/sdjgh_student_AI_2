// 사이드바 모듈: 토글/접기 및 리사이저.
window.App.registerModule((ctx) => {
    const { dom } = ctx;

    /**
     * 화면 크기에 따라 사이드바를 토글한다.
     */
    ctx.sidebar.toggleSidebar = function toggleSidebar() {
        const isMobile = window.innerWidth <= 768;
        if (isMobile) {
            if (dom.sidebar) dom.sidebar.classList.toggle('active');
            if (dom.mobileOverlay) dom.mobileOverlay.classList.toggle('active');
        } else {
            if (dom.sidebar) dom.sidebar.classList.toggle('collapsed');
        }
    };

    /**
     * 모바일에서 사이드바를 강제로 닫는다.
     */
    ctx.sidebar.closeSidebarMobile = function closeSidebarMobile() {
        if (window.innerWidth <= 768) {
            if (dom.sidebar) dom.sidebar.classList.remove('active');
            if (dom.mobileOverlay) dom.mobileOverlay.classList.remove('active');
        }
    };

    if (dom.sidebarCloseBtn) {
        dom.sidebarCloseBtn.addEventListener('click', () => {
            ctx.sidebar.closeSidebarMobile();
        });
    }

    // 메뉴 토글 버튼(데스크톱/모바일).
    dom.menuToggleButtons.forEach(btn => btn.addEventListener('click', (e) => {
        e.stopPropagation();
        ctx.sidebar.toggleSidebar();
    }));
    // 오버레이/메인 콘텐츠 클릭 시 모바일 사이드바 닫기.
    if (dom.mobileOverlay) {
        dom.mobileOverlay.addEventListener('click', ctx.sidebar.closeSidebarMobile);
    }
    if (dom.mainContent) {
        dom.mainContent.addEventListener('click', ctx.sidebar.closeSidebarMobile);
    }
    // 데스크톱 전환 시 모바일 오버레이 초기화.
    window.addEventListener('resize', () => {
        const isMobile = window.innerWidth <= 768;
        if (!isMobile) {
            if (dom.sidebar) dom.sidebar.classList.remove('active');
            if (dom.mobileOverlay) dom.mobileOverlay.classList.remove('active');
        }
    });
    // 최초 로드 시 초기 상태 설정.
    if (window.innerWidth > 768) {
        if (dom.sidebar) dom.sidebar.classList.remove('collapsed');
    } else {
        if (dom.sidebar) {
            dom.sidebar.classList.remove('active');
            dom.sidebar.classList.add('collapsed');
        }
    }

    // 사이드바 너비 드래그 리사이즈.
    let isResizingSidebar = false;
    if (dom.sidebarResizer) {
        dom.sidebarResizer.addEventListener('mousedown', () => {
            isResizingSidebar = true;
            dom.sidebarResizer.classList.add('resizing');
            document.body.style.cursor = 'col-resize';
            document.body.style.userSelect = 'none';
        });

        document.addEventListener('mousemove', (e) => {
            if (!isResizingSidebar) return;
            const newWidth = e.clientX;
            if (newWidth > 200 && newWidth < 600) {
                if (dom.sidebar) dom.sidebar.style.width = `${newWidth}px`;
            }
        });

        document.addEventListener('mouseup', () => {
            if (isResizingSidebar) {
                isResizingSidebar = false;
                dom.sidebarResizer.classList.remove('resizing');
                document.body.style.cursor = '';
                document.body.style.userSelect = '';
            }
        });
    }
});
