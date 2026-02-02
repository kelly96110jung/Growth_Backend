## MedExplain 프로젝트 고정 스펙 v3 (최종)

| 항목 | 내용 |
|---|---|
| **0) 기본 전제** | • Streaming Recognize 사용<br>• 서버가 스트리밍 세션을 관리<br>• Gemini API Key 사용<br>• 상용화 목적 ❌ (저장 OK, 약관 동의 기반) |
| **1) 대상 / 사용자 / 진료과** | **1차 진료과**: 성형외과<br><br>**사용자**<br>• 성형외과 진료를 받는 일반인<br>• 외국인 환자 (영어 / 중국어)<br>• 의료 통역사 보조 용도 |
| **2) 시간 / 성능 / 녹음 규칙** | **상담 시간**: 기본 5분, 최대 20분<br><br>**스트리밍 관리 방식**<br>• 내부적으로 30초 내외 ~ 최대 1분 세그먼트 단위 관리<br><br>**성능 목표**<br>• 5초 내 결과<br>• 출력1(원문 전사)은 5초 내 표시 |
| **3) 출력 정의 (고정)** | **출력1 (원문)**<br>• Streaming STT 결과<br>• Interim / Final 구분<br>• 언어 그대로 표시 (ko / en / zh)<br><br>**출력2 (변환본)**<br>• 번역문 (ko → en / zh)<br>• 용어 글로스 (사전 기반, 원문 병기)<br>• 의학용어는 번역하지 않음<br>• 뜻은 별도 카드 제공<br><br>**모르는 용어**<br>• 빨간색 표시<br>• 라벨: 확인 필요 |
| **4) 모드 설계** | **모드 A: 환자 이해 모드**<br>입력: 의사 한국어 (+영문 의학용어)<br>출력: 용어 글로스, 쉬운 말 설명 / 요약<br><br>**모드 B: 외국인 의사소통 모드**<br>방향: 의사 ko → 환자 en / zh<br>출력: 번역문, 용어 글로스, 확인 필요 표시 |
| **5) 품질 정책 (절대 규칙)** | 정확도 > 안정성 > 자연스러움<br><br>확실하지 않으면<br>• 억지 번역 ❌<br>• 경고 + 원문 유지 ⭕ |
| **6) 스트리밍 + 세션 운영** | • 세션 최대 20분<br>• 세그먼트 단위 누적 관리<br><br>• 연결 끊김 시 서버 세션 유지<br>• 자동 재시도<br>• 재시도 실패 시 warnings 기록 |
| **7) 전체 아키텍처** | **Flutter App** → 오디오 스트림 전송 / UI 표시<br>**서버** → STT 스트리밍 / 용어 매칭 / 번역 / Gemini 슬롯<br>**이벤트** → stt_interim, stt_final, transform_ready, warning |
| **8) API 계약** | POST /session/start (mode, source_lang, target_lang, department)<br>POST /session/{id}/audio (audio chunk)<br>POST /session/{id}/end (output1, output2, warnings) |
| **9) A / B / C 역할** | **A (모바일)**: 녹음 / UI / 세션 제어<br>**B (서버)**: 세션 관리 / STT / 번역 / Gemini<br>**C (UX/데모)**: 성형외과 시나리오 / 약관 / 발표 흐름 |
