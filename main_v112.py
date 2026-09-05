from __future__ import annotations

import time
import webbrowser
from pathlib import Path

import main_v19 as base
import engine_v112 as ext
from bridge import TASKS, RESULTS
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import *

VERSION = '1.12'
base.VERSION = VERSION
try:
    base.base.VERSION = VERSION
except Exception:
    pass

UI_CSS = r'''
QLabel{background:transparent}

/* Sidebar */
QPushButton[nav="true"]{
    text-align:left;
    background:#111a2e;
    border:1px solid #263550;
    border-left:3px solid #263550;
    border-radius:10px;
    padding:11px 14px;
    min-height:30px;
    color:#cbd5e9;
    font-size:14px;
    font-weight:700;
}
QPushButton[nav="true"]:hover{
    background:#202b49;
    border:1px solid #516b9d;
    border-left:3px solid #7b72ff;
    color:#ffffff;
}
QPushButton[nav="true"]:checked{
    background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #2f57db,stop:1 #5d46e9);
    border:1px solid #7086ff;
    border-left:4px solid #b7c2ff;
    color:#ffffff;
}
QPushButton[nav="true"]:checked:hover{
    background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #3c65ed,stop:1 #6a53f4);
    border-color:#91a4ff;
}

/* Hero */
QFrame#heroV112{
    background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #6847df,stop:.46 #5367e8,stop:1 #7e3de0);
    border:1px solid #735df1;
    border-radius:14px;
}
QLabel#heroTitleV112{font-size:29px;font-weight:900;color:#ffffff}
QLabel#heroSubV112{font-size:13px;color:#eef0ff}
QLabel#heroTiny{font-size:11px;color:#d7dcff}
QFrame#orbitCard{background:rgba(42,24,104,.35);border:1px solid rgba(255,255,255,.12);border-radius:58px}

/* Source card and platform chips */
QFrame#sourceCard{background:#121a30;border:1px solid #273958;border-radius:13px}
QLabel#cardTitle{font-size:16px;font-weight:800;color:#f2f5ff}
QLabel#cardSub{font-size:11px;color:#8fa3c5}
QToolButton[platform="true"]{
    background:#131d31;
    border:1px solid #33445f;
    border-radius:9px;
    padding:5px 9px;
    color:#d4ddef;
    font-size:11px;
    font-weight:700;
    min-height:27px;
}
QToolButton[platform="true"]:hover{
    background:#202b45;
    border:1px solid #5b6f99;
    color:white;
}
QToolButton[platform="true"]:checked{
    background:#345dff;
    border:1px solid #7893ff;
    color:#ffffff;
}
QToolButton[platform="true"]:checked:hover{background:#4168ff;border-color:#9aabff}

QPushButton#searchPrimary{
    background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #4a61ff,stop:1 #9b3df1);
    border:1px solid #8c72ff;
    border-radius:9px;
    min-height:34px;
    font-weight:800;
}
QPushButton#searchPrimary:hover{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #5b70ff,stop:1 #aa4cff)}

/* Right panel */
QFrame#quickCard,QFrame#previewCard{background:#151c31;border:1px solid #2b3957;border-radius:13px}
QLabel#panelTitle{font-size:14px;font-weight:800;color:#f1f3ff}
QLabel#fieldLabel{font-size:11px;color:#c7d1e6}
QComboBox[quick="true"]{background:#111a2d;border:1px solid #33445f;border-radius:8px;padding:7px 9px;min-height:25px;font-size:11px}
QPushButton[switch="true"]{background:#243149;border:1px solid #455672;border-radius:12px;padding:0;min-width:42px;max-width:42px;min-height:23px;max-height:23px;color:#9cb0d0}
QPushButton[switch="true"]:checked{background:#6555f5;border:1px solid #8c83ff;color:#ffffff}

QScrollBar:horizontal{background:#0b1322;height:7px;margin:0;border-radius:3px}
QScrollBar::handle:horizontal{background:#344866;min-width:60px;border-radius:3px}
QScrollBar::handle:horizontal:hover{background:#536b91}
QScrollBar::add-line:horizontal,QScrollBar::sub-line:horizontal{width:0;background:none}
QScrollBar:vertical{background:#0b1322;width:7px;margin:0;border-radius:3px}
QScrollBar::handle:vertical{background:#344866;min-height:50px;border-radius:3px}
QScrollBar::handle:vertical:hover{background:#536b91}
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;background:none}
'''

