from __future__ import annotations

import re
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

import browser_cdp_v123 as browser_cdp
import engine_v112 as source_engine
from bridge import TASKS, extension_recent, wait_for_result
from engine import log, normalize_title, tokens
from product_source import rank_candidates, search_seed
from sourcing_v122 import coupang_scraper

Progress = Callable[[int, str], None]
PLATFORMS = ['TikTok', 'YouTube', 'Instagram', 'Douyin', 'Xiaohongshu', 'Kuaishou', '1688']


def _emit(cb: Progress | None, pct: int, msg: str):
    if cb:
        cb(max(0, min(100, int(pct))), msg)
    log('[sourcing-v123] ' + msg)


def _identity_seed(profile: dict) -> str:
    brand = re.sub(r'\s+', ' ', str((profile or {}).get('brand') or '')).strip()
    model = re.sub(r'\s+', ' ', str((profile or {}).get('model') or '')).strip()
    if brand and model:
        return f'{brand} {model}'.strip()
    if model:
        return model
    title = normalize_title(str((profile or {}).get('title') or '')).strip()
    ts = tokens(title)
    # Keep letter/number identity tokens first, because they survive language changes.
    ids = [x for x in ts if re.search(r'[A-Za-z0-9]', x)]
    if ids:
        return ' '.join(ids[:4])
    return ' '.join(ts[:5]) or title


def _fallback_queries(profile: dict, platform: str) -> list[str]:
    title = normalize_title(str((profile or {}).get('title') or '')).strip()
    identity = _identity_seed(profile)
    model = re.sub(r'\s+', ' ', str((profile or {}).get('model') or '')).strip()
    brand = re.sub(r'\s+', ' ', str((profile or {}).get('brand') or '')).strip()
    base = identity or title
    out: list[str] = []

    def add(q: str):
        q = re.sub(r'\s+', ' ', q or '').strip()
        if q and q.lower() not in {x.lower() for x in out}:
            out.append(q)

    if model:
        add(model)
    if brand and model:
        add(f'{brand} {model}')
    add(base)

    if platform in ('Douyin', 'Xiaohongshu', 'Kuaishou'):
        for suffix in ('测评', '开箱', '使用', '同款'):
            add(f'{base} {suffix}')
    elif platform == '1688':
        for suffix in ('产品视频', '厂家', '详情', '同款'):
            add(f'{base} {suffix}')
    elif platform == 'YouTube':
        for suffix in ('review', 'demo', 'unboxing', 'shorts'):
            add(f'{base} {suffix}')
    elif platform == 'Instagram':
        for suffix in ('reel', 'review', 'demo', 'unboxing'):
            add(f'{base} {suffix}')
    else:
        for suffix in ('review', 'demo', 'unboxing', 'how to use'):
            add(f'{base} {suffix}')

    # Korean title remains a last-resort exact identity search; do not lead with it on Chinese platforms.
    if title and title.lower() != base.lower():
        add(title)
    return out[:6]


def keyword_converter(profile: dict, gemini_key: str = '') -> dict[str, list[str]]:
    seed = search_seed(profile) or str((profile or {}).get('title') or '').strip()
    ai_plan: dict[str, list[str]] = {}
    if gemini_key and seed:
        try:
            ai_plan = source_engine.gemini_query_plan(seed, gemini_key) or {}
        except Exception as e:
            log('v123 Gemini query planning: ' + str(e))
            ai_plan = {}

    out: dict[str, list[str]] = {}
    for p in PLATFORMS:
        merged: list[str] = []
        # Identity-preserving fallback comes first so model/brand cannot be lost by AI translation.
        for q in _fallback_queries(profile, p)[:3]:
            if q and q.lower() not in {x.lower() for x in merged}:
                merged.append(q)
        for q in ai_plan.get(p, []) or []:
            q = re.sub(r'\s+', ' ', str(q or '')).strip()
            if q and q.lower() not in {x.lower() for x in merged}:
                merged.append(q)
        for q in _fallback_queries(profile, p)[3:]:
            if q and q.lower() not in {x.lower() for x in merged}:
                merged.append(q)
        out[p] = merged[:6]
    return out


def marketplace_query_planner(profile: dict, gemini_key: str = '', enabled: list[str] | None = None) -> dict[str, list[str]]:
    plan = keyword_converter(profile, gemini_key)
    allowed = set(enabled or PLATFORMS)
    return {p: plan.get(p, []) for p in PLATFORMS if p in allowed}


def platform_shorts_searcher(platform: str, query: str) -> list[tuple[str, str]]:
    return [
        ('direct', source_engine.direct_search_url(platform, query)),
        ('external', source_engine.external_search_url(platform, query)),
    ]


def _extension_collect(platform: str, url: str, keyword: str) -> list[dict]:
    if not extension_recent(5.0):
        return []
    tid = uuid.uuid4().hex
    TASKS.put({'type': 'collect_links', 'task_id': tid, 'platform': platform, 'url': url, 'keyword': keyword, 'wait_ms': 7000})
    packet = wait_for_result(tid, 26)
    return list((packet or {}).get('items') or [])


