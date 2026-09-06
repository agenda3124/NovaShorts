from __future__ import annotations

import html as html_lib
import io
import json
import re
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
from typing import Any

import requests
from PIL import Image

from engine import normalize_title, relevance, tokens

UA = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36'
)


def is_http_url(value: str) -> bool:
    try:
        p = urllib.parse.urlparse((value or '').strip())
        return p.scheme in ('http', 'https') and bool(p.netloc)
    except Exception:
        return False


def _clean(value: Any) -> str:
    if value is None:
        return ''
    if isinstance(value, (list, tuple)):
        value = value[0] if value else ''
    if isinstance(value, dict):
        value = value.get('name') or value.get('@id') or ''
    s = html_lib.unescape(str(value))
    s = re.sub(r'<[^>]+>', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def _meta(doc: str, key: str) -> str:
    # Accept property/name before or after content.
    pats = [
        rf'<meta[^>]+(?:property|name)=["\']{re.escape(key)}["\'][^>]+content=["\']([^"\']+)["\']',
        rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']{re.escape(key)}["\']',
    ]
    for pat in pats:
        m = re.search(pat, doc, re.I | re.S)
        if m:
            return _clean(m.group(1))
    return ''


def _walk_product(obj: Any) -> dict[str, Any] | None:
    if isinstance(obj, dict):
        tp = obj.get('@type')
        types = tp if isinstance(tp, list) else [tp]
        if any(str(x).lower() == 'product' for x in types if x):
            return obj
        for v in obj.values():
            hit = _walk_product(v)
            if hit:
                return hit
    elif isinstance(obj, list):
        for v in obj:
            hit = _walk_product(v)
            if hit:
                return hit
    return None


def _jsonld_product(doc: str) -> dict[str, Any]:
    for raw in re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        doc,
        re.I | re.S,
    ):
        txt = html_lib.unescape(raw.strip())
        try:
            obj = json.loads(txt)
        except Exception:
            continue
        hit = _walk_product(obj)
        if hit:
            return hit
    return {}


def _model_from_title(title: str) -> str:
    # Product model strings usually mix letters and digits (IRT6030, M5001A, A9S, etc.).
    vals = re.findall(r'(?<![A-Za-z0-9])[A-Za-z]{1,8}[-_ ]?\d[A-Za-z0-9._-]{1,18}(?![A-Za-z0-9])', title or '')
    vals = [re.sub(r'\s+', '', x).strip('._-') for x in vals]
    return max(vals, key=len) if vals else ''


def clean_product_title(title: str) -> str:
    s = _clean(title)
    s = re.sub(r'\s*[|｜]\s*쿠팡\s*$', '', s, flags=re.I)
    s = re.sub(r'\s*[-–—]\s*Coupang\s*$', '', s, flags=re.I)
    s = re.sub(r'^쿠팡!\s*', '', s, flags=re.I)
    return normalize_title(s)


def parse_product_html(doc: str, final_url: str = '') -> dict[str, Any]:
    product = _jsonld_product(doc)
    title_tag = ''
    m = re.search(r'<title[^>]*>(.*?)</title>', doc, re.I | re.S)
    if m:
        title_tag = _clean(m.group(1))

    title = clean_product_title(
        product.get('name')
        or _meta(doc, 'og:title')
        or _meta(doc, 'twitter:title')
        or title_tag
    )
    image = _clean(product.get('image') or _meta(doc, 'og:image') or _meta(doc, 'twitter:image'))
    brand = _clean(product.get('brand'))
    model = _clean(product.get('model') or product.get('mpn') or product.get('sku')) or _model_from_title(title)
    description = _clean(product.get('description') or _meta(doc, 'og:description'))

    pid = ''
    m = re.search(r'/products/(\d+)', final_url or '')
    if m:
        pid = m.group(1)

    low = (doc or '').lower()
    blocked = any(x in low for x in ('access denied', 'request blocked', 'captcha')) and not title
    return {
        'title': title,
        'brand': brand,
        'model': model,
        'image': image,
        'description': description,
        'url': final_url,
        'product_id': pid,
        'blocked': blocked,
        'source': 'http',
    }


def fetch_product_profile(url: str, timeout: int = 18) -> dict[str, Any]:
    if not is_http_url(url):
        raise ValueError('올바른 상품 URL을 입력하세요.')
    headers = {
        'User-Agent': UA,
        'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.7,en;q=0.6',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    }
    r = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
    r.raise_for_status()
    profile = parse_product_html(r.text, r.url)
    profile['input_url'] = url
    profile['http_status'] = r.status_code
    return profile


def profile_from_browser(data: dict[str, Any], input_url: str = '') -> dict[str, Any]:
    p = dict(data or {})
    p['title'] = clean_product_title(p.get('title') or p.get('ogTitle') or p.get('pageTitle') or '')
    p['brand'] = _clean(p.get('brand'))
    p['model'] = _clean(p.get('model') or p.get('sku')) or _model_from_title(p['title'])
    p['image'] = _clean(p.get('image') or p.get('ogImage'))
    p['description'] = _clean(p.get('description'))
    p['url'] = p.get('url') or input_url
    p['input_url'] = input_url
    p['blocked'] = False
    p['source'] = 'browser'
    return p


