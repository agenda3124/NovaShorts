# NovaShorts v1.22 · SSMaker 자료 전수 기능 대응표

이 문서는 사용자가 제공한 `SSMaker_tree.txt`, `SSMaker_first_run_trace.txt`, `ssmaker_after_login_tree.txt`, 실제 작동 영상에서 **직접 확인되는 이름과 동작 범주**를 기준으로 작성한 clean-room 기능 대응표입니다.

> SSMaker의 핵심 모듈은 `.pyd` 바이너리이므로 내부 알고리즘 자체를 복사하거나 동일하다고 주장하지 않습니다. 대신 자료에서 확인되는 각 기능 단위를 NovaShorts의 독립 구현으로 만들고 실제 제작 파이프라인에 연결했습니다.

| SSMaker 자료에서 확인된 항목 | NovaShorts v1.22 대응 | 실제 활성 경로 | 상태 |
|---|---|---|---|
| `core.providers` | `parity_v122.providers` | 진단/프로바이더 확인 | 활성 |
| `core.audio.pipeline` | `parity_v122.audio_analysis` | Whisper 후 음성 분석 | 활성 |
| `core.sourcing.coupang_scraper` | `sourcing_v122.coupang_scraper` | 상품주소 모드 | 활성 |
| `core.sourcing.keyword_converter` | `sourcing_v122.keyword_converter` | 상품 분석 후 다국어 검색어 | 활성 |
| `core.sourcing.marketplace_query_planner` | `sourcing_v122.marketplace_query_planner` | 7개 플랫폼 계획 | 활성 |
| `core.sourcing.pipeline` | `sourcing_v122.sourcing_pipeline` | 상품주소 → 영상후보 | 활성 |
| `core.sourcing.platform_pipeline` | `sourcing_v122.platform_pipeline` | 플랫폼별 검색/수집 | 활성 |
| `core.sourcing.platform_shorts_searcher` | `sourcing_v122.platform_shorts_searcher` | 직접 검색 + site 검색 폴백 | 활성 |
| `core.sourcing.platform_video_collector` | `sourcing_v122.platform_video_collector` | Chrome/Edge + 확장 폴백 | 활성 |
| `core.sourcing.product_searcher` | `sourcing_v122.product_searcher` | 모델/브랜드/제목/이미지 관련도 | 활성 |
| `core.video.CreateFinalVideo` | `parity_v122.CreateFinalVideo` | 최종 1080×1920 제작 | 활성 |
| `core.video.reeditor` | `parity_v122.reeditor` | 단일/다중 소스 장면 재편집 | 활성 |
| `core.video.render_integrity` | `parity_v122.render_integrity` | 최종 렌더 검증/복구 | 활성 |
| `core.video.video_validator` | `parity_v122.video_validator` | 입력 및 출력 영상 검증 | 활성 |
| `core.video.batch.analysis` | `parity_v122.batch_analysis` | 영상+음성 분석 | 활성 |
| `core.video.batch.encoder` | `parity_v122.encoder` | 모든 입력 정규화 | 활성 |
| `core.video.batch.processor` | `pipeline_v122.run_processing_pipeline_v122` | 전체 일괄 처리 | 활성 |
| `core.video.batch.subtitle_handler` | `parity_v122.subtitle_split` | 한국어 SRT 생성 | 활성 |
| `core.video.batch.tts_generator` | `parity_v122.tts_generator` | Edge TTS | 활성 |
| `core.video.batch.tts_speed` | `parity_v122.tts_speed` | 목표 길이에 음성 자동 맞춤 | 활성 |
| `core.video.batch.utils` | `parity_v122.ffprobe_media` | 미디어 검사 | 활성 |
| `core.video.batch.whisper_analyzer` | `parity_v122.whisper_analyzer` | 내장 Whisper base | 활성 |
| `processors.subtitle_detector` | `parity_v122.subtitle_detector` | OCR 기반 화면 자막 탐지 | 활성 |
| `processors.subtitle_processor` | `parity_v122.subtitle_processor` | 텍스트 마스크/인페인팅 제거 | 활성 |
| `processors.tts_processor` | `parity_v122.tts_processor` | TTS + 길이 맞춤 + SRT | 활성 |
| `processors.video_composer` | `parity_v122.video_composer` | 영상/음성/자막 합성 | 활성 |
| `prompts.audio_analysis` | `parity_v122.audio_analysis` | 발화 구간/언어/비율 분석 | 활성 |
| `prompts.subtitle_split` | `parity_v122.subtitle_split` | 문장 길이 기반 자막 분할 | 활성 |
| `prompts.translation` | `parity_v122.translation` | 비한국어 음성 → 한국어 | 활성 |
| `prompts.video_analysis` | `parity_v122.video_analysis` | 장면 변화/미디어/OCR 분석 | 활성 |
| `prompts.video_validation` | `parity_v122.video_validation` | 대본 사실성/원본 일치 검증 | 활성 |
| `managers.settings_manager` | `engine.Settings` + keyring 보안 저장 | 설정 저장/재실행 유지 | 활성 |
| `ui.panels.settings_tab` | NovaShorts 설정 페이지 | 분석/편집/업로드 설정 | 활성 |
| `ui.panels.upload_panel` | NovaShorts 업로드 페이지 | YouTube 업로드/메타데이터 | 활성 |
| `browser-extension/*` | `browser-extension/*` + 자동 페어링 | 플랫폼/상품 메타데이터 보조 수집 | 활성 |

