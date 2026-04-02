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

        // xAI 드롭다운
        const xaiSelect = document.getElementById('modelXai');
        if (xaiSelect && enabledModels.xai && enabledModels.xai.length > 0) {
            xaiSelect.innerHTML = '';
            enabledModels.xai.forEach(modelId => {
                const option = document.createElement('option');
                option.value = modelId;
                option.textContent = modelId;
                xaiSelect.appendChild(option);
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
        google: ['gemini-3-flash-preview', 'gemini-2.5-flash'],
        xai: ['grok-4-1-fast-reasoning']
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

    // xAI
    const xaiSelect = document.getElementById('modelXai');
    if (xaiSelect) {
        xaiSelect.innerHTML = '';
        defaultModels.xai.forEach(modelId => {
            const option = document.createElement('option');
            option.value = modelId;
            option.textContent = modelId;
            xaiSelect.appendChild(option);
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
                ${p.student_count > 0 ? `<span class="badge" style="background:#e74c3c">${p.student_count}명 배정</span>` : ''}
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
    document.getElementById('modelGoogle').value = persona.model_google || 'gemini-3-flash-preview';
    document.getElementById('modelXai').value = persona.model_xai || 'grok-4-1-fast-reasoning';
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
    document.getElementById('restrictXai').checked = persona.restrict_xai || false;

    // 교사 목록 로드
    loadPersonaTeachers(persona.id);

    // 학생 배정 섹션 표시 및 로드
    const studentSection = document.getElementById('studentAssignmentSection');
    if (studentSection) {
        studentSection.style.display = 'block';
        loadPersonaStudents(persona.id);
    }

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
    document.getElementById('modelGoogle').value = 'gemini-3-flash-preview';
    document.getElementById('modelXai').value = 'grok-4-1-fast-reasoning';
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
    document.getElementById('restrictXai').checked = false;

    document.getElementById('teacherList').innerHTML = '<p style="color: #999; text-align: center;">새 페르소나를 저장한 후 교사를 추가할 수 있습니다</p>';

    const studentSection = document.getElementById('studentAssignmentSection');
    if (studentSection) studentSection.style.display = 'none';
    const studentList = document.getElementById('studentList');
    if (studentList) studentList.innerHTML = '<p style="color: #999; text-align: center;">새 페르소나를 저장한 후 학생을 배정할 수 있습니다</p>';
    const badge = document.getElementById('studentRestrictionBadge');
    if (badge) badge.style.display = 'none';
    _pickerAll = [];
    _pickerSelected.clear();
    // 프롬프트 캐시 초기화
    currentPrompts = {};
    const promptTextarea = document.getElementById('systemPrompt');
    if (promptTextarea) promptTextarea.value = '';
    const providerSelect = document.getElementById('promptProvider');
    if (providerSelect) {
        providerSelect.value = 'default';
        providerSelect.dataset.prevProvider = 'default';
    }
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
        model_xai: document.getElementById('modelXai').value,
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
        restrict_openai: document.getElementById('restrictOpenai').checked,
        restrict_xai: document.getElementById('restrictXai').checked
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
            const personaId = result.persona_id || selectedPersonaId;

            // 현재 textarea에 작성 중인 프롬프트를 캐시에 반영 (저장 버튼 누르기 직전 상태)
            const providerEl = document.getElementById('promptProvider');
            const currentProvider = providerEl?.value;
            const currentText = document.getElementById('systemPrompt')?.value;
            if (currentProvider && currentText) {
                currentPrompts[currentProvider] = currentText;
            }

            // currentPrompts에 있는 모든 provider 프롬프트를 일괄 저장
            if (personaId && Object.keys(currentPrompts).length > 0) {
                for (const [provider, promptText] of Object.entries(currentPrompts)) {
                    const trimmed = promptText.trim();
                    if (!trimmed) continue;
                    try {
                        await fetch(`/api/admin/persona/${personaId}/prompt`, {
                            method: 'PUT',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ provider, system_prompt: trimmed })
                        });
                    } catch (e) {
                        console.error(`프롬프트 저장 실패 (${provider}):`, e);
                    }
                }
            }

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

// ─── 학생 배정 모달 ────────────────────────────────────────────

// 모달 상태
let _pickerAll = [];              // 전체 학생 목록 (is_assigned 포함)
let _pickerSelected = new Set();  // 체크된 student.id
let _pickerLastIdx = null;        // Shift 클릭용 마지막 인덱스

/**
 * 페르소나에 배정된 학생 목록 로드 (섹션 목록 갱신)
 */
async function loadPersonaStudents(personaId) {
    try {
        const response = await fetch(`/api/admin/persona/${personaId}/students`);
        const data = await response.json();

        // 제한 모드 배지
        const badge = document.getElementById('studentRestrictionBadge');
        if (badge) badge.style.display = data.is_restricted ? 'block' : 'none';

        // 섹션 내 배정된 학생 목록
        const studentListEl = document.getElementById('studentList');
        if (data.students && data.students.length > 0) {
            studentListEl.innerHTML = data.students.map(s => `
                <div class="teacher-item">
                    <div>
                        <strong>${s.username}</strong>
                        ${s.email ? `<br><small>${s.email}</small>` : ''}
                    </div>
                </div>
            `).join('');
        } else {
            studentListEl.innerHTML = '<p style="color: #999; text-align: center;">배정된 학생이 없습니다 (전체 학생에게 공개)</p>';
        }

        // 모달용 전체 목록 캐싱
        _pickerAll = data.all_students || [];
    } catch (error) {
        console.error('학생 목록 로드 실패:', error);
    }
}

/**
 * 학생 배정 모달 열기
 */
function openStudentPickerModal() {
    if (!selectedPersonaId) {
        alert('페르소나를 먼저 선택하거나 저장해주세요.');
        return;
    }
    _pickerSelected.clear();
    _pickerLastIdx = null;
    document.getElementById('studentPickerSearch').value = '';
    renderPickerList('');
    document.getElementById('studentPickerModal').classList.add('open');
    document.getElementById('studentPickerSearch').focus();
}

/**
 * 학생 배정 모달 닫기
 */
function closeStudentPickerModal() {
    document.getElementById('studentPickerModal').classList.remove('open');
}

/**
 * 모달 내 학생 목록 렌더링
 */
function renderPickerList(query) {
    const listEl = document.getElementById('studentPickerList');
    const q = query.toLowerCase();
    const filtered = _pickerAll.filter(s =>
        s.username.toLowerCase().includes(q) ||
        (s.email && s.email.toLowerCase().includes(q))
    );
    listEl._filtered = filtered;

    if (filtered.length === 0) {
        listEl.innerHTML = '<div class="student-picker-empty">학생이 없습니다</div>';
        updatePickerInfo();
        return;
    }

    listEl.innerHTML = filtered.map((s, idx) => {
        const isChecked = _pickerSelected.has(s.id);
        return `
        <div class="student-picker-item ${isChecked ? 'selected' : ''}"
             data-id="${s.id}" onclick="handlePickerClick(event, ${idx}, ${s.id})">
            <input type="checkbox" ${isChecked ? 'checked' : ''}
                   onclick="event.stopPropagation(); handlePickerClick(event, ${idx}, ${s.id})">
            <div style="flex:1;">
                <div class="student-name">${s.username}</div>
                ${s.email ? `<div class="student-email">${s.email}</div>` : ''}
            </div>
            <div class="picker-assigned-badge ${s.is_assigned ? 'assigned' : 'unassigned'}">
                ${s.is_assigned ? '배정됨' : '미배정'}
            </div>
        </div>`;
    }).join('');

    updatePickerInfo();
}

/**
 * 모달 항목 클릭 (체크박스 + Shift 범위선택)
 */
function handlePickerClick(event, idx, studentId) {
    const filtered = document.getElementById('studentPickerList')._filtered || _pickerAll;

    if (event.shiftKey && _pickerLastIdx !== null) {
        const start = Math.min(_pickerLastIdx, idx);
        const end   = Math.max(_pickerLastIdx, idx);
        const shouldSelect = !_pickerSelected.has(studentId);
        for (let i = start; i <= end; i++) {
            if (filtered[i]) {
                if (shouldSelect) _pickerSelected.add(filtered[i].id);
                else              _pickerSelected.delete(filtered[i].id);
            }
        }
    } else {
        if (_pickerSelected.has(studentId)) _pickerSelected.delete(studentId);
        else                                _pickerSelected.add(studentId);
        _pickerLastIdx = idx;
    }

    renderPickerList(document.getElementById('studentPickerSearch').value);
}

/**
 * 선택 인원 카운트 갱신
 */
function updatePickerInfo() {
    const infoEl = document.getElementById('studentPickerInfo');
    if (infoEl) infoEl.textContent = `${_pickerSelected.size}명 선택됨`;
}

/**
 * 모달 검색 필터
 */
function filterStudentPicker() {
    _pickerLastIdx = null;
    renderPickerList(document.getElementById('studentPickerSearch').value);
}

/**
 * 일괄 배정 — 선택된 학생 중 미배정자만 배정
 */
async function bulkAssignStudents() {
    const targets = Array.from(_pickerSelected).filter(id => {
        const s = _pickerAll.find(s => s.id === id);
        return s && !s.is_assigned;
    });
    if (targets.length === 0) {
        alert('배정할 학생이 없습니다.\n미배정 학생을 선택해주세요.');
        return;
    }

    let ok = 0, fail = 0;
    for (const studentId of targets) {
        try {
            const res = await fetch(`/api/admin/persona/${selectedPersonaId}/assign-student`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ student_id: studentId })
            });
            (await res.json()).success ? ok++ : fail++;
        } catch { fail++; }
    }

    // 모달 내 상태 갱신 (닫지 않음)
    await _refreshPickerData();
    if (fail > 0) alert(`${ok}명 배정 완료, ${fail}명 실패`);
}

/**
 * 일괄 취소 — 선택된 학생 중 배정된 학생만 취소
 */
async function bulkUnassignStudents() {
    const targets = Array.from(_pickerSelected).filter(id => {
        const s = _pickerAll.find(s => s.id === id);
        return s && s.is_assigned;
    });
    if (targets.length === 0) {
        alert('취소할 학생이 없습니다.\n배정된 학생을 선택해주세요.');
        return;
    }

    let ok = 0, fail = 0;
    for (const studentId of targets) {
        try {
            const res = await fetch(
                `/api/admin/persona/${selectedPersonaId}/unassign-student/${studentId}`,
                { method: 'DELETE' }
            );
            (await res.json()).success ? ok++ : fail++;
        } catch { fail++; }
    }

    await _refreshPickerData();
    if (fail > 0) alert(`${ok}명 취소 완료, ${fail}명 실패`);
}

/**
 * 모달 내 데이터 새로고침 (모달 열린 채로 갱신)
 */
async function _refreshPickerData() {
    try {
        const response = await fetch(`/api/admin/persona/${selectedPersonaId}/students`);
        const data = await response.json();
        _pickerAll = data.all_students || [];
        _pickerSelected.clear();

        // 섹션 목록도 갱신
        const badge = document.getElementById('studentRestrictionBadge');
        if (badge) badge.style.display = data.is_restricted ? 'block' : 'none';
        const studentListEl = document.getElementById('studentList');
        if (data.students && data.students.length > 0) {
            studentListEl.innerHTML = data.students.map(s => `
                <div class="teacher-item">
                    <div>
                        <strong>${s.username}</strong>
                        ${s.email ? `<br><small>${s.email}</small>` : ''}
                    </div>
                </div>
            `).join('');
        } else {
            studentListEl.innerHTML = '<p style="color: #999; text-align: center;">배정된 학생이 없습니다 (전체 학생에게 공개)</p>';
        }

        renderPickerList(document.getElementById('studentPickerSearch').value);
        await loadPersonas(); // 카드 배지 갱신
    } catch (error) {
        console.error('데이터 갱신 실패:', error);
    }
}

// 모달 외부 클릭 시 닫기
document.addEventListener('click', function(e) {
    const modal = document.getElementById('studentPickerModal');
    if (modal && e.target === modal) closeStudentPickerModal();
});

// ────────────────────────────────────────────────────────────

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
 * @param {boolean} fromUser - true: 사용자가 직접 탭을 바꾼 경우 (textarea 캐싱 O)
 *                             false: 코드에서 자동 호출된 경우 (캐싱 X — 다른 페르소나 데이터 오염 방지)
 */
function loadPromptForProvider(fromUser = false) {
    const select = document.getElementById('promptProvider');
    const textarea = document.getElementById('systemPrompt');

    // 사용자가 직접 탭을 바꿀 때만 이전 내용을 캐시에 저장
    if (fromUser && select.dataset.prevProvider) {
        const prev = select.dataset.prevProvider;
        const prevVal = textarea.value;
        if (prevVal) currentPrompts[prev] = prevVal;
    }

    const provider = select.value;
    select.dataset.prevProvider = provider;
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


// ─── 시스템 프롬프트 스냅샷 ────────────────────────────────────

let _snapshotSlots = [];      // 슬롯 목록 캐시
let _pendingSaveSlot = null;  // 저장 확인 대기 중인 슬롯 번호

/**
 * 슬롯 목록 로드 (두 모달 공용)
 */
async function _loadSnapshotSlots() {
    try {
        const res = await fetch(`/api/admin/persona/${selectedPersonaId}/prompt-snapshots`);
        const data = await res.json();
        _snapshotSlots = data.slots || [];
    } catch (e) {
        console.error('슬롯 목록 로드 실패:', e);
        _snapshotSlots = [];
    }
}

/**
 * 저장 모달 열기
 */
async function openSaveSnapshotModal() {
    if (!selectedPersonaId) { alert('페르소나를 먼저 선택하세요'); return; }
    await _loadSnapshotSlots();
    _pendingSaveSlot = null;

    const listEl = document.getElementById('saveSnapshotSlotList');
    listEl.innerHTML = _snapshotSlots.map(s => `
        <div class="snapshot-slot-item" onclick="selectSaveSlot(${s.slot})">
            <div class="slot-num">${s.slot}</div>
            <div class="slot-info">
                ${s.empty
                    ? '<span class="slot-empty">빈 슬롯</span>'
                    : `<div class="slot-memo">${s.memo || '(메모 없음)'}</div>
                       <div class="slot-date">${s.saved_at}</div>`
                }
            </div>
        </div>
    `).join('');

    document.getElementById('saveMemoRow').style.display = 'none';
    document.getElementById('saveSnapshotMemo').value = '';
    document.getElementById('saveSnapshotModal').classList.add('open');
}

function closeSaveSnapshotModal() {
    document.getElementById('saveSnapshotModal').classList.remove('open');
}

/**
 * 저장 슬롯 선택 → 메모 입력 행 표시
 */
function selectSaveSlot(slot) {
    _pendingSaveSlot = slot;

    // 선택된 슬롯 강조
    document.querySelectorAll('#saveSnapshotSlotList .snapshot-slot-item').forEach((el, i) => {
        el.style.background = (i + 1 === slot) ? '#eff6ff' : '';
        el.style.borderColor = (i + 1 === slot) ? '#3b82f6' : '#e5e7eb';
    });

    // 기존 메모 미리 채우기
    const existing = _snapshotSlots.find(s => s.slot === slot);
    document.getElementById('saveSnapshotMemo').value = (existing && !existing.empty) ? (existing.memo || '') : '';
    document.getElementById('saveMemoRow').style.display = 'block';
    document.getElementById('saveSnapshotMemo').focus();
}

function cancelSaveSlot() {
    _pendingSaveSlot = null;
    document.getElementById('saveMemoRow').style.display = 'none';
    document.querySelectorAll('#saveSnapshotSlotList .snapshot-slot-item').forEach(el => {
        el.style.background = '';
        el.style.borderColor = '#e5e7eb';
    });
}

/**
 * 슬롯 저장 확정
 */
async function confirmSaveSlot() {
    if (!_pendingSaveSlot) return;

    // 현재 textarea의 내용을 currentPrompts에 반영
    const providerEl = document.getElementById('promptProvider');
    const textareaVal = document.getElementById('systemPrompt').value;
    if (providerEl && textareaVal) {
        currentPrompts[providerEl.value] = textareaVal;
    }

    const memo = document.getElementById('saveSnapshotMemo').value.trim();

    try {
        const res = await fetch(
            `/api/admin/persona/${selectedPersonaId}/prompt-snapshots/${_pendingSaveSlot}`,
            {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ memo })
            }
        );
        const result = await res.json();
        if (result.success) {
            closeSaveSnapshotModal();
        } else {
            alert('저장 실패: ' + (result.error || '알 수 없는 오류'));
        }
    } catch (e) {
        console.error('스냅샷 저장 실패:', e);
        alert('저장 중 오류가 발생했습니다');
    }
}

