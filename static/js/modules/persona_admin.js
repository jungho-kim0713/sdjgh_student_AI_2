/**
 * 관리자 페르소나 관리 JavaScript
 *
 * 페르소나 목록 조회, 생성, 수정, 삭제 및 교사 권한 관리
 */

let personas = [];
let selectedPersonaId = null;
let allTeachers = [];
let currentPrompts = {}; // provider별 프롬프트 캐시
let pollingInterval = null; // 문서 상태 polling용 interval

// 페이지 로드 시 초기화
document.addEventListener('DOMContentLoaded', async () => {
    await populateModelDropdowns(); // 모델 드롭다운 먼저 초기화
    await loadPersonas();
    await loadTeachers();
});

/**
 * 페르소나 목록 로드
 */
async function loadPersonas() {
    try {
        const response = await fetch('/api/admin/persona/list');
        const data = await response.json();

        if (data.personas) {
            personas = data.personas;
            renderPersonaList();
        } else {
            alert('페르소나 목록을 불러오는데 실패했습니다.');
        }
    } catch (error) {
        console.error('페르소나 목록 로드 실패:', error);
        alert('페르소나 목록을 불러오는데 실패했습니다.');
    }
}

/**
 * 교사 목록 로드
 */
async function loadTeachers() {
    try {
        const response = await fetch('/api/admin/get_users');
        const users = await response.json();
        allTeachers = users.filter(u => u.role === 'teacher');
    } catch (error) {
        console.error('교사 목록 로드 실패:', error);
    }
}

/**
 * 모델 드롭다운을 동적으로 채우기
 * 관리자 패널에서 활성화된 모델만 표시
 */
async function populateModelDropdowns() {
    try {
        // 활성화된 모델 리스트 조회
        const response = await fetch('/api/admin/enabled_models');
        const enabledModels = await response.json();

        // OpenAI 드롭다운
        const openaiSelect = document.getElementById('modelOpenai');
        if (openaiSelect && enabledModels.openai && enabledModels.openai.length > 0) {
            openaiSelect.innerHTML = '';
            enabledModels.openai.forEach(modelId => {
                const option = document.createElement('option');
                option.value = modelId;
                option.textContent = modelId;
                openaiSelect.appendChild(option);
            });
        }

        // Anthropic 드롭다운
        const anthropicSelect = document.getElementById('modelAnthropic');
        if (anthropicSelect && enabledModels.anthropic && enabledModels.anthropic.length > 0) {
            anthropicSelect.innerHTML = '';
            enabledModels.anthropic.forEach(modelId => {
                const option = document.createElement('option');
                option.value = modelId;
                option.textContent = modelId;
                anthropicSelect.appendChild(option);
            });
        }

        // Google 드롭다운
        const googleSelect = document.getElementById('modelGoogle');
        if (googleSelect && enabledModels.google && enabledModels.google.length > 0) {
            googleSelect.innerHTML = '';
            enabledModels.google.forEach(modelId => {
                const option = document.createElement('option');
                option.value = modelId;
                option.textContent = modelId;
                googleSelect.appendChild(option);
            });
        }

        console.log('✅ 모델 드롭다운 초기화 완료:', enabledModels);

    } catch (error) {
        console.error('모델 드롭다운 초기화 실패:', error);
        // 에러 발생 시 기본값 설정
        setDefaultModelDropdowns();
    }
}

/**
 * 에러 발생 시 기본 모델 드롭다운 설정
 */
function setDefaultModelDropdowns() {
    console.warn('⚠️ 기본 모델 드롭다운 사용');

    const defaultModels = {
        openai: ['gpt-4o-mini', 'gpt-4o'],
        anthropic: ['claude-haiku-4-5-20251001', 'claude-sonnet-4-5-20250929'],
        google: ['gemini-2.0-flash', 'gemini-1.5-pro']
    };

    // OpenAI
    const openaiSelect = document.getElementById('modelOpenai');
    if (openaiSelect) {
        openaiSelect.innerHTML = '';
        defaultModels.openai.forEach(modelId => {
            const option = document.createElement('option');
            option.value = modelId;
            option.textContent = modelId;
            openaiSelect.appendChild(option);
        });
    }

    // Anthropic
    const anthropicSelect = document.getElementById('modelAnthropic');
    if (anthropicSelect) {
        anthropicSelect.innerHTML = '';
        defaultModels.anthropic.forEach(modelId => {
            const option = document.createElement('option');
            option.value = modelId;
            option.textContent = modelId;
            anthropicSelect.appendChild(option);
        });
    }

    // Google
    const googleSelect = document.getElementById('modelGoogle');
    if (googleSelect) {
        googleSelect.innerHTML = '';
        defaultModels.google.forEach(modelId => {
            const option = document.createElement('option');
            option.value = modelId;
            option.textContent = modelId;
            googleSelect.appendChild(option);
        });
    }
}

