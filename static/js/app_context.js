// 공용 컨텍스트 생성기.
// DOM 참조를 모으고 초기 상태를 만들며
// 모듈 네임스페이스(ui, files, sessions 등)를 노출한다.
window.App = window.App || {};

/**
 * 모든 모듈이 공유할 컨텍스트를 생성해 반환한다.
 * @returns {object} 모듈 공용 컨텍스트
 */
window.App.createContext = function createContext() {
    // <html data-*> 속성에서 사용자/관리자 정보를 읽는다.
    const htmlTag = document.documentElement;
    const isAdmin = htmlTag.dataset.isAdmin ? htmlTag.dataset.isAdmin.toLowerCase() === 'true' : false;
    const currentUsername = htmlTag.dataset.username || "Guest";
    const currentUserRole = htmlTag.dataset.userRole || "user";

    // 자주 쓰는 DOM 요소를 한 곳에 캐시한다.
    const dom = {
        htmlTag,
        sidebar: document.getElementById('sidebar'),
        menuToggleButtons: document.querySelectorAll('.menu-toggle-button'),
        sidebarCloseBtn: document.getElementById('sidebar-close-btn'),
        newChatButton: document.querySelector('.new-chat-button'),
        searchInput: document.getElementById('search-input'),
        historyListContainer: document.getElementById('chat-history-list'),
        historyTitle: document.getElementById('history-title'),
        myChatFilterBtn: document.getElementById('my-chat-filter-btn'),
        openCurrentFilesBtn: document.getElementById('open-current-files-btn'),
        chatContainer: document.querySelector('.chat-container'),
        mainContent: document.getElementById('main-content'),
        chatWindow: document.getElementById('chat-window'),
        chatForm: document.getElementById('chat-form'),
        userInput: document.getElementById('user-input'),
        voiceInputBtn: document.getElementById('voice-input-btn'),
        modelSelector: document.getElementById('model-selector'),
        providerDropdown: document.querySelector('.provider-dropdown'),
        currentProviderBtn: document.getElementById('current-provider-btn'),
        currentProviderIcon: document.getElementById('current-provider-icon'),
        providerMenu: document.getElementById('provider-menu'),
        providerOptions: document.querySelectorAll('.provider-option'),
        dragOverlay: document.getElementById('drag-overlay'),
        previewContainer: document.getElementById('image-preview-container'),
        fileInput: document.getElementById('file-upload'),
        fileUploadLabel: document.querySelector('.file-upload-button'),
        statusButton: document.getElementById('status-button'),
        expandInputBtn: document.getElementById('expand-input-btn'),
        codeCanvas: document.getElementById('code-canvas'),
        canvasCloseBtn: document.getElementById('canvas-close-btn'),
        canvasCopyBtn: document.getElementById('canvas-copy-btn'),
        canvasCodeBlock: document.getElementById('canvas-code-block'),
        canvasFilename: document.getElementById('canvas-filename'),
        canvasResizer: document.getElementById('canvas-resizer'),
        sidebarResizer: document.getElementById('sidebar-resizer'),
        mobileOverlay: document.getElementById('mobile-overlay'),
        adminPanelButton: document.getElementById('admin-panel-button'),
        adminModalOverlay: document.getElementById('admin-modal-overlay'),
        adminModal: document.getElementById('admin-modal'),
        adminModalCloseButton: document.getElementById('admin-modal-close-button'),
        navUserList: document.getElementById('nav-user-list'),
        navModelConfig: document.getElementById('nav-model-config'),
        adminNav: document.querySelector('.admin-nav'),
        adminUserListView: document.getElementById('admin-user-list-view'),
        adminModelConfigView: document.getElementById('admin-model-config-view'),
        adminUserHistoryView: document.getElementById('admin-user-history-view'),
        adminUserListBody: document.getElementById('admin-user-list-body'),
        adminModelConfigBody: document.getElementById('admin-model-config-body'),
        adminUserHistoryBody: document.getElementById('admin-user-history-body'),
        adminProviderStatusBody: document.getElementById('admin-provider-status-body'),
        adminHistoryUsername: document.getElementById('admin-history-username'),
        adminBackToListBtn: document.getElementById('admin-back-to-list-btn')
    };

    // 파일 입력: 여러 타입과 다중 선택 허용.
    if (dom.fileInput) {
        dom.fileInput.setAttribute('accept', 'image/*,audio/*,video/*,.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.hwp,.txt,.py,.md,.csv,.json,.js,.html,.css,.c,.cpp,.java');
        dom.fileInput.setAttribute('multiple', 'multiple');
    }
    // 툴팁으로 안내 문구 제공.
    if (dom.fileUploadLabel) {
        dom.fileUploadLabel.setAttribute('title', '이미지(Ctrl+V 가능), 문서, 코드 등 여러 파일을 드래그하거나 선택하세요.');
    }

    // 상태 버튼 내부 텍스트 요소 캐시.
    if (dom.statusButton) {
        dom.statusText = dom.statusButton.querySelector('.status-text');
    } else {
        dom.statusText = null;
    }

    // 대화 기록 컨텍스트 메뉴(이름 변경/삭제).
    const contextMenu = document.createElement('div');
    contextMenu.className = 'history-context-menu';
    contextMenu.innerHTML = `
        <button class="ctx-edit-btn">✏️ 이름 변경</button>
        <button class="ctx-delete-btn delete-btn">🗑️ 삭제</button>
    `;
    document.body.appendChild(contextMenu);

    // 파일 목록 모달(오버레이 + 컨테이너).
    const fileModalOverlay = document.createElement('div');
    fileModalOverlay.className = 'modal-overlay';
    fileModalOverlay.id = 'file-modal-overlay';
    fileModalOverlay.style.zIndex = '2000';
    document.body.appendChild(fileModalOverlay);

    const fileModal = document.createElement('div');
    fileModal.className = 'file-modal';
    fileModal.id = 'file-modal';
    fileModal.innerHTML = `
        <div class="file-modal-header">
            <h3 class="file-modal-title">📁 첨부 파일 목록</h3>
            <button class="file-modal-close">×</button>
        </div>
        <div class="file-modal-body">
            <div class="file-section">
                <h4 class="file-section-title">📤 내가 올린 파일</h4>
                <ul id="user-files-list" class="file-list"></ul>
            </div>
            <div class="file-section">
                <h4 class="file-section-title">🤖 AI가 생성한 파일</h4>
                <ul id="ai-files-list" class="file-list"></ul>
            </div>
        </div>
    `;
    document.body.appendChild(fileModal);

    // 동적으로 생성한 요소를 dom 캐시에 붙인다.
    dom.contextMenu = contextMenu;
    dom.fileModalOverlay = fileModalOverlay;
    dom.fileModal = fileModal;
    dom.userFilesList = document.getElementById('user-files-list');
    dom.aiFilesList = document.getElementById('ai-files-list');
    dom.fileModalCloseBtn = fileModal.querySelector('.file-modal-close');

    // 공용 컨텍스트 반환: DOM 캐시 + 상태 + 모듈 API 네임스페이스.
    return {
        dom,
        state: {
            isAdmin,
            currentUsername,
            currentUserRole,
            currentProvider: 'anthropic',
            providerStatuses: { google: 'active', anthropic: 'active', openai: 'active' },
            personaProviderRestrictions: { google: false, anthropic: false, openai: false },
            currentSessionId: null,
            selectedFiles: [],
            isMyChatFilterActive: false,
            activeSessionId: null,
            activeSessionTitle: null
        },
        ui: {},
        canvas: {},
        provider: {},
        messages: {},
        files: {},
        sessions: {},
        chat: {},
        sidebar: {},
        admin: {}
    };
};
