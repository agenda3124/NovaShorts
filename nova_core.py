from __future__ import annotations

import asyncio
import hashlib
import json
import os
import queue
import re
import secrets
import shutil
import subprocess
import threading
import time
import urllib.parse
import webbrowser
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Callable, Iterable

import requests

APP_NAME = "NovaShorts"
APP_VERSION = "1.5"
HOME = Path.home() / ".novashorts"
SETTINGS_FILE = HOME / "settings.json"
LOG_FILE = HOME / "logs" / "novashorts.log"
OUTPUT_DIR = Path.home() / "Videos" / "NovaShorts"

PLATFORMS = {
    "Douyin": "site:douyin.com/video",
    "Xiaohongshu": "site:xiaohongshu.com/explore",
    "Kuaishou": "site:kuaishou.com/short-video",
    "TikTok": "site:tiktok.com/@ /video/",
    "1688": "site:1688.com",
}


def ensure_dirs() -> None:
    HOME.mkdir(parents=True, exist_ok=True)
    (HOME / "logs").mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def log(msg: str) -> None:
    ensure_dirs()
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


@dataclass
class Settings:
    output_folder: str = str(OUTPUT_DIR)
    ai_provider: str = "Gemini"
    gemini_api_key: str = ""
    coupang_access_key: str = ""
    coupang_secret_key: str = ""
    sourcing_min_similarity_percent: int = 55
    sourcing_auto_skip_low_similarity: bool = True
    sourcing_use_gemini_query_planning: bool = True
    sourcing_method: str = "platform+external-search"
    platform_video_sources: list[str] | None = None
    youtube_client_secret_file: str = ""
    youtube_auto_upload: bool = False
    youtube_upload_interval: int = 60
    youtube_title_prompt: str = ""
    youtube_description_prompt: str = ""
    youtube_hashtag_prompt: str = ""
    youtube_comment_enabled: bool = False
    youtube_comment_prompt: str = ""
    x_connected: bool = False
    x_account_name: str = ""
    lnkbio_client_id: str = ""
    lnkbio_client_secret: str = ""
    lnkbio_profile_url: str = ""
    lnkbio_auto_publish: bool = False
    watermark_enabled: bool = False
    watermark_channel_name: str = ""
    watermark_position: str = "bottom_right"
    watermark_font_size: str = "medium"
    subtitle_overlay: bool = True
    subtitle_position: str = "bottom_center"
    subtitle_custom_y: int = 80
    tts_voice: str = "ko-KR-SunHiNeural"
    bridge_token: str = ""

    def __post_init__(self):
        if self.platform_video_sources is None:
            self.platform_video_sources = list(PLATFORMS)
        if not self.bridge_token:
            self.bridge_token = secrets.token_urlsafe(24)


def load_settings() -> Settings:
    ensure_dirs()
    if not SETTINGS_FILE.exists():
        s = Settings()
        save_settings(s)
        return s
    try:
        raw = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        allowed = Settings.__dataclass_fields__.keys()
        return Settings(**{k: v for k, v in raw.items() if k in allowed})
    except Exception as e:
        log(f"settings load failed: {e}")
        return Settings()


def save_settings(settings: Settings) -> None:
    ensure_dirs()
    SETTINGS_FILE.write_text(json.dumps(asdict(settings), ensure_ascii=False, indent=2), encoding="utf-8")


def detect_tool(name: str, extra_candidates: Iterable[str] = ()) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    for c in extra_candidates:
        if c and Path(c).exists():
            return str(Path(c))
    return None


def runtime_diagnostics() -> dict[str, str | bool]:
    local = Path(os.environ.get("LOCALAPPDATA", ""))
    tesseract_candidates = [
        str(local / "Programs" / "Tesseract-OCR" / "tesseract.exe"),
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    ]
    return {
        "python": True,
        "ffmpeg": bool(detect_tool("ffmpeg")),
        "ffprobe": bool(detect_tool("ffprobe")),
        "tesseract": bool(detect_tool("tesseract", tesseract_candidates)),
        "yt_dlp": bool(detect_tool("yt-dlp")),
    }