def platform_video_collector(platform: str, query: str, progress: Progress | None = None) -> tuple[list[dict], list[dict]]:
    rows: list[dict] = []
    seen: set[str] = set()
    attempts: list[dict] = []

    for mode, url in platform_shorts_searcher(platform, query):
        detail = browser_cdp.collect_links_detailed(platform, url, query, 14.0 if mode == 'direct' else 10.0)
        got = list(detail.get('items') or [])
        if not got and detail.get('status') in ('error', 'blocked'):
            try:
                got = _extension_collect(platform, url, query)
                if got:
                    detail = dict(detail)
                    detail['status'] = 'ok'
                    detail['note'] = f'확장 프로그램 폴백 {len(got)}개'
            except Exception as e:
                log(f'v123 extension collect {platform}: {e}')

        for raw in got:
            r = dict(raw or {})
            u = str(r.get('url') or '').strip()
            if not u or u in seen or r.get('error'):
                continue
            seen.add(u)
            r['platform'] = platform
            r['keyword'] = query
            rows.append(r)

        attempts.append({
            'query': query,
            'mode': mode,
            'status': detail.get('status', 'empty'),
            'note': detail.get('note', ''),
            'found': len(got),
            'page_title': detail.get('page_title', ''),
        })
        if rows:
            break

    if progress:
        progress(0, f'{platform} · {query[:28]} · {len(rows)}건')
    return rows[:80], attempts


def platform_pipeline(platform: str, queries: list[str], progress: Progress | None = None) -> tuple[list[dict], dict]:
    out: list[dict] = []
    seen: set[str] = set()
    attempts: list[dict] = []
    for q in (queries or [])[:5]:
        rows, detail = platform_video_collector(platform, q, progress)
        attempts.extend(detail)
        for row in rows:
            u = str(row.get('url') or '')
            if u and u not in seen:
                seen.add(u)
                out.append(row)
        # Enough candidates: stop opening more search tabs.
        if len(out) >= 8:
            break
    statuses = [str(x.get('status') or '') for x in attempts]
    if out:
        state = 'ok'
    elif 'login_required' in statuses:
        state = 'login_required'
    elif 'blocked' in statuses:
        state = 'blocked'
    elif 'error' in statuses:
        state = 'error'
    else:
        state = 'empty'
    diag = {'platform': platform, 'count': len(out), 'state': state, 'attempts': attempts}
    return out, diag


def product_searcher(profile: dict, candidates: list[dict], limit: int = 80) -> list[dict]:
    return rank_candidates(profile or {}, candidates or [])[:max(1, int(limit))]


def sourcing_pipeline(profile: dict, gemini_key: str = '', enabled_platforms: list[str] | None = None, progress: Progress | None = None) -> dict:
    enabled = [p for p in (enabled_platforms or PLATFORMS) if p in PLATFORMS] or PLATFORMS[:]
    _emit(progress, 10, '플랫폼별 검색어 생성')
    plan = marketplace_query_planner(profile, gemini_key, enabled)
    try:
        browser_cdp.ensure_browser()
    except Exception as e:
        log('v123 browser launch: ' + str(e))

    # Two concurrent platforms keeps the browser usable and avoids a burst of empty popups/tabs.
    jobs = [(p, plan.get(p, [])) for p in enabled if plan.get(p)]
    all_rows: list[dict] = []
    diagnostics: dict[str, dict] = {}
    done = 0
    with ThreadPoolExecutor(max_workers=min(2, max(1, len(jobs)))) as ex:
        futs = {ex.submit(platform_pipeline, p, qs, progress): p for p, qs in jobs}
        for fut in as_completed(futs):
            p = futs[fut]
            try:
                rows, diag = fut.result()
                all_rows.extend(rows or [])
                diagnostics[p] = diag
            except Exception as e:
                log(f'v123 platform pipeline {p}: {e}')
                diagnostics[p] = {'platform': p, 'count': 0, 'state': 'error', 'attempts': [{'status': 'error', 'note': str(e)[:160]}]}
            done += 1
            count = int((diagnostics.get(p) or {}).get('count') or 0)
            _emit(progress, 18 + int(done / max(1, len(jobs)) * 50), f'{p} 수집 완료 · {count}건')

    counts = {p: int((diagnostics.get(p) or {}).get('count') or 0) for p in enabled}
    _emit(progress, 72, '상품 관련도 계산')
    ranked = product_searcher(profile, all_rows, 80) if all_rows else []
    _emit(progress, 80, f'수집 {sum(counts.values())}건 · 관련 후보 {len(ranked)}건')
    return {
        'profile': profile,
        'plan': plan,
        'candidates': ranked,
        'diagnostics': diagnostics,
        'counts': counts,
        'gemini_used': bool(gemini_key),
    }
