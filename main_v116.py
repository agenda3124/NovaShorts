from __future__ import annotations

import main_v115 as base
import main_v18 as core_ui
import main_v19, main_v112, main_v113, main_v114
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import *

VERSION = '1.16'
for mod in [base, main_v114, main_v113, main_v112, main_v19, core_ui]:
    try:
        mod.VERSION = VERSION
    except Exception:
        pass

PLATFORM_ORDER = base.PLATFORM_ORDER
platform_chip = base.platform_chip

V116_CSS = r'''
QFrame#sourceSection116,QFrame#platformSection116,QFrame#splitCard116{
    background:#111b30;
    border:1px solid #2b3d5d;
    border-radius:13px;
}
QLabel#sourceSectionTitle116{
    color:#eef3ff;
    font-size:13px;
    font-weight:800;
}
QLineEdit[source116="true"]{
    min-height:34px;
    max-height:34px;
    padding:4px 10px;
}
QPushButton[sourceAction116="true"]{
    min-height:34px;
    max-height:34px;
    min-width:170px;
}
QToolButton[platform="true"]{
    min-height:32px;
    max-height:34px;
    padding:4px 9px;
}
QFrame#quickCard116,QFrame#previewCard116{
    background:#151d31;
    border:1px solid #2f4161;
    border-radius:13px;
}
QLabel#quickTitle116{font-size:14px;font-weight:850;color:#f5f7ff}
QLabel[quickRowLabel116="true"]{background:transparent;color:#d2dbec;font-size:12px}
QComboBox[quick116="true"]{
    background:#101a2d;
    border:1px solid #3a4f72;
    border-radius:8px;
    padding:5px 10px;
    min-height:32px;
    max-height:32px;
    font-size:12px;
    color:#f2f5ff;
}
QComboBox[quick116="true"]::drop-down{border:0;width:26px}
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
        self.setStyleSheet(self.styleSheet() + V116_CSS)

    def right_panel(self):
        w = QWidget()
        w.setFixedWidth(360)
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(9)

        quick = QFrame()
        quick.setObjectName('quickCard116')
        quick.setFixedHeight(326)
        qv = QVBoxLayout(quick)
        qv.setContentsMargins(14, 10, 14, 11)
        qv.setSpacing(4)

        head = QLabel('⚙  빠른 설정')
        head.setObjectName('quickTitle116')
        head.setFixedHeight(22)
        qv.addWidget(head)

        self.quick_field_pairs = []

        def combo_row(label, items):
            row = QWidget()
            row.setFixedHeight(38)
            rh = QHBoxLayout(row)
            rh.setContentsMargins(0, 0, 0, 0)
            rh.setSpacing(10)
            lab = QLabel(label)
            lab.setProperty('quickRowLabel116', True)
            lab.setFixedWidth(105)
            lab.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            combo = QComboBox()
            combo.setProperty('quick116', True)
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
            row.setFixedHeight(31)
            rh = QHBoxLayout(row)
            rh.setContentsMargins(0, 0, 0, 0)
            rh.setSpacing(10)
            lab = QLabel(label)
            lab.setProperty('quickRowLabel116', True)
            lab.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            rh.addWidget(lab, 1)
            rh.addWidget(sw, 0, Qt.AlignRight | Qt.AlignVCenter)
            qv.addWidget(row)
            self.quick_toggle_pairs.append((lab, sw))

        v.addWidget(quick, 0)

        preview = QFrame()
        preview.setObjectName('previewCard116')
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

    def _section_title(self, text):
        lab = QLabel(text)
        lab.setObjectName('sourceSectionTitle116')
        lab.setFixedHeight(20)
        return lab

    def _source_input_row(self, edit, button):
        row = QWidget()
        row.setFixedHeight(42)
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 2, 0, 2)
        h.setSpacing(12)
        h.addWidget(edit, 1)
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
        product_card.setObjectName('sourceSection116')
        product_card.setFixedHeight(154)
        pv = QVBoxLayout(product_card)
        pv.setContentsMargins(14, 10, 14, 12)
        pv.setSpacing(8)
        pv.addWidget(self._section_title('상품 / 검색어'))

        self.product = QLineEdit()
        self.product.setProperty('source116', True)
        self.product.setPlaceholderText('상품명')
        self.product_url = QLineEdit()
        self.product_url.setProperty('source116', True)
        self.product_url.setPlaceholderText('쿠팡/상품 URL')

        b1 = QPushButton('AI 검색어 생성')
        b1.setProperty('sourceAction116', True)
        b1.clicked.connect(self.make_plan)
        b2 = QPushButton('쿠팡 API 검색')
        b2.setProperty('sourceAction116', True)
        b2.clicked.connect(self.coupang_lookup)

        row1 = self._source_input_row(self.product, b1)
        row2 = self._source_input_row(self.product_url, b2)
        pv.addWidget(row1)
        pv.addWidget(row2)
        v.addWidget(product_card)

        platform_card = QFrame()
        platform_card.setObjectName('platformSection116')
        platform_card.setFixedHeight(100)
        pvl = QVBoxLayout(platform_card)
        pvl.setContentsMargins(14, 9, 14, 11)
        pvl.setSpacing(7)
        pvl.addWidget(self._section_title('플랫폼'))
        chip_row = QWidget()
        chip_row.setFixedHeight(42)
        chips = QHBoxLayout(chip_row)
        chips.setContentsMargins(0, 3, 0, 3)
        chips.setSpacing(7)
        self.pchecks = {}
        selected_now = set(getattr(self.s, 'platform_sources', []) or [])
        for p in PLATFORM_ORDER:
            btn = platform_chip(p, p in selected_now, True)
            btn.setMinimumWidth(82)
            btn.setMaximumHeight(34)
            self.pchecks[p] = btn
            chips.addWidget(btn)
        chips.addStretch()
        pvl.addWidget(chip_row)
        v.addWidget(platform_card)

        split = QSplitter(Qt.Horizontal)
        split.setChildrenCollapsible(False)

        left = QFrame()
        left.setObjectName('splitCard116')
        lv = QVBoxLayout(left)
        lv.setContentsMargins(13, 10, 13, 12)
        lv.setSpacing(8)
        lv.addWidget(self._section_title('검색 계획'))
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
        right.setObjectName('splitCard116')
        rv = QVBoxLayout(right)
        rv.setContentsMargins(13, 10, 13, 12)
        rv.setSpacing(8)
        rv.addWidget(self._section_title('수집된 영상 목록'))
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
