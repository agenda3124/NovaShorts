from __future__ import annotations

import re
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

import browser_cdp
import engine_v112 as source_engine
from bridge import TASKS, extension_recent, wait_for_result
from engine import log
from product_source import (
    fetch_product_profile,
    merge_profiles,
    profile_from_browser,
    rank_candidates,
    search_seed,
)

Progress = Callable[[int, str], None]
PLATFORMS = ['TikTok', 'YouTube', 'Instagram', 'Douyin', 'Xiaohongshu', 'Kuaishou', '1688']


def _emit(cb: Progress | None, pct: int, msg: str):
    if cb:
        cb(max(0, min(100, int(pct))), msg)
    log('[sourcing-v122] ' + msg)


def coupang_scraper(url: str, progress: Progress | None = None) -> dict:
    """Functional equivalent of the original coupang_scraper module.

    Normal HTTP metadata extraction is attempted first. If Coupang blocks it, the
    dedicated Chrome/Edge profile is used. The extension path is only a last fallback.
    """
    _emit(progress, 2, '상품 주소 분석')
    profile: dict = {}
    http_error = ''
    try:
        profile = fetch_product_profile(url)
    except Exception as e:
        http_error = str(e)
        log('product HTTP blocked: ' + http_error)

    if not profile.get('title') or not profile.get('image') or bool(profile.get('blocked')):
        try:
            raw = browser_cdp.analyze_product_page(url, 5.2)
            bp = profile_from_browser(raw, url)
            bad = str(bp.get('title') or '').lower()
            if any(x in bad for x in ('access denied', 'forbidden', 'captcha', 'request blocked')):
                bp['title'] = ''
            profile = merge_profiles(profile, bp)
        except Exception as e:
            log('product CDP fallback: ' + str(e))

    if not profile.get('title') and extension_recent(5.0):
        try:
            tid = uuid.uuid4().hex
            TASKS.put({'type': 'analyze_product_page', 'task_id': tid, 'url': url, 'wait_ms': 4500})
            packet = wait_for_result(tid, 20)
            if packet and packet.get('profile'):
                profile = merge_profiles(profile, profile_from_browser(packet.get('profile') or {}, url))
        except Exception as e:
            log('product extension fallback: ' + str(e))

    if not profile.get('product_id'):
        m = re.search(r'/products/(\d+)', url)
        if m:
            profile['product_id'] = m.group(1)
    if not profile.get('title'):
        msg = '상품명을 확인하지 못했습니다. 자동으로 열린 Chrome/Edge에서 상품 페이지가 정상 표시되는지 확인하세요.'
        if http_error:
            msg += '\n일반 요청 차단: ' + http_error.split('\n')[0][:160]
        raise RuntimeError(msg)
    profile['input_url'] = url
    _emit(progress, 8, '상품 정보 확인 완료')
    return profile


def keyword_converter(profile: dict, gemini_key: str = '') -> dict[str, list[str]]:
    """Functional equivalent of keyword_converter.

    Brand/model/title are retained as hard identity tokens. Gemini only expands the
    platform language variants; rule fallbacks keep the feature available without a key.
    """
    seed = search_seed(profile) or str((profile or {}).get('title') or '').strip()
    if not seed:
        return {p: [] for p in PLATFORMS}
    plan = source_engine.gemini_query_plan(seed, gemini_key) if gemini_key else source_engine.rule_query_plan(seed)
    # Add an exact model/brand seed so AI expansion cannot lose the identity token.
    exact = ' '.join(x for x in [str(profile.get('brand') or '').strip(), str(profile.get('model') or '').strip()] if x).strip()
    out: dict[str, list[str]] = {}
    for p in PLATFORMS:
        vals: list[str] = []
        if exact:
            vals.append(exact)
        for q in plan.get(p, []) or []:
            q = re.sub(r'\s+', ' ', str(q or '')).strip()
            if q and q.lower() not in [x.lower() for x in vals]:
                vals.append(q)
        out[p] = vals[:4]
    return out


def marketplace_query_planner(profile: dict, gemini_key: str = '', enabled: list[str] | None = None) -> dict[str, list[str]]:
    plan = keyword_converter(profile, gemini_key)
    allowed = set(enabled or PLATFORMS)
    return {p: plan.get(p, []) for p in PLATFORMS if p in allowed}


