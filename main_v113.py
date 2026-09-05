from __future__ import annotations

import main_v112 as base
from pathlib import Path
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont
from PySide6.QtWidgets import *

VERSION = '1.13'
base.VERSION = VERSION
try:
    base.base.VERSION = VERSION
    base.base.base.VERSION = VERSION
except Exception:
    pass

V113_CSS = r'''
/* v1.13: clipping-safe compact layout */
QPushButton[nav="true"]{
    text-align:left;
    background:#111a2e;
    border:1px solid #2a3a57;
    border-left:3px solid #2a3a57;
    border-radius:10px;
    padding:11px 14px;
    min-height:30px;
    color:#d2daea;
    font-size:14px;
    font-weight:700;
}
QPushButton[nav="true"]:hover{
    background:#1b2741;
    border:1px solid #647db0;
    border-left:4px solid #8c7cff;
    color:#ffffff;
}
QPushButton[nav="true"]:checked{
    background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #3159d9,stop:1 #6149e8);
    border:1px solid #7e8ff7;
    border-left:5px solid #c1caff;
    color:#ffffff;
}
QPushButton[nav="true"]:checked:hover{
    background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #3c68ec,stop:1 #7259f4);
    border-color:#9aa9ff;
}

QFrame#sourceCardV113{
    background:#121a30;
    border:1px solid #2b3c5c;
    border-radius:13px;
}
QLabel#homeTitleV113{font-size:27px;font-weight:900;color:#f6f8ff}
QLabel#homeSubV113{font-size:12px;color:#91a4c6}

QFrame#quickCardV113,QFrame#previewCardV113{
    background:#151c31;
    border:1px solid #2e3e5d;
    border-radius:13px;
}
QLabel[quickLabel="true"]{
    color:#cdd7eb;
    font-size:12px;
    min-height:18px;
    max-height:18px;
}
QComboBox[quick="true"]{
    background:#111a2d;
    border:1px solid #3a4c6b;
    border-radius:8px;
    padding:5px 10px;
    min-height:30px;
    max-height:30px;
    font-size:12px;
}
QComboBox[quick="true"]:hover{border-color:#647fb4}

QPushButton[toggle="true"]{
    background:#243149;
    border:1px solid #455a79;
    border-radius:8px;
    color:#aebbd1;
    min-width:58px;
    max-width:58px;
    min-height:26px;
    max-height:26px;
    padding:0;
    font-size:11px;
    font-weight:800;
}
QPushButton[toggle="true"]:hover{
    background:#2c3b58;
    border-color:#61799e;
    color:#ffffff;
}
QPushButton[toggle="true"]:checked{
    background:#6555f5;
    border:1px solid #968bff;
    color:#ffffff;
}

QGroupBox#settingsCardV113{
    background:#121a30;
    border:1px solid #2c3d5c;
    border-radius:12px;
    margin-top:13px;
    padding:12px;
}
QGroupBox#settingsCardV113::title{
    subcontrol-origin:margin;
    left:14px;
    padding:0 6px;
    color:#eef2ff;
    font-weight:800;
}
QLineEdit[setting="true"],QSpinBox[setting="true"]{
    min-height:28px;
    max-height:28px;
    padding:3px 9px;
}
QLabel[settingLabel="true"]{font-size:12px;color:#d7dfef}
'''


class OnOffButton(QPushButton):
    def __init__(self, checked=False, parent=None):
        super().__init__(parent)
        self.setProperty('toggle', True)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setChecked(bool(checked))
        self.toggled.connect(self._sync_text)
        self._sync_text(self.isChecked())

    def _sync_text(self, checked):
        self.setText('ON' if checked else 'OFF')