## 실제 작동 영상에서 확인된 UX 대응

- 상품 주소 → 상품 분석/소싱/제작: 활성
- 영상 1개 → 바로 제작: 활성
- 여러 영상 → 장면 기반 다중소스 재편집: 활성
- 준비한 자료 → 영상 + 사용자가 준비한 한국어 대본: 활성
- 목소리 설정: 활성
- 목소리 미리듣기: 활성
- 자막 설정을 필요할 때 펼쳐 변경: 활성
- 영상 만들기 한 번으로 전체 파이프라인 실행: 활성
- 작업 목록/진행 상태: 기존 NovaShorts 작업 큐에 연결
- 완성 영상 즉시 재생/결과 폴더 열기: 활성
- 한국어 음성 + 한국어 자막 결과: 활성

## 원본 의존 라이브러리에서 확인하고 대응한 범주

- faster-whisper / CTranslate2 → 내장 Whisper base 음성 분석
- Edge TTS → 한국어 TTS 및 미리듣기
- OpenCV / Tesseract → 자막 탐지·제거
- Selenium / webdriver manager / browser extension → NovaShorts 전용 Chrome/Edge CDP + 자동 확장 페어링
- Google GenAI → 검색어·대본·번역·검증 보강
- Google API/OAuth → YouTube 업로드, OAuth 토큰 재사용, 선택적 댓글 작성
- keyring / win32cred → API 키를 가능한 경우 Windows 자격 증명 저장소에 보관
- MoviePy/AV 계열 기능 범주 → FFmpeg/OpenCV 기반 정규화·재편집·합성·무결성 검사로 clean-room 대응

## 일부러 동일하다고 주장하지 않는 부분

- `.pyd` 내부의 비공개 알고리즘/프롬프트 원문
- 원본 `resource/voice_samples` 20개 WAV의 실제 공급자/캐릭터 매핑. 파일명이 있다는 사실은 확인되지만 어떤 TTS 엔진의 어떤 보이스인지 자료만으로 확정할 수 없으므로 NovaShorts는 확인 가능한 Edge TTS 한국어 보이스와 미리듣기를 제공합니다.
- CAPTCHA, 로그인 우회, 라이선스/구독 우회 기능. NovaShorts는 일반 브라우저 세션과 사용자가 직접 완료한 로그인을 재사용하며 우회 기능을 구현하지 않습니다.
- YouTube의 “고정 댓글(pin)” 자동화. 제공 영상은 고정 댓글을 언급하지만 제공 자료만으로 SSMaker가 API로 자동 고정하는지 확인되지 않았고 YouTube Data API에 일반적인 댓글 고정 엔드포인트가 없으므로 NovaShorts는 설정 시 댓글 작성까지만 수행합니다.
