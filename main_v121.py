from __future__ import annotations

import os
import re
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import main_v120 as base
import main_v113
from PySide6.QtCore import QObject, Signal, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import *

import browser_cdp
import engine_v112 as source_engine
from bridge import TASKS, extension_recent, wait_for_result
from engine import download_video, log, save_settings
from pipeline_v121 import run_processing_pipeline_v121
from product_source import fetch_product_profile, merge_profiles, profile_from_browser, profile_summary, rank_candidates

VERSION = '1.21'

for mod in [base, getattr(base, 'base', None), getattr(getattr(base, 'base', None), 'base', None)]:
    try:
        if mod is not None:
            mod.VERSION = VERSION
    except Exception:
        pass

V121_CSS = r'''
QFrame#makerCard121,QFrame#makerSettings121,QFrame#makerResult121{background:#111b30;border:1px solid #2d4263;border-radius:13px;}
QLabel#makerTitle121{background:transparent;color:#f6f8ff;font-size:25px;font-weight:900;}
QLabel#makerSub121{background:transparent;color:#8fa4c7;font-size:12px;}
QPushButton[mode121="true"]{background:#131f34;border:1px solid #304663;border-radius:10px;min-height:42px;padding:0 16px;color:#cbd7eb;font-weight:750;}
QPushButton[mode121="true"]:checked{background:#2f55d9;border-color:#6f88ff;color:white;}
QPushButton[accordion121="true"]{background:#111b30;border:1px solid #2b405f;border-radius:9px;min-height:38px;text-align:left;padding:0 12px;color:#e7edfa;font-weight:750;}
QFrame[accordionBody121="true"]{background:#0f192b;border:1px solid #263956;border-radius:9px;}
QLabel[fieldLabel121="true"]{background:transparent;color:#cbd6e9;font-size:12px;font-weight:650;}
QPushButton[makePrimary121="true"]{background:#315cff;border:1px solid #7188ff;border-radius:11px;min-height:48px;color:white;font-size:15px;font-weight:850;}
QPushButton[makePrimary121="true"]:hover{background:#4a6fff;}
QPushButton[soft121="true"]{background:#17243c;border:1px solid #344b6d;border-radius:9px;min-height:34px;color:#dbe5f7;font-weight:700;}
QLabel#productInfo121{background:#0d1729;border:1px solid #263a58;border-radius:8px;padding:8px;color:#9fb2d1;}
QListWidget#sourceList121{background:#0d1729;border:1px solid #314764;border-radius:9px;padding:5px;}
QLabel#resultPath121{background:transparent;color:#78e5a0;font-size:12px;}
'''


class HomeBus121(QObject):
    profile = Signal(dict)