class Nova(base.Nova):
    def build(self):
        super().build()
        self.setWindowTitle(f'NovaShorts Studio v{VERSION}')
        self.resize(1600, 930)
        self.setMinimumSize(1260, 760)
        self.setStyleSheet(base.base.base.CSS + base.base.EXTRA_CSS + base.UI_CSS + V113_CSS)

    def home_page(self):
        # User-requested compact home: no hero/banner, so sourcing/results do not get pushed below the fold.
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(9)

        title = QLabel('영상 소싱')
        title.setObjectName('homeTitleV113')
        sub = QLabel('상품명이나 키워드로 글로벌 플랫폼의 인기 영상을 수집합니다.')
        sub.setObjectName('homeSubV113')
        v.addWidget(title)
        v.addWidget(sub)

        card = QFrame()
        card.setObjectName('sourceCardV113')
        card.setFixedHeight(160)
        cv = QVBoxLayout(card)
        cv.setContentsMargins(14, 11, 14, 12)
        cv.setSpacing(8)

        top = QHBoxLayout()
        icon = QLabel('🔎')
        icon.setFixedWidth(23)
        top.addWidget(icon)
        texts = QVBoxLayout()
        t = QLabel('소싱하기')
        t.setObjectName('cardTitle')
        s = QLabel('플랫폼을 선택하고 검색 키워드를 입력하세요.')
        s.setObjectName('cardSub')
        texts.addWidget(t)
        texts.addWidget(s)
        top.addLayout(texts)
        top.addStretch()
        cv.addLayout(top)

        chips = QHBoxLayout()
        chips.setSpacing(6)
        self.home_checks = {}
        selected_now = set(getattr(self.s, 'platform_sources', []) or [])
        for p in base.PLATFORM_ORDER:
            b = base.platform_chip(p, p in selected_now or not selected_now, True)
            b.setMinimumWidth(82)
            b.setMaximumWidth(112)
            self.home_checks[p] = b
            chips.addWidget(b)
        chips.addStretch()
        cv.addLayout(chips)

        search = QHBoxLayout()
        search.setSpacing(8)
        self.home_keyword = QLineEdit()
        self.home_keyword.setPlaceholderText('검색 키워드를 입력하세요 (예: 주방 꿀템, 청소, 홈인테리어)')
        self.home_keyword.setFixedHeight(38)
        go = QPushButton('⌕  검색하기')
        go.setObjectName('searchPrimary')
        go.setFixedHeight(38)
        go.setMinimumWidth(126)
        go.clicked.connect(self.home_to_source)
        search.addWidget(self.home_keyword, 1)
        search.addWidget(go)
        cv.addLayout(search)
        v.addWidget(card)

        row = QHBoxLayout()
        label = QLabel('수집된 영상 목록')
        label.setObjectName('section')
        row.addWidget(label)
        self.home_count = QLabel('0')
        self.home_count.setObjectName('muted')
        row.addWidget(self.home_count)
        row.addStretch()
        self.home_edit_btn = QPushButton('선택 영상으로 편집하기 →')
        self.home_edit_btn.clicked.connect(self.home_edit_selected)
        row.addWidget(self.home_edit_btn)
        v.addLayout(row)

        self.card_area = QScrollArea()
        self.card_area.setWidgetResizable(True)
        self.card_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.card_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.card_area.setMinimumHeight(245)
        self.card_host = QWidget()
        self.card_layout = QHBoxLayout(self.card_host)
        self.card_layout.setContentsMargins(0, 0, 0, 3)
        self.card_layout.setSpacing(9)
        self.card_area.setWidget(self.card_host)
        v.addWidget(self.card_area, 1)
        self.render_cards([])
        return w

    def right_panel(self):
        w = QWidget()
        w.setFixedWidth(352)
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(9)

        g = QFrame()
        g.setObjectName('quickCardV113')
        g.setFixedHeight(360)
        gv = QVBoxLayout(g)
        gv.setContentsMargins(14, 11, 14, 12)
        gv.setSpacing(5)

        head = QLabel('⚙  빠른 설정')
        head.setObjectName('panelTitle')
        head.setFixedHeight(24)
        gv.addWidget(head)

        def combo_field(label, items):
            lab = QLabel(label)
            lab.setProperty('quickLabel', True)
            gv.addWidget(lab)
            c = QComboBox()
            c.setProperty('quick', True)
            c.addItems(items)
            c.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
            c.setMinimumWidth(310)
            gv.addWidget(c)
            return c

        self.quick_ai = combo_field('AI 모델', ['Gemini 2.5 Flash (기본)', '규칙 기반'])
        self.quick_ai.setCurrentIndex(0 if self.s.use_gemini_query_planning else 1)
        self.quick_ai.currentIndexChanged.connect(self.quick_save)

        self.quick_voice = combo_field('TTS 음성', ['Edge TTS - SunHi', 'Edge TTS - InJoon', 'Edge TTS - Hyunsu'])
        voices = ['ko-KR-SunHiNeural', 'ko-KR-InJoonNeural', 'ko-KR-HyunsuNeural']
        self.quick_voice.setCurrentIndex(voices.index(self.s.tts_voice) if self.s.tts_voice in voices else 0)
        self.quick_voice.currentIndexChanged.connect(self.quick_voice_changed)

        self.quick_res = combo_field('영상 해상도', ['1080 × 1920 (세로)'])
        gv.addSpacing(4)

        self.quick_ocr = OnOffButton(True)
        self.quick_cut = OnOffButton(True)
        self.quick_wm = OnOffButton(self.s.watermark_enabled)
        self.quick_link = OnOffButton(self.s.lnkbio_auto_publish)
        self.quick_wm.toggled.connect(self.quick_save)
        self.quick_link.toggled.connect(self.quick_save)

        for label, sw in [
            ('자막 제거 (OCR)', self.quick_ocr),
            ('자동 컷 편집', self.quick_cut),
            ('워터마크 추가', self.quick_wm),
            ('업로드 후 링크 생성', self.quick_link),
        ]:
            r = QHBoxLayout()
            r.setSpacing(8)
            l = QLabel(label)
            l.setProperty('quickLabel', True)
            l.setMinimumWidth(190)
            l.setFixedHeight(28)
            r.addWidget(l)
            r.addStretch()
            r.addWidget(sw, alignment=Qt.AlignVCenter)
            gv.addLayout(r)

        v.addWidget(g)

        pg = QFrame()
        pg.setObjectName('previewCardV113')
        pg.setMinimumHeight(250)
        pg.setMaximumHeight(286)
        pv = QVBoxLayout(pg)
        pv.setContentsMargins(12, 9, 12, 10)
        pv.setSpacing(6)
        ph = QLabel('미리보기')
        ph.setObjectName('panelTitle')
        ph.setFixedHeight(22)
        pv.addWidget(ph)
        self.video_view = base.base.base.VideoView()
        self.video_view.setMinimumHeight(165)
        self.player.setVideoOutput(self.video_view.video_item)
        pv.addWidget(self.video_view, 1)
        self.preview_label = QLabel('선택/완성 영상을 불러오세요')
        self.preview_label.setObjectName('muted')
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setFixedHeight(20)
        pv.addWidget(self.preview_label)
        ctrl = QHBoxLayout()
        self.play_btn = QPushButton('▶ 재생')
        self.play_btn.clicked.connect(self.toggle_play)
        op = QPushButton('파일 열기')
        op.setProperty('secondary', True)
        op.clicked.connect(self.preview_pick)
        ctrl.addWidget(self.play_btn)
        ctrl.addWidget(op)
        pv.addLayout(ctrl)
        v.addWidget(pg)
        v.addStretch()
        return w

    def settings_page(self):
        # Compact but scroll-safe: fits 1600x930 without clipping, scrolls only on smaller windows.
        outer = QWidget()
        ov = QVBoxLayout(outer)
        ov.setContentsMargins(0, 0, 0, 0)
        ov.setSpacing(7)

        title = QLabel('설정')
        title.setObjectName('title')
        title.setFixedHeight(38)
        ov.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setFrameShape(QFrame.NoFrame)

        host = QWidget()
        v = QVBoxLayout(host)
        v.setContentsMargins(0, 0, 4, 0)
        v.setSpacing(8)

        g = QGroupBox('API / 연동 / 출력')
        g.setObjectName('settingsCardV113')
        q = QGridLayout(g)
        q.setContentsMargins(16, 19, 16, 13)
        q.setHorizontalSpacing(14)
        q.setVerticalSpacing(6)

        self.setout = QLineEdit(self.s.output_folder)
        self.gkey = QLineEdit(self.s.gemini_api_key); self.gkey.setEchoMode(QLineEdit.Password)
        self.cakey = QLineEdit(self.s.coupang_access_key); self.cakey.setEchoMode(QLineEdit.Password)
        self.cskey = QLineEdit(self.s.coupang_secret_key); self.cskey.setEchoMode(QLineEdit.Password)
        self.sim = QSpinBox(); self.sim.setRange(0, 100); self.sim.setValue(self.s.min_similarity)
        self.ysecret = QLineEdit(self.s.youtube_client_secret_file)
        self.lid = QLineEdit(self.s.lnkbio_client_id)
        self.lsec = QLineEdit(self.s.lnkbio_client_secret); self.lsec.setEchoMode(QLineEdit.Password)

        fields = [self.setout, self.gkey, self.cakey, self.cskey, self.sim, self.ysecret, self.lid, self.lsec]
        for f in fields:
            f.setProperty('setting', True)

        rows = [
            ('출력 폴더', self.setout),
            ('Gemini API Key', self.gkey),
            ('Coupang Access Key', self.cakey),
            ('Coupang Secret Key', self.cskey),
            ('최소 유사도', self.sim),
            ('YouTube client_secret.json', self.ysecret),
            ('Lnk.Bio Client ID', self.lid),
            ('Lnk.Bio Client Secret', self.lsec),
        ]
        for i, (name, widget) in enumerate(rows):
            lab = QLabel(name)
            lab.setProperty('settingLabel', True)
            lab.setMinimumWidth(190)
            lab.setFixedHeight(34)
            lab.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            q.addWidget(lab, i, 0)
            q.addWidget(widget, i, 1)
        q.setColumnStretch(1, 1)

        self.skip = QCheckBox('저유사도 자동 제외')
        self.skip.setChecked(self.s.auto_skip_low_similarity)
        self.gplan = QCheckBox('Gemini 검색계획')
        self.gplan.setChecked(self.s.use_gemini_query_planning)
        checks = QHBoxLayout()
        checks.addWidget(self.skip)
        checks.addWidget(self.gplan)
        checks.addStretch()
        q.addLayout(checks, len(rows), 1)

        bs = QPushButton('설정 저장')
        bs.setFixedHeight(38)
        bs.setMinimumWidth(180)
        bs.clicked.connect(self.save)
        q.addWidget(bs, len(rows) + 1, 1, alignment=Qt.AlignRight)
        v.addWidget(g)

        dg = QGroupBox('런타임 진단')
        dg.setObjectName('settingsCardV113')
        dv = QVBoxLayout(dg)
        dv.setContentsMargins(14, 17, 14, 11)
        dv.setSpacing(6)
        self.diagbox = QPlainTextEdit()
        self.diagbox.setReadOnly(True)
        self.diagbox.setFixedHeight(86)
        dv.addWidget(self.diagbox)
        bd = QPushButton('다시 진단')
        bd.setFixedHeight(34)
        bd.clicked.connect(self.refresh_diag)
        dv.addWidget(bd)
        v.addWidget(dg)
        v.addStretch()

        scroll.setWidget(host)
        ov.addWidget(scroll, 1)
        return outer

    def quick_save(self):
        self.s.watermark_enabled = self.quick_wm.isChecked()
        self.s.use_gemini_query_planning = self.quick_ai.currentIndex() == 0
        self.s.lnkbio_auto_publish = self.quick_link.isChecked()
        base.ext.save_settings(self.s)


if __name__ == '__main__':
    app = QApplication([])
    app.setApplicationName('NovaShorts')
    app.setFont(QFont('Malgun Gothic', 10))
    win = Nova()
    win.show()
    app.exec()
