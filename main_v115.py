from __future__ import annotations

import main_v114 as base
import main_v18 as core_ui
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import *

VERSION = '1.15'
base.VERSION = VERSION
try:
    base.base.VERSION = VERSION
    base.base.base.VERSION = VERSION
    base.base.base.base.VERSION = VERSION
except Exception:
    pass

PLATFORM_ORDER = base.base.base.PLATFORM_ORDER
platform_chip = base.base.base.platform_chip

V115_CSS = r'''
/* v1.15: DPI-safe spacing / clipping fixes */
QFrame#sidebar{background:#0d1729;border-right:1px solid #22324e}
QLabel#brand115{font-size:19px;font-weight:900;color:#f3f6ff}
QLabel#version115{font-size:10px;font-weight:700;color:#8ea3c8}
QLabel#sub115{font-size:10px;color:#7085a8}

QPushButton[nav="true"]{
    text-align:left;
    background:#111b2f;
    border:1px solid #263955;
    border-left:3px solid #263955;
    border-radius:9px;
    padding:7px 10px;
    min-height:25px;
    max-height:32px;
    color:#d4dced;
    font-size:12px;
    font-weight:700;
}
QPushButton[nav="true"]:hover{
    background:#1b2943;
    border:1px solid #5a77a7;
    border-left:4px solid #8578ff;
    color:#ffffff;
}
QPushButton[nav="true"]:checked{
    background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #3159d9,stop:1 #5c49e5);
    border:1px solid #788df1;
    border-left:4px solid #c0c9ff;
    color:#ffffff;
}

QFrame#quickCard115,QFrame#previewCard115{
    background:#151d31;
    border:1px solid #2f4161;
    border-radius:13px;
}
QLabel#quickTitle115{font-size:14px;font-weight:850;color:#f5f7ff}
QWidget[quickRow115="true"]{background:transparent}
QLabel[quickRowLabel115="true"]{
    background:transparent;
    color:#d2dbec;
    font-size:12px;
    min-height:34px;
    max-height:34px;
}
QComboBox[quick115="true"]{
    background:#101a2d;
    border:1px solid #3a4f72;
    border-radius:8px;
    padding:5px 10px;
    min-height:34px;
    max-height:34px;
    font-size:12px;
    color:#f2f5ff;
}
QComboBox[quick115="true"]:hover{border-color:#6f89bd}
QComboBox[quick115="true"]::drop-down{border:0;width:26px}

QPushButton[toggle="true"]{
    background:#25334b;
    border:1px solid #475c7b;
    border-radius:14px;
    color:#aebbd1;
    min-width:64px;
    max-width:64px;
    min-height:28px;
    max-height:28px;
    padding:0;
    font-size:11px;
    font-weight:900;
}
QPushButton[toggle="true"]:hover{background:#30415e;border-color:#6d84aa;color:#fff}
QPushButton[toggle="true"]:checked{background:#6555f5;border:1px solid #9a91ff;color:#fff}

QGroupBox[source115="true"]{
    background:#111b30;
    border:1px solid #2d405f;
    border-radius:14px;
    margin-top:20px;
    padding:16px 13px 12px 13px;
}
QGroupBox[source115="true"]::title{
    subcontrol-origin:margin;
    subcontrol-position:top left;
    left:16px;
    padding:0 8px;
    color:#eef3ff;
    font-weight:800;
}
'''