def normalize_product_title(title: str) -> str:
    title = re.sub(r"\[[^\]]+\]|\([^\)]+\)", " ", title)
    title = re.sub(r"\b(무료배송|로켓배송|당일배송|정품|국내배송)\b", " ", title, flags=re.I)
    title = re.sub(r"\s+", " ", title).strip()
    return title


def tokenize(text: str) -> list[str]:
    toks = re.findall(r"[가-힣A-Za-z0-9一-龥ぁ-んァ-ン]+", text.lower())
    return [t for t in toks if len(t) > 1]


def rule_based_query_plan(product_title: str) -> dict[str, list[str]]:
    base = normalize_product_title(product_title)
    tokens = tokenize(base)
    compact = " ".join(tokens[:6]) or base
    return {
        "Douyin": [compact, compact + " 测评", compact + " 使用"],
        "Xiaohongshu": [compact, compact + " 好物", compact + " 测评"],
        "Kuaishou": [compact, compact + " 使用", compact + " 推荐"],
        "TikTok": [compact, compact + " review", compact + " demo"],
        "1688": [compact, compact + " 视频", compact + " 详情"],
    }


def gemini_query_plan(product_title: str, api_key: str) -> dict[str, list[str]]:
    if not api_key:
        return rule_based_query_plan(product_title)
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
    prompt = (
        "Return JSON only. Create concise marketplace/video search keywords for the product below. "
        "Keys must be Douyin, Xiaohongshu, Kuaishou, TikTok, 1688; each value is an array of 3 search strings. "
        "Use Simplified Chinese for Chinese platforms and English for TikTok. Product: " + product_title
    )
    try:
        r = requests.post(url, params={"key": api_key}, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=25)
        r.raise_for_status()
        text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
        data = json.loads(text)
        if all(k in data and isinstance(data[k], list) for k in PLATFORMS):
            return {k: [str(x) for x in data[k]][:3] for k in PLATFORMS}
    except Exception as e:
        log(f"gemini query planning fallback: {e}")
    return rule_based_query_plan(product_title)


def external_search_url(platform: str, keyword: str) -> str:
    site = PLATFORMS[platform]
    q = urllib.parse.quote_plus(f"{site} {keyword}")
    return f"https://www.google.com/search?q={q}"


def direct_search_url(platform: str, keyword: str) -> str:
    q = urllib.parse.quote(keyword)
    if platform == "Douyin":
        return f"https://www.douyin.com/search/{q}?type=video"
    if platform == "Xiaohongshu":
        return f"https://www.xiaohongshu.com/search_result?keyword={q}&source=web_search_result_notes"
    if platform == "Kuaishou":
        return f"https://www.kuaishou.com/search/video?searchKey={q}"
    if platform == "TikTok":
        return f"https://www.tiktok.com/search/video?q={q}"
    return f"https://s.1688.com/selloffer/offer_search.htm?keywords={q}"


def open_platform_searches(plan: dict[str, list[str]], platforms: Iterable[str]) -> None:
    for p in platforms:
        for kw in plan.get(p, [])[:1]:
            webbrowser.open(direct_search_url(p, kw))
            time.sleep(0.2)


def candidate_relevance_score(product_title: str, candidate_text: str) -> int:
    a = set(tokenize(product_title))
    b = set(tokenize(candidate_text))
    if not a or not b:
        return 0
    overlap = len(a & b) / max(1, len(a))
    partial = sum(1 for x in a if any(x in y or y in x for y in b)) / max(1, len(a))
    score = round((0.65 * overlap + 0.35 * partial) * 100)
    return max(0, min(100, score))


