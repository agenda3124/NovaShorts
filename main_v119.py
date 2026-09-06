from __future__ import annotations

import time
import uuid
from pathlib import Path

import main_v118 as base
import main_v117 as ui117
import engine_v112 as source_engine
from PySide6.QtCore import QObject, Signal, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import *

from bridge import TASKS, extension_recent, wait_for_result, wait_for_results
from engine import coupang_search, download_video, relevance
from product_source import (
    fetch_product_profile,
    merge_profiles,
    profile_from_browser,
    profile_summary,
    rank_candidates,
    score_candidate,
    search_seed,
)

VERSION = '1.19'
PLATFORM_ORDER = ['TikTok', 'YouTube', 'Instagram', 'Douyin', 'Xiaohongshu', 'Kuaishou', '1688']
platform_chip = ui117.platform_chip

for mod in [base, getattr(base, 'base', None), ui117]:
    try:
        mod.VERSION = VERSION
    except Exception:
        pass

V119_CSS = r'''
QLabel#productProfile119 {
    background:transparent;
    color:#8fa4c7;
    font-size:11px;
    padding-left:2px;
}
QPushButton[apiAssist119="true"] {
    background:#17243c;
    border:1px solid #334765;
    border-radius:8px;
    color:#cfd9ed;
    min-height:28px;
    max-height:28px;
    padding:0 12px;
    font-size:11px;
    font-weight:700;
}
QPushButton[apiAssist119="true"]:hover {
    background:#21304b;
    border-color:#5c75a1;
    color:white;
}
'''


class ProductBus(QObject):
    profile_ready = Signal(dict)


