from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
import urllib.parse
from pathlib import Path

import requests
import websocket

from engine import HOME, log

CDP_PORT = 9222
CDP_BASE = f'http://127.0.0.1:{CDP_PORT}'


def find_browser() -> str | None:
    candidates = [
        Path(os.environ.get('PROGRAMFILES', r'C:\Program Files')) / 'Google/Chrome/Application/chrome.exe',
        Path(os.environ.get('PROGRAMFILES(X86)', r'C:\Program Files (x86)')) / 'Google/Chrome/Application/chrome.exe',
        Path(os.environ.get('LOCALAPPDATA', '')) / 'Google/Chrome/Application/chrome.exe',
        Path(os.environ.get('PROGRAMFILES(X86)', r'C:\Program Files (x86)')) / 'Microsoft/Edge/Application/msedge.exe',
        Path(os.environ.get('PROGRAMFILES', r'C:\Program Files')) / 'Microsoft/Edge/Application/msedge.exe',
    ]
    for p in candidates:
        if str(p) and p.exists():
            return str(p)
    return shutil.which('chrome') or shutil.which('msedge')


def status(timeout: float = 0.8) -> dict:
    try:
        r = requests.get(CDP_BASE + '/json/version', timeout=timeout)
        if r.ok:
            return {'connected': True, 'data': r.json(), 'browser': find_browser() or ''}
    except Exception:
        pass
    return {'connected': False, 'data': {}, 'browser': find_browser() or ''}


def ensure_browser(timeout: float = 12.0) -> dict:
    st = status()
    if st['connected']:
        return st
    exe = find_browser()
    if not exe:
        raise RuntimeError('Chrome 또는 Edge 브라우저를 찾지 못했습니다.')
    profile = HOME / 'browser-profile'
    profile.mkdir(parents=True, exist_ok=True)
    args = [
        exe,
        f'--remote-debugging-port={CDP_PORT}',
        '--remote-allow-origins=*',
        f'--user-data-dir={profile}',
        '--no-first-run',
        '--no-default-browser-check',
        '--disable-features=TranslateUI',
        'about:blank',
    ]
    flags = 0
    if os.name == 'nt':
        flags = getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)
    subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags)
    end = time.time() + timeout
    while time.time() < end:
        st = status()
        if st['connected']:
            log('[cdp] browser connected')
            return st
        time.sleep(0.35)
    raise RuntimeError('브라우저 자동 연결에 실패했습니다. 열린 Chrome/Edge 창을 닫고 다시 시도하세요.')


def _new_tab(url: str) -> dict:
    ensure_browser()
    endpoint = CDP_BASE + '/json/new?' + urllib.parse.quote(url, safe='')
    r = requests.put(endpoint, timeout=5)
    r.raise_for_status()
    return r.json()


def _close_tab(tab: dict):
    tid = str((tab or {}).get('id') or '')
    if not tid:
        return
    try:
        requests.get(CDP_BASE + '/json/close/' + tid, timeout=2)
    except Exception:
        pass


def _evaluate(tab: dict, expression: str, timeout: float = 15.0):
    ws_url = str((tab or {}).get('webSocketDebuggerUrl') or '')
    if not ws_url:
        raise RuntimeError('브라우저 디버깅 소켓을 찾지 못했습니다.')
    ws = websocket.create_connection(ws_url, timeout=timeout, origin='http://127.0.0.1')
    try:
        ws.send(json.dumps({'id': 1, 'method': 'Runtime.enable'}))
        ws.send(json.dumps({
            'id': 2,
            'method': 'Runtime.evaluate',
            'params': {
                'expression': expression,
                'returnByValue': True,
                'awaitPromise': True,
                'userGesture': True,
            },
        }))
        end = time.time() + timeout
        while time.time() < end:
            raw = ws.recv()
            msg = json.loads(raw)
            if msg.get('id') != 2:
                continue
            if msg.get('error'):
                raise RuntimeError(str(msg['error']))
            result = ((msg.get('result') or {}).get('result') or {})
            if result.get('subtype') == 'error':
                raise RuntimeError(str(result.get('description') or '브라우저 스크립트 오류'))
            return result.get('value')
        raise RuntimeError('브라우저 페이지 응답 시간이 초과되었습니다.')
    finally:
        try:
            ws.close()
        except Exception:
            pass


def _wait_page(tab: dict, seconds: float = 5.0):
    end = time.time() + max(1.0, seconds)
    while time.time() < end:
        try:
            state = _evaluate(tab, 'document.readyState', timeout=3)
            if state in ('interactive', 'complete'):
                break
        except Exception:
            pass
        time.sleep(0.35)
    time.sleep(1.2)