/**
 * 불러오기 모달 열기
 */
async function openLoadSnapshotModal() {
    if (!selectedPersonaId) { alert('페르소나를 먼저 선택하세요'); return; }
    await _loadSnapshotSlots();

    const listEl = document.getElementById('loadSnapshotSlotList');
    listEl.innerHTML = _snapshotSlots.map(s => `
        <div class="snapshot-slot-item ${s.empty ? 'disabled' : ''}"
             onclick="${s.empty ? '' : `restoreSnapshotSlot(${s.slot})`}"
             style="${s.empty ? 'opacity:0.4;cursor:default;' : 'cursor:pointer;'}">
            <div class="slot-num">${s.slot}</div>
            <div class="slot-info">
                ${s.empty
                    ? '<span class="slot-empty">빈 슬롯</span>'
                    : `<div class="slot-memo">${s.memo || '(메모 없음)'}</div>
                       <div class="slot-date">${s.saved_at}</div>`
                }
            </div>
            ${!s.empty ? '<span style="font-size:0.8rem;color:#3b82f6;flex-shrink:0;">불러오기 →</span>' : ''}
        </div>
    `).join('');

    document.getElementById('loadSnapshotModal').classList.add('open');
}

function closeLoadSnapshotModal() {
    document.getElementById('loadSnapshotModal').classList.remove('open');
}