/**
 * 페르소나 목록 렌더링
 */
function renderPersonaList() {
    const listElement = document.getElementById('personaList');

    if (personas.length === 0) {
        listElement.innerHTML = '<p style="color: #999; text-align: center;">페르소나가 없습니다</p>';
        return;
    }

    listElement.innerHTML = personas.map(p => `
        <div class="persona-item ${selectedPersonaId === p.id ? 'active' : ''}"
             onclick="selectPersona(${p.id})">
            <div>
                <span class="icon">${p.icon || '🤖'}</span>
                <span class="name">${p.role_name}</span>
                ${p.use_rag ? '<span class="badge">RAG</span>' : ''}
            </div>
            <div class="key">${p.role_key}</div>
        </div>
    `).join('');
}

/**
 * 페르소나 선택
 */
async function selectPersona(personaId) {
    selectedPersonaId = personaId;
    renderPersonaList();

    try {
        const response = await fetch(`/api/admin/persona/${personaId}`);
        const data = await response.json();

        if (data.id) {
            await loadPersonaDetails(data);
        } else {
            alert('페르소나 정보를 불러오는데 실패했습니다.');
        }
    } catch (error) {
        console.error('페르소나 상세 정보 로드 실패:', error);
        alert('페르소나 정보를 불러오는데 실패했습니다.');
    }
}

/**
 * 페르소나 상세 정보 폼에 로드
 */
async function loadPersonaDetails(persona) {
    // 빈 상태 숨기기, 폼 표시
    document.querySelector('.empty-state').style.display = 'none';
    document.getElementById('personaDetailForm').style.display = 'block';

    // 모델 드롭다운이 비어있으면 다시 로드
    const openaiSelect = document.getElementById('modelOpenai');
    if (!openaiSelect || openaiSelect.options.length === 0) {
        await populateModelDropdowns();
    }

    // 기본 정보
    document.getElementById('roleKey').value = persona.role_key || '';
    document.getElementById('roleKey').disabled = persona.is_system; // 시스템 페르소나는 수정 불가
    document.getElementById('roleName').value = persona.role_name || '';
    document.getElementById('icon').value = persona.icon || '🤖';
    document.getElementById('description').value = persona.description || '';

    // AI 모델 설정 (드롭다운이 준비된 후 값 설정)
    document.getElementById('modelOpenai').value = persona.model_openai || 'gpt-4o-mini';
    document.getElementById('modelAnthropic').value = persona.model_anthropic || 'claude-haiku-4-5-20251001';
    document.getElementById('modelGoogle').value = persona.model_google || 'gemini-2.0-flash';
    document.getElementById('maxTokens').value = persona.max_tokens || 4096;

    // RAG 설정
    document.getElementById('useRag').checked = persona.use_rag || false;
    document.getElementById('chunkStrategy').value = persona.chunk_strategy || 'paragraph';
    document.getElementById('chunkSize').value = persona.chunk_size || 500;
    document.getElementById('chunkOverlap').value = persona.chunk_overlap || 100;
    document.getElementById('retrievalStrategy').value = persona.retrieval_strategy || 'soft_topk';
    document.getElementById('ragTopK').value = persona.rag_top_k || 3;
    document.getElementById('ragMaxK').value = persona.rag_max_k || 7;
    document.getElementById('ragSimilarityThreshold').value = persona.rag_similarity_threshold || 0.5;
    document.getElementById('ragGapThreshold').value = persona.rag_gap_threshold || 0.1;

    // RAG 설정 표시/숨김
    toggleRagSettings();
    toggleRagStrategySettings();

    // 권한 설정
    document.getElementById('allowUser').checked = persona.allow_user !== false;
    document.getElementById('allowTeacher').checked = persona.allow_teacher !== false;
    document.getElementById('restrictGoogle').checked = persona.restrict_google || false;
    document.getElementById('restrictAnthropic').checked = persona.restrict_anthropic || false;
    document.getElementById('restrictOpenai').checked = persona.restrict_openai || false;

    // 교사 목록 로드
    loadPersonaTeachers(persona.id);

    // 시스템 프롬프트 로드
    loadAllPrompts(persona.id);

    // 지식 베이스 표시/숨김 및 데이터 로드
    const knowledgeBaseSection = document.getElementById('knowledgeBaseSection');
    if (persona.use_rag) {
        knowledgeBaseSection.style.display = 'block';
        loadKnowledgeDocuments();
        loadKnowledgeStats();
    } else {
        knowledgeBaseSection.style.display = 'none';
    }
}

