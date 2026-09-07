from __future__ import annotations

import re
import time
import urllib.parse
from typing import Any

import browser_cdp as _base
import browser_cdp_v122 as _launcher
from engine import log

# Keep the v1.22 dedicated-profile launcher (bundled extension, persistent login),
# but replace the fixed-delay link collector with an adaptive search collector.
ensure_browser = _launcher.ensure_browser
_base.ensure_browser = ensure_browser
status = _base.status
find_browser = _base.find_browser
analyze_product_page = _base.analyze_product_page
extract_media = _base.extract_media
open_visible = _base.open_visible

_LOGIN_MARKERS = (
    'login', 'log in', 'sign in', '로그인', '登录', '登入', '扫码', '请登录',
    'captcha', 'verify', 'verification', '验证', '安全验证', 'robot', '人机验证',
)
_BLOCK_MARKERS = ('access denied', 'forbidden', 'request blocked', 'too many requests', '403')


def unwrap_search_url(url: str) -> str:
    """Unwrap Google result redirects into the actual platform URL."""
    raw = str(url or '').strip()
    if not raw:
        return ''
    try:
        p = urllib.parse.urlparse(raw)
        host = (p.netloc or '').lower()
        if 'google.' in host and p.path == '/url':
            qs = urllib.parse.parse_qs(p.query)
            target = (qs.get('q') or qs.get('url') or [''])[0]
            if target:
                return urllib.parse.unquote(target)
    except Exception:
        pass
    return raw


def _page_state(tab: dict) -> dict[str, Any]:
    script = r'''(() => ({
      ready: document.readyState,
      anchors: document.querySelectorAll('a[href]').length,
      body: ((document.body && document.body.innerText) || '').slice(0,5000),
      title: document.title || '',
      url: location.href || ''
    }))()'''
    try:
        return dict(_base._evaluate(tab, script, timeout=5) or {})
    except Exception:
        return {}


def _adaptive_wait(tab: dict, max_seconds: float = 14.0) -> dict[str, Any]:
    """Wait for dynamic result pages until anchor count stabilizes instead of sleeping 4-5s."""
    end = time.time() + max(4.0, float(max_seconds))
    last = -1
    stable = 0
    state: dict[str, Any] = {}
    while time.time() < end:
        state = _page_state(tab)
        n = int(state.get('anchors') or 0)
        if state.get('ready') in ('interactive', 'complete') and n >= 12:
            if n == last:
                stable += 1
            else:
                stable = 0
            # Two stable samples is enough on a normal results page; slow pages keep waiting.
            if stable >= 2:
                break
        last = n
        time.sleep(0.65)
    return state


def _extract_anchor_rows(tab: dict) -> list[dict]:
    script = r'''(async()=>{
      const pause=ms=>new Promise(r=>setTimeout(r,ms));
      let last=-1, stable=0;
      for(let i=0;i<7;i++){
        const before=document.querySelectorAll('a[href]').length;
        window.scrollTo(0, Math.min(document.body.scrollHeight, (i+1)*Math.max(innerHeight,900)));
        await pause(700);
        const after=document.querySelectorAll('a[href]').length;
        stable = (after===last) ? stable+1 : 0;
        last=after;
        if(stable>=2 && after>=before && i>=3) break;
      }
      window.scrollTo(0,0); await pause(250);
      return Array.from(document.querySelectorAll('a[href]')).map(a=>{
        const img=a.querySelector('img') || a.closest('div')?.querySelector('img');
        const box=a.closest('article,li,div');
        const title=(a.innerText || a.getAttribute('title') || (img&&img.alt) || (box&&box.innerText) || '').replace(/\s+/g,' ').trim();
        return {
          url:a.href||'',
          title:title.slice(0,260),
          thumbnail:img ? (img.currentSrc||img.src||img.getAttribute('data-src')||img.getAttribute('data-original')||'') : ''
        };
      }).filter(x=>x.url);
    })()'''
    try:
        return list(_base._evaluate(tab, script, timeout=22) or [])
    except Exception as e:
        log('adaptive anchor extraction: ' + str(e))
        return []


def _classify_empty(state: dict, error: str = '') -> tuple[str, str]:
    text = (' '.join([
        str(state.get('title') or ''), str(state.get('body') or ''), str(error or '')
    ])).lower()
    if any(x in text for x in _BLOCK_MARKERS):
        return 'blocked', '접근 차단/검증 페이지'
    if any(x in text for x in _LOGIN_MARKERS):
        return 'login_required', '로그인 또는 추가 인증 필요 가능성'
    if error:
        return 'error', str(error)[:180]
    return 'empty', '검색 결과 링크를 찾지 못함'


def collect_links_detailed(platform: str, url: str, keyword: str = '', wait_seconds: float = 14.0) -> dict:
    """Collect platform result URLs and return diagnostics for zero-result troubleshooting."""
    tab = None
    try:
        tab = _base._new_tab(url)
        state = _adaptive_wait(tab, max(wait_seconds, 10.0))
        raw_rows = _extract_anchor_rows(tab)
        rx = _base._platform_pattern(platform)
        seen: set[str] = set()
        out: list[dict] = []
        for raw in raw_rows:
            u = unwrap_search_url(str((raw or {}).get('url') or ''))
            if not u or u in seen or not rx.search(u):
                continue
            seen.add(u)
            row = dict(raw or {})
            row['url'] = u
            row['platform'] = platform
            row['keyword'] = keyword
            out.append(row)
            if len(out) >= 80:
                break
        if out:
            return {
                'items': out,
                'status': 'ok',
                'note': f'{len(out)}개 영상 링크',
                'anchor_count': len(raw_rows),
                'page_title': str(state.get('title') or ''),
                'final_url': str(state.get('url') or url),
            }
        st, note = _classify_empty(state)
        return {
            'items': [], 'status': st, 'note': note,
            'anchor_count': len(raw_rows),
            'page_title': str(state.get('title') or ''),
            'final_url': str(state.get('url') or url),
        }
    except Exception as e:
        state = _page_state(tab) if tab else {}
        st, note = _classify_empty(state, str(e))
        return {'items': [], 'status': st, 'note': note, 'error': str(e), 'anchor_count': 0, 'page_title': str(state.get('title') or ''), 'final_url': str(state.get('url') or url)}
    finally:
        if tab:
            try:
                _base._close_tab(tab)
            except Exception:
                pass


def collect_links(platform: str, url: str, keyword: str = '', wait_seconds: float = 14.0) -> list[dict]:
    return list(collect_links_detailed(platform, url, keyword, wait_seconds).get('items') or [])

# Patch legacy callers too.
_base.collect_links = collect_links
