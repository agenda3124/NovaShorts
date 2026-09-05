from __future__ import annotations

import main_v116 as base
import main_v18 as core_ui
import main_v113
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import *

VERSION = '1.17'
for mod in [base, getattr(base, 'base', None)]:
    try:
        if mod is not None:
            mod.VERSION = VERSION
    except Exception:
        pass

PLATFORM_ORDER = base.PLATFORM_ORDER
platform_chip = base.platform_chip

V117_CSS = r'''
/* v1.17 - DPI-safe source rows and redesigned quick settings */
QFrame#quickCard117,QFrame#previewCard117{
    background:#151d31;
    border:1px solid #304564;
    border-radius:14px;
}
QLabel#quickTitle117{
    background:transparent;
    color:#f6f8ff;
    font-size:15px;
    font-weight:850;
}
QWidget[quickRow117="true"]{
    background:#111b30;
    border:1px solid #263a58;
    border-radius:9px;
}
QLabel[quickRowLabel117="true"]{
    background:transparent;
    color:#dce5f5;
    border:0;
    font-size:12px;
    font-weight:650;
}
QComboBox[quick117="true"]{
    background:#0e1a2e;
    border:1px solid #3d5578;
    border-radius:8px;
    padding:0 11px;
    min-height:36px;
    max-height:36px;
    color:#f5f7ff;
    font-size:12px;
}
QComboBox[quick117="true"]:hover{border-color:#6d88b7;background:#101e34}
QComboBox[quick117="true"]::drop-down{border:0;width:26px}

QFrame#sourceSection117,QFrame#platformSection117,QFrame#splitCard117{
    background:#111b30;
    border:1px solid #2d4162;
    border-radius:14px;
}
QLabel#sourceSectionTitle117{
    background:transparent;
    color:#f0f4ff;
    font-size:13px;
    font-weight:850;
}
QWidget[sourceRow117="true"]{
    background:transparent;
    border:0;
}
QLineEdit[source117="true"]{
    background:#0d182b;
    border:1px solid #385174;
    border-radius:10px;
    padding:0 12px;
    color:#f4f7ff;
    font-size:12px;
}
QLineEdit[source117="true"]:focus{border-color:#6c86ff}
QPushButton[sourceAction117="true"]{
    min-width:180px;
    background:#315cff;
    border:0;
    border-radius:10px;
    padding:0 16px;
    color:#ffffff;
    font-weight:800;
}
QPushButton[sourceAction117="true"]:hover{background:#4c70ff}
QToolButton[platform="true"]{
    min-height:36px;
    max-height:36px;
    padding:4px 10px;
}
'''