/**
 * 페르소나에 할당된 교사 목록 로드
 */
async function loadPersonaTeachers(personaId) {
    try {
        const response = await fetch(`/api/admin/persona/${personaId}/teachers`);
        const data = await response.json();

        const teacherListElement = document.getElementById('teacherList');

        if (data.teachers && data.teachers.length > 0) {
            teacherListElement.innerHTML = data.teachers.map(t => `
                <div class="teacher-item">
                    <div>
                        <strong>${t.username}</strong>
                        ${t.email ? `<br><small>${t.email}</small>` : ''}
                    </div>
                    <button onclick="removeTeacher(${t.id})" class="btn-small">제거</button>
                </div>
            `).join('');
        } else {
            teacherListElement.innerHTML = '<p style="color: #999; text-align: center;">할당된 교사가 없습니다</p>';
        }
    } catch (error) {
        console.error('교사 목록 로드 실패:', error);
    }
}

/**
 * RAG 활성화 체크박스 변경 시
 */
document.addEventListener('DOMContentLoaded', () => {
    const useRagCheckbox = document.getElementById('useRag');
    if (useRagCheckbox) {
        useRagCheckbox.addEventListener('change', toggleRagSettings);
    }
});

function toggleRagSettings() {
    const useRag = document.getElementById('useRag').checked;
    document.getElementById('ragSettings').style.display = useRag ? 'block' : 'none';
}

/**
 * RAG 검색 전략 변경 시
 */
function toggleRagStrategySettings() {
    const strategy = document.getElementById('retrievalStrategy').value;

    if (strategy === 'soft_topk') {
        document.getElementById('softTopkSettings').style.display = 'block';
        document.getElementById('gapBasedSettings').style.display = 'none';
    } else if (strategy === 'gap_based') {
        document.getElementById('softTopkSettings').style.display = 'none';
        document.getElementById('gapBasedSettings').style.display = 'block';
    }
}

/**
 * RAG 고급 설정 토글
 */
function toggleAdvancedRagSettings() {
    const advancedSettings = document.getElementById('advancedRagSettings');
    const toggleBtn = document.getElementById('advancedRagToggle');

    if (advancedSettings.style.display === 'none') {
        advancedSettings.style.display = 'block';
        toggleBtn.innerHTML = '🔧 고급 설정 숨기기 ▲';
        toggleBtn.style.background = '#5a6268';
    } else {
        advancedSettings.style.display = 'none';
        toggleBtn.innerHTML = '🔧 고급 설정 표시 ▼';
        toggleBtn.style.background = '#6c757d';
    }
}

/**
 * 새 페르소나 생성
 */