def download_video(url: str, out_dir: str, progress: Callable[[str], None] | None = None) -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    template = str(out / "%(title).120s_%(id)s.%(ext)s")
    cmd = ["yt-dlp", "--no-playlist", "--merge-output-format", "mp4", "-o", template, url]
    if progress:
        progress("yt-dlp 다운로드 시작")
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr[-2000:] or "yt-dlp failed")
    lines = [x.strip() for x in proc.stdout.splitlines() if x.strip()]
    if progress and lines:
        progress(lines[-1])
    # newest mp4/webm/mkv
    files = sorted([p for p in out.iterdir() if p.suffix.lower() in {".mp4", ".webm", ".mkv", ".mov"}], key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        raise RuntimeError("다운로드 파일을 찾지 못했습니다.")
    return files[0]


def extract_audio(video: str, wav_out: str) -> str:
    cmd = ["ffmpeg", "-y", "-i", video, "-vn", "-ac", "1", "-ar", "16000", wav_out]
    subprocess.run(cmd, check=True, capture_output=True)
    return wav_out


def burn_subtitle(video: str, srt: str, output: str) -> str:
    filt = f"subtitles='{srt.replace('\\', '/').replace(':', '\\:')}'"
    cmd = ["ffmpeg", "-y", "-i", video, "-vf", filt, "-c:a", "copy", output]
    subprocess.run(cmd, check=True, capture_output=True)
    return output


def apply_watermark(video: str, text: str, output: str, position: str = "bottom_right") -> str:
    pos = {
        "bottom_right": "x=w-tw-40:y=h-th-40",
        "bottom_left": "x=40:y=h-th-40",
        "top_right": "x=w-tw-40:y=40",
        "top_left": "x=40:y=40",
        "center": "x=(w-tw)/2:y=(h-th)/2",
    }.get(position, "x=w-tw-40:y=h-th-40")
    safe = text.replace("'", "\\'").replace(":", "\\:")
    vf = f"drawtext=text='{safe}':fontcolor=white:fontsize=28:borderw=2:bordercolor=black@0.5:{pos}"
    cmd = ["ffmpeg", "-y", "-i", video, "-vf", vf, "-c:a", "copy", output]
    subprocess.run(cmd, check=True, capture_output=True)
    return output


def compose_vertical(video: str, audio: str | None, output: str) -> str:
    vf = "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black"
    cmd = ["ffmpeg", "-y", "-i", video]
    if audio:
        cmd += ["-i", audio, "-map", "0:v:0", "-map", "1:a:0", "-shortest"]
    cmd += ["-vf", vf, "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-c:a", "aac", "-b:a", "192k", output]
    subprocess.run(cmd, check=True, capture_output=True)
    return output


async def _tts_async(text: str, voice: str, output: str) -> None:
    import edge_tts
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output)


def generate_tts(text: str, voice: str, output: str) -> str:
    asyncio.run(_tts_async(text, voice, output))
    return output


def tesseract_ocr_image(image_path: str, lang: str = "chi_sim+kor+eng") -> str:
    cmd = ["tesseract", image_path, "stdout", "-l", lang, "--psm", "6"]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr[-1000:])
    return proc.stdout