class Nova(base.Nova):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f'NovaShorts Studio v{VERSION}')
        try:
            self.status.setText(f'NovaShorts v{VERSION} 시작')
        except Exception:
            pass

    def build(self):
        super().build()
        self.resize(1600, 930)
        self.setMinimumSize(1200, 760)
        self.setWindowTitle(f'NovaShorts Studio v{VERSION}')
        self.setStyleSheet(self.styleSheet() + V117_CSS)

    def right_panel(self):
        w = QWidget()
        w.setFixedWidth(360)
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(10)

        quick = QFrame()
        quick.setObjectName('quickCard117')
        quick.setMinimumHeight(374)
        quick.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        qv = QVBoxLayout(quick)
        qv.setContentsMargins(14, 12, 14, 14)
        qv.setSpacing(7)
        qv.setSizeConstraint(QLayout.SetMinimumSize)

        head = QLabel('⚙  빠른 설정')
        head.setObjectName('quickTitle117')
        head.setFixedHeight(24)
        qv.addWidget(head)

        self.quick_field_pairs = []

        def combo_row(label, items):
            row = QWidget()
            row.setProperty('quickRow117', True)
            row.setMinimumHeight(46)
            row.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            rh = QHBoxLayout(row)
            rh.setContentsMargins(10, 4, 8, 4)
            rh.setSpacing(10)
            lab = QLabel(label)
            lab.setProperty('quickRowLabel117', True)
            lab.setFixedWidth(105)
            lab.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            combo = QComboBox()
            combo.setProperty('quick117', True)
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

        self.quick_ocr = main_v113.OnOffButton(True)
        self.quick_cut = main_v113.OnOffButton(True)
        self.quick_wm = main_v113.OnOffButton(self.s.watermark_enabled)
        self.quick_link = main_v113.OnOffButton(self.s.lnkbio_auto_publish)
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
            row.setProperty('quickRow117', True)
            row.setMinimumHeight(42)
            row.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            rh = QHBoxLayout(row)
            rh.setContentsMargins(10, 4, 8, 4)
            rh.setSpacing(10)
            lab = QLabel(label)
            lab.setProperty('quickRowLabel117', True)
            lab.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            rh.addWidget(lab, 1)
            rh.addWidget(sw, 0, Qt.AlignRight | Qt.AlignVCenter)
            qv.addWidget(row)
            self.quick_toggle_pairs.append((lab, sw))

        v.addWidget(quick, 0)

        preview = QFrame()
        preview.setObjectName('previewCard117')
        preview.setMinimumHeight(250)
        preview.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        pv = QVBoxLayout(preview)
        pv.setContentsMargins(12, 9, 12, 10)
        pv.setSpacing(6)
        ph = QLabel('미리보기')
        ph.setObjectName('panelTitle')
        ph.setFixedHeight(22)
        pv.addWidget(ph)
        self.video_view = core_ui.VideoView()
        self.video_view.setMinimumHeight(155)
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

    def _section_title117(self, text):
        lab = QLabel(text)
        lab.setObjectName('sourceSectionTitle117')
        lab.setFixedHeight(20)
        return lab

    def _source_row117(self, field, button):
        row = QWidget()
        row.setProperty('sourceRow117', True)
        row.setMinimumHeight(48)
        row.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 2, 0, 2)
        h.setSpacing(12)
        field.setFixedHeight(42)
        button.setFixedHeight(42)
        h.addWidget(field, 1)
        h.addWidget(button)
        return row

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
        product_card.setMinimumHeight(166)
        product_card.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        pv = QVBoxLayout(product_card)
        pv.setContentsMargins(14, 11, 14, 14)
        pv.setSpacing(8)
        pv.setSizeConstraint(QLayout.SetMinimumSize)
        pv.addWidget(self._section_title117('상품 / 검색어'))

        self.product = QLineEdit()
        self.product.setProperty('source117', True)
        self.product.setPlaceholderText('상품명')
        self.product_url = QLineEdit()
        self.product_url.setProperty('source117', True)
        self.product_url.setPlaceholderText('쿠팡/상품 URL')

        b1 = QPushButton('AI 검색어 생성')
        b1.setProperty('sourceAction117', True)
        b1.clicked.connect(self.make_plan)
        b2 = QPushButton('쿠팡 API 검색')
        b2.setProperty('sourceAction117', True)
        b2.clicked.connect(self.coupang_lookup)

        self.source_row_product = self._source_row117(self.product, b1)
        self.source_row_url = self._source_row117(self.product_url, b2)
        pv.addWidget(self.source_row_product)
        pv.addWidget(self.source_row_url)
        v.addWidget(product_card)

        platform_card = QFrame()
        platform_card.setObjectName('platformSection117')
        platform_card.setMinimumHeight(98)
        platform_card.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        pvl = QVBoxLayout(platform_card)
        pvl.setContentsMargins(14, 10, 14, 12)
        pvl.setSpacing(8)
        pvl.setSizeConstraint(QLayout.SetMinimumSize)
        pvl.addWidget(self._section_title117('플랫폼'))
        chips = QHBoxLayout()
        chips.setContentsMargins(0, 0, 0, 0)
        chips.setSpacing(8)
        self.pchecks = {}
        selected_now = set(getattr(self.s, 'platform_sources', []) or [])
        for p in PLATFORM_ORDER:
            btn = platform_chip(p, p in selected_now, True)
            btn.setMinimumWidth(82)
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


if __name__ == '__main__':
    app = QApplication([])
    app.setApplicationName('NovaShorts')
    app.setFont(QFont('Malgun Gothic', 10))
    win = Nova()
    win.show()
    app.exec()