function createNewPersona() {
    selectedPersonaId = null;
    renderPersonaList();

    // 폼 초기화
    document.querySelector('.empty-state').style.display = 'none';
    document.getElementById('personaDetailForm').style.display = 'block';

    document.getElementById('roleKey').value = '';
    document.getElementById('roleKey').disabled = false;
    document.getElementById('roleName').value = '';
    document.getElementById('icon').value = '🤖';
    document.getElementById('description').value = '';

    document.getElementById('modelOpenai').value = 'gpt-4o-mini';
    document.getElementById('modelAnthropic').value = 'claude-haiku-4-5-20251001';
    document.getElementById('modelGoogle').value = 'gemini-2.0-flash';
    document.getElementById('maxTokens').value = '4096';

    document.getElementById('useRag').checked = false;
    document.getElementById('retrievalStrategy').value = 'soft_topk';
    document.getElementById('ragTopK').value = '3';
    document.getElementById('ragMaxK').value = '7';
    document.getElementById('ragSimilarityThreshold').value = '0.5';
    document.getElementById('ragGapThreshold').value = '0.1';

    toggleRagSettings();
    toggleRagStrategySettings();

    document.getElementById('allowUser').checked = true;
    document.getElementById('allowTeacher').checked = true;
    document.getElementById('restrictGoogle').checked = false;
    document.getElementById('restrictAnthropic').checked = false;
    document.getElementById('restrictOpenai').checked = false;

    document.getElementById('teacherList').innerHTML = '<p style="color: #999; text-align: center;">새 페르소나를 저장한 후 교사를 추가할 수 있습니다</p>';
}

/**
 * 페르소나 저장 (생성 또는 수정)
 */