/**
 * 슬롯 복원
 */
async function restoreSnapshotSlot(slot) {
    if (!confirm(`슬롯 ${slot}의 프롬프트를 불러오시겠습니까?\n현재 작성 중인 내용은 사라집니다.`)) return;

    try {
        const res = await fetch(
            `/api/admin/persona/${selectedPersonaId}/prompt-snapshots/${slot}/restore`,
            { method: 'POST' }
        );
        const result = await res.json();
        if (result.success) {
            // currentPrompts 갱신
            currentPrompts = result.prompts || {};

            // 현재 선택된 provider textarea 갱신
            const providerEl = document.getElementById('promptProvider');
            if (providerEl) {
                providerEl.dataset.prevProvider = providerEl.value;
                document.getElementById('systemPrompt').value = currentPrompts[providerEl.value] || '';
            }

            closeLoadSnapshotModal();
        } else {
            alert('불러오기 실패: ' + (result.error || '알 수 없는 오류'));
        }
    } catch (e) {
        console.error('스냅샷 복원 실패:', e);
        alert('불러오기 중 오류가 발생했습니다');
    }
}

// 모달 외부 클릭 시 닫기
document.addEventListener('click', function(e) {
    if (e.target === document.getElementById('saveSnapshotModal')) closeSaveSnapshotModal();
    if (e.target === document.getElementById('loadSnapshotModal')) closeLoadSnapshotModal();
});

// ────────────────────────────────────────────────────────────

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
document.addEventListener('DOMContentLoaded', function () {
    const useRagCheckbox = document.getElementById('useRag');
    const knowledgeBaseSection = document.getElementById('knowledgeBaseSection');

    if (useRagCheckbox) {
        useRagCheckbox.addEventListener('change', function () {
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
