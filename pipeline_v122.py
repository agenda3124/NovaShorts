from __future__ import annotations

import json
import re
import time
from pathlib import Path

from engine import lnk_bio_add, log, media_duration, watermark, youtube_upload
from features import make_thumbnail
from parity_v122 import (
    CreateFinalVideo,
    audio_analysis,
    batch_analysis,
    encoder,
    reeditor,
    render_integrity,
    subtitle_detector,
    subtitle_processor,
    translation,
    tts_processor,
    video_analysis,
    video_validation,
    video_validator,
    whisper_analyzer,
)
from pipeline_v120 import _emit, generate_korean_script, generate_publish_metadata


def _safe_json(path: Path, value):
    try:
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    except Exception as e:
        log('json write: ' + str(e))


def _validate_sources(sources: list[str]):
    errors = []
    for p in sources:
        chk = video_validator(p)
        if not chk.get('ok'):
            errors.append(Path(p).name + ': ' + '; '.join(chk.get('errors') or []))
    if errors:
        raise RuntimeError('입력 영상 검증 실패\n' + '\n'.join(errors[:10]))


def run_processing_pipeline_v122(
    source_videos: list[str],
    product: dict,
    settings,
    product_url: str = '',
    manual_script: str = '',
    progress=None,
) -> dict:
    """Full v1.22 clean-room production path mapped to every evidenced SSMaker stage."""
    sources = [str(Path(x)) for x in source_videos if x and Path(x).exists()]
    if not sources:
        raise RuntimeError('소스 영상이 없습니다.')
    _validate_sources(sources)

    base_out = Path(settings.output_folder)
    run_dir = base_out / ('NovaShorts_' + time.strftime('%Y%m%d_%H%M%S'))
    run_dir.mkdir(parents=True, exist_ok=True)
    product = dict(product or {})
    if product_url and not product.get('url'):
        product['url'] = product_url

    _emit(progress, 1, '전체 제작 파이프라인 시작')

    normalized: list[str] = []
    detectors: list[dict] = []
    working_sources: list[str] = []
    source_analyses: list[dict] = []
    transcripts: list[dict] = []
    translated_parts: list[str] = []

    # 1. batch.encoder + video_validator
    for i, src in enumerate(sources):
        norm = run_dir / f'00_normalized_{i:02d}.mp4'
        encoder(src, str(norm), vertical=False, progress=progress)
        normalized.append(str(norm))
    _emit(progress, 8, f'입력 영상 {len(normalized)}개 정규화 완료')

    # 2. subtitle_detector / subtitle_processor, independently per source.
    for i, src in enumerate(normalized):
        det_dir = run_dir / f'ocr_{i:02d}'
        detector = {'detected': False, 'count': 0, 'chinese_count': 0, 'rows': []}
        try:
            detector = subtitle_detector(src, str(det_dir), progress)
        except Exception as e:
            log('subtitle detector nonfatal: ' + str(e))
        detectors.append(detector)
        current = src
        if bool(getattr(settings, 'pipeline_remove_subtitles', True)) and detector.get('detected'):
            cleaned = run_dir / f'01_subtitle_clean_{i:02d}.mp4'
            try:
                current = subtitle_processor(src, str(cleaned), detector, progress)
            except Exception as e:
                log('subtitle processor nonfatal: ' + str(e))
        working_sources.append(str(current))
    _safe_json(run_dir / 'subtitle_detection.json', detectors)

    # 3. whisper_analyzer + audio_analysis + video_analysis.
    for i, src in enumerate(working_sources):
        transcript = {'language': '', 'segments': [], 'text': ''}
        try:
            transcript = whisper_analyzer(src, getattr(settings, 'whisper_model', 'base'), progress)
        except Exception as e:
            log('whisper nonfatal: ' + str(e))
            rows = (detectors[i] or {}).get('rows') or []
            transcript['text'] = ' '.join(str(x.get('text') or '') for x in rows)
        transcripts.append(transcript)

        va = {}
        if bool(getattr(settings, 'pipeline_video_analysis', True)):
            try:
                va = video_analysis(src, detectors[i], progress)
            except Exception as e:
                log('video analysis nonfatal: ' + str(e))
        aa = audio_analysis(transcript, (va or {}).get('media') or {}) if bool(getattr(settings, 'pipeline_audio_analysis', True)) else {}
        source_analyses.append({'video': va, 'audio': aa})

        text = str(transcript.get('text') or '')
        if bool(getattr(settings, 'pipeline_translate_source', True)):
            text = translation(text, str(transcript.get('language') or ''), getattr(settings, 'gemini_api_key', ''))
        if text:
            translated_parts.append(text)

    _safe_json(run_dir / 'transcripts.json', transcripts)
    _safe_json(run_dir / 'analysis.json', source_analyses)
    _emit(progress, 42, '영상·음성 분석 완료')

    # 4. Korean script. Prepared-material mode can deliberately override AI writing.
    analysis_text = ' '.join(translated_parts).strip()
    script = re.sub(r'\s+', ' ', str(manual_script or '')).strip()
    if script:
        _emit(progress, 47, '준비한 한국어 대본 사용')
    else:
        script = generate_korean_script(product, analysis_text, getattr(settings, 'gemini_api_key', ''), progress)
    if not script:
        raise RuntimeError('한국어 대본을 생성하지 못했습니다.')
    (run_dir / 'script.txt').write_text(script, encoding='utf-8')

    # 5. prompts.video_validation before voice/rendering.
    semantic_validation = {'ok': True, 'warnings': []}
    if bool(getattr(settings, 'pipeline_semantic_validation', True)):
        semantic_validation = video_validation(
            product, analysis_text, script,
            getattr(settings, 'gemini_api_key', '') if bool(getattr(settings, 'pipeline_video_validation_ai', True)) else ''
        )
    _safe_json(run_dir / 'script_validation.json', semantic_validation)
    _emit(progress, 52, '대본 사실성 검증 완료')

    # 6. tts_generator + tts_speed + subtitle_handler / subtitle_split.
    target = float(getattr(settings, 'pipeline_target_seconds', 20) or 20)
    tts = run_dir / '02_tts_fitted.m4a'
    srt = run_dir / '02_korean.srt'
    tts_processor(
        script,
        getattr(settings, 'tts_voice', 'ko-KR-SunHiNeural'),
        getattr(settings, 'tts_rate', '+0%'),
        target if bool(getattr(settings, 'pipeline_auto_tts_speed', True)) else max(1.0, target),
        str(tts), str(srt), progress
    )
    audio_len = media_duration(str(tts)) or target

    # 7. reeditor: use all sources, distribute scene cuts instead of concatenating whole videos.
    edited = run_dir / '03_reedited.mp4'
    if bool(getattr(settings, 'pipeline_auto_cut', True)):
        reeditor(working_sources, str(edited), audio_len, progress)
    else:
        encoder(working_sources[0], str(edited), vertical=True, progress=progress)

    # 8. CreateFinalVideo / video_composer.
    final = run_dir / '04_final_short.mp4'
    CreateFinalVideo(
        str(edited), str(tts), str(final), str(srt),
        bool(getattr(settings, 'pipeline_add_korean_subtitles', True)), progress
    )

    # 9. Watermark remains optional.
    final_media = final
    if bool(getattr(settings, 'watermark_enabled', False)) and str(getattr(settings, 'watermark_text', '') or '').strip():
        wm = run_dir / '05_final_watermark.mp4'
        watermark(str(final), str(settings.watermark_text), str(wm), getattr(settings, 'watermark_position', 'bottom_right'))
        final_media = wm
        _emit(progress, 86, '워터마크 적용')

    # 10. render_integrity + video_validator, and repair when necessary.
    integrity = {'ok': True, 'path': str(final_media), 'errors': []}
    if bool(getattr(settings, 'pipeline_validate_output', True)):
        repair_path = run_dir / '06_final_repaired.mp4'
        integrity = render_integrity(
            str(final_media), str(repair_path) if bool(getattr(settings, 'pipeline_render_repair', True)) else None, progress
        )
        if integrity.get('repaired') and integrity.get('ok'):
            final_media = Path(str(integrity.get('path') or repair_path))
        if not integrity.get('ok'):
            raise RuntimeError('최종 영상 검증 실패: ' + '; '.join(integrity.get('errors') or []))
    _safe_json(run_dir / 'render_integrity.json', integrity)

    # 11. Thumbnail and publishing metadata.
    thumb = ''
    if bool(getattr(settings, 'pipeline_auto_thumbnail', True)):
        thumb_path = run_dir / 'thumbnail.jpg'
        first = re.split(r'(?<=[.!?요다])\s+', script.strip())[0][:28] if script.strip() else str(product.get('title') or '')[:28]
        try:
            thumb = make_thumbnail(str(final_media), first, str(thumb_path))
            _emit(progress, 91, '썸네일 생성')
        except Exception as e:
            log('thumbnail nonfatal: ' + str(e))

    metadata = generate_publish_metadata(product, script, getattr(settings, 'gemini_api_key', ''))
    _safe_json(run_dir / 'publish_metadata.json', metadata)

    # 12. External actions are still explicit opt-ins in settings.
    youtube_id = ''
    if bool(getattr(settings, 'youtube_auto_upload', False)):
        secret = str(getattr(settings, 'youtube_client_secret_file', '') or '')
        if secret and Path(secret).exists():
            _emit(progress, 94, 'YouTube 업로드')
            youtube_id = youtube_upload(
                str(final_media), secret, metadata['title'], metadata['description'], metadata['tags'],
                getattr(settings, 'youtube_privacy', 'private') or 'private'
            )
            if youtube_id and bool(getattr(settings, 'youtube_comment_enabled', False)):
                try:
                    from engine import youtube_comment
                    comment_text = str(getattr(settings, 'youtube_comment_prompt', '') or metadata.get('comment') or product.get('url') or '')
                    if comment_text:
                        youtube_comment(youtube_id, secret, comment_text)
                except Exception as e:
                    log('youtube comment nonfatal: ' + str(e))

    link_result = None
    if bool(getattr(settings, 'lnkbio_auto_publish', False)):
        cid = str(getattr(settings, 'lnkbio_client_id', '') or '')
        sec = str(getattr(settings, 'lnkbio_client_secret', '') or '')
        url = str(product.get('url') or product_url or '')
        if cid and sec and url:
            _emit(progress, 97, 'Lnk.Bio 상품 링크 생성')
            try:
                link_result = lnk_bio_add(cid, sec, str(product.get('title') or metadata['title'])[:80], url)
            except Exception as e:
                log('Lnk.Bio nonfatal: ' + str(e))

    result = {
        'run_dir': str(run_dir),
        'sources': sources,
        'working_sources': working_sources,
        'subtitle_detection': detectors,
        'transcripts': transcripts,
        'analysis': source_analyses,
        'translated_source_text': analysis_text,
        'script': script,
        'script_validation': semantic_validation,
        'tts': str(tts),
        'subtitle_srt': str(srt),
        'edited_video': str(edited),
        'final_video': str(final_media),
        'integrity': integrity,
        'thumbnail': str(thumb or ''),
        'metadata': metadata,
        'youtube_id': youtube_id,
        'lnkbio': link_result,
    }
    _safe_json(run_dir / 'result.json', result)
    _emit(progress, 100, '전체 제작 완료 · 검증 통과')
    return result