def platform_shorts_searcher(platform: str, query: str) -> list[str]:
    """Return the direct platform search followed by a site-search fallback."""
    return [source_engine.direct_search_url(platform, query), source_engine.external_search_url(platform, query)]


def _extension_collect(platform: str, url: str, keyword: str) -> list[dict]:
    if not extension_recent(5.0):
        return []
    tid = uuid.uuid4().hex
    TASKS.put({
        'type': 'collect_links',
        'task_id': tid,
        'platform': platform,
        'url': url,
        'keyword': keyword,
        'wait_ms': 5000,
    })
    packet = wait_for_result(tid, 22)
    return list((packet or {}).get('items') or [])


def platform_video_collector(platform: str, query: str, progress: Progress | None = None) -> list[dict]:
    """Functional equivalent of platform_video_collector.

    It uses a normal visible browser profile; there is no CAPTCHA/stealth bypass.
    """
    rows: list[dict] = []
    seen: set[str] = set()
    for idx, url in enumerate(platform_shorts_searcher(platform, query)):
        got: list[dict] = []
        try:
            got = browser_cdp.collect_links(platform, url, query, 5.2 if idx == 0 else 4.2)
        except Exception as e:
            log(f'collect {platform} browser: {e}')
            try:
                got = _extension_collect(platform, url, query)
            except Exception as ee:
                log(f'collect {platform} extension: {ee}')
        for raw in got or []:
            r = dict(raw or {})
            u = str(r.get('url') or '').strip()
            if not u or u in seen or r.get('error'):
                continue
            seen.add(u)
            r['platform'] = platform
            r['keyword'] = query
            rows.append(r)
        if rows and idx == 0:
            break
    if progress:
        progress(0, f'{platform} 후보 {len(rows)}개')
    return rows[:80]


def platform_pipeline(platform: str, queries: list[str], progress: Progress | None = None) -> list[dict]:
    out: list[dict] = []
    seen: set[str] = set()
    for q in (queries or [])[:3]:
        for row in platform_video_collector(platform, q, progress):
            u = str(row.get('url') or '')
            if u and u not in seen:
                seen.add(u)
                out.append(row)
    return out


def product_searcher(profile: dict, candidates: list[dict], limit: int = 60) -> list[dict]:
    """Functional equivalent of product_searcher: model/brand/text/image ranking."""
    ranked = rank_candidates(profile or {}, candidates or [])
    return ranked[:max(1, int(limit))]


def sourcing_pipeline(
    profile: dict,
    gemini_key: str = '',
    enabled_platforms: list[str] | None = None,
    progress: Progress | None = None,
) -> dict:
    """End-to-end clean-room equivalent of the original sourcing pipeline."""
    enabled = [p for p in (enabled_platforms or PLATFORMS) if p in PLATFORMS]
    if not enabled:
        enabled = PLATFORMS[:]
    _emit(progress, 12, '플랫폼별 검색어 계획')
    plan = marketplace_query_planner(profile, gemini_key, enabled)
    try:
        browser_cdp.ensure_browser()
    except Exception as e:
        log('browser launch before sourcing: ' + str(e))

    jobs = [(p, plan.get(p, [])) for p in enabled if plan.get(p)]
    all_rows: list[dict] = []
    done = 0
    with ThreadPoolExecutor(max_workers=min(4, max(1, len(jobs)))) as ex:
        futs = {ex.submit(platform_pipeline, p, qs, progress): p for p, qs in jobs}
        for fut in as_completed(futs):
            p = futs[fut]
            try:
                all_rows.extend(fut.result() or [])
            except Exception as e:
                log(f'platform pipeline {p}: {e}')
            done += 1
            _emit(progress, 15 + int(done / max(1, len(jobs)) * 55), f'{p} 수집 완료')

    _emit(progress, 74, '상품 관련도 교차검증')
    ranked = product_searcher(profile, all_rows, 80)
    _emit(progress, 80, f'관련 영상 후보 {len(ranked)}개 정렬 완료')
    return {'profile': profile, 'plan': plan, 'candidates': ranked}
