# NovaShorts v1.23 — SSMaker 기능 대응 + 소싱 안정화

v1.23은 v1.22의 SSMaker 기능 대응 구조를 유지하면서, 실제 사용 테스트에서 드러난 상품 영상 소싱 문제를 수정한 버전입니다.

## 유지되는 1:1 대응 범주
- core.providers
- core.audio.pipeline
- core.sourcing.coupang_scraper
- core.sourcing.keyword_converter
- core.sourcing.marketplace_query_planner
- core.sourcing.pipeline
- core.sourcing.platform_pipeline
- core.sourcing.platform_shorts_searcher
- core.sourcing.platform_video_collector
- core.sourcing.product_searcher
- core.video.CreateFinalVideo
- core.video.reeditor
- core.video.render_integrity
- core.video.video_validator
- core.video.batch.analysis
- core.video.batch.encoder
- core.video.batch.processor
- core.video.batch.subtitle_handler
- core.video.batch.tts_generator
- core.video.batch.tts_speed
- core.video.batch.whisper_analyzer
- processors.subtitle_detector
- processors.subtitle_processor
- processors.tts_processor
- processors.video_composer
- prompts.audio_analysis
- prompts.subtitle_split
- prompts.translation
- prompts.video_analysis
- prompts.video_validation
- managers.settings_manager
- ui.panels.settings_tab
- ui.panels.upload_panel
- browser-extension

## v1.23 소싱 수정
| 문제 | v1.23 구현 |
|---|---|
| 검색창은 열리지만 실제 결과 로딩 전 수집 종료 | DOM/링크 수가 안정될 때까지 적응형 대기 |
| 한꺼번에 많은 검색 탭 생성 | 플랫폼 동시 작업 2개로 제한 |
| 직접 검색 0건 | 검색어 자동 변경 후 Google site 검색 폴백 |
| Google 검색 결과가 redirect URL이라 필터 탈락 | 실제 플랫폼 URL로 unwrap |
| 한국어 상품명이 중국 플랫폼에서 그대로 검색됨 | 모델/브랜드 식별 토큰 우선 + 플랫폼별 보조어 + Gemini 다국어 확장 |
| 수집 0건인데 유사도 실패로 표시 | 수집 0건은 유사도 계산하지 않고 별도 오류 표시 |
| 원인 파악 불가 | 플랫폼별 `수집 건수 / 정상 / 결과 없음 / 로그인 필요 / 접근 차단 / 오류` 표시 |

## 실제 연결 경로
`상품 URL → 상품 분석 → 식별 토큰 추출 → 플랫폼별 검색계획 → 적응형 브라우저 수집 → URL 정규화 → 플랫폼별 진단 → 후보 랭킹 → 유사도 기준 → 다운로드 → 기존 v1.22 전체 영상 제작 파이프라인`