def analyze_product_page(url: str, wait_seconds: float = 5.0) -> dict:
    tab = _new_tab(url)
    try:
        _wait_page(tab, wait_seconds)
        script = r'''(() => {
          const meta=(key)=>document.querySelector(`meta[property="${key}"]`)?.content||document.querySelector(`meta[name="${key}"]`)?.content||'';
          const clean=v=>String(v||'').replace(/\s+/g,' ').trim();
          const walk=o=>{
            if(!o)return null;
            if(Array.isArray(o)){for(const v of o){const r=walk(v);if(r)return r;}return null;}
            if(typeof o==='object'){
              const t=o['@type'];const a=Array.isArray(t)?t:[t];
              if(a.some(x=>String(x||'').toLowerCase()==='product'))return o;
              for(const v of Object.values(o)){const r=walk(v);if(r)return r;}
            }
            return null;
          };
          let product=null;
          for(const s of document.querySelectorAll('script[type="application/ld+json"]')){
            try{const r=walk(JSON.parse(s.textContent||'{}'));if(r){product=r;break;}}catch(e){}
          }
          const brand=product&&product.brand?(typeof product.brand==='object'?(product.brand.name||''):product.brand):'';
          const image=product&&product.image?(Array.isArray(product.image)?product.image[0]:product.image):'';
          const visibleTitle = document.querySelector('h1')?.innerText || document.querySelector('[class*="product-title"]')?.innerText || document.querySelector('[class*="prod-buy-header"]')?.innerText || '';
          return {
            url:location.href,
            pageTitle:document.title||'',
            title:clean((product&&product.name)||meta('og:title')||visibleTitle||document.title||''),
            ogTitle:meta('og:title'),
            image:clean(image||meta('og:image')||meta('twitter:image')),
            ogImage:meta('og:image'),
            brand:clean(brand),
            model:clean((product&&(product.model||product.mpn))||''),
            sku:clean((product&&product.sku)||''),
            description:clean((product&&product.description)||meta('og:description')||''),
            bodyText:clean((document.body&&document.body.innerText||'').slice(0,5000))
          };
        })()'''
        value = _evaluate(tab, script, timeout=12)
        return dict(value or {})
    finally:
        _close_tab(tab)


def _platform_pattern(platform: str):
    pats = {
        'TikTok': r'tiktok\.com/@[^/]+/video/',
        'YouTube': r'(youtube\.com/(watch\?v=|shorts/)|youtu\.be/)',
        'Instagram': r'instagram\.com/(reel|reels|p)/',
        'Douyin': r'douyin\.com/video/',
        'Xiaohongshu': r'xiaohongshu\.com/(explore|discovery/item)/',
        'Kuaishou': r'kuaishou\.com/(short-video|f)/',
        '1688': r'1688\.com/offer/',
    }
    return re.compile(pats.get(platform, r'https?://'), re.I)


def collect_links(platform: str, url: str, keyword: str = '', wait_seconds: float = 5.5) -> list[dict]:
    tab = _new_tab(url)
    try:
        _wait_page(tab, wait_seconds)
        script = r'''(async()=>{
          const pause=ms=>new Promise(r=>setTimeout(r,ms));
          for(let i=0;i<4;i++){
            window.scrollTo(0,Math.min(document.body.scrollHeight,(i+1)*Math.max(innerHeight,900)));
            await pause(650);
          }
          window.scrollTo(0,0);
          const out=[];
          for(const a of document.querySelectorAll('a[href]')){
            const img=a.querySelector('img');
            out.push({
              url:a.href||'',
              title:(a.innerText||a.getAttribute('title')||(img&&img.alt)||'').replace(/\s+/g,' ').trim(),
              thumbnail:img?(img.currentSrc||img.src||img.getAttribute('data-src')||img.getAttribute('data-original')||''):''
            });
          }
          return out;
        })()'''
        rows = _evaluate(tab, script, timeout=18) or []
        rx = _platform_pattern(platform)
        seen = set()
        out = []
        for row in rows:
            u = str((row or {}).get('url') or '').strip()
            if not u or u in seen or not rx.search(u):
                continue
            seen.add(u)
            x = dict(row or {})
            x['platform'] = platform
            x['keyword'] = keyword
            out.append(x)
            if len(out) >= 60:
                break
        return out
    finally:
        _close_tab(tab)


def extract_media(url: str, wait_seconds: float = 5.5) -> list[str]:
    tab = _new_tab(url)
    try:
        _wait_page(tab, wait_seconds)
        script = r'''(() => {
          const out=[]; const add=u=>{try{if(u){const x=new URL(u,location.href).href;if(/^https?:/i.test(x))out.push(x);}}catch(e){}};
          document.querySelectorAll('video').forEach(v=>{add(v.currentSrc);add(v.src);});
          document.querySelectorAll('video source,source[type*="video"]').forEach(s=>add(s.src||s.getAttribute('src')));
          ['og:video','og:video:url','og:video:secure_url'].forEach(k=>add(document.querySelector(`meta[property="${k}"]`)?.content));
          try{performance.getEntriesByType('resource').forEach(e=>{if(/\.(mp4|m3u8|webm)(\?|$)/i.test(e.name)||/video/i.test(e.initiatorType||''))add(e.name);});}catch(e){}
          return [...new Set(out)].slice(0,30);
        })()'''
        return [str(x) for x in (_evaluate(tab, script, timeout=12) or []) if x]
    finally:
        _close_tab(tab)


def open_visible(url: str):
    tab = _new_tab(url)
    return tab
