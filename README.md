# NovaShorts

NovaShorts is a Windows desktop shorts-production studio built from independently reimplemented, user-observed functionality of the analyzed SSMaker v1.5.126 workflow.

This project intentionally excludes the original application's membership, subscription, licensing, and authentication service. External integrations require the user's own credentials/API keys.

## Included feature areas

- Coupang product input and settings
- AI/rule-based sourcing query planning
- Douyin / Xiaohongshu / Kuaishou / TikTok / 1688 sourcing workflow
- Chrome extension bridge on 127.0.0.1:38471
- Candidate collection, similarity scoring and low-score filtering
- yt-dlp video downloading
- OCR/Tesseract subtitle detection helpers
- subtitle cleanup/inpainting workflow
- Edge TTS
- FFmpeg video/audio composition
- subtitle/watermark controls
- batch queue
- YouTube OAuth upload, metadata and optional comment
- X sharing metadata/settings
- Lnk.Bio settings and link publishing helper
- persistent settings, logs, runtime diagnostics and update checks

## Windows build

GitHub Actions builds `NovaShorts.exe` and uploads `NovaShorts_v1.5.zip` as a workflow artifact.
