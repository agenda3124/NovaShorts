from __future__ import annotations

import json
import re
import tempfile
import time
from pathlib import Path

from engine import media_duration, subtitle_scan, watermark, youtube_upload, lnk_bio_add, log
from features import auto_cut_vertical, make_thumbnail
from pipeline_v120 import (
    _emit,
    _ff,
    compose_final,
    generate_korean_script,
    generate_publish_metadata,
    generate_tts_bundle,
    smart_subtitle_remove,
    transcribe_video,
)


def merge_source_videos(videos: list[str], output: str, progress=None) -> str:
    paths = [Path(x) for x in videos if x and Path(x).exists()]
    if not paths:
        raise RuntimeError('사용할 영상 파일이 없습니다.')
    if len(paths) == 1:
        return str(paths[0])
    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='novashorts_merge_') as td:
        td = Path(td)
        normalized = []
        for i, src in enumerate(paths):
            dst = td / f'norm_{i:02d}.mp4'
            vf = 'scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black,fps=30'
            p = _ff([
                '-y', '-i', str(src), '-vf', vf,
                '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '21',
                '-c:a', 'aac', '-ar', '48000', '-ac', '2', '-b:a', '160k',
                str(dst)
            ], check=False)
            if p.returncode:
                _ff([
                    '-y', '-i', str(src), '-vf', vf, '-an',
                    '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '21', str(dst)
                ])
            normalized.append(dst)
            _emit(progress, 10 + int((i + 1) / len(paths) * 8), f'소스 영상 정리 {i+1}/{len(paths)}')
        lst = td / 'concat.txt'
        lst.write_text('\n'.join("file '" + x.as_posix().replace("'", "''") + "'" for x in normalized), encoding='utf-8')
        p = _ff(['-y', '-f', 'concat', '-safe', '0', '-i', str(lst), '-c', 'copy', str(out)], check=False)
        if p.returncode:
            _ff(['-y', '-f', 'concat', '-safe', '0', '-i', str(lst), '-c:v', 'libx264', '-c:a', 'aac', str(out)])
    return str(out)