def merge_profiles(primary: dict[str, Any], secondary: dict[str, Any]) -> dict[str, Any]:
    a = dict(primary or {})
    b = dict(secondary or {})
    out = dict(a)
    for key in ('title', 'brand', 'model', 'image', 'description', 'url', 'product_id'):
        if not out.get(key) and b.get(key):
            out[key] = b[key]
    if b.get('source') == 'browser' and b.get('title'):
        # Browser data represents the page the user can actually see after redirects/login.
        for key in ('title', 'brand', 'model', 'image', 'description', 'url'):
            if b.get(key):
                out[key] = b[key]
        out['source'] = 'browser'
    out['blocked'] = bool(out.get('blocked') and not out.get('title'))
    return out


def search_seed(profile: dict[str, Any]) -> str:
    parts = []
    for key in ('brand', 'model', 'title'):
        v = _clean((profile or {}).get(key))
        if v and v.lower() not in [x.lower() for x in parts]:
            parts.append(v)
    return ' '.join(parts).strip()


def profile_summary(profile: dict[str, Any]) -> str:
    if not profile:
        return '상품 분석 전'
    parts = []
    if profile.get('brand'):
        parts.append('브랜드 ' + str(profile['brand']))
    if profile.get('model'):
        parts.append('모델 ' + str(profile['model']))
    if profile.get('product_id'):
        parts.append('상품번호 ' + str(profile['product_id']))
    src = '브라우저' if profile.get('source') == 'browser' else '페이지'
    return f'{src} 분석 완료' + ((' · ' + ' · '.join(parts)) if parts else '')


def _image_bytes(url: str, timeout: int = 6) -> bytes:
    r = requests.get(url, headers={'User-Agent': UA, 'Referer': url}, timeout=timeout)
    r.raise_for_status()
    if len(r.content) > 8 * 1024 * 1024:
        raise ValueError('image too large')
    return r.content


@lru_cache(maxsize=128)
def _dhash(url: str) -> int:
    data = _image_bytes(url)
    im = Image.open(io.BytesIO(data)).convert('L').resize((9, 8))
    px = list(im.getdata())
    bits = 0
    for y in range(8):
        for x in range(8):
            bits = (bits << 1) | int(px[y * 9 + x] > px[y * 9 + x + 1])
    return bits


def image_similarity(url_a: str, url_b: str) -> int | None:
    if not (is_http_url(url_a) and is_http_url(url_b)):
        return None
    try:
        a, b = _dhash(url_a), _dhash(url_b)
        dist = (a ^ b).bit_count()
        return max(0, min(100, round((1 - dist / 64) * 100)))
    except Exception:
        return None


def _contains_norm(haystack: str, needle: str) -> bool:
    a = re.sub(r'[^a-z0-9가-힣一-龥]', '', (haystack or '').lower())
    b = re.sub(r'[^a-z0-9가-힣一-龥]', '', (needle or '').lower())
    return bool(b and b in a)


def score_candidate(profile: dict[str, Any], candidate: dict[str, Any], check_image: bool = True) -> dict[str, Any]:
    row = dict(candidate or {})
    title = _clean(row.get('title') or row.get('text'))
    seed = search_seed(profile)
    text_score = relevance(seed, title) if seed and title else 0

    model = _clean(profile.get('model'))
    brand = _clean(profile.get('brand'))
    if model and _contains_norm(title, model):
        text_score = max(text_score, 92)
    if brand and _contains_norm(title, brand):
        text_score = min(100, max(text_score, 60) + 10)

    img_score = None
    if check_image and profile.get('image') and row.get('thumbnail'):
        img_score = image_similarity(str(profile['image']), str(row['thumbnail']))

    if img_score is None:
        combined = text_score
    else:
        combined = round(text_score * 0.68 + img_score * 0.32)
        if img_score >= 90:
            combined = max(combined, 82)
        elif img_score >= 82:
            combined = max(combined, 70)

    row['_text_score'] = int(text_score)
    row['_image_score'] = img_score
    row['_score'] = max(0, min(100, int(combined)))
    return row


def rank_candidates(profile: dict[str, Any], rows: list[dict[str, Any]], max_image_checks: int = 28) -> list[dict[str, Any]]:
    clean = []
    seen = set()
    for r in rows or []:
        u = str((r or {}).get('url') or '').strip()
        if not u or u in seen or (r or {}).get('error'):
            continue
        seen.add(u)
        clean.append(dict(r))

    # First calculate cheap text scores.
    ranked = [score_candidate(profile, r, check_image=False) for r in clean]

    # Image checks are network-bound; run a bounded number concurrently.
    indices = [i for i, r in enumerate(ranked) if r.get('thumbnail')][:max_image_checks]
    if profile.get('image') and indices:
        with ThreadPoolExecutor(max_workers=6) as ex:
            futs = {ex.submit(score_candidate, profile, ranked[i], True): i for i in indices}
            for fut in as_completed(futs):
                i = futs[fut]
                try:
                    ranked[i] = fut.result()
                except Exception:
                    pass

    ranked.sort(key=lambda x: (x.get('_score', 0), x.get('_image_score') or -1), reverse=True)
    return ranked