class Nova(base.Nova):
    def build(self):
        super().build()
        self.setWindowTitle(f'NovaShorts Studio v{VERSION}')
        self.resize(1600, 930)
        self.setMinimumSize(1200, 760)
        self.setStyleSheet(
            base.base.base.base.base.CSS
            + base.base.base.base.EXTRA_CSS
            + base.base.base.UI_CSS
            + base.base.V113_CSS
            + base.V114_CSS
            + V115_CSS
        )

    def sidebar(self):
        f = QFrame()
        f.setObjectName('sidebar')
        f.setFixedWidth(205)
        v = QVBoxLayout(f)
        v.setContentsMargins(9, 12, 9, 11)
        v.setSpacing(5)

        brand = QLabel('✦  NovaShorts')
        brand.setObjectName('brand115')
        brand.setFixedHeight(26)
        v.addWidget(brand)

        version = QLabel(f'Version {VERSION}')
        version.setObjectName('version115')
        version.setFixedHeight(15)
        v.addWidget(version)

        sub = QLabel('Global Shorts Production')
        sub.setObjectName('sub115')
        sub.setFixedHeight(15)
        v.addWidget(sub)
        v.addSpacing(6)

        self.nav = []
        items = [
            ('홈', '⌂'), ('소싱', '◎'), ('편집', '✣'), ('AI 음성', '◉'),
            ('썸네일', '▣'), ('업로드', '⇧'), ('링크 관리', '↗'), ('설정', '⚙')
        ]
        for i, (txt, ico) in enumerate(items):
            b = QPushButton(f'{ico}   {txt}')
            b.setProperty('nav', True)
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _, n=i: self.go(n))
            self.nav.append(b)
            v.addWidget(b)
        self.nav[0].setChecked(True)

        v.addStretch()
        badge = QLabel(f'★ NovaShorts\n글로벌 쇼츠 제작 스튜디오\nver. {VERSION}')
        badge.setStyleSheet(
            'background:#182451;border:1px solid #405bd0;border-radius:10px;'
            'padding:9px;color:#edf1ff;font-size:10px;font-weight:700'
        )
        v.addWidget(badge)
        return f

    def right_panel(self):
        # Do not use a fixed height for the quick panel. Windows DPI/font scaling can
        # make the last rows taller than expected, so the frame follows its sizeHint.
        w = QWidget()
        w.setFixedWidth(360)
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(10)

        quick = QFrame()
        quick.setObjectName('quickCard115')
        quick.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        qv = QVBoxLayout(quick)
        qv.setContentsMargins(14, 11, 14, 13)
        qv.setSpacing(7)
        qv.setSizeConstraint(QLayout.SetMinimumSize)

        head = QLabel('⚙  빠른 설정')
        head.setObjectName('quickTitle115')
        head.setFixedHeight(24)
        qv.addWidget(head)

        self.quick_field_pairs = []

        def combo_row(label, items):
            row = QWidget()
            row.setProperty('quickRow115', True)
            row.setMinimumHeight(40)
            rh = QHBoxLayout(row)
            rh.setContentsMargins(0, 0, 0, 0)
            rh.setSpacing(10)
            lab = QLabel(label)
            lab.setProperty('quickRowLabel115', True)
            lab.setFixedWidth(106)
            lab.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            combo = QComboBox()
            combo.setProperty('quick115', True)
            combo.addItems(items)
            combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            rh.addWidget(lab)
            rh.addWidget(combo, 1)
            qv.addWidget(row)
            self.quick_field_pairs.append((lab, combo))
            return combo

        self.quick_ai = combo_row('AI 모델', ['Gemini 2.5 Flash (기본)', '규칙 기반'])
        self.quick_ai.setCurrentIndex(0 if self.s.use_gemini_query_planning else 1)
        self.quick_ai.currentIndexChanged.connect(self.quick_save)

        self.quick_voice = combo_row('TTS 음성', ['Edge TTS - SunHi', 'Edge TTS - InJoon', 'Edge TTS - Hyunsu'])
        voices = ['ko-KR-SunHiNeural', 'ko-KR-InJoonNeural', 'ko-KR-HyunsuNeural']
        self.quick_voice.setCurrentIndex(voices.index(self.s.tts_voice) if self.s.tts_voice in voices else 0)
        self.quick_voice.currentIndexChanged.connect(self.quick_voice_changed)

        self.quick_res = combo_row('영상 해상도', ['1080 × 1920 (세로)'])

        self.quick_ocr = base.base.OnOffButton(True)
        self.quick_cut = base.base.OnOffButton(True)
        self.quick_wm = base.base.OnOffButton(self.s.watermark_enabled)
        self.quick_link = base.base.OnOffButton(self.s.lnkbio_auto_publish)
        self.quick_wm.toggled.connect(self.quick_save)
        self.quick_link.toggled.connect(self.quick_save)

        self.quick_toggle_pairs = []
        for label, sw in [
            ('자막 제거 (OCR)', self.quick_ocr),
            ('자동 컷 편집', self.quick_cut),
            ('워터마크 추가', self.quick_wm),
            ('업로드 후 링크 생성', self.quick_link),
        ]:
            row = QWidget()
            row.setProperty('quickRow115', True)
            row.setMinimumHeight(38)
            rh = QHBoxLayout(row)
            rh.setContentsMargins(0, 0, 0, 0)
            rh.setSpacing(10)
            lab = QLabel(label)
            lab.setProperty('quickRowLabel115', True)
            lab.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            rh.addWidget(lab, 1)
            rh.addWidget(sw, 0, Qt.AlignRight | Qt.AlignVCenter)
            qv.addWidget(row)
            self.quick_toggle_pairs.append((lab, sw))

        v.addWidget(quick, 0)

        preview = QFrame()
        preview.setObjectName('previewCard115')
        preview.setMinimumHeight(250)
        preview.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        pv = QVBoxLayout(preview)
        pv.setContentsMargins(12, 10, 12, 11)
        pv.setSpacing(7)
        ph = QLabel('미리보기')
        ph.setObjectName('panelTitle')
        ph.setFixedHeight(22)
        pv.addWidget(ph)
        self.video_view = core_ui.VideoView()
        self.video_view.setMinimumHeight(160)
        self.player.setVideoOutput(self.video_view.video_item)
        pv.addWidget(self.video_view, 1)
        self.preview_label = QLabel('선택/완성 영상을 불러오세요')
        self.preview_label.setObjectName('muted')
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setFixedHeight(20)
        pv.addWidget(self.preview_label)
        ctrl = QHBoxLayout()
        ctrl.setSpacing(8)
        self.play_btn = QPushButton('▶ 재생')
        self.play_btn.clicked.connect(self.toggle_play)
        op = QPushButton('파일 열기')
        op.setProperty('secondary', True)
        op.clicked.connect(self.preview_pick)
        ctrl.addWidget(self.play_btn)
        ctrl.addWidget(op)
        pv.addLayout(ctrl)
        v.addWidget(preview, 1)
        return w

    def source_page(self):
        # More breathing room around the page title / group-box legends. This avoids
        # the visually clipped legend seen under Windows display scaling.
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(12)

        title = QLabel('글로벌 영상 소싱')
        title.setObjectName('title')
        title.setFixedHeight(42)
        v.addWidget(title)
        v.addSpacing(6)

        g = QGroupBox('상품 / 검색어')
        g.setProperty('source115', True)
        g.setMinimumHeight(142)
        q = QGridLayout(g)
        q.setContentsMargins(16, 24, 16, 14)
        q.setHorizontalSpacing(10)
        q.setVerticalSpacing(8)
        self.product = QLineEdit()
        self.product.setPlaceholderText('상품명')
        self.product_url = QLineEdit()
        self.product_url.setPlaceholderText('쿠팡/상품 URL')
        b1 = QPushButton('AI 검색어 생성')
        b1.clicked.connect(self.make_plan)
        b2 = QPushButton('쿠팡 API 검색')
        b2.clicked.connect(self.coupang_lookup)
        self.product.setMinimumHeight(38)
        self.product_url.setMinimumHeight(38)
        b1.setMinimumHeight(38)
        b2.setMinimumHeight(38)
        q.addWidget(self.product, 0, 0, 1, 3)
        q.addWidget(b1, 0, 3)
        q.addWidget(self.product_url, 1, 0, 1, 3)
        q.addWidget(b2, 1, 3)
        v.addWidget(g)

        pg = QGroupBox('플랫폼')
        pg.setProperty('source115', True)
        pg.setMinimumHeight(96)
        ph = QHBoxLayout(pg)
        ph.setContentsMargins(14, 24, 14, 12)
        ph.setSpacing(6)
        self.pchecks = {}
        selected_now = set(getattr(self.s, 'platform_sources', []) or [])
        for p in PLATFORM_ORDER:
            b = platform_chip(p, p in selected_now, True)
            self.pchecks[p] = b
            ph.addWidget(b)
        ph.addStretch()
        v.addWidget(pg)

        split = QSplitter(Qt.Horizontal)
        split.setChildrenCollapsible(False)
        qg = QGroupBox('검색 계획')
        qg.setProperty('source115', True)
        qv = QVBoxLayout(qg)
        qv.setContentsMargins(13, 23, 13, 12)
        qv.setSpacing(8)
        self.planbox = QPlainTextEdit()
        qv.addWidget(self.planbox)
        hh = QHBoxLayout()
        hh.setSpacing(8)
        bo = QPushButton('검색 페이지 열기')
        bo.clicked.connect(self.open_searches)
        bc = QPushButton('Chrome Bridge 자동수집')
        bc.clicked.connect(self.bridge_collect)
        hh.addWidget(bo)
        hh.addWidget(bc)
        qv.addLayout(hh)
        split.addWidget(qg)

        cg = QGroupBox('수집된 영상 목록')
        cg.setProperty('source115', True)
        cv = QVBoxLayout(cg)
        cv.setContentsMargins(13, 23, 13, 12)
        cv.setSpacing(8)
        self.candidates = QListWidget()
        self.candidates.itemSelectionChanged.connect(self.candidate_selected)
        cv.addWidget(self.candidates)
        self.cand_url = QLineEdit()
        self.cand_url.setPlaceholderText('선택 후보 URL')
        self.cand_text = QLineEdit()
        self.cand_text.setPlaceholderText('선택 후보 제목')
        cv.addWidget(self.cand_url)
        cv.addWidget(self.cand_text)
        rh = QHBoxLayout()
        self.score = QLabel('유사도 -')
        bs = QPushButton('유사도 계산')
        bs.clicked.connect(self.score_it)
        bd = QPushButton('선택 영상 다운로드')
        bd.clicked.connect(self.download_it)
        rh.addWidget(self.score)
        rh.addStretch()
        rh.addWidget(bs)
        rh.addWidget(bd)
        cv.addLayout(rh)
        split.addWidget(cg)
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 2)
        v.addWidget(split, 1)
        return w


if __name__ == '__main__':
    app = QApplication([])
    app.setApplicationName('NovaShorts')
    app.setFont(QFont('Malgun Gothic', 10))
    win = Nova()
    win.show()
    app.exec()
