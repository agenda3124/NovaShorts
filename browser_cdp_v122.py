from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

import browser_cdp as _base
from engine import HOME, app_dir, log


def ensure_browser(timeout: float = 12.0) -> dict:
    st = _base.status()
    if st['connected']:
        return st
    exe = _base.find_browser()
    if not exe:
        raise RuntimeError('Chrome 또는 Edge 브라우저를 찾지 못했습니다.')
    profile = HOME / 'browser-profile'
    profile.mkdir(parents=True, exist_ok=True)
    args = [
        exe,
        f'--remote-debugging-port={_base.CDP_PORT}',
        '--remote-allow-origins=*',
        f'--user-data-dir={profile}',
        '--no-first-run',
        '--no-default-browser-check',
        '--disable-features=TranslateUI',
    ]
    extension = app_dir() / 'browser-extension'
    if (extension / 'manifest.json').exists():
        # Dedicated NovaShorts browser profile: load the bundled public-metadata extension automatically.
        args += [f'--load-extension={extension}']
    args.append('about:blank')
    flags = getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0) if os.name == 'nt' else 0
    subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags)
    end = time.time() + timeout
    while time.time() < end:
        st = _base.status()
        if st['connected']:
            log('[cdp-v122] browser connected; bundled extension=' + str((extension / 'manifest.json').exists()))
            return st
        time.sleep(0.35)
    raise RuntimeError('브라우저 자동 연결에 실패했습니다. NovaShorts 전용 Chrome/Edge 창을 닫고 다시 시도하세요.')


# Make the existing CDP helpers use the upgraded launcher without copying their page scripts.
_base.ensure_browser = ensure_browser
status = _base.status
find_browser = _base.find_browser
analyze_product_page = _base.analyze_product_page
collect_links = _base.collect_links
extract_media = _base.extract_media
open_visible = _base.open_visible