def extract_frames_for_ocr(video: str, out_dir: str, fps: float = 0.5) -> list[Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    pattern = str(out / "frame_%05d.jpg")
    cmd = ["ffmpeg", "-y", "-i", video, "-vf", f"fps={fps}", pattern]
    subprocess.run(cmd, check=True, capture_output=True)
    return sorted(out.glob("frame_*.jpg"))


def subtitle_scan(video: str, work_dir: str, progress: Callable[[str], None] | None = None) -> list[dict]:
    frames = extract_frames_for_ocr(video, str(Path(work_dir) / "ocr_frames"), 0.5)
    hits = []
    for i, frame in enumerate(frames):
        try:
            text = tesseract_ocr_image(str(frame))
        except Exception as e:
            log(f"ocr failed {frame}: {e}")
            continue
        text = re.sub(r"\s+", " ", text).strip()
        chinese = bool(re.search(r"[一-龥]", text))
        if text:
            hits.append({"frame": str(frame), "t": i * 2.0, "text": text, "chinese": chinese})
        if progress and i % 5 == 0:
            progress(f"OCR {i+1}/{len(frames)}")
    return hits


def create_blurred_subtitle_cleanup(video: str, output: str, y_start_percent: int = 62) -> str:
    # Deterministic bottom-region blur fallback when exact polygon masks are unavailable.
    yexpr = f"ih*{max(0,min(95,y_start_percent))}/100"
    vf = (
        f"[0:v]split=2[base][crop];"
        f"[crop]crop=iw:ih-{yexpr}:0:{yexpr},boxblur=luma_radius=12:luma_power=2[blur];"
        f"[base][blur]overlay=0:{yexpr}"
    )
    cmd = ["ffmpeg", "-y", "-i", video, "-filter_complex", vf, "-c:a", "copy", output]
    subprocess.run(cmd, check=True, capture_output=True)
    return output


def youtube_upload(video_file: str, client_secret_file: str, title: str, description: str, tags: list[str], privacy: str = "private") -> str:
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    scopes = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube.force-ssl"]
    flow = InstalledAppFlow.from_client_secrets_file(client_secret_file, scopes)
    creds = flow.run_local_server(port=0)
    youtube = build("youtube", "v3", credentials=creds)
    body = {
        "snippet": {"title": title, "description": description, "tags": tags, "categoryId": "22"},
        "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False},
    }
    req = youtube.videos().insert(part="snippet,status", body=body, media_body=MediaFileUpload(video_file, chunksize=-1, resumable=True))
    response = None
    while response is None:
        _, response = req.next_chunk()
    return response["id"]


def youtube_comment(video_id: str, text: str, client_secret_file: str) -> None:
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    scopes = ["https://www.googleapis.com/auth/youtube.force-ssl"]
    flow = InstalledAppFlow.from_client_secrets_file(client_secret_file, scopes)
    creds = flow.run_local_server(port=0)
    youtube = build("youtube", "v3", credentials=creds)
    youtube.commentThreads().insert(part="snippet", body={"snippet": {"videoId": video_id, "topLevelComment": {"snippet": {"textOriginal": text}}}}).execute()


def lnk_bio_add(client_id: str, client_secret: str, title: str, url: str) -> dict:
    token = requests.post("https://lnk.bio/oauth/token", data={"grant_type": "client_credentials", "client_id": client_id, "client_secret": client_secret}, timeout=20)
    token.raise_for_status()
    access = token.json().get("access_token")
    r = requests.post("https://lnk.bio/oauth/v1/lnk/add", headers={"Authorization": f"Bearer {access}"}, data={"title": title, "url": url}, timeout=20)
    r.raise_for_status()
    return r.json()


def open_x_compose(text: str) -> None:
    webbrowser.open("https://x.com/intent/post?text=" + urllib.parse.quote(text))


def make_project_id(product_title: str) -> str:
    return hashlib.sha1((product_title + str(time.time_ns())).encode("utf-8")).hexdigest()[:10]


class BatchQueue:
    def __init__(self):
        self.q: queue.Queue[tuple[str, Callable[[], None]]] = queue.Queue()
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None

    def add(self, name: str, fn: Callable[[], None]) -> None:
        self.q.put((name, fn))

    def start(self, on_status: Callable[[str], None] | None = None) -> None:
        if self.thread and self.thread.is_alive():
            return
        self.stop_event.clear()

        def worker():
            while not self.stop_event.is_set():
                try:
                    name, fn = self.q.get(timeout=0.5)
                except queue.Empty:
                    continue
                try:
                    if on_status:
                        on_status(f"배치 시작: {name}")
                    fn()
                    if on_status:
                        on_status(f"배치 완료: {name}")
                except Exception as e:
                    log(f"batch {name} failed: {e}")
                    if on_status:
                        on_status(f"배치 오류: {name} · {e}")
                finally:
                    self.q.task_done()
        self.thread = threading.Thread(target=worker, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
