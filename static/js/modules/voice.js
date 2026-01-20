// 음성 입력(SpeechRecognition) 모듈: 실시간 자막 포함.
window.App.registerModule((ctx) => {
    const { dom } = ctx;
    if (!dom.voiceInputBtn || !dom.userInput) return;

    // Web Speech API 감지(Chrome은 webkit 접두사 사용).
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

    if (SpeechRecognition) {
        const recognition = new SpeechRecognition();
        recognition.lang = 'ko-KR';
        // 실시간 자막을 위해 연속 인식 + 중간 결과 사용.
        recognition.continuous = true;
        recognition.interimResults = true;
        recognition.maxAlternatives = 1;

        let isRecording = false;

        // 입력창 위 자막 오버레이.
        const captionOverlay = document.createElement('div');
        captionOverlay.id = 'voice-caption-overlay';
        captionOverlay.style.cssText = `
            display: none;
            position: absolute;
            bottom: 100%;
            left: 20px;
            right: 20px;
            padding: 8px 12px;
            background-color: rgba(0, 0, 0, 0.7);
            color: #fff;
            font-size: 0.9rem;
            border-radius: 8px;
            margin-bottom: 8px;
            z-index: 100;
            pointer-events: none;
            transition: opacity 0.2s;
            text-align: center;
        `;
        const textareaWrapper = document.querySelector('.textarea-wrapper');
        if (textareaWrapper) {
            textareaWrapper.appendChild(captionOverlay);
        }

        // 마이크 버튼 클릭으로 녹음 토글.
        dom.voiceInputBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();

            if (isRecording) {
                console.log("🎤 녹음 수동 중지 요청");
                recognition.stop();
                return;
            }

            try {
                console.log("🎤 녹음 시작 요청");
                recognition.start();
            } catch (err) {
                console.error("Speech Recognition Start Error:", err);
                recognition.stop();
            }
        });

        // 단축키: Ctrl+M(또는 macOS Cmd+M).
        document.addEventListener('keydown', (e) => {
            if ((e.ctrlKey || e.metaKey) && (e.key === 'm' || e.key === 'M')) {
                e.preventDefault();
                if (dom.voiceInputBtn && dom.voiceInputBtn.style.display !== 'none') {
                    console.log("⌨️ 단축키(Ctrl+M) 감지됨 -> 마이크 토글");
                    dom.voiceInputBtn.click();
                }
            }
        });

        /**
         * 인식 시작 시 UI 처리를 수행한다.
         */
        recognition.onstart = () => {
            console.log("✅ 음성 인식 서비스 시작됨");
            isRecording = true;
            dom.voiceInputBtn.classList.add('recording');

            captionOverlay.style.display = 'block';
            captionOverlay.textContent = "듣고 있어요... 👂 (단축키: Ctrl+M)";

            dom.userInput.focus();
        };

        /**
         * 인식 종료 시 UI를 정리한다.
         */
        recognition.onend = () => {
            console.log("🛑 음성 인식 서비스 종료됨");
            isRecording = false;
            dom.voiceInputBtn.classList.remove('recording');

            setTimeout(() => {
                captionOverlay.style.display = 'none';
                captionOverlay.textContent = "";
            }, 500);
        };

        /**
         * 중간/최종 인식 결과를 처리한다.
         * @param {SpeechRecognitionEvent} event - 인식 이벤트
         */
        recognition.onresult = (event) => {
            let interimTranscript = '';

            for (let i = event.resultIndex; i < event.results.length; ++i) {
                const transcript = event.results[i][0].transcript;

                if (event.results[i].isFinal) {
                    console.log("📝 확정된 문장:", transcript);

                    const startPos = dom.userInput.selectionStart;
                    const endPos = dom.userInput.selectionEnd;

                    const prefix = (dom.userInput.value.length > 0 && startPos === dom.userInput.value.length && !dom.userInput.value.endsWith(' ')) ? ' ' : '';

                    const textToInsert = prefix + transcript;
                    dom.userInput.setRangeText(textToInsert, startPos, endPos, 'end');
                    dom.userInput.dispatchEvent(new Event('input', { bubbles: true }));
                    dom.userInput.scrollTop = dom.userInput.scrollHeight;

                    captionOverlay.textContent = "듣고 있어요... 👂 (단축키: Ctrl+M)";
                } else {
                    interimTranscript += transcript;
                }
            }

            if (interimTranscript.length > 0) {
                captionOverlay.textContent = interimTranscript + " ...";
                captionOverlay.style.color = "#a7f3d0";
            }
        };

        /**
         * 인식 오류를 처리한다.
         * @param {SpeechRecognitionErrorEvent} event - 오류 이벤트
         */
        recognition.onerror = (event) => {
            console.error("❌ 음성 인식 에러:", event.error);

            if (event.error === 'no-speech') {
                isRecording = false;
                dom.voiceInputBtn.classList.remove('recording');
                captionOverlay.textContent = "말소리가 들리지 않아 종료되었습니다 😴";
                setTimeout(() => { captionOverlay.style.display = 'none'; }, 2000);
                return;
            }

            if (event.error === 'not-allowed') {
                isRecording = false;
                dom.voiceInputBtn.classList.remove('recording');
                alert("마이크 권한이 필요합니다.");
                captionOverlay.style.display = 'none';
            }
        };
    } else {
        console.warn("Web Speech API not supported in this browser.");
        dom.voiceInputBtn.style.display = 'none';
    }
});