class Nova(base.Nova):
    def __init__(self):
        self.product_profile = {}
        super().__init__()
        self.product_bus119 = ProductBus()
        self.product_bus119.profile_ready.connect(self._apply_product_profile119)
        self.setWindowTitle(f'NovaShorts Studio v{VERSION}')
        try:
            self.status.setText(f'NovaShorts v{VERSION} 시작')
        except Exception:
            pass

    def build(self):
        super().build()
        self.setWindowTitle(f'NovaShorts Studio v{VERSION}')
        self.setStyleSheet(self.styleSheet() + V119_CSS)

    def source_page(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(10)

        title = QLabel('글로벌 영상 소싱')
        title.setObjectName('title')
        title.setFixedHeight(38)
        v.addWidget(title)

        product_card = QFrame()
        product_card.setObjectName('sourceSection117')
        product_card.setFixedHeight(218)
        pv = QVBoxLayout(product_card)
        pv.setContentsMargins(14, 12, 14, 12)
        pv.setSpacing(8)
        pv.addWidget(self._section_title117('상품 / 검색어'))

        self.product = QLineEdit()
        self.product.setProperty('source117', True)
        self.product.setPlaceholderText('상품명 · 브랜드 · 모델명을 입력하세요')
        self.product_url = QLineEdit()
        self.product_url.setProperty('source117', True)
        self.product_url.setPlaceholderText('쿠팡/상품 URL을 붙여넣으세요')
        self.product_url.returnPressed.connect(self.analyze_product_url119)

        b1 = QPushButton('제품명 소싱 시작')
        b1.setProperty('sourceAction117', True)
        b1.clicked.connect(self.source_from_name119)
        b2 = QPushButton('URL 분석 · 소싱')
        b2.setProperty('sourceAction117', True)
        b2.clicked.connect(self.analyze_product_url119)

        self.source_row_product = self._source_row117(self.product, b1)
        self.source_row_url = self._source_row117(self.product_url, b2)
        pv.addWidget(self.source_row_product)
        pv.addWidget(self.source_row_url)

        info_row = QWidget()
        info_row.setFixedHeight(32)
        ih = QHBoxLayout(info_row)
        ih.setContentsMargins(0, 0, 0, 0)
        ih.setSpacing(8)
        self.product_profile_label119 = QLabel('상품 분석 전 · URL 소싱은 쿠팡 API 키 없이도 시도합니다.')
        self.product_profile_label119.setObjectName('productProfile119')
        ih.addWidget(self.product_profile_label119, 1)
        api_btn = QPushButton('쿠팡 API 보강')
        api_btn.setProperty('apiAssist119', True)
        api_btn.clicked.connect(self.coupang_lookup)
        ih.addWidget(api_btn)
        pv.addWidget(info_row)
        v.addWidget(product_card)

        platform_card = QFrame()
        platform_card.setObjectName('platformSection117')
        platform_card.setFixedHeight(102)
        pvl = QVBoxLayout(platform_card)
        pvl.setContentsMargins(14, 10, 14, 12)
        pvl.setSpacing(8)
        pvl.addWidget(self._section_title117('플랫폼'))
        chips = QHBoxLayout()
        chips.setContentsMargins(0, 0, 0, 0)
        chips.setSpacing(8)
        self.pchecks = {}
        selected_now = set(getattr(self.s, 'platform_sources', []) or [])
        for p in PLATFORM_ORDER:
            btn = platform_chip(p, p in selected_now or not selected_now, True)
            btn.setMinimumWidth(78)
            btn.setFixedHeight(38)
            self.pchecks[p] = btn
            chips.addWidget(btn)
        chips.addStretch()
        pvl.addLayout(chips)
        v.addWidget(platform_card)

        split = QSplitter(Qt.Horizontal)
        split.setChildrenCollapsible(False)

        left = QFrame()
        left.setObjectName('splitCard117')
        lv = QVBoxLayout(left)
        lv.setContentsMargins(13, 10, 13, 12)
        lv.setSpacing(8)
        lv.addWidget(self._section_title117('검색 계획'))
        self.planbox = QPlainTextEdit()
        lv.addWidget(self.planbox, 1)
        lbuttons = QHBoxLayout()
        lbuttons.setSpacing(8)
        bo = QPushButton('검색 페이지 열기')
        bo.clicked.connect(self.open_searches)
        bc = QPushButton('Chrome Bridge 자동수집')
        bc.clicked.connect(self.bridge_collect)
        lbuttons.addWidget(bo)
        lbuttons.addWidget(bc)
        lv.addLayout(lbuttons)
        split.addWidget(left)

        right = QFrame()
        right.setObjectName('splitCard117')
        rv = QVBoxLayout(right)
        rv.setContentsMargins(13, 10, 13, 12)
        rv.setSpacing(8)
        rv.addWidget(self._section_title117('수집된 영상 목록'))
        self.candidates = QListWidget()
        self.candidates.itemSelectionChanged.connect(self.candidate_selected)
        rv.addWidget(self.candidates, 1)
        self.cand_url = QLineEdit()
        self.cand_url.setPlaceholderText('선택 후보 URL')
        self.cand_text = QLineEdit()
        self.cand_text.setPlaceholderText('선택 후보 제목')
        rv.addWidget(self.cand_url)
        rv.addWidget(self.cand_text)
        rb = QHBoxLayout()
        self.score = QLabel('유사도 -')
        bs = QPushButton('유사도 계산')
        bs.clicked.connect(self.score_it)
        bd = QPushButton('선택 영상 다운로드')
        bd.clicked.connect(self.download_it)
        rb.addWidget(self.score)
        rb.addStretch()
        rb.addWidget(bs)
        rb.addWidget(bd)
        rv.addLayout(rb)
        split.addWidget(right)
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 2)
        v.addWidget(split, 1)
        return w

    def home_to_source(self):
        text = self.home_keyword.text().strip()
        if not text:
            return
        self.product_profile = {'title': text, 'brand': '', 'model': '', 'image': '', 'source': 'manual'}
        self.go(1)
        self.product.setText(text)
        if hasattr(self, 'product_profile_label119'):
            self.product_profile_label119.setText('제품명 입력 · 검색어 생성 후 자동수집')
        for p, cb in self.pchecks.items():
            if p in self.home_checks:
                cb.setChecked(self.home_checks[p].isChecked())
        self.auto_collect_after_plan = True
        self.make_plan()

    def source_from_name119(self):
        title = self.product.text().strip()
        if not title:
            self.bus.err.emit('상품명을 입력하세요.')
            return
        self.product_profile = {'title': title, 'brand': '', 'model': '', 'image': '', 'source': 'manual'}
        self.product_profile_label119.setText('제품명 입력 · 플랫폼 검색 준비')
        self.auto_collect_after_plan = True
        self.make_plan()

    def analyze_product_url119(self):
        url = self.product_url.text().strip()
        if not url:
            self.bus.err.emit('쿠팡/상품 URL을 입력하세요.')
            return

        def run():
            profile = {}
            http_error = ''
            try:
                profile = fetch_product_profile(url)
            except Exception as e:
                http_error = str(e)

            # If normal HTTP extraction is incomplete, or if the browser extension is
            # available, use the user's visible browser session as a clean fallback.
            should_try_browser = not profile.get('title') or not profile.get('image')
            if extension_recent(5.0):
                should_try_browser = True

            if should_try_browser and extension_recent(5.0):
                tid = uuid.uuid4().hex
                TASKS.put({'type': 'analyze_product_page', 'task_id': tid, 'url': url, 'wait_ms': 4200})
                result = wait_for_result(tid, 18)
                if result and result.get('profile'):
                    browser_profile = profile_from_browser(result.get('profile') or {}, url)
                    profile = merge_profiles(profile, browser_profile)

            if not profile.get('title'):
                hint = 'Chrome Bridge 확장 프로그램을 새 버전으로 다시 로드한 뒤 재시도하세요.'
                if http_error:
                    hint += '\n페이지 분석: ' + http_error
                raise RuntimeError('상품명 추출에 실패했습니다.\n' + hint)

            self.product_bus119.profile_ready.emit(profile)

        self.work('상품 URL 분석', run)

    def _apply_product_profile119(self, profile):
        self.product_profile = dict(profile or {})
        title = str(self.product_profile.get('title') or '').strip()
        if title:
            self.product.setText(title)
        if hasattr(self, 'product_profile_label119'):
            self.product_profile_label119.setText(profile_summary(self.product_profile))
        self.say('상품 분석 완료 · 관련 영상 검색을 시작합니다.')
        self.auto_collect_after_plan = True
        self.make_plan()

    def coupang_lookup(self):
        kw = self.product.text().strip()
        if not kw:
            self.bus.err.emit('먼저 상품명을 입력하거나 상품 URL을 분석하세요.')
            return
        if not self.s.coupang_access_key or not self.s.coupang_secret_key:
            self.bus.err.emit('쿠팡 API 보강은 선택 기능입니다.\nURL 분석·소싱은 API 키 없이 사용할 수 있습니다.\nAPI 보강을 쓰려면 설정에서 Access/Secret Key를 입력하세요.')
            return

        def run():
            data = coupang_search(kw, self.s.coupang_access_key, self.s.coupang_secret_key)
            items = data.get('data', {}).get('productData', []) if isinstance(data.get('data'), dict) else data.get('data', [])
            items = items or []
            if not items:
                raise RuntimeError('쿠팡 API 상품 검색 결과가 없습니다.')
            x = items[0]
            api_profile = {
                'title': x.get('productName', '') or kw,
                'brand': '',
                'model': '',
                'image': x.get('productImage', ''),
                'url': x.get('productUrl', ''),
                'source': 'coupang_api',
            }
            merged = merge_profiles(self.product_profile, api_profile) if self.product_profile else api_profile
            self.product_bus119.profile_ready.emit(merged)

        self.work('쿠팡 API 보강', run)

    def make_plan(self):
        title = self.product.text().strip()
        if not title:
            return
        if not self.product_profile or self.product_profile.get('title') != title:
            self.product_profile = {'title': title, 'brand': '', 'model': '', 'image': '', 'source': 'manual'}
        seed = search_seed(self.product_profile) or title

        def run():
            if self.s.use_gemini_query_planning:
                plan = source_engine.gemini_query_plan(seed, self.s.gemini_api_key)
            else:
                plan = source_engine.rule_query_plan(seed)
            self.bus.plan.emit(plan)

        self.work('AI 검색어 생성', run)

    def open_searches(self):
        if not self.query_plan:
            return
        import webbrowser
        for p in self.selected():
            kw = (self.query_plan.get(p) or [''])[0]
            if kw:
                webbrowser.open(source_engine.direct_search_url(p, kw))

    def bridge_collect(self):
        if not self.query_plan:
            return
        if not extension_recent(5.0):
            self.bus.err.emit(
                'Chrome Bridge 확장 프로그램이 연결되어 있지 않습니다.\n'
                'v1.19 ZIP의 browser-extension 폴더를 Chrome 확장 프로그램에서 다시 로드하고 토큰을 연결하세요.'
            )
            return

        task_ids = []
        for p in self.selected():
            for kw in (self.query_plan.get(p) or [])[:2]:
                if not kw:
                    continue
                tid = uuid.uuid4().hex
                TASKS.put({
                    'type': 'collect_links',
                    'task_id': tid,
                    'platform': p,
                    'url': source_engine.direct_search_url(p, kw),
                    'keyword': kw,
                    'wait_ms': 4700,
                })
                task_ids.append(tid)

        if not task_ids:
            return
        self.say(f'플랫폼 자동수집 {len(task_ids)}개 작업 전송')

        def wait_and_rank():
            packets = wait_for_results(task_ids, 55)
            rows = []
            for packet in packets:
                rows.extend(packet.get('items', []) or [])
            profile = self.product_profile or {'title': self.product.text().strip()}
            ranked = rank_candidates(profile, rows)
            self.bus.candidates.emit(ranked)

        self.work('플랫폼 후보 수집', wait_and_rank)

    def on_candidates(self, rows):
        ranked = []
        seen = set()
        for raw in rows or []:
            r = dict(raw or {})
            u = str(r.get('url') or '').strip()
            if not u or u in seen or r.get('error'):
                continue
            seen.add(u)
            if '_score' not in r:
                r = score_candidate(self.product_profile or {'title': self.product.text()}, r, check_image=False)
            ranked.append(r)

        ranked.sort(key=lambda x: x.get('_score', 0), reverse=True)
        if self.s.auto_skip_low_similarity:
            passed = [r for r in ranked if int(r.get('_score', 0)) >= self.s.min_similarity]
            # Avoid the misleading "0 results" state when the similarity filter is too strict.
            # Keep a few best candidates visibly marked for manual review.
            if passed:
                clean = passed
            else:
                clean = ranked[:5]
                for r in clean:
                    r['_review_only'] = True
        else:
            clean = ranked

        self.candidate_rows = clean
        self.candidates.clear()
        for r in clean:
            title = r.get('title', '') or r.get('text', '')
            img = r.get('_image_score')
            extra = f' · 이미지 {img}%' if isinstance(img, int) else ''
            review = ' · 기준미달/검토' if r.get('_review_only') else ''
            it = QListWidgetItem(
                f"[{r.get('platform','')}] {title[:76]}\n"
                f"관련도 {r.get('_score',0)}%{extra}{review}  {r.get('url','')}"
            )
            it.setData(Qt.UserRole, r)
            self.candidates.addItem(it)
        self.render_cards(clean)
        self.say(f'관련 영상 후보 {len(clean)}개')

    def score_it(self):
        row = {
            'title': self.cand_text.text().strip(),
            'url': self.cand_url.text().strip(),
            'thumbnail': '',
        }
        it = self.candidates.currentItem() if hasattr(self, 'candidates') else None
        if it:
            row.update(it.data(Qt.UserRole) or {})
        scored = score_candidate(self.product_profile or {'title': self.product.text()}, row, check_image=True)
        s = int(scored.get('_score', 0))
        img = scored.get('_image_score')
        suffix = f' · 이미지 {img}%' if isinstance(img, int) else ''
        self.score.setText(f'관련도 {s}%{suffix}')
        self.score.setStyleSheet('color:#65e28a;font-weight:700' if s >= self.s.min_similarity else 'color:#ffb95f;font-weight:700')

    def download_it(self):
        url = self.cand_url.text().strip()
        if not url:
            return

        def run():
            first_error = None
            try:
                path = download_video(url, self.s.output_folder, lambda x: self.bus.log.emit(x))
                self.bus.downloaded.emit(str(path))
                return
            except Exception as e:
                first_error = e

            # Browser-page media fallback mirrors the verified SSMaker-style fallback:
            # first try the normal downloader, then inspect the loaded public page for
            # playable media URLs and retry those URLs.
            if extension_recent(5.0):
                tid = uuid.uuid4().hex
                TASKS.put({'type': 'extract_media', 'task_id': tid, 'url': url, 'wait_ms': 5000})
                packet = wait_for_result(tid, 22)
                media_urls = (((packet or {}).get('media') or {}).get('media') or [])
                for media_url in media_urls[:10]:
                    try:
                        path = download_video(media_url, self.s.output_folder, lambda x: self.bus.log.emit(x))
                        self.bus.downloaded.emit(str(path))
                        return
                    except Exception:
                        continue
            raise RuntimeError('영상 다운로드에 실패했습니다.\n' + str(first_error or '재생 가능한 미디어 URL을 찾지 못했습니다.'))

        self.work('영상 다운로드', run)


if __name__ == '__main__':
    app = QApplication([])
    app.setApplicationName('NovaShorts')
    app.setFont(QFont('Malgun Gothic', 10))
    win = Nova()
    win.show()
    app.exec()