async function savePersona() {
    const roleKey = document.getElementById('roleKey').value.trim();
    const roleName = document.getElementById('roleName').value.trim();

    if (!roleKey || !roleName) {
        alert('식별자와 표시 이름은 필수입니다.');
        return;
    }

    // role_key 유효성 검사 (영문 소문자, 숫자, 언더스코어만)
    if (!/^[a-z0-9_]+$/.test(roleKey)) {
        alert('식별자는 영문 소문자, 숫자, 언더스코어만 사용할 수 있습니다.');
        return;
    }

    const data = {
        role_key: roleKey,
        role_name: roleName,
        icon: document.getElementById('icon').value,
        description: document.getElementById('description').value,

        model_openai: document.getElementById('modelOpenai').value,
        model_anthropic: document.getElementById('modelAnthropic').value,
        model_google: document.getElementById('modelGoogle').value,
        max_tokens: parseInt(document.getElementById('maxTokens').value),

        use_rag: document.getElementById('useRag').checked,
        chunk_strategy: document.getElementById('chunkStrategy').value,
        chunk_size: parseInt(document.getElementById('chunkSize').value),
        chunk_overlap: parseInt(document.getElementById('chunkOverlap').value),
        retrieval_strategy: document.getElementById('retrievalStrategy').value,
        rag_top_k: parseInt(document.getElementById('ragTopK').value),
        rag_max_k: parseInt(document.getElementById('ragMaxK').value),
        rag_similarity_threshold: parseFloat(document.getElementById('ragSimilarityThreshold').value),
        rag_gap_threshold: parseFloat(document.getElementById('ragGapThreshold').value),

        allow_user: document.getElementById('allowUser').checked,
        allow_teacher: document.getElementById('allowTeacher').checked,
        restrict_google: document.getElementById('restrictGoogle').checked,
        restrict_anthropic: document.getElementById('restrictAnthropic').checked,
        restrict_openai: document.getElementById('restrictOpenai').checked
    };

    try {
        let response;
        if (selectedPersonaId) {
            // 수정
            response = await fetch(`/api/admin/persona/${selectedPersonaId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
        } else {
            // 생성
            response = await fetch('/api/admin/persona/create', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
        }

        const result = await response.json();

        if (result.success) {
            alert(selectedPersonaId ? '페르소나가 수정되었습니다.' : '페르소나가 생성되었습니다.');
            await loadPersonas();

            // 새로 생성된 경우 해당 페르소나 선택
            if (result.persona_id) {
                await selectPersona(result.persona_id);
            }
        } else {
            alert('저장 실패: ' + (result.error || '알 수 없는 오류'));
        }
    } catch (error) {
        console.error('저장 실패:', error);
        alert('저장 중 오류가 발생했습니다.');
    }
}

/**
 * 페르소나 삭제
 */
async function deletePersona() {
    if (!selectedPersonaId) {
        alert('삭제할 페르소나를 선택해주세요.');
        return;
    }

    if (!confirm('정말 이 페르소나를 삭제하시겠습니까?\n관련된 지식 베이스와 교사 권한도 함께 삭제됩니다.')) {
        return;
    }

    try {
        const response = await fetch(`/api/admin/persona/${selectedPersonaId}`, {
            method: 'DELETE'
        });

        const result = await response.json();

        if (result.success) {
            alert('페르소나가 삭제되었습니다.');
            selectedPersonaId = null;
            await loadPersonas();
            cancelEdit();
        } else {
            alert('삭제 실패: ' + (result.error || '알 수 없는 오류'));
        }
    } catch (error) {
        console.error('삭제 실패:', error);
        alert('삭제 중 오류가 발생했습니다.');
    }
}

/**
 * 편집 취소
 */
function cancelEdit() {
    selectedPersonaId = null;
    renderPersonaList();

    document.querySelector('.empty-state').style.display = 'flex';
    document.getElementById('personaDetailForm').style.display = 'none';
}

/**
 * 교사 추가
 */
async function addTeacher() {
    if (!selectedPersonaId) {
        alert('페르소나를 먼저 선택하거나 저장해주세요.');
        return;
    }

    if (allTeachers.length === 0) {
        alert('추가 가능한 교사가 없습니다.');
        return;
    }

    // 간단한 프롬프트로 교사 선택
    const teacherOptions = allTeachers.map(t => `${t.id}: ${t.username} (${t.email || 'No email'})`).join('\n');
    const teacherIdStr = prompt(`교사 ID를 입력하세요:\n\n${teacherOptions}`);

    if (!teacherIdStr) return;

    const teacherId = parseInt(teacherIdStr);
    if (isNaN(teacherId)) {
        alert('유효한 교사 ID를 입력해주세요.');
        return;
    }

    try {
        const response = await fetch(`/api/admin/persona/${selectedPersonaId}/grant-teacher`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                teacher_id: teacherId,
                can_edit_prompt: true,
                can_manage_knowledge: true,
                can_view_analytics: true
            })
        });

        const result = await response.json();

        if (result.success) {
            alert('교사 권한이 부여되었습니다.');
            await loadPersonaTeachers(selectedPersonaId);
        } else {
            alert('권한 부여 실패: ' + (result.error || '알 수 없는 오류'));
        }
    } catch (error) {
        console.error('교사 추가 실패:', error);
        alert('교사 추가 중 오류가 발생했습니다.');
    }
}

/**
 * 교사 제거
 */
async function removeTeacher(teacherId) {
    if (!selectedPersonaId) return;

    if (!confirm('이 교사의 권한을 제거하시겠습니까?')) {
        return;
    }

    try {
        const response = await fetch(`/api/admin/persona/${selectedPersonaId}/revoke-teacher/${teacherId}`, {
            method: 'DELETE'
        });

        const result = await response.json();

        if (result.success) {
            alert('교사 권한이 제거되었습니다.');
            await loadPersonaTeachers(selectedPersonaId);
        } else {
            alert('권한 제거 실패: ' + (result.error || '알 수 없는 오류'));
        }
    } catch (error) {
        console.error('교사 제거 실패:', error);
        alert('교사 제거 중 오류가 발생했습니다.');
    }
}

/**
 * 모든 provider 프롬프트 로드
 */
async function loadAllPrompts(personaId) {
    try {
        const response = await fetch(`/api/admin/persona/${personaId}/prompts`);
        const data = await response.json();

        currentPrompts = {};
        if (data.prompts) {
            data.prompts.forEach(p => {
                currentPrompts[p.provider] = p.system_prompt;
            });
        }

        // 현재 선택된 provider 프롬프트 표시
        loadPromptForProvider();
    } catch (error) {
        console.error('프롬프트 로드 실패:', error);
    }
}

/**
 * Provider 변경 시 해당 프롬프트 표시
 */
function loadPromptForProvider() {
    const provider = document.getElementById('promptProvider').value;
    const textarea = document.getElementById('systemPrompt');
    textarea.value = currentPrompts[provider] || '';
}

/**
 * 시스템 프롬프트 저장
 */
async function saveSystemPrompt() {
    if (!selectedPersonaId) {
        alert('페르소나를 먼저 선택하세요');
        return;
    }

    const provider = document.getElementById('promptProvider').value;
    const prompt = document.getElementById('systemPrompt').value.trim();

    if (!prompt) {
        alert('프롬프트를 입력하세요');
        return;
    }

    try {
        const response = await fetch(`/api/admin/persona/${selectedPersonaId}/prompt`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ provider, system_prompt: prompt })
        });

        const result = await response.json();

        if (result.success) {
            alert('시스템 프롬프트가 저장되었습니다');
            currentPrompts[provider] = prompt;
        } else {
            alert('저장 실패: ' + (result.error || '알 수 없는 오류'));
        }
    } catch (error) {
        console.error('저장 실패:', error);
        alert('저장 중 오류가 발생했습니다');
    }
}


// ================================================================
// RAG 지식 베이스 관리
// ================================================================

let selectedFile = null;

/**
 * 파일 선택 핸들러
 */
function handleKnowledgeFileSelect(event) {
    const file = event.target.files[0];
    if (!file) {
        selectedFile = null;
        document.getElementById('selectedFileName').textContent = '';
        document.getElementById('uploadBtn').style.display = 'none';
        return;
    }

    selectedFile = file;
    const fileSizeMB = (file.size / (1024 * 1024)).toFixed(2);
    document.getElementById('selectedFileName').textContent = `${file.name} (${fileSizeMB} MB)`;
    document.getElementById('uploadBtn').style.display = 'inline-block';
}

/**
 * 파일 업로드
 */
async function uploadKnowledgeFile() {
    if (!selectedPersonaId) {
        alert('페르소나를 먼저 선택하세요');
        return;
    }

    if (!selectedFile) {
        alert('파일을 선택하세요');
        return;
    }

    try {
        // 프로그레스 바 표시
        document.getElementById('uploadProgress').style.display = 'block';
        document.getElementById('uploadProgressBar').style.width = '0%';
        document.getElementById('uploadProgressBar').textContent = '0%';
        document.getElementById('uploadStatus').textContent = '업로드 중...';

        const formData = new FormData();
        formData.append('file', selectedFile);

        const response = await fetch(`/api/admin/persona/${selectedPersonaId}/knowledge/upload`, {
            method: 'POST',
            body: formData
        });

        const result = await response.json();

        if (result.success) {
            // 프로그레스 바 완료
            document.getElementById('uploadProgressBar').style.width = '100%';
            document.getElementById('uploadProgressBar').textContent = '100%';
            document.getElementById('uploadStatus').textContent = '✅ 업로드 완료! 벡터화 작업이 백그라운드에서 진행됩니다.';

            // 3초 후 프로그레스 바 숨기기
            setTimeout(() => {
                document.getElementById('uploadProgress').style.display = 'none';
            }, 3000);

            // 파일 선택 초기화
            selectedFile = null;
            document.getElementById('knowledgeFileInput').value = '';
            document.getElementById('selectedFileName').textContent = '';
            document.getElementById('uploadBtn').style.display = 'none';

            // 문서 목록 새로고침
            await loadKnowledgeDocuments();
            await loadKnowledgeStats();
        } else {
            alert('업로드 실패: ' + (result.error || '알 수 없는 오류'));
            document.getElementById('uploadProgress').style.display = 'none';
        }
    } catch (error) {
        console.error('업로드 실패:', error);
        alert('업로드 중 오류가 발생했습니다');
        document.getElementById('uploadProgress').style.display = 'none';
    }
}

/**
 * 문서 목록 로드
 */
async function loadKnowledgeDocuments() {
    if (!selectedPersonaId) {
        stopPolling();
        return;
    }

    try {
        const response = await fetch(`/api/admin/persona/${selectedPersonaId}/knowledge/documents`);
        const data = await response.json();

        const docList = document.getElementById('documentList');

        if (!data.documents || data.documents.length === 0) {
            docList.innerHTML = '<p style="color: #999; text-align: center; padding: 20px;">문서가 없습니다</p>';
            stopPolling();
            return;
        }

        let html = '';
        data.documents.forEach(doc => {
            const statusClass = `status-${doc.processing_status}`;
            const statusText = {
                'pending': '대기 중',
                'processing': '처리 중',
                'completed': '완료',
                'failed': '실패'
            }[doc.processing_status] || doc.processing_status;

            const uploadDate = new Date(doc.uploaded_at).toLocaleString('ko-KR');
            const fileSizeMB = (doc.file_size / (1024 * 1024)).toFixed(2);

            html += `
                <div class="document-item">
                    <div class="document-info">
                        <div class="document-name">
                            📄 ${doc.filename}
                            <span class="document-status ${statusClass}">${statusText}</span>
                        </div>
                        <div class="document-meta">
                            ${fileSizeMB} MB • ${doc.chunk_count}개 청크 • ${uploadDate}
                            ${doc.error_message ? `<br><span style="color: #e74c3c;">⚠️ ${doc.error_message}</span>` : ''}
                        </div>
                    </div>
                    <div class="document-actions">
                        <button onclick="deleteKnowledgeDocument(${doc.id})" class="btn-small" title="삭제">
                            🗑️
                        </button>
                    </div>
                </div>
            `;
        });

        docList.innerHTML = html;

        // 처리 중인 문서가 있는지 확인
        const hasProcessing = data.documents.some(doc =>
            doc.processing_status === 'processing' || doc.processing_status === 'pending'
        );

        // Polling 관리
        if (hasProcessing) {
            startPolling();
        } else {
            stopPolling();
        }
    } catch (error) {
        console.error('문서 목록 로드 실패:', error);
        stopPolling();
    }
}

/**
 * Polling 시작 (처리 중인 문서가 있을 때)
 */
function startPolling() {
    // 이미 polling 중이면 중복 시작 방지
    if (pollingInterval) return;

    console.log('📡 문서 상태 polling 시작 (3초마다)');
    pollingInterval = setInterval(() => {
        loadKnowledgeDocuments();
        loadKnowledgeStats();
    }, 3000); // 3초마다
}

/**
 * Polling 중지 (모든 문서 처리 완료 시)
 */
function stopPolling() {
    if (pollingInterval) {
        console.log('🛑 문서 상태 polling 중지');
        clearInterval(pollingInterval);
        pollingInterval = null;
    }
}

/**
 * 문서 삭제
 */
async function deleteKnowledgeDocument(docId) {
    if (!confirm('이 문서를 삭제하시겠습니까? 관련된 모든 청크 데이터가 함께 삭제됩니다.')) {
        return;
    }

    try {
        const response = await fetch(`/api/admin/persona/${selectedPersonaId}/knowledge/document/${docId}`, {
            method: 'DELETE'
        });

        const result = await response.json();

        if (result.success) {
            alert('문서가 삭제되었습니다');
            await loadKnowledgeDocuments();
            await loadKnowledgeStats();
        } else {
            alert('삭제 실패: ' + (result.error || '알 수 없는 오류'));
        }
    } catch (error) {
        console.error('삭제 실패:', error);
        alert('삭제 중 오류가 발생했습니다');
    }
}

/**
 * RAG 통계 로드
 */
async function loadKnowledgeStats() {
    if (!selectedPersonaId) return;

    try {
        const response = await fetch(`/api/admin/persona/${selectedPersonaId}/knowledge/stats`);
        const stats = await response.json();

        if (stats.document_count > 0) {
            document.getElementById('ragStats').style.display = 'block';
            document.getElementById('statTotalDocs').textContent = stats.document_count;
            document.getElementById('statCompletedDocs').textContent = stats.completed_count;
            document.getElementById('statProcessingDocs').textContent = stats.processing_count;
            document.getElementById('statFailedDocs').textContent = stats.failed_count;
            document.getElementById('statTotalChunks').textContent = stats.chunk_count;
        } else {
            document.getElementById('ragStats').style.display = 'none';
        }
    } catch (error) {
        console.error('통계 로드 실패:', error);
    }
}

/**
 * RAG 체크박스 변경 시 지식 베이스 섹션 표시/숨김
 */
document.addEventListener('DOMContentLoaded', function() {
    const useRagCheckbox = document.getElementById('useRag');
    const knowledgeBaseSection = document.getElementById('knowledgeBaseSection');

    if (useRagCheckbox) {
        useRagCheckbox.addEventListener('change', function() {
            if (this.checked) {
                knowledgeBaseSection.style.display = 'block';
                // RAG 활성화 시 문서 목록 및 통계 로드
                if (selectedPersonaId) {
                    loadKnowledgeDocuments();
                    loadKnowledgeStats();
                }
            } else {
                knowledgeBaseSection.style.display = 'none';
            }
        });
    }
});