PLATFORM_ORDER = ['TikTok', 'YouTube', 'Instagram', 'Douyin', 'Xiaohongshu', 'Kuaishou', '1688']
PLATFORM_LABELS = {
    'TikTok': 'TikTok', 'YouTube': 'YouTube', 'Instagram': 'Instagram',
    'Douyin': 'Douyin', 'Xiaohongshu': '小红书', 'Kuaishou': 'Kuaishou', '1688': '1688'
}


def icon_path(name: str) -> str:
    return str(ext.app_dir() / 'assets' / 'platforms' / f'{name.lower()}.svg')


def platform_chip(name: str, checked: bool = False, compact: bool = True) -> QToolButton:
    b = QToolButton()
    b.setProperty('platform', True)
    b.setCheckable(True)
    b.setChecked(checked)
    b.setCursor(Qt.PointingHandCursor)
    b.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
    p = icon_path(name)
    if Path(p).exists():
        b.setIcon(QIcon(p))
    b.setIconSize(QSize(20 if compact else 23, 20 if compact else 23))
    b.setText(PLATFORM_LABELS.get(name, name))
    b.setMinimumWidth(88 if compact else 105)
    b.setMaximumHeight(37 if compact else 43)
    return b


class Nova(base.Nova):
    def build(self):
        super().build()
        self.setWindowTitle(f'NovaShorts Studio v{VERSION}')
        self.resize(1600, 930)
        self.setMinimumSize(1260, 760)
        self.setStyleSheet(base.base.CSS + base.EXTRA_CSS + UI_CSS)

    def sidebar(self):
        f = QFrame(); f.setObjectName('sidebar'); f.setFixedWidth(258)
        v = QVBoxLayout(f); v.setContentsMargins(12, 15, 12, 13); v.setSpacing(7)
        brand = QLabel(f'✦  NovaShorts   v{VERSION}'); brand.setObjectName('brand'); brand.setMinimumWidth(225); v.addWidget(brand)
        sub = QLabel('Global Shorts Production'); sub.setObjectName('muted'); v.addWidget(sub); v.addSpacing(9)
        self.nav = []
        items = [('홈','⌂'),('소싱','◎'),('편집','✣'),('AI 음성','◉'),('썸네일','▣'),('업로드','⇧'),('링크 관리','↗'),('설정','⚙')]
        for i, (txt, ico) in enumerate(items):
            b = QPushButton(f'{ico}   {txt}')
            b.setProperty('nav', True); b.setCheckable(True); b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _, n=i: self.go(n)); self.nav.append(b); v.addWidget(b)
        self.nav[0].setChecked(True)
        v.addStretch()
        badge = QLabel(f'★ NovaShorts v{VERSION}\n글로벌 쇼츠 제작 스튜디오')
        badge.setStyleSheet('background:#182451;border:1px solid #405bd0;border-radius:12px;padding:13px;color:#edf1ff;font-weight:700')
        v.addWidget(badge)
        return f

    def hero_v112(self):
        f = QFrame(); f.setObjectName('heroV112'); f.setFixedHeight(178)
        h = QHBoxLayout(f); h.setContentsMargins(24, 18, 22, 18); h.setSpacing(16)
        left = QVBoxLayout(); left.setSpacing(6)
        title = QLabel('세상의 핫한 영상을\n나만의 쇼츠로 🚀'); title.setObjectName('heroTitleV112'); left.addWidget(title)
        sub = QLabel('글로벌 트렌드 소싱부터 AI 편집, 자동 업로드까지'); sub.setObjectName('heroSubV112'); left.addWidget(sub)
        tiny = QLabel('NovaShorts와 함께 더 쉽게, 더 빠르게!'); tiny.setObjectName('heroTiny'); left.addWidget(tiny)
        left.addStretch(); h.addLayout(left, 3)

        orbit = QFrame(); orbit.setObjectName('orbitCard'); orbit.setFixedSize(300, 140)
        grid = QGridLayout(orbit); grid.setContentsMargins(18, 14, 18, 14); grid.setSpacing(10)
        for idx, name in enumerate(['TikTok','YouTube','Instagram','Xiaohongshu','Kuaishou','1688']):
            p = icon_path(name); btn = QToolButton(); btn.setAutoRaise(True); btn.setCursor(Qt.ArrowCursor)
            if Path(p).exists(): btn.setIcon(QIcon(p))
            btn.setIconSize(QSize(34,34)); btn.setFixedSize(44,44); btn.setStyleSheet('QToolButton{background:#14182a;border:1px solid rgba(255,255,255,.15);border-radius:12px;padding:4px}')
            grid.addWidget(btn, idx//3, idx%3, alignment=Qt.AlignCenter)
        h.addWidget(orbit, 2, alignment=Qt.AlignVCenter|Qt.AlignRight)
        return f

    def home_page(self):
        w = QWidget(); v = QVBoxLayout(w); v.setContentsMargins(0,0,0,0); v.setSpacing(9)
        v.addWidget(self.hero_v112())

        card = QFrame(); card.setObjectName('sourceCard'); card.setFixedHeight(166)
        cv = QVBoxLayout(card); cv.setContentsMargins(13,10,13,11); cv.setSpacing(7)
        title_row = QHBoxLayout(); ico = QLabel('🔍'); ico.setFixedWidth(22); title_row.addWidget(ico)
        tb = QVBoxLayout(); t = QLabel('소싱하기'); t.setObjectName('cardTitle'); s = QLabel('키워드를 입력하면 글로벌 플랫폼의 인기 영상을 찾아옵니다.'); s.setObjectName('cardSub'); tb.addWidget(t); tb.addWidget(s); title_row.addLayout(tb); title_row.addStretch(); cv.addLayout(title_row)

        chips = QHBoxLayout(); chips.setSpacing(7); self.home_checks = {}
        selected_now = set(getattr(self.s, 'platform_sources', []) or [])
        for p in PLATFORM_ORDER:
            b = platform_chip(p, p in selected_now or (not selected_now and p == 'TikTok'), True)
            self.home_checks[p] = b; chips.addWidget(b)
        chips.addStretch(); cv.addLayout(chips)

        search = QHBoxLayout(); search.setSpacing(8)
        self.home_keyword = QLineEdit(); self.home_keyword.setPlaceholderText('검색 키워드를 입력하세요 (예: 주방 꿀템, 청소, 홈인테리어)'); self.home_keyword.setMinimumHeight(36)
        go = QPushButton('⌕ 검색하기'); go.setObjectName('searchPrimary'); go.setMinimumWidth(120); go.clicked.connect(self.home_to_source)
        search.addWidget(self.home_keyword,1); search.addWidget(go); cv.addLayout(search)
        v.addWidget(card)

        row = QHBoxLayout(); label = QLabel('수집된 영상 목록'); label.setObjectName('section'); row.addWidget(label)
        self.home_count = QLabel('0'); self.home_count.setObjectName('muted'); row.addWidget(self.home_count); row.addStretch()
        self.home_edit_btn = QPushButton('선택 영상으로 편집하기 →'); self.home_edit_btn.clicked.connect(self.home_edit_selected); row.addWidget(self.home_edit_btn); v.addLayout(row)

        self.card_area = QScrollArea(); self.card_area.setWidgetResizable(True); self.card_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded); self.card_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff); self.card_area.setMinimumHeight(200)
        self.card_host = QWidget(); self.card_layout = QHBoxLayout(self.card_host); self.card_layout.setContentsMargins(0,0,0,3); self.card_layout.setSpacing(9); self.card_area.setWidget(self.card_host); v.addWidget(self.card_area,1)
        self.render_cards([])
        return w

    def source_page(self):
        w = QWidget(); v = QVBoxLayout(w); v.setContentsMargins(0,0,0,0); v.setSpacing(8)
        title = QLabel('글로벌 영상 소싱'); title.setObjectName('title'); v.addWidget(title)
        g = QGroupBox('상품 / 검색어'); g.setFixedHeight(118); q = QGridLayout(g)
        self.product = QLineEdit(); self.product.setPlaceholderText('상품명')
        self.product_url = QLineEdit(); self.product_url.setPlaceholderText('쿠팡/상품 URL')
        b1 = QPushButton('AI 검색어 생성'); b1.clicked.connect(self.make_plan); b2 = QPushButton('쿠팡 API 검색'); b2.clicked.connect(self.coupang_lookup)
        q.addWidget(self.product,0,0,1,3); q.addWidget(b1,0,3); q.addWidget(self.product_url,1,0,1,3); q.addWidget(b2,1,3); v.addWidget(g)

        pg = QGroupBox('플랫폼'); pg.setFixedHeight(88); ph = QHBoxLayout(pg); ph.setContentsMargins(12,14,12,9); ph.setSpacing(6); self.pchecks = {}
        selected_now = set(getattr(self.s, 'platform_sources', []) or [])
        for p in PLATFORM_ORDER:
            b = platform_chip(p, p in selected_now, True); self.pchecks[p] = b; ph.addWidget(b)
        ph.addStretch(); v.addWidget(pg)

        split = QSplitter(Qt.Horizontal)
        qg = QGroupBox('검색 계획'); qv = QVBoxLayout(qg); self.planbox = QPlainTextEdit(); qv.addWidget(self.planbox)
        hh = QHBoxLayout(); bo = QPushButton('검색 페이지 열기'); bo.clicked.connect(self.open_searches); bc = QPushButton('Chrome Bridge 자동수집'); bc.clicked.connect(self.bridge_collect); hh.addWidget(bo); hh.addWidget(bc); qv.addLayout(hh); split.addWidget(qg)
        cg = QGroupBox('수집된 영상 목록'); cv = QVBoxLayout(cg); self.candidates = QListWidget(); self.candidates.itemSelectionChanged.connect(self.candidate_selected); cv.addWidget(self.candidates)
        self.cand_url = QLineEdit(); self.cand_url.setPlaceholderText('선택 후보 URL'); self.cand_text = QLineEdit(); self.cand_text.setPlaceholderText('선택 후보 제목'); cv.addWidget(self.cand_url); cv.addWidget(self.cand_text)
        rh = QHBoxLayout(); self.score = QLabel('유사도 -'); bs = QPushButton('유사도 계산'); bs.clicked.connect(self.score_it); bd = QPushButton('선택 영상 다운로드'); bd.clicked.connect(self.download_it); rh.addWidget(self.score); rh.addStretch(); rh.addWidget(bs); rh.addWidget(bd); cv.addLayout(rh); split.addWidget(cg)
        split.setStretchFactor(0,1); split.setStretchFactor(1,2); v.addWidget(split,1)
        return w

    def right_panel(self):
        w = QWidget(); w.setFixedWidth(318); v = QVBoxLayout(w); v.setContentsMargins(0,0,0,0); v.setSpacing(9)

        g = QFrame(); g.setObjectName('quickCard'); gv = QVBoxLayout(g); gv.setContentsMargins(14,10,14,12); gv.setSpacing(6)
        head = QLabel('⚙  빠른 설정'); head.setObjectName('panelTitle'); gv.addWidget(head)

        def combo_field(label, items):
            lab = QLabel(label); lab.setObjectName('fieldLabel'); gv.addWidget(lab)
            c = QComboBox(); c.setProperty('quick',True); c.addItems(items); c.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon); gv.addWidget(c); return c

        self.quick_ai = combo_field('AI 모델',['Gemini 2.5 Flash (기본)','규칙 기반'])
        self.quick_ai.setCurrentIndex(0 if self.s.use_gemini_query_planning else 1); self.quick_ai.currentIndexChanged.connect(self.quick_save)
        self.quick_voice = combo_field('TTS 음성',['Edge TTS - SunHi','Edge TTS - InJoon','Edge TTS - Hyunsu'])
        voices=['ko-KR-SunHiNeural','ko-KR-InJoonNeural','ko-KR-HyunsuNeural']; self.quick_voice.setCurrentIndex(voices.index(self.s.tts_voice) if self.s.tts_voice in voices else 0); self.quick_voice.currentIndexChanged.connect(self.quick_voice_changed)
        self.quick_res = combo_field('영상 해상도',['1080 × 1920 (세로)'])

        self.quick_ocr = base.base.Switch(True); self.quick_cut = base.base.Switch(True); self.quick_wm = base.base.Switch(self.s.watermark_enabled); self.quick_link = base.base.Switch(self.s.lnkbio_auto_publish)
        self.quick_wm.toggled.connect(self.quick_save); self.quick_link.toggled.connect(self.quick_save)
        for label, sw in [('자막 제거 (OCR)',self.quick_ocr),('자동 컷 편집',self.quick_cut),('워터마크 추가',self.quick_wm),('업로드 후 링크 생성',self.quick_link)]:
            r=QHBoxLayout(); l=QLabel(label); l.setObjectName('fieldLabel'); r.addWidget(l); r.addStretch(); r.addWidget(sw); gv.addLayout(r)
        v.addWidget(g)

        pg = QFrame(); pg.setObjectName('previewCard'); pv = QVBoxLayout(pg); pv.setContentsMargins(12,9,12,11); pv.setSpacing(6)
        ph = QLabel('미리보기'); ph.setObjectName('panelTitle'); pv.addWidget(ph)
        self.video_view = base.base.VideoView(); self.video_view.setMinimumHeight(190); self.player.setVideoOutput(self.video_view.video_item); pv.addWidget(self.video_view,1)
        self.preview_label = QLabel('선택/완성 영상을 불러오세요'); self.preview_label.setObjectName('muted'); self.preview_label.setAlignment(Qt.AlignCenter); pv.addWidget(self.preview_label)
        ctrl = QHBoxLayout(); self.play_btn=QPushButton('▶ 재생'); self.play_btn.clicked.connect(self.toggle_play); op=QPushButton('파일 열기'); op.setProperty('secondary',True); op.clicked.connect(self.preview_pick); ctrl.addWidget(self.play_btn); ctrl.addWidget(op); pv.addLayout(ctrl); v.addWidget(pg)
        v.addStretch(); return w

    def queue_panel(self):
        g = QGroupBox('작업 대기열'); g.setFixedHeight(138); v=QVBoxLayout(g); v.setContentsMargins(12,13,12,8); v.setSpacing(4)
        top=QHBoxLayout(); top.addStretch(); start=QPushButton('▶ 모두 시작'); start.clicked.connect(self.resume_jobs); stop=QPushButton('■ 모두 중지'); stop.setProperty('danger',True); stop.clicked.connect(self.stop_jobs); clear=QPushButton('목록 비우기'); clear.setProperty('secondary',True); clear.clicked.connect(self.clear_queue); top.addWidget(start); top.addWidget(stop); top.addWidget(clear); v.addLayout(top)
        self.queue=QTableWidget(0,5); self.queue.setHorizontalHeaderLabels(['작업명','상태','진행률','시작 시간','작업']); self.queue.horizontalHeader().setSectionResizeMode(0,QHeaderView.Stretch)
        for c in [1,2,3,4]: self.queue.horizontalHeader().setSectionResizeMode(c,QHeaderView.ResizeToContents)
        self.queue.verticalHeader().setVisible(False); self.queue.setMinimumHeight(64); self.queue.setMaximumHeight(72); v.addWidget(self.queue); return g

    def render_cards(self, rows):
        while self.card_layout.count():
            item=self.card_layout.takeAt(0); widget=item.widget()
            if widget: widget.deleteLater()
        if not rows:
            for _ in range(4):
                f=QFrame(); f.setObjectName('videoCard'); f.setFixedSize(190,190); vl=QVBoxLayout(f); vl.setContentsMargins(8,8,8,8)
                img=QLabel('영상 후보'); img.setAlignment(Qt.AlignCenter); img.setFixedHeight(105); img.setStyleSheet('background:#172542;border-radius:9px;color:#7890b5;font-weight:700'); vl.addWidget(img)
                txt=QLabel('소싱을 시작하면\n검색 결과가 표시됩니다'); txt.setObjectName('muted'); txt.setAlignment(Qt.AlignCenter); txt.setWordWrap(True); vl.addWidget(txt); self.card_layout.addWidget(f)
            self.card_layout.addStretch(); self.home_count.setText('0'); return
        for r in rows[:8]:
            card=base.base.CandidateCard(r,r.get('_score',0)); card.setFixedHeight(215); card.selected.connect(self.card_select); self.card_layout.addWidget(card)
            thumb=r.get('thumbnail','')
            if thumb and thumb.startswith(('http://','https://')): self.load_card_thumb(card,thumb)
        self.card_layout.addStretch(); self.home_count.setText(str(len(rows)))

    # Seven-platform sourcing functions.
    def make_plan(self):
        title=self.product.text().strip()
        if not title: return
        def f(): self.bus.plan.emit(ext.gemini_query_plan(title,self.s.gemini_api_key) if self.s.use_gemini_query_planning else ext.rule_query_plan(title))
        self.work('AI 검색어 생성',f)

    def open_searches(self):
        if not self.query_plan: return
        for p in self.selected():
            kw=(self.query_plan.get(p) or [''])[0]
            if kw: webbrowser.open(ext.direct_search_url(p,kw))

    def bridge_collect(self):
        if not self.query_plan: return
        count=0
        for p in self.selected():
            for kw in (self.query_plan.get(p) or [])[:2]:
                TASKS.put({'type':'collect_links','platform':p,'url':ext.direct_search_url(p,kw),'keyword':kw}); count+=1
        if count==0: return
        self.say(f'Chrome Bridge 작업 {count}개 전송')
        def wait():
            end=time.time()+45; rows=[]
            while time.time()<end and not self.stop_requested:
                try:
                    r=RESULTS.get(timeout=1); rows.extend(r.get('items',[]))
                except Exception: pass
            self.bus.candidates.emit(rows)
        self.work('플랫폼 후보 수집',wait)

    def quick_save(self):
        self.s.watermark_enabled=self.quick_wm.isChecked()
        self.s.use_gemini_query_planning=self.quick_ai.currentIndex()==0
        self.s.lnkbio_auto_publish=self.quick_link.isChecked()
        ext.save_settings(self.s)

    def save(self):
        self.s.platform_sources=self.selected()
        super().save()


if __name__ == '__main__':
    app=QApplication([])
    app.setApplicationName('NovaShorts')
    app.setFont(QFont('Malgun Gothic',10))
    win=Nova(); win.show(); app.exec()