def run_processing_pipeline_v121(
    source_videos: list[str],
    product: dict,
    settings,
    product_url: str = '',
    manual_script: str = '',
    progress=None,
) -> dict:
    sources = [str(Path(x)) for x in source_videos if x and Path(x).exists()]
    if not sources:
        raise RuntimeError('소스 영상이 없습니다.')
    base_out = Path(settings.output_folder)
    run_dir = base_out / ('NovaShorts_' + time.strftime('%Y%m%d_%H%M%S'))
    run_dir.mkdir(parents=True, exist_ok=True)
    product = dict(product or {})
    if product_url and not product.get('url'):
        product['url'] = product_url

    _emit(progress, 2, '영상 만들기 시작')
    merged = run_dir / '00_source_merged.mp4'
    working = Path(merge_source_videos(sources, str(merged), progress)) if len(sources) > 1 else Path(sources[0])

    ocr_rows = []
    try:
        ocr_rows = subtitle_scan(str(working), str(run_dir / 'ocr'), lambda m: _emit(progress, 20, m))
        (run_dir / 'ocr_result.json').write_text(json.dumps(ocr_rows, ensure_ascii=False, indent=2), encoding='utf-8')
    except Exception as e:
        log('ocr scan nonfatal: ' + str(e))

    if bool(getattr(settings, 'pipeline_remove_subtitles', True)):
        cleaned = run_dir / '01_subtitle_clean.mp4'
        try:
            smart_subtitle_remove(str(working), str(cleaned), progress)
            working = cleaned
        except Exception as e:
            log('smart subtitle remove fallback: ' + str(e))

    transcript = {'language': '', 'segments': [], 'text': ''}
    try:
        transcript = transcribe_video(str(working), getattr(settings, 'whisper_model', 'base'), progress)
        (run_dir / 'transcript.json').write_text(json.dumps(transcript, ensure_ascii=False, indent=2), encoding='utf-8')
    except Exception as e:
        log('whisper nonfatal: ' + str(e))
        if ocr_rows:
            transcript['text'] = ' '.join(str(x.get('text') or '') for x in ocr_rows)

    script = re.sub(r'\s+', ' ', str(manual_script or '')).strip()
    if script:
        _emit(progress, 50, '준비한 대본 사용')
    else:
        script = generate_korean_script(product, transcript.get('text', ''), getattr(settings, 'gemini_api_key', ''), progress)
    (run_dir / 'script.txt').write_text(script, encoding='utf-8')

    tts = run_dir / '02_tts.mp3'
    srt = run_dir / '02_korean.srt'
    generate_tts_bundle(
        script,
        getattr(settings, 'tts_voice', 'ko-KR-SunHiNeural'),
        getattr(settings, 'tts_rate', '+0%'),
        str(tts), str(srt), progress
    )
    audio_len = media_duration(str(tts)) or float(getattr(settings, 'pipeline_target_seconds', 20))

    edited = working
    if bool(getattr(settings, 'pipeline_auto_cut', True)):
        cut = run_dir / '03_auto_cut.mp4'
        target = max(6.0, min(60.0, audio_len + 0.15))
        auto_cut_vertical(str(working), str(cut), target_seconds=target, clip_seconds=2.4, progress=lambda m: _emit(progress, 68, m))
        edited = cut

    final = run_dir / '04_final_short.mp4'
    compose_final(
        str(edited), str(tts), str(final), str(srt),
        bool(getattr(settings, 'pipeline_add_korean_subtitles', True)), progress
    )

    final_media = final
    if bool(getattr(settings, 'watermark_enabled', False)) and str(getattr(settings, 'watermark_text', '') or '').strip():
        wm = run_dir / '05_final_watermark.mp4'
        watermark(str(final), str(settings.watermark_text), str(wm), getattr(settings, 'watermark_position', 'bottom_right'))
        final_media = wm
        _emit(progress, 84, '워터마크 적용')

    thumb = ''
    if bool(getattr(settings, 'pipeline_auto_thumbnail', True)):
        thumb_path = run_dir / 'thumbnail.jpg'
        first = re.split(r'(?<=[.!?요다])\s+', script.strip())[0][:28] if script.strip() else str(product.get('title') or '')[:28]
        try:
            thumb = make_thumbnail(str(final_media), first, str(thumb_path))
            _emit(progress, 88, '썸네일 생성')
        except Exception as e:
            log('thumbnail nonfatal: ' + str(e))

    metadata = generate_publish_metadata(product, script, getattr(settings, 'gemini_api_key', ''))
    (run_dir / 'publish_metadata.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')

    youtube_id = ''
    if bool(getattr(settings, 'youtube_auto_upload', False)):
        secret = str(getattr(settings, 'youtube_client_secret_file', '') or '')
        if secret and Path(secret).exists():
            _emit(progress, 92, 'YouTube 자동 업로드')
            youtube_id = youtube_upload(
                str(final_media), secret, metadata['title'], metadata['description'], metadata['tags'],
                getattr(settings, 'youtube_privacy', 'private') or 'private'
            )

    link_result = None
    if bool(getattr(settings, 'lnkbio_auto_publish', False)):
        cid = str(getattr(settings, 'lnkbio_client_id', '') or '')
        sec = str(getattr(settings, 'lnkbio_client_secret', '') or '')
        url = str(product.get('url') or product_url or '')
        if cid and sec and url:
            _emit(progress, 96, 'Lnk.Bio 상품 링크 생성')
            try:
                link_result = lnk_bio_add(cid, sec, str(product.get('title') or metadata['title'])[:80], url)
            except Exception as e:
                log('Lnk.Bio nonfatal: ' + str(e))

    result = {
        'run_dir': str(run_dir),
        'sources': sources,
        'source': str(working),
        'ocr_count': len(ocr_rows),
        'transcript': transcript,
        'script': script,
        'tts': str(tts),
        'subtitle_srt': str(srt),
        'final_video': str(final_media),
        'thumbnail': str(thumb or ''),
        'metadata': metadata,
        'youtube_id': youtube_id,
        'lnkbio': link_result,
    }
    (run_dir / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    _emit(progress, 100, '영상 만들기 완료')
    return result
