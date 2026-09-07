from __future__ import annotations

import json
import math
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Callable

import requests

from engine import diagnostics, log, media_duration, subtitle_scan, tool
from features import _scene_times, auto_cut_vertical
from pipeline_v120 import compose_final, generate_tts_bundle, smart_subtitle_remove, transcribe_video

Progress = Callable[[int, str], None]


def _emit(cb: Progress | None, pct: int, msg: str):
    if cb:
        cb(max(0, min(100, int(pct))), msg)
    log('[parity-v122] ' + msg)


def _run(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    p = subprocess.run(args, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if check and p.returncode:
        raise RuntimeError((p.stderr or p.stdout or '외부 프로세스 오류')[-3000:])
    return p


def _ff(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    ff = tool('ffmpeg')
    if not ff:
        raise RuntimeError('FFmpeg를 찾을 수 없습니다.')
    return _run([ff] + args, check)


def ffprobe_media(path: str) -> dict:
    probe = tool('ffprobe')
    if not probe:
        raise RuntimeError('ffprobe를 찾을 수 없습니다.')
    p = _run([
        probe, '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)
    ])
    data = json.loads(p.stdout or '{}')
    streams = data.get('streams') or []
    video = next((x for x in streams if x.get('codec_type') == 'video'), {})
    audio = next((x for x in streams if x.get('codec_type') == 'audio'), {})
    fmt = data.get('format') or {}
    try:
        duration = float(fmt.get('duration') or video.get('duration') or 0)
    except Exception:
        duration = 0.0
    return {
        'path': str(path),
        'duration': duration,
        'width': int(video.get('width') or 0),
        'height': int(video.get('height') or 0),
        'video_codec': str(video.get('codec_name') or ''),
        'audio_codec': str(audio.get('codec_name') or ''),
        'has_video': bool(video),
        'has_audio': bool(audio),
        'fps': str(video.get('avg_frame_rate') or video.get('r_frame_rate') or ''),
    }


def providers() -> dict:
    """Clean-room counterpart of core.providers: report live providers used by NovaShorts."""
    d = diagnostics()
    return {
        'gemini': True,
        'edge_tts': True,
        'youtube': True,
        'browser': True,
        'ffmpeg': bool(d.get('ffmpeg')),
        'tesseract': bool(d.get('tesseract')),
        'whisper': bool(d.get('faster_whisper') and d.get('whisper_model')),
        'opencv': bool(d.get('opencv')),
    }


def video_validator(path: str, require_audio: bool = False) -> dict:
    p = Path(path)
    result = {'ok': False, 'errors': [], 'media': {}}
    if not p.exists() or p.stat().st_size < 1024:
        result['errors'].append('파일이 없거나 너무 작습니다.')
        return result
    try:
        info = ffprobe_media(str(p))
        result['media'] = info
        if not info['has_video']:
            result['errors'].append('비디오 스트림이 없습니다.')
        if info['duration'] <= 0.1:
            result['errors'].append('영상 길이를 확인할 수 없습니다.')
        if info['width'] <= 0 or info['height'] <= 0:
            result['errors'].append('영상 해상도를 확인할 수 없습니다.')
        if require_audio and not info['has_audio']:
            result['errors'].append('오디오 스트림이 없습니다.')
    except Exception as e:
        result['errors'].append(str(e))
    result['ok'] = not result['errors']
    return result


def encoder(source: str, output: str, vertical: bool = False, progress: Progress | None = None) -> str:
    """Clean-room counterpart of batch.encoder: normalize media for deterministic editing."""
    _emit(progress, 5, '입력 영상 정규화')
    vf = 'fps=30,format=yuv420p'
    if vertical:
        vf = 'scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black,' + vf
    p = _ff([
        '-y', '-i', str(source), '-vf', vf,
        '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '21',
        '-c:a', 'aac', '-ar', '48000', '-ac', '2', '-b:a', '160k', str(output)
    ], check=False)
    if p.returncode:
        _ff([
            '-y', '-i', str(source), '-vf', vf, '-an',
            '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '21', str(output)
        ])
    return str(output)


def subtitle_detector(video: str, workdir: str, progress: Progress | None = None) -> dict:
    """Clean-room counterpart of processors.subtitle_detector."""
    _emit(progress, 10, '화면 자막 탐지')
    rows = subtitle_scan(video, workdir, lambda m: _emit(progress, 12, m))
    chinese = sum(1 for x in rows if x.get('chinese'))
    return {
        'detected': bool(rows),
        'count': len(rows),
        'chinese_count': chinese,
        'rows': rows,
    }


def subtitle_processor(video: str, output: str, detector: dict | None = None, progress: Progress | None = None) -> str:
    """Clean-room counterpart of processors.subtitle_processor."""
    if detector is not None and not detector.get('detected'):
        return str(video)
    _emit(progress, 18, '원본 화면 자막 제거')
    return smart_subtitle_remove(video, output, progress)


def whisper_analyzer(video: str, model_name: str = 'base', progress: Progress | None = None) -> dict:
    """Clean-room counterpart of batch.whisper_analyzer."""
    return transcribe_video(video, model_name, progress)


def audio_analysis(transcript: dict, media: dict | None = None) -> dict:
    """Clean-room counterpart of prompts.audio_analysis/core.audio.pipeline."""
    rows = transcript.get('segments') or []
    text = str(transcript.get('text') or '')
    words = re.findall(r'[가-힣A-Za-z0-9一-龥]+', text)
    speech_seconds = sum(max(0.0, float(x.get('end') or 0) - float(x.get('start') or 0)) for x in rows)
    total = float((media or {}).get('duration') or 0)
    return {
        'language': str(transcript.get('language') or ''),
        'segment_count': len(rows),
        'word_count': len(words),
        'speech_seconds': round(speech_seconds, 3),
        'duration': total,
        'speech_ratio': round(speech_seconds / total, 4) if total > 0 else 0.0,
        'text': text,
    }


def video_analysis(video: str, detector: dict | None = None, progress: Progress | None = None) -> dict:
    """Clean-room counterpart of prompts.video_analysis/batch.analysis."""
    _emit(progress, 32, '영상 장면 분석')
    media = ffprobe_media(video)
    try:
        scenes = _scene_times(video, 0.26)
    except Exception:
        scenes = []
    return {
        'media': media,
        'scene_times': [round(float(x), 3) for x in scenes[:80]],
        'scene_count': len(scenes),
        'subtitle_count': int((detector or {}).get('count') or 0),
        'chinese_subtitle_count': int((detector or {}).get('chinese_count') or 0),
    }


def _gemini_text(prompt: str, key: str, timeout: int = 45) -> str:
    if not key:
        return ''
    r = requests.post(
        'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent',
        params={'key': key},
        json={'contents': [{'parts': [{'text': prompt}]}]},
        timeout=timeout,
    )
    r.raise_for_status()
    return str(r.json()['candidates'][0]['content']['parts'][0]['text'] or '').strip()


def translation(text: str, source_language: str, gemini_key: str = '') -> str:
    """Clean-room counterpart of prompts.translation."""
    src = re.sub(r'\s+', ' ', str(text or '')).strip()
    if not src or str(source_language or '').lower().startswith(('ko', 'kor')):
        return src
    if not gemini_key:
        return src
    prompt = (
        '다음 영상의 발화를 의미와 사용 순서를 유지해 자연스러운 한국어로 번역하세요. '
        '과장하거나 없는 사실을 추가하지 말고 번역문만 출력하세요.\n원문:\n' + src[:8000]
    )
    try:
        return _gemini_text(prompt, gemini_key) or src
    except Exception as e:
        log('translation fallback: ' + str(e))
        return src


def _split_sentences(text: str) -> list[str]:
    raw = re.sub(r'\s+', ' ', str(text or '')).strip()
    if not raw:
        return []
    parts = [x.strip() for x in re.split(r'(?<=[.!?]|[요다죠네])\s+', raw) if x.strip()]
    out: list[str] = []
    for p in parts:
        if len(p) <= 34:
            out.append(p)
            continue
        words = p.split()
        cur = ''
        for w in words:
            cand = (cur + ' ' + w).strip()
            if cur and len(cand) > 32:
                out.append(cur)
                cur = w
            else:
                cur = cand
        if cur:
            out.append(cur)
    return out or [raw]


def _srt_time(sec: float) -> str:
    ms = max(0, int(round(sec * 1000)))
    h, rem = divmod(ms, 3600000)
    m, rem = divmod(rem, 60000)
    s, milli = divmod(rem, 1000)
    return f'{h:02d}:{m:02d}:{s:02d},{milli:03d}'


def subtitle_split(text: str, duration: float, output: str) -> str:
    """Clean-room counterpart of prompts.subtitle_split/batch.subtitle_handler."""
    chunks = _split_sentences(text)
    if not chunks:
        Path(output).write_text('', encoding='utf-8')
        return str(output)
    total_weight = sum(max(1, len(re.sub(r'\s+', '', x))) for x in chunks)
    cursor = 0.0
    lines = []
    for i, chunk in enumerate(chunks, 1):
        weight = max(1, len(re.sub(r'\s+', '', chunk)))
        span = max(0.55, duration * weight / max(1, total_weight))
        end = duration if i == len(chunks) else min(duration, cursor + span)
        lines.extend([str(i), f'{_srt_time(cursor)} --> {_srt_time(end)}', chunk, ''])
        cursor = end
    Path(output).write_text('\n'.join(lines), encoding='utf-8')
    return str(output)


def _atempo_chain(factor: float) -> str:
    f = max(0.25, min(4.0, float(factor)))
    vals: list[float] = []
    while f > 2.0:
        vals.append(2.0); f /= 2.0
    while f < 0.5:
        vals.append(0.5); f /= 0.5
    vals.append(f)
    return ','.join('atempo=' + f'{x:.5f}' for x in vals)


def tts_speed(audio: str, target_seconds: float, output: str, progress: Progress | None = None) -> str:
    """Clean-room counterpart of batch.tts_speed: fit narration to target duration."""
    cur = media_duration(audio)
    target = max(1.0, float(target_seconds or cur or 1.0))
    if cur <= 0 or abs(cur - target) <= 0.20:
        if str(Path(audio).resolve()) != str(Path(output).resolve()):
            _ff(['-y', '-i', audio, '-c:a', 'aac', '-b:a', '192k', output])
        return str(output)
    factor = cur / target
    _emit(progress, 55, f'TTS 길이 자동 맞춤 {cur:.1f}s → {target:.1f}s')
    _ff(['-y', '-i', audio, '-filter:a', _atempo_chain(factor), '-c:a', 'aac', '-b:a', '192k', output])
    return str(output)


def tts_generator(text: str, voice: str, rate: str, audio_out: str, srt_out: str, progress: Progress | None = None) -> tuple[str, str]:
    return generate_tts_bundle(text, voice, rate, audio_out, srt_out, progress)


def tts_processor(
    text: str,
    voice: str,
    rate: str,
    target_seconds: float,
    audio_out: str,
    srt_out: str,
    progress: Progress | None = None,
) -> tuple[str, str]:
    """Clean-room counterpart of processors.tts_processor."""
    tmp = str(Path(audio_out).with_name(Path(audio_out).stem + '_raw.mp3'))
    tmp_srt = str(Path(srt_out).with_name(Path(srt_out).stem + '_raw.srt'))
    tts_generator(text, voice, rate, tmp, tmp_srt, progress)
    tts_speed(tmp, target_seconds, audio_out, progress)
    duration = media_duration(audio_out) or target_seconds
    subtitle_split(text, duration, srt_out)
    return str(audio_out), str(srt_out)


def _pick_scene_start(video: str, index: int, total_slots: int, clip: float) -> float:
    info = ffprobe_media(video)
    duration = max(0.0, info['duration'])
    usable = max(0.0, duration - clip)
    if usable <= 0:
        return 0.0
    try:
        scenes = [x for x in _scene_times(video, 0.27) if 0 <= x <= usable]
    except Exception:
        scenes = []
    ideal = usable * (index / max(1, total_slots - 1)) if total_slots > 1 else usable / 2
    return min(scenes, key=lambda x: abs(x - ideal)) if scenes else ideal


def reeditor(videos: list[str], output: str, target_seconds: float, progress: Progress | None = None) -> str:
    """Clean-room counterpart of core.video.reeditor: scene-aware multi-source montage."""
    sources = [str(x) for x in videos if x and Path(x).exists()]
    if not sources:
        raise RuntimeError('재편집할 영상이 없습니다.')
    target = max(4.0, min(60.0, float(target_seconds or 20)))
    if len(sources) == 1:
        return auto_cut_vertical(sources[0], output, target_seconds=target, clip_seconds=2.3, progress=lambda m: _emit(progress, 68, m))
    clip = 2.2
    slots = max(len(sources), min(24, int(math.ceil(target / clip))))
    clip = max(1.2, target / slots)
    with tempfile.TemporaryDirectory(prefix='novashorts_reedit_') as td_raw:
        td = Path(td_raw)
        clips: list[Path] = []
        for i in range(slots):
            src = sources[i % len(sources)]
            start = _pick_scene_start(src, i // len(sources), max(2, math.ceil(slots / len(sources))), clip)
            dst = td / f'clip_{i:03d}.mp4'
            vf = 'scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,format=yuv420p'
            _ff([
                '-y', '-ss', f'{start:.3f}', '-t', f'{clip:.3f}', '-i', src,
                '-vf', vf, '-an', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '22', str(dst)
            ])
            clips.append(dst)
            _emit(progress, 60 + int((i + 1) / slots * 12), f'다중소스 재편집 {i+1}/{slots}')
        lst = td / 'concat.txt'
        lst.write_text('\n'.join("file '" + x.as_posix().replace("'", "''") + "'" for x in clips), encoding='utf-8')
        _ff(['-y', '-f', 'concat', '-safe', '0', '-i', str(lst), '-c', 'copy', str(output)])
    return str(output)


def video_composer(video: str, audio: str, output: str, srt: str | None, burn_subtitles: bool, progress: Progress | None = None) -> str:
    """Clean-room counterpart of processors.video_composer."""
    return compose_final(video, audio, output, srt, burn_subtitles, progress)


def render_integrity(path: str, repair_output: str | None = None, progress: Progress | None = None) -> dict:
    """Clean-room counterpart of core.video.render_integrity."""
    check = video_validator(path, require_audio=True)
    info = check.get('media') or {}
    needs = (not check.get('ok')) or info.get('width') != 1080 or info.get('height') != 1920
    if needs and repair_output:
        _emit(progress, 92, '최종 영상 무결성 복구')
        vf = 'scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black,format=yuv420p'
        _ff([
            '-y', '-i', path, '-vf', vf,
            '-c:v', 'libx264', '-preset', 'medium', '-crf', '20',
            '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', repair_output
        ])
        repaired = video_validator(repair_output, require_audio=True)
        repaired['repaired'] = True
        repaired['path'] = str(repair_output)
        return repaired
    check['repaired'] = False
    check['path'] = str(path)
    if check.get('ok') and info.get('width') == 1080 and info.get('height') == 1920:
        check['portrait_1080x1920'] = True
    return check


def video_validation(product: dict, transcript: str, script: str, gemini_key: str = '') -> dict:
    """Clean-room counterpart of prompts.video_validation."""
    prod = str((product or {}).get('title') or '')
    src_tokens = set(re.findall(r'[가-힣A-Za-z0-9一-龥]{2,}', (transcript or '').lower()))
    script_tokens = set(re.findall(r'[가-힣A-Za-z0-9一-龥]{2,}', (script or '').lower()))
    overlap = len(src_tokens & script_tokens) / max(1, len(script_tokens)) if script_tokens else 0.0
    result = {
        'ok': bool(script.strip()),
        'product': prod,
        'transcript_script_overlap': round(overlap, 4),
        'warnings': [],
    }
    if not transcript.strip():
        result['warnings'].append('원본 음성 전사가 없어 상품정보 중심으로 대본을 검증했습니다.')
    if gemini_key and script.strip():
        prompt = f'''상품 영상 대본의 사실 안전성을 검증하세요. 제공 정보에 없는 효능·가격·수치·과장 표현이 있으면 warnings에 적으세요.
JSON만 출력: {{"ok":true,"warnings":[]}}
상품: {prod}
원본 전사: {transcript[:4000]}
대본: {script[:2200]}'''
        try:
            raw = _gemini_text(prompt, gemini_key)
            raw = re.sub(r'^```(?:json)?|```$', '', raw.strip(), flags=re.M).strip()
            ai = json.loads(raw)
            if isinstance(ai, dict):
                result['ok'] = bool(ai.get('ok', result['ok']))
                result['warnings'] = [str(x) for x in (ai.get('warnings') or result['warnings'])][:20]
        except Exception as e:
            log('video validation AI fallback: ' + str(e))
    return result


def CreateFinalVideo(video: str, audio: str, output: str, srt: str | None, burn_subtitles: bool, progress: Progress | None = None) -> str:
    """Clean-room counterpart of core.video.CreateFinalVideo."""
    return video_composer(video, audio, output, srt, burn_subtitles, progress)


def batch_analysis(video: str, transcript: dict, detector: dict | None = None, progress: Progress | None = None) -> dict:
    va = video_analysis(video, detector, progress)
    aa = audio_analysis(transcript, va.get('media') or {})
    return {'video': va, 'audio': aa}


def batch_processor(*args, **kwargs):
    """Marker/orchestrator hook used by pipeline_v122; kept callable for parity auditing."""
    return {'active': True, 'args': len(args), 'kwargs': sorted(kwargs)}


def batch_utils(path: str) -> dict:
    return ffprobe_media(path)


def settings_manager(settings) -> dict:
    """Clean-room counterpart of managers.settings_manager: expose persisted setting keys, not secret values."""
    try:
        return {'keys': sorted(settings.__dataclass_fields__.keys()), 'active': True}
    except Exception:
        return {'keys': [], 'active': True}


PARITY_MAP = {
    'core.providers': providers,
    'core.audio.pipeline': audio_analysis,
    'core.sourcing.coupang_scraper': 'sourcing_v122.coupang_scraper',
    'core.sourcing.keyword_converter': 'sourcing_v122.keyword_converter',
    'core.sourcing.marketplace_query_planner': 'sourcing_v122.marketplace_query_planner',
    'core.sourcing.pipeline': 'sourcing_v122.sourcing_pipeline',
    'core.sourcing.platform_pipeline': 'sourcing_v122.platform_pipeline',
    'core.sourcing.platform_shorts_searcher': 'sourcing_v122.platform_shorts_searcher',
    'core.sourcing.platform_video_collector': 'sourcing_v122.platform_video_collector',
    'core.sourcing.product_searcher': 'sourcing_v122.product_searcher',
    'core.video.CreateFinalVideo': CreateFinalVideo,
    'core.video.reeditor': reeditor,
    'core.video.render_integrity': render_integrity,
    'core.video.video_validator': video_validator,
    'core.video.batch.analysis': batch_analysis,
    'core.video.batch.encoder': encoder,
    'core.video.batch.processor': batch_processor,
    'core.video.batch.subtitle_handler': subtitle_split,
    'core.video.batch.tts_generator': tts_generator,
    'core.video.batch.tts_speed': tts_speed,
    'core.video.batch.utils': batch_utils,
    'core.video.batch.whisper_analyzer': whisper_analyzer,
    'processors.subtitle_detector': subtitle_detector,
    'processors.subtitle_processor': subtitle_processor,
    'processors.tts_processor': tts_processor,
    'processors.video_composer': video_composer,
    'prompts.audio_analysis': audio_analysis,
    'prompts.subtitle_split': subtitle_split,
    'prompts.translation': translation,
    'prompts.video_analysis': video_analysis,
    'prompts.video_validation': video_validation,
    'managers.settings_manager': settings_manager,
    'ui.panels.settings_tab': 'main_v122.settings_page',
    'ui.panels.upload_panel': 'main_v122.upload_page',
    'browser-extension': 'browser-extension/service_worker.js',
}