class Nova(base.Nova):
    def __init__(self):
        self.home_pending_create121 = False
        self.home_product_profile121 = {}
        self.home_multi_files121 = []
        self.home_ready_files121 = []
        self.home_final121 = ''
        super().__init__()
        self.home_bus121 = HomeBus121()
        self.home_bus121.profile.connect(self._home_profile_ready121)
        self.setWindowTitle(f'NovaShorts Studio v{VERSION}')
        try:
            self.status.setText(f'NovaShorts v{VERSION} 시작 · 한 화면 제작 모드')
        except Exception:
            pass
        self._sync_home_controls121()
        self._apply_page_mode121()

    def build(self):
        super().build()
        self.setWindowTitle(f'NovaShorts Studio v{VERSION}')
        self.setStyleSheet(self.styleSheet() + V121_CSS)
        self.setMinimumSize(1024, 680)
        try:
            if self.nav:
                self.nav[0].setText('▶   제작')
        except Exception:
            pass

    def source_page(self):
        w = super().source_page()
        for b in w.findChildren(QPushButton):
            if b.text() == 'Chrome Bridge 자동수집':
                b.setText('브라우저 자동수집')
        return w

    def home_page(self):
        outer = QWidget()
        ov = QVBoxLayout(outer)
        ov.setContentsMargins(0, 0, 0, 0)
        ov.setSpacing(7)
        head = QHBoxLayout()
        titles = QVBoxLayout()
        title = QLabel('쇼츠 만들기'); title.setObjectName('makerTitle121')
        sub = QLabel('준비한 자료를 고르고 필요한 설정만 바꾼 뒤, 영상 만들기만 누르세요.'); sub.setObjectName('makerSub121')
        titles.addWidget(title); titles.addWidget(sub); head.addLayout(titles); head.addStretch()
        self.browser_state121 = QLabel('Chrome/Edge 자동 연결'); self.browser_state121.setObjectName('muted'); head.addWidget(self.browser_state121)
        ov.addLayout(head)

        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff); scroll.setFrameShape(QFrame.NoFrame)
        host = QWidget(); v = QVBoxLayout(host); v.setContentsMargins(0, 3, 5, 5); v.setSpacing(9)

        mode_card = QFrame(); mode_card.setObjectName('makerCard121')
        mv = QVBoxLayout(mode_card); mv.setContentsMargins(13, 11, 13, 13); mv.setSpacing(9)
        mt = QLabel('무엇으로 만들까요?'); mt.setObjectName('section'); mv.addWidget(mt)
        mh = QHBoxLayout(); mh.setSpacing(8); self.mode_group121 = QButtonGroup(self); self.mode_group121.setExclusive(True); self.mode_buttons121 = []
        for i, name in enumerate(['상품 주소', '영상 1개', '여러 영상', '준비한 자료']):
            b = QPushButton(name); b.setProperty('mode121', True); b.setCheckable(True); b.setChecked(i == 0)
            b.clicked.connect(lambda checked=False, n=i: self._set_mode121(n)); self.mode_group121.addButton(b, i); self.mode_buttons121.append(b); mh.addWidget(b, 1)
        mv.addLayout(mh)
        self.mode_stack121 = QStackedWidget()
        self.mode_stack121.addWidget(self._product_mode121()); self.mode_stack121.addWidget(self._single_mode121()); self.mode_stack121.addWidget(self._multi_mode121()); self.mode_stack121.addWidget(self._prepared_mode121())
        mv.addWidget(self.mode_stack121); v.addWidget(mode_card)

        settings_card = QFrame(); settings_card.setObjectName('makerSettings121')
        sv = QVBoxLayout(settings_card); sv.setContentsMargins(12, 10, 12, 12); sv.setSpacing(7)
        st = QLabel('제작 설정'); st.setObjectName('section'); sv.addWidget(st)
        self.home_voice121 = QComboBox(); self.home_voice121.addItems(['Edge TTS - SunHi', 'Edge TTS - InJoon', 'Edge TTS - Hyunsu'])
        self.home_rate121 = QComboBox(); self.home_rate121.addItems(['-10%', '+0%', '+10%', '+20%'])
        self._accordion121(sv, '목소리 설정', self._settings_body121([('목소리', self.home_voice121), ('말하기 속도', self.home_rate121)]))
        self.home_remove_sub121 = main_v113.OnOffButton(True); self.home_add_sub121 = main_v113.OnOffButton(True)
        self._accordion121(sv, '자막 설정', self._settings_body121([('원본 자막 제거', self.home_remove_sub121), ('한국어 자막 넣기', self.home_add_sub121)]))
        self.home_auto_cut121 = main_v113.OnOffButton(True); self.home_target121 = QSpinBox(); self.home_target121.setRange(8, 60)
        self.home_thumb121 = main_v113.OnOffButton(True); self.home_wm121 = main_v113.OnOffButton(False)
        self._accordion121(sv, '편집 설정', self._settings_body121([('자동 컷 편집', self.home_auto_cut121), ('목표 길이(초)', self.home_target121), ('썸네일 자동 생성', self.home_thumb121), ('워터마크', self.home_wm121)]))
        v.addWidget(settings_card)

        self.home_make121 = QPushButton('▶  영상 만들기 시작'); self.home_make121.setProperty('makePrimary121', True); self.home_make121.clicked.connect(self.start_home_make121); v.addWidget(self.home_make121)
        result = QFrame(); result.setObjectName('makerResult121'); rv = QHBoxLayout(result); rv.setContentsMargins(12, 9, 10, 9)
        self.home_result_status121 = QLabel('완성된 영상은 여기에서 바로 확인할 수 있습니다.'); self.home_result_status121.setObjectName('resultPath121'); rv.addWidget(self.home_result_status121, 1)
        play = QPushButton('▶ 재생'); play.setProperty('soft121', True); play.clicked.connect(self._play_home_result121)
        folder = QPushButton('폴더 열기'); folder.setProperty('soft121', True); folder.clicked.connect(self._open_home_result_folder121)
        rv.addWidget(play); rv.addWidget(folder); v.addWidget(result); v.addStretch()
        scroll.setWidget(host); ov.addWidget(scroll, 1); self.home_scroll121 = scroll
        return outer

    def _product_mode121(self):
        w = QWidget(); q = QGridLayout(w); q.setContentsMargins(0, 3, 0, 0); q.setHorizontalSpacing(8); q.setVerticalSpacing(7)
        self.home_product_url121 = QLineEdit(); self.home_product_url121.setPlaceholderText('쿠팡/상품 주소를 붙여넣으세요')
        self.home_product_name121 = QLineEdit(); self.home_product_name121.setPlaceholderText('상품명은 자동으로 확인됩니다')
        check = QPushButton('입력 내용 확인'); check.setProperty('soft121', True); check.clicked.connect(self.home_confirm_product121)
        self.home_product_info121 = QLabel('주소를 넣으면 상품명·브랜드·모델·대표이미지를 확인합니다.'); self.home_product_info121.setObjectName('productInfo121'); self.home_product_info121.setWordWrap(True)
        q.addWidget(self.home_product_url121, 0, 0, 1, 3); q.addWidget(check, 0, 3); q.addWidget(self.home_product_name121, 1, 0, 1, 4); q.addWidget(self.home_product_info121, 2, 0, 1, 4)
        return w

    def _single_mode121(self):
        w = QWidget(); q = QGridLayout(w); q.setContentsMargins(0, 3, 0, 0); q.setSpacing(8)
        self.home_single_path121 = QLineEdit(); self.home_single_path121.setPlaceholderText('사용할 영상 파일 1개를 선택하세요')
        pick = QPushButton('파일 선택'); pick.setProperty('soft121', True); pick.clicked.connect(self._pick_single121)
        self.home_single_title121 = QLineEdit(); self.home_single_title121.setPlaceholderText('상품명/주제 (선택)')
        q.addWidget(self.home_single_path121, 0, 0, 1, 3); q.addWidget(pick, 0, 3); q.addWidget(self.home_single_title121, 1, 0, 1, 4)
        return w

    def _multi_mode121(self):
        w = QWidget(); q = QGridLayout(w); q.setContentsMargins(0, 3, 0, 0); q.setSpacing(8)
        self.home_multi_list121 = QListWidget(); self.home_multi_list121.setObjectName('sourceList121'); self.home_multi_list121.setMinimumHeight(86)
        add = QPushButton('영상 추가'); add.setProperty('soft121', True); add.clicked.connect(lambda: self._add_multi121(False))
        clear = QPushButton('비우기'); clear.setProperty('soft121', True); clear.clicked.connect(lambda: self._clear_multi121(False))
        self.home_multi_title121 = QLineEdit(); self.home_multi_title121.setPlaceholderText('상품명/주제 (선택)')
        q.addWidget(self.home_multi_list121, 0, 0, 2, 3); q.addWidget(add, 0, 3); q.addWidget(clear, 1, 3); q.addWidget(self.home_multi_title121, 2, 0, 1, 4)
        return w

    def _prepared_mode121(self):
        w = QWidget(); q = QGridLayout(w); q.setContentsMargins(0, 3, 0, 0); q.setSpacing(8)
        self.home_ready_list121 = QListWidget(); self.home_ready_list121.setObjectName('sourceList121'); self.home_ready_list121.setMinimumHeight(76)
        add = QPushButton('자료 영상 추가'); add.setProperty('soft121', True); add.clicked.connect(lambda: self._add_multi121(True))
        clear = QPushButton('비우기'); clear.setProperty('soft121', True); clear.clicked.connect(lambda: self._clear_multi121(True))
        self.home_ready_title121 = QLineEdit(); self.home_ready_title121.setPlaceholderText('상품명/주제')
        self.home_ready_script121 = QPlainTextEdit(); self.home_ready_script121.setPlaceholderText('준비한 한국어 대본이 있으면 붙여넣으세요. 비워두면 자동 작성합니다.'); self.home_ready_script121.setMinimumHeight(72)
        q.addWidget(self.home_ready_list121, 0, 0, 2, 3); q.addWidget(add, 0, 3); q.addWidget(clear, 1, 3); q.addWidget(self.home_ready_title121, 2, 0, 1, 4); q.addWidget(self.home_ready_script121, 3, 0, 1, 4)
        return w

    def _settings_body121(self, pairs):
        frame = QFrame(); frame.setProperty('accordionBody121', True); g = QGridLayout(frame); g.setContentsMargins(10, 8, 10, 8); g.setHorizontalSpacing(12); g.setVerticalSpacing(7)
        for i, (name, ctl) in enumerate(pairs):
            lab = QLabel(name); lab.setProperty('fieldLabel121', True); lab.setMinimumWidth(130); g.addWidget(lab, i, 0)
            if isinstance(ctl, (QComboBox, QSpinBox)):
                ctl.setMinimumWidth(180); g.addWidget(ctl, i, 1)
            else:
                g.addWidget(ctl, i, 1, alignment=Qt.AlignRight)
            g.setColumnStretch(1, 1)
        return frame

    def _accordion121(self, layout, title, body):
        header = QPushButton('▸  ' + title); header.setProperty('accordion121', True); header.setCheckable(True); body.setVisible(False)
        def toggle(on):
            body.setVisible(on); header.setText(('▾  ' if on else '▸  ') + title)
        header.toggled.connect(toggle); layout.addWidget(header); layout.addWidget(body)

    def _set_mode121(self, idx): self.mode_stack121.setCurrentIndex(idx)

    def _pick_single121(self):
        p, _ = QFileDialog.getOpenFileName(self, '영상 선택', '', 'Video (*.mp4 *.mov *.mkv *.webm)')
        if p: self.home_single_path121.setText(p)

    def _add_multi121(self, prepared=False):
        files, _ = QFileDialog.getOpenFileNames(self, '영상 여러 개 선택', '', 'Video (*.mp4 *.mov *.mkv *.webm)')
        if not files: return
        target = self.home_ready_files121 if prepared else self.home_multi_files121
        view = self.home_ready_list121 if prepared else self.home_multi_list121
        for p in files:
            if p not in target: target.append(p); view.addItem(p)

    def _clear_multi121(self, prepared=False):
        if prepared: self.home_ready_files121 = []; self.home_ready_list121.clear()
        else: self.home_multi_files121 = []; self.home_multi_list121.clear()

    def _sync_home_controls121(self):
        if not hasattr(self, 'home_voice121'): return
        voices = ['ko-KR-SunHiNeural', 'ko-KR-InJoonNeural', 'ko-KR-HyunsuNeural']
        self.home_voice121.setCurrentIndex(voices.index(self.s.tts_voice) if self.s.tts_voice in voices else 0)
        self.home_rate121.setCurrentText(getattr(self.s, 'tts_rate', '+0%'))
        self.home_remove_sub121.setChecked(bool(getattr(self.s, 'pipeline_remove_subtitles', True))); self.home_add_sub121.setChecked(bool(getattr(self.s, 'pipeline_add_korean_subtitles', True)))
        self.home_auto_cut121.setChecked(bool(getattr(self.s, 'pipeline_auto_cut', True))); self.home_target121.setValue(int(getattr(self.s, 'pipeline_target_seconds', 20)))
        self.home_thumb121.setChecked(bool(getattr(self.s, 'pipeline_auto_thumbnail', True))); self.home_wm121.setChecked(bool(getattr(self.s, 'watermark_enabled', False)))

    def _save_home_controls121(self):
        voices = ['ko-KR-SunHiNeural', 'ko-KR-InJoonNeural', 'ko-KR-HyunsuNeural']
        self.s.tts_voice = voices[max(0, min(self.home_voice121.currentIndex(), 2))]; self.s.tts_rate = self.home_rate121.currentText()
        self.s.pipeline_remove_subtitles = self.home_remove_sub121.isChecked(); self.s.pipeline_add_korean_subtitles = self.home_add_sub121.isChecked(); self.s.pipeline_auto_cut = self.home_auto_cut121.isChecked()
        self.s.pipeline_target_seconds = self.home_target121.value(); self.s.pipeline_auto_thumbnail = self.home_thumb121.isChecked(); self.s.watermark_enabled = self.home_wm121.isChecked(); save_settings(self.s)
        try:
            self.quick_ocr.setChecked(self.s.pipeline_remove_subtitles); self.quick_cut.setChecked(self.s.pipeline_auto_cut); self.quick_wm.setChecked(self.s.watermark_enabled)
        except Exception: pass

    def _product_profile_sync121(self, url: str) -> dict:
        profile = {}; http_error = ''
        try: profile = fetch_product_profile(url)
        except Exception as e: http_error = str(e)
        if not profile.get('title') or not profile.get('image') or bool(profile.get('blocked')):
            try:
                raw = browser_cdp.analyze_product_page(url, 5.0); bp = profile_from_browser(raw, url); bad = str(bp.get('title') or '').lower()
                if any(x in bad for x in ('access denied', 'forbidden', 'captcha', 'request blocked')): bp['title'] = ''
                profile = merge_profiles(profile, bp)
            except Exception as e: log('CDP product fallback: ' + str(e))
        if not profile.get('title') and extension_recent(5.0):
            try:
                tid = uuid.uuid4().hex; TASKS.put({'type': 'analyze_product_page', 'task_id': tid, 'url': url, 'wait_ms': 4200}); result = wait_for_result(tid, 18)
                if result and result.get('profile'): profile = merge_profiles(profile, profile_from_browser(result.get('profile') or {}, url))
            except Exception: pass
        if not profile.get('product_id'):
            m = re.search(r'/products/(\d+)', url)
            if m: profile['product_id'] = m.group(1)
        if not profile.get('title'):
            msg = '상품명을 확인하지 못했습니다. 자동으로 열린 Chrome/Edge에서 상품 페이지가 정상 표시되는지 확인한 뒤 다시 눌러주세요.'
            if http_error: msg += '\n쿠팡의 일반 요청 차단: ' + http_error.split('\n')[0][:150]
            raise RuntimeError(msg)
        return profile

    def home_confirm_product121(self):
        url = self.home_product_url121.text().strip()
        if not url: self.bus.err.emit('상품 주소를 입력하세요.'); return
        self.home_product_info121.setText('상품 내용을 확인하는 중… 브라우저는 필요할 때 자동으로 연결됩니다.')
        def run(): self.home_bus121.profile.emit(self._product_profile_sync121(url))
        self.work('상품 주소 확인', run)

    def _home_profile_ready121(self, profile):
        self.home_product_profile121 = dict(profile or {}); self.product_profile = dict(profile or {}); title = str(profile.get('title') or '')
        self.home_product_name121.setText(title); self.home_product_info121.setText(profile_summary(profile) + '\n' + title)
        if hasattr(self, 'product'): self.product.setText(title)
        if hasattr(self, 'product_url'): self.product_url.setText(str(profile.get('input_url') or profile.get('url') or self.home_product_url121.text()))
        if self.home_pending_create121: self.home_pending_create121 = False; self._start_product_source121()

    def start_home_make121(self):
        self._save_home_controls121(); mode = self.mode_stack121.currentIndex()
        if mode == 0:
            url = self.home_product_url121.text().strip()
            if not url: self.bus.err.emit('상품 주소를 입력하세요.'); return
            known = str(self.home_product_profile121.get('input_url') or self.home_product_profile121.get('url') or '')
            if not self.home_product_profile121.get('title') or (known and known != url): self.home_pending_create121 = True; self.home_confirm_product121(); return
            self._start_product_source121(); return
        if mode == 1:
            p = self.home_single_path121.text().strip()
            if not p or not Path(p).exists(): self.bus.err.emit('영상 파일 1개를 선택하세요.'); return
            self._start_local_pipeline121([p], {'title': self.home_single_title121.text().strip() or Path(p).stem, 'source': 'local'}, ''); return
        if mode == 2:
            files = [x for x in self.home_multi_files121 if Path(x).exists()]
            if len(files) < 2: self.bus.err.emit('영상 파일을 두 개 이상 추가하세요.'); return
            self._start_local_pipeline121(files, {'title': self.home_multi_title121.text().strip() or Path(files[0]).stem, 'source': 'local_multi'}, ''); return
        files = [x for x in self.home_ready_files121 if Path(x).exists()]
        if not files: self.bus.err.emit('준비한 자료의 영상 파일을 추가하세요.'); return
        self._start_local_pipeline121(files, {'title': self.home_ready_title121.text().strip() or Path(files[0]).stem, 'source': 'prepared'}, self.home_ready_script121.toPlainText().strip())

    def _start_product_source121(self):
        title = str(self.home_product_profile121.get('title') or self.home_product_name121.text()).strip()
        if not title: self.bus.err.emit('상품명을 확인하지 못했습니다.'); return
        self.product_profile = dict(self.home_product_profile121); self.product.setText(title); self.product_url.setText(self.home_product_url121.text().strip())
        self.auto_pipeline_requested120 = True; self.auto_collect_after_plan = True; self.home_result_status121.setText('상품 관련 영상을 자동으로 찾는 중…'); self.make_plan()

    def _start_local_pipeline121(self, files, profile, manual_script):
        if self.stop_requested: self.say('작업이 중지 상태입니다. 모두 시작을 눌러주세요.'); return
        self.product_profile = dict(profile or {}); self.home_result_status121.setText('영상 제작 중…')
        def run():
            result = run_processing_pipeline_v121(files, self.product_profile, self.s, '', manual_script, lambda pct, msg: self.pipeline_bus120.progress.emit(pct, msg)); self.pipeline_bus120.done.emit(result)
        self.work('영상 만들기', run)

    def analyze_product_url119(self):
        url = self.product_url.text().strip()
        if not url: self.bus.err.emit('쿠팡/상품 URL을 입력하세요.'); return
        def run(): self.product_bus119.profile_ready.emit(self._product_profile_sync121(url))
        self.work('상품 URL 분석', run)

    def bridge_collect(self):
        if not self.query_plan: return
        jobs = [(p, kw, source_engine.direct_search_url(p, kw)) for p in self.selected() for kw in (self.query_plan.get(p) or [])[:2] if kw]
        if not jobs: return
        self.say(f'브라우저 자동수집 {len(jobs)}개 검색')
        def one(job):
            p, kw, url = job
            try: return browser_cdp.collect_links(p, url, kw, 5.0)
            except Exception:
                if extension_recent(5.0):
                    tid = uuid.uuid4().hex; TASKS.put({'type': 'collect_links', 'task_id': tid, 'platform': p, 'url': url, 'keyword': kw, 'wait_ms': 4700}); packet = wait_for_result(tid, 18); return list((packet or {}).get('items') or [])
                return []
        def run():
            rows = []
            try: browser_cdp.ensure_browser()
            except Exception as e: log('CDP launch: ' + str(e))
            with ThreadPoolExecutor(max_workers=3) as ex:
                for fut in as_completed([ex.submit(one, x) for x in jobs]):
                    try: rows.extend(fut.result() or [])
                    except Exception: pass
            self.bus.candidates.emit(rank_candidates(self.product_profile or {'title': self.product.text().strip()}, rows))
        self.work('플랫폼 자동수집', run)

    def render_cards(self, rows):
        return

    def _download_candidate_sync120(self, row: dict) -> str:
        url = str(row.get('url') or '').strip()
        if not url: raise RuntimeError('후보 URL이 없습니다.')
        try: return str(download_video(url, self.s.output_folder, lambda x: self.pipeline_bus120.progress.emit(10, x)))
        except Exception as first:
            try:
                for media_url in browser_cdp.extract_media(url, 5.0)[:12]:
                    try: return str(download_video(media_url, self.s.output_folder, lambda x: self.pipeline_bus120.progress.emit(12, x)))
                    except Exception: continue
            except Exception: pass
            if extension_recent(5.0):
                tid = uuid.uuid4().hex; TASKS.put({'type': 'extract_media', 'task_id': tid, 'url': url, 'wait_ms': 5000}); packet = wait_for_result(tid, 22)
                for media_url in ((((packet or {}).get('media') or {}).get('media') or [])[:12]):
                    try: return str(download_video(media_url, self.s.output_folder, lambda x: self.pipeline_bus120.progress.emit(12, x)))
                    except Exception: continue
            raise RuntimeError('영상 다운로드에 실패했습니다.\n' + str(first))

    def _start_pipeline_row120(self, row: dict):
        if self.stop_requested: self.say('작업이 중지 상태입니다. 모두 시작을 눌러주세요.'); return
        title = str(row.get('title') or '').strip(); self.cand_url.setText(str(row.get('url') or '')); self.cand_text.setText(title); self.home_result_status121.setText('관련 영상 선택 완료 · 다운로드 및 제작 중…')
        def run():
            self.pipeline_bus120.progress.emit(4, '관련 영상 다운로드'); source = self._download_candidate_sync120(row); self.bus.downloaded.emit(source)
            profile = dict(getattr(self, 'product_profile', {}) or {'title': self.product.text().strip() or title})
            if not profile.get('title'): profile['title'] = title or Path(source).stem
            result = run_processing_pipeline_v121([source], profile, self.s, self.product_url.text().strip(), '', lambda pct, msg: self.pipeline_bus120.progress.emit(pct, msg)); self.pipeline_bus120.done.emit(result)
        self.work('상품 영상 자동 제작', run)

    def _pipeline_done120(self, result: dict):
        super()._pipeline_done120(result)
        final = str(result.get('final_video') or '')
        if final: self.home_final121 = final; self.home_result_status121.setText('완성 · ' + final)

    def _play_home_result121(self):
        if self.home_final121 and Path(self.home_final121).exists(): self.load_preview(self.home_final121); self.player.play(); self.play_btn.setText('Ⅱ 일시정지')

    def _open_home_result_folder121(self):
        folder = str(Path(self.home_final121).parent) if self.home_final121 and Path(self.home_final121).exists() else str(Path(self.s.output_folder))
        try: os.startfile(folder)
        except Exception: pass

    def _apply_page_mode121(self):
        try:
            if hasattr(self, 'quick_card118'): self.quick_card118.setVisible(self.pages.currentIndex() != 0)
        except Exception: pass

    def go(self, n):
        super().go(n); self._apply_page_mode121()


if __name__ == '__main__':
    app = QApplication([]); app.setApplicationName('NovaShorts'); app.setFont(QFont('Malgun Gothic', 10)); win = Nova(); win.show(); app.exec()
