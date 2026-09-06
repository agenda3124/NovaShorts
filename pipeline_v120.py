from __future__ import annotations

import asyncio
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Callable

import requests

from engine import (
    app_dir,
    generate_tts,
    lnk_bio_add,
    log,
    media_duration,
    tool,
    watermark,
    youtube_upload,
)
from features import auto_cut_vertical, make_thumbnail

Progress = Callable[[int, str], None]


def _emit(cb: Progress | None, pct: int, msg: str):
    if cb:
        cb(max(0, min(100, int(pct))), msg)
    log('[pipeline] ' + msg)


def _run(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    p = subprocess.run(args, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if check and p.returncode:
        raise RuntimeError((p.stderr or p.stdout or '외부 프로세스 오류')[-3000:])
    return p


def _ff(args: list[str], check: bool = True):
    ff = tool('ffmpeg')
    if not ff:
        raise RuntimeError('FFmpeg를 찾을 수 없습니다.')
    return _run([ff] + args, check=check)


def _safe_name(text: str, default='shorts') -> str:
    x = re.sub(r'[\\/:*?"<>|\r\n]+', ' ', str(text or '')).strip()
    x = re.sub(r'\s+', ' ', x)[:60]
    return x or default


def _gemini_text(prompt: str, key: str, timeout=45) -> str:
    if not key:
        return ''
    r = requests.post(
        'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent',
        params={'key': key},
        json={'contents': [{'parts': [{'text': prompt}]}]},
        timeout=timeout,
    )
    r.raise_for_status()
    return r.json()['candidates'][0]['content']['parts'][0]['text'].strip()


def smart_subtitle_remove(video: str, output: str, progress: Progress | None = None, roi_top=0.52) -> str:
    """Remove lower-frame burned-in text with text-mask + temporal inpainting.

    It is intentionally conservative: only the lower portion of the image is processed,
    and only text-like connected components are masked. Audio is remuxed from the source.
    """
    try:
        import cv2
        import numpy as np
    except Exception as e:
        raise RuntimeError('스마트 자막 제거에 OpenCV가 필요합니다: ' + str(e))

    src = str(video)
    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(src)
    if not cap.isOpened():
        raise RuntimeError('영상 열기에 실패했습니다.')
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if width <= 0 or height <= 0:
        cap.release()
        raise RuntimeError('영상 해상도를 확인할 수 없습니다.')

    with tempfile.TemporaryDirectory(prefix='novashorts_inpaint_') as td:
        silent = Path(td) / 'silent.mp4'
        writer = cv2.VideoWriter(str(silent), cv2.VideoWriter_fourcc(*'mp4v'), fps, (width, height))
        if not writer.isOpened():
            cap.release()
            raise RuntimeError('자막 제거 임시 영상 작성에 실패했습니다.')

        y0 = max(0, min(height - 2, int(height * roi_top)))
        prev_mask = None
        idx = 0
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            roi = frame[y0:height, :]
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            # Text strokes: edge response + bright/dark local contrast.
            edges = cv2.Canny(gray, 55, 165)
            bright = cv2.threshold(gray, 205, 255, cv2.THRESH_BINARY)[1]
            dark = cv2.threshold(gray, 48, 255, cv2.THRESH_BINARY_INV)[1]
            local = cv2.bitwise_or(bright, dark)
            local = cv2.bitwise_and(local, cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1))
            mask0 = cv2.bitwise_or(edges, local)
            mask0 = cv2.morphologyEx(mask0, cv2.MORPH_CLOSE, np.ones((3, 9), np.uint8), iterations=1)
            mask0 = cv2.dilate(mask0, np.ones((5, 11), np.uint8), iterations=1)

            mask = np.zeros_like(mask0)
            contours, _ = cv2.findContours(mask0, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            rh, rw = mask.shape[:2]
            for c in contours:
                x, y, w, h = cv2.boundingRect(c)
                area = w * h
                if h < max(7, int(height * 0.006)) or h > int(height * 0.09):
                    continue
                if w < 6 or w > int(rw * 0.88):
                    continue
                if area < 70:
                    continue
                # Subtitle-like components are usually horizontal and not huge blocks.
                if w / max(1, h) < 0.45 and area < 400:
                    continue
                cv2.rectangle(mask, (max(0, x - 3), max(0, y - 3)), (min(rw - 1, x + w + 3), min(rh - 1, y + h + 3)), 255, -1)

            # Stabilize masks frame-to-frame so letters do not flash back.
            if prev_mask is not None:
                mask = cv2.bitwise_or(mask, cv2.bitwise_and(prev_mask, cv2.dilate(mask, np.ones((9, 15), np.uint8))))
            prev_mask = mask.copy()
            coverage = float(cv2.countNonZero(mask)) / float(mask.size or 1)
            if 0.0005 <= coverage <= 0.22:
                cleaned = cv2.inpaint(roi, mask, 3, cv2.INPAINT_TELEA)
                frame[y0:height, :] = cleaned
            writer.write(frame)
            idx += 1
            if idx % max(1, int(fps * 1.5)) == 0:
                pct = int(idx / total * 100) if total else 0
                _emit(progress, min(35, 8 + pct // 4), f'자막 제거 {pct}%')

        cap.release()
        writer.release()
        # Restore original audio while transcoding the temporary mp4v stream to H.264.
        _ff([
            '-y', '-i', str(silent), '-i', src,
            '-map', '0:v:0', '-map', '1:a?',
            '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20',
            '-c:a', 'aac', '-b:a', '192k', '-shortest', str(out)
        ])
    return str(out)


def _whisper_model_ref(model_name='base') -> str:
    local = app_dir() / 'models' / f'whisper-{model_name}'
    if local.exists():
        return str(local)
    return model_name


def transcribe_video(video: str, model_name='base', progress: Progress | None = None) -> dict:
    try:
        from faster_whisper import WhisperModel
    except Exception as e:
        raise RuntimeError('음성 분석 모듈(faster-whisper)을 불러올 수 없습니다: ' + str(e))
    _emit(progress, 38, '영상 음성 분석 시작')
    model = WhisperModel(_whisper_model_ref(model_name), device='cpu', compute_type='int8')
    segments, info = model.transcribe(video, beam_size=3, vad_filter=True, word_timestamps=False)
    rows = []
    for i, seg in enumerate(segments):
        txt = (seg.text or '').strip()
        if txt:
            rows.append({'start': float(seg.start), 'end': float(seg.end), 'text': txt})
        if i and i % 5 == 0:
            _emit(progress, min(48, 38 + i), f'음성 구간 분석 {i}개')
    transcript = ' '.join(x['text'] for x in rows).strip()
    return {'language': getattr(info, 'language', '') or '', 'segments': rows, 'text': transcript}


def fallback_script(product: dict, transcript: str) -> str:
    title = str(product.get('title') or '이 제품').strip()
    core = re.sub(r'\s+', ' ', transcript or '').strip()
    if core:
        core = core[:240]
        return f"잠깐, {title} 이거 영상으로 보니까 생각보다 더 신기한데요. {core} 직접 쓰는 장면을 보니까 왜 사람들이 찾는지 알겠더라고요. 필요한 분들은 제품명 꼭 확인해보세요."
    return f"잠깐, {title} 이거 그냥 사진만 보고 넘길 뻔했는데요. 실제 사용하는 장면을 보니까 어떻게 쓰는지 바로 이해되더라고요. 복잡하게 설명할 필요 없이 영상으로 보면 차이가 확실해요. 궁금했던 분들은 제품명 꼭 확인해보세요."


def generate_korean_script(product: dict, transcript: str, gemini_key: str, progress: Progress | None = None) -> str:
    title = str(product.get('title') or '').strip()
    brand = str(product.get('brand') or '').strip()
    model = str(product.get('model') or '').strip()
    _emit(progress, 50, '한국어 쇼츠 대본 생성')
    if not gemini_key:
        return fallback_script(product, transcript)
    prompt = f'''한국 쇼츠/릴스용 18~25초 대본을 작성하세요.
반드시 실제 사용자가 말하는 자연스러운 한국어 1인칭 문장으로 쓰고 광고 문구처럼 쓰지 마세요.
첫 1~2문장은 강한 궁금증 훅, 중간은 영상에서 확인 가능한 사용 장면/특징, 마지막은 짧은 확인 유도로 끝내세요.
제공된 영상/상품 정보 밖의 효능, 가격, 수치, 과장 사실을 만들지 마세요.
출력은 대본만, 220~330자.
상품명: {title}
브랜드: {brand}
모델: {model}
영상 음성 전사: {transcript[:3500]}'''
    try:
        text = _gemini_text(prompt, gemini_key)
        text = re.sub(r'^```.*?\n|```$', '', text, flags=re.S).strip()
        return text or fallback_script(product, transcript)
    except Exception as e:
        log('script gemini fallback: ' + str(e))
        return fallback_script(product, transcript)


async def _tts_stream(text: str, voice: str, rate: str, audio_out: str, srt_out: str):
    import edge_tts
    communicator = edge_tts.Communicate(text, voice, rate=rate)
    submaker = edge_tts.SubMaker()
    with open(audio_out, 'wb') as af:
        async for chunk in communicator.stream():
            if chunk['type'] == 'audio':
                af.write(chunk['data'])
            elif chunk['type'] in ('WordBoundary', 'SentenceBoundary'):
                try:
                    submaker.feed(chunk)
                except Exception:
                    pass
    try:
        srt = submaker.get_srt()
    except Exception:
        srt = ''
    Path(srt_out).write_text(srt or '', encoding='utf-8')


def generate_tts_bundle(text: str, voice: str, rate: str, audio_out: str, srt_out: str, progress: Progress | None = None) -> tuple[str, str]:
    _emit(progress, 55, '한국어 TTS 생성')
    try:
        asyncio.run(_tts_stream(text, voice, rate, audio_out, srt_out))
    except Exception as e:
        log('tts stream fallback: ' + str(e))
        generate_tts(text, voice, audio_out, rate)
        Path(srt_out).write_text('', encoding='utf-8')
    return audio_out, srt_out


def _escape_subtitle_path(path: str) -> str:
    p = str(Path(path).resolve()).replace('\\', '/')
    p = p.replace(':', '\\:').replace("'", "\\'")
    return p


def compose_final(video: str, audio: str, output: str, srt: str | None = None, burn_subtitles=True, progress: Progress | None = None) -> str:
    _emit(progress, 78, '1080×1920 최종 렌더')
    vf = 'scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black'
    if burn_subtitles and srt and Path(srt).exists() and Path(srt).stat().st_size > 10:
        sp = _escape_subtitle_path(srt)
        vf += ",subtitles='" + sp + "':force_style='FontName=Malgun Gothic,FontSize=20,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=3,Shadow=0,Alignment=2,MarginV=145'"
    _ff([
        '-y', '-stream_loop', '-1', '-i', video, '-i', audio,
        '-map', '0:v:0', '-map', '1:a:0', '-shortest',
        '-vf', vf, '-c:v', 'libx264', '-preset', 'medium', '-crf', '20',
        '-c:a', 'aac', '-b:a', '192k', output
    ])
    return output


def generate_publish_metadata(product: dict, script: str, gemini_key: str) -> dict:
    title = str(product.get('title') or '제품 영상').strip()
    fallback = {
        'title': (title[:68] + (' #shorts' if '#shorts' not in title.lower() else ''))[:95],
        'description': script + '\n\n#shorts #제품영상',
        'tags': ['shorts', '제품영상', _safe_name(title, '상품')[:25]],
        'comment': str(product.get('url') or ''),
    }
    if not gemini_key:
        return fallback
    prompt = f'''다음 상품 쇼츠의 YouTube 메타데이터를 JSON으로만 작성하세요.
키는 title, description, tags, comment. tags는 문자열 배열.
과장/허위 사실 금지, 제목 70자 이내, 설명은 자연스러운 한국어.
상품: {title}
대본: {script[:1500]}'''
    try:
        raw = _gemini_text(prompt, gemini_key)
        raw = re.sub(r'^```(?:json)?|```$', '', raw.strip(), flags=re.M).strip()
        data = json.loads(raw)
        return {
            'title': str(data.get('title') or fallback['title'])[:95],
            'description': str(data.get('description') or fallback['description']),
            'tags': [str(x)[:40] for x in (data.get('tags') or fallback['tags'])][:15],
            'comment': str(data.get('comment') or fallback['comment']),
        }
    except Exception as e:
        log('metadata fallback: ' + str(e))
        return fallback


def run_processing_pipeline(source_video: str, product: dict, settings, product_url='', progress: Progress | None = None) -> dict:
    """Run every confirmed local production stage in sequence.

    External publication is opt-in through settings.youtube_auto_upload / lnkbio_auto_publish.
    """
    src = Path(source_video)
    if not src.exists():
        raise RuntimeError('소스 영상 파일이 없습니다.')
    base_out = Path(settings.output_folder)
    run_dir = base_out / ('NovaShorts_' + time.strftime('%Y%m%d_%H%M%S'))
    run_dir.mkdir(parents=True, exist_ok=True)
    product = dict(product or {})
    if product_url and not product.get('url'):
        product['url'] = product_url

    _emit(progress, 2, '원클릭 자동 제작 시작')
    working = src

    # 1) OCR scan for diagnostics / reference.
    ocr_rows = []
    try:
        from engine import subtitle_scan
        ocr_rows = subtitle_scan(str(working), str(run_dir / 'ocr'), lambda m: _emit(progress, 6, m))
        (run_dir / 'ocr_result.json').write_text(json.dumps(ocr_rows, ensure_ascii=False, indent=2), encoding='utf-8')
    except Exception as e:
        log('ocr scan nonfatal: ' + str(e))

    # 2) Burned-in subtitle removal.
    if bool(getattr(settings, 'pipeline_remove_subtitles', True)):
        cleaned = run_dir / '01_subtitle_clean.mp4'
        try:
            smart_subtitle_remove(str(working), str(cleaned), progress)
            working = cleaned
        except Exception as e:
            # Keep the pipeline alive and record the fallback instead of aborting all later stages.
            log('smart subtitle remove fallback: ' + str(e))

    # 3) Audio/video understanding using bundled Whisper.
    transcript = {'language': '', 'segments': [], 'text': ''}
    try:
        transcript = transcribe_video(str(working), getattr(settings, 'whisper_model', 'base'), progress)
        (run_dir / 'transcript.json').write_text(json.dumps(transcript, ensure_ascii=False, indent=2), encoding='utf-8')
    except Exception as e:
        log('whisper nonfatal: ' + str(e))
        if ocr_rows:
            transcript['text'] = ' '.join(str(x.get('text') or '') for x in ocr_rows)

    # 4) Korean script.
    script = generate_korean_script(product, transcript.get('text', ''), getattr(settings, 'gemini_api_key', ''), progress)
    (run_dir / 'script.txt').write_text(script, encoding='utf-8')

    # 5) TTS + Korean subtitle timing.
    tts = run_dir / '02_tts.mp3'
    srt = run_dir / '02_korean.srt'
    generate_tts_bundle(script, getattr(settings, 'tts_voice', 'ko-KR-SunHiNeural'), getattr(settings, 'tts_rate', '+0%'), str(tts), str(srt), progress)
    audio_len = media_duration(str(tts)) or float(getattr(settings, 'pipeline_target_seconds', 20))

    # 6) Scene-aware/automatic cutting to TTS duration.
    edited = working
    if bool(getattr(settings, 'pipeline_auto_cut', True)):
        cut = run_dir / '03_auto_cut.mp4'
        target = max(6.0, min(60.0, audio_len + 0.15))
        auto_cut_vertical(str(working), str(cut), target_seconds=target, clip_seconds=2.4, progress=lambda m: _emit(progress, 68, m))
        edited = cut

    # 7) 9:16 final render + Korean subtitle overlay.
    final = run_dir / '04_final_short.mp4'
    compose_final(str(edited), str(tts), str(final), str(srt), bool(getattr(settings, 'pipeline_add_korean_subtitles', True)), progress)

    # 8) Watermark.
    final_media = final
    if bool(getattr(settings, 'watermark_enabled', False)) and str(getattr(settings, 'watermark_text', '') or '').strip():
        wm = run_dir / '05_final_watermark.mp4'
        watermark(str(final), str(settings.watermark_text), str(wm), getattr(settings, 'watermark_position', 'bottom_right'))
        final_media = wm
        _emit(progress, 84, '워터마크 적용')

    # 9) Thumbnail.
    thumb = ''
    if bool(getattr(settings, 'pipeline_auto_thumbnail', True)):
        thumb_path = run_dir / 'thumbnail.jpg'
        first = re.split(r'(?<=[.!?요다])\s+', script.strip())[0][:28] if script.strip() else str(product.get('title') or '')[:28]
        try:
            thumb = make_thumbnail(str(final_media), first, str(thumb_path))
            _emit(progress, 88, '썸네일 생성')
        except Exception as e:
            log('thumbnail nonfatal: ' + str(e))

    # 10) Publishing metadata.
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
        else:
            log('YouTube auto upload skipped: client_secret missing')

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
        'source': str(src),
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
    _emit(progress, 100, '원클릭 자동 제작 완료')
    return result
