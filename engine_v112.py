from __future__ import annotations

import json
import re
import urllib.parse
import requests

from engine import *  # reuse shared settings/download/render/upload helpers

PLATFORMS = {
    'TikTok': 'site:tiktok.com/@ /video/',
    'YouTube': 'site:youtube.com/shorts OR site:youtube.com/watch',
    'Instagram': 'site:instagram.com/reel',
    'Douyin': 'site:douyin.com/video',
    'Xiaohongshu': 'site:xiaohongshu.com/explore',
    'Kuaishou': 'site:kuaishou.com/short-video',
    '1688': 'site:1688.com',
}


def rule_query_plan(title: str) -> dict[str, list[str]]:
    base = ' '.join(tokens(normalize_title(title))[:7]) or title
    return {
        'TikTok': [base, base + ' review', base + ' demo'],
        'YouTube': [base + ' shorts', base + ' review', base + ' demo'],
        'Instagram': [base + ' reels', base + ' review', base + ' demo'],
        'Douyin': [base, base + ' 测评', base + ' 使用'],
        'Xiaohongshu': [base, base + ' 好物', base + ' 测评'],
        'Kuaishou': [base, base + ' 使用', base + ' 推荐'],
        '1688': [base, base + ' 视频', base + ' 详情'],
    }


def gemini_query_plan(title: str, key: str) -> dict[str, list[str]]:
    if not key:
        return rule_query_plan(title)
    prompt = (
        'Return JSON only with keys TikTok, YouTube, Instagram, Douyin, Xiaohongshu, Kuaishou, 1688. '
        'Each value must contain 3 concise product video search strings. Use Simplified Chinese for Chinese platforms '
        'and natural English for TikTok, YouTube and Instagram. Product: ' + title
    )
    try:
        r = requests.post(
            'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent',
            params={'key': key},
            json={'contents': [{'parts': [{'text': prompt}]}]},
            timeout=30,
        )
        r.raise_for_status()
        text = r.json()['candidates'][0]['content']['parts'][0]['text']
        text = re.sub(r'^```(?:json)?|```$', '', text.strip(), flags=re.M).strip()
        data = json.loads(text)
        return {p: [str(x) for x in data.get(p, [])][:3] for p in PLATFORMS}
    except Exception as e:
        log('Gemini fallback: ' + str(e))
        return rule_query_plan(title)


def direct_search_url(platform: str, query: str) -> str:
    q = urllib.parse.quote(query)
    urls = {
        'TikTok': f'https://www.tiktok.com/search/video?q={q}',
        'YouTube': f'https://www.youtube.com/results?search_query={q}',
        'Instagram': f'https://www.instagram.com/explore/search/keyword/?q={q}',
        'Douyin': f'https://www.douyin.com/search/{q}?type=video',
        'Xiaohongshu': f'https://www.xiaohongshu.com/search_result?keyword={q}&source=web_search_result_notes',
        'Kuaishou': f'https://www.kuaishou.com/search/video?searchKey={q}',
        '1688': f'https://s.1688.com/selloffer/offer_search.htm?keywords={q}',
    }
    return urls[platform]


def external_search_url(platform: str, query: str) -> str:
    return 'https://www.google.com/search?q=' + urllib.parse.quote_plus(PLATFORMS[platform] + ' ' + query)
