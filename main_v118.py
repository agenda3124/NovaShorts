from __future__ import annotations

import main_v117 as base
import main_v18 as core_ui
import main_v113
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import *

VERSION = '1.18'

# Keep the visible version consistent through the inherited modules.
for mod in [base, getattr(base, 'base', None)]:
    try:
        if mod is not None:
            mod.VERSION = VERSION
    except Exception:
        pass

V118_CSS = r'''
/* v1.18 - responsive right panel + clean settings rows */
QScrollArea#rightScroll118 {
    background: transparent;
    border: 0;
}
QScrollArea#rightScroll118 > QWidget > QWidget {
    background: transparent;
}
QFrame#quickCard118, QFrame#previewCard118, QFrame#settingsCard118 {
    background:#151d31;
    border:1px solid #304564;
    border-radius:14px;
}
QLabel#quickTitle118, QLabel#settingsTitle118 {
    background:transparent;
    color:#f6f8ff;
    font-size:15px;
    font-weight:850;
}
QWidget[quickRow118="true"], QFrame[settingRow118="true"], QFrame[settingOptions118="true"] {
    background:#111b30;
    border:1px solid #263a58;
    border-radius:9px;
}
QLabel[quickRowLabel118="true"], QLabel[settingLabel118="true"] {
    background:transparent;
    border:0;
    color:#dce5f5;
    font-size:12px;
    font-weight:650;
}
QComboBox[quick118="true"] {
    background:#0e1a2e;
    border:1px solid #3d5578;
    border-radius:8px;
    padding:0 11px;
    min-height:36px;
    max-height:36px;
    color:#f5f7ff;
    font-size:12px;
}
QComboBox[quick118="true"]:hover { border-color:#6d88b7; background:#101e34; }
QComboBox[quick118="true"]::drop-down { border:0; width:26px; }
QLineEdit[setting118="true"], QSpinBox[setting118="true"] {
    background:#0e1a2e;
    border:1px solid #3d5578;
    border-radius:8px;
    padding:0 11px;
    min-height:36px;
    max-height:36px;
    color:#f5f7ff;
    font-size:12px;
}
QLineEdit[setting118="true"]:focus, QSpinBox[setting118="true"]:focus {
    border-color:#6c86ff;
    background:#101e34;
}
QCheckBox[settingCheck118="true"] {
    background:transparent;
    color:#dce5f5;
    spacing:7px;
    font-size:12px;
}
QPlainTextEdit#diag118 {
    background:#0e1a2e;
    border:1px solid #3d5578;
    border-radius:8px;
    color:#dce5f5;
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
        self.setWindowTitle(f'NovaShorts Studio v{VERSION}')
        self.setMinimumSize(1024, 680)
        self.setStyleSheet(self.styleSheet() + V118_CSS)

        # Start inside the usable desktop area. Qt 6 already handles Windows DPI,
        # so these are logical pixels and work at 100/125/150% display scaling.
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            tw = min(1600, max(1024, int(geo.width() * 0.96)))
            th = min(930, max(680, int(geo.height() * 0.94)))
            self.resize(tw, th)
        else:
            self.resize(1600, 930)
        self._apply_responsive118()

    def sidebar(self):
        f = super().sidebar()
        self.sidebar_frame118 = f
        return f

    def topbar(self):
        f = QFrame()
        f.setObjectName('topbar')
        f.setFixedHeight(68)
        h = QHBoxLayout(f)
        h.setContentsMargins(18, 8, 16, 8)
        h.setSpacing(12)
        title = QLabel('NovaShorts')
        title.setObjectName('brand')
        title.setMinimumWidth(132)
        h.addWidget(title)
        self.top_breadcrumb118 = QLabel('상품 → 글로벌 소싱 → AI 편집 → 자동 게시')
        self.top_breadcrumb118.setObjectName('muted')
        self.top_breadcrumb118.setMinimumWidth(280)
        h.addWidget(self.top_breadcrumb118)
        h.addStretch()
        history = QPushButton('▣ 작업 기록')
        history.setProperty('secondary', True)
        history.clicked.connect(lambda: self.queue.setFocus())
        h.addWidget(history)
        b = QPushButton('⚙ 설정')
        b.setProperty('secondary', True)
        b.clicked.connect(lambda: self.go(7))
        h.addWidget(b)
        return f

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_responsive118()

    def _apply_responsive118(self):
        if not hasattr(self, 'right_scroll118'):
            return
        ww = self.width()
        wh = self.height()

        if ww >= 1550:
            rw, sw = 360, 205
        elif ww >= 1350:
            rw, sw = 338, 198
        else:
            rw, sw = 318, 188

        self.right_scroll118.setMinimumWidth(rw)
        self.right_scroll118.setMaximumWidth(rw)
        if hasattr(self, 'sidebar_frame118'):
            self.sidebar_frame118.setFixedWidth(sw)
        if hasattr(self, 'top_breadcrumb118'):
            self.top_breadcrumb118.setVisible(ww >= 1240)
        if hasattr(self, 'queue_group118'):
            self.queue_group118.setFixedHeight(172 if wh >= 850 else 142)
        if hasattr(self, 'progress'):
            self.progress.setFixedWidth(245 if ww >= 1400 else 180)

    def right_panel(self):
        scroll = QScrollArea()
        scroll.setObjectName('rightScroll118')
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setMinimumWidth(318)
        scroll.setMaximumWidth(360)
        self.right_scroll118 = scroll

        host = QWidget()
        host.setMinimumWidth(292)
        v = QVBoxLayout(host)
        v.setContentsMargins(0, 0, 4, 0)
        v.setSpacing(10)

        quick = QFrame()
        quick.setObjectName('quickCard118')
        quick.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        qv = QVBoxLayout(quick)
        qv.setContentsMargins(12, 11, 12, 13)
        qv.setSpacing(6)
        qv.setSizeConstraint(QLayout.SetMinimumSize)

        head = QLabel('⚙  빠른 설정')
        head.setObjectName('quickTitle118')
        head.setMinimumHeight(24)
        qv.addWidget(head)

        self.quick_field_pairs = []

        def combo_row(label, items):
            row = QWidget()
            row.setProperty('quickRow118', True)
            row.setMinimumHeight(44)
            row.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            rh = QHBoxLayout(row)
            rh.setContentsMargins(10, 4, 8, 4)
            rh.setSpacing(9)
            lab = QLabel(label)
            lab.setProperty('quickRowLabel118', True)
            lab.setMinimumWidth(92)
            lab.setMaximumWidth(108)
            lab.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            combo = QComboBox()
            combo.setProperty('quick118', True)
            combo.addItems(items)
            combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            combo.setMinimumWidth(150)
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
            row.setProperty('quickRow118', True)
            row.setMinimumHeight(40)
            row.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            rh = QHBoxLayout(row)
            rh.setContentsMargins(10, 4, 8, 4)
            rh.setSpacing(9)
            lab = QLabel(label)
            lab.setProperty('quickRowLabel118', True)
            lab.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            rh.addWidget(lab, 1)
            rh.addWidget(sw, 0, Qt.AlignRight | Qt.AlignVCenter)
            qv.addWidget(row)
            self.quick_toggle_pairs.append((lab, sw))

        # Size from real contents instead of a guessed fixed height.
        quick.adjustSize()
        quick.setMinimumHeight(max(370, qv.sizeHint().height() + 8))
        self.quick_card118 = quick
        v.addWidget(quick, 0)

        preview = QFrame()
        preview.setObjectName('previewCard118')
        preview.setMinimumHeight(220)
        preview.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        pv = QVBoxLayout(preview)
        pv.setContentsMargins(12, 9, 12, 10)
        pv.setSpacing(6)
        ph = QLabel('미리보기')
        ph.setObjectName('panelTitle')
        ph.setMinimumHeight(22)
        pv.addWidget(ph)
        self.video_view = core_ui.VideoView()
        self.video_view.setMinimumHeight(125)
        self.player.setVideoOutput(self.video_view.video_item)
        pv.addWidget(self.video_view, 1)
        self.preview_label = QLabel('선택/완성 영상을 불러오세요')
        self.preview_label.setObjectName('muted')
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumHeight(20)
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

        scroll.setWidget(host)
        self.right_host118 = host
        self.preview_card118 = preview
        return scroll

    def settings_page(self):
        outer = QWidget()
        ov = QVBoxLayout(outer)
        ov.setContentsMargins(0, 0, 0, 0)
        ov.setSpacing(7)

        title = QLabel('설정')
        title.setObjectName('title')
        title.setMinimumHeight(36)
        ov.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setFrameShape(QFrame.NoFrame)

        host = QWidget()
        v = QVBoxLayout(host)
        v.setContentsMargins(0, 0, 5, 0)
        v.setSpacing(10)

        card = QFrame()
        card.setObjectName('settingsCard118')
        form = QVBoxLayout(card)
        form.setContentsMargins(14, 12, 14, 14)
        form.setSpacing(7)
        card_title = QLabel('API / 연동 / 출력')
        card_title.setObjectName('settingsTitle118')
        card_title.setMinimumHeight(22)
        form.addWidget(card_title)

        self.setout = QLineEdit(self.s.output_folder)
        self.gkey = QLineEdit(self.s.gemini_api_key)
        self.gkey.setEchoMode(QLineEdit.Password)
        self.cakey = QLineEdit(self.s.coupang_access_key)
        self.cakey.setEchoMode(QLineEdit.Password)
        self.cskey = QLineEdit(self.s.coupang_secret_key)
        self.cskey.setEchoMode(QLineEdit.Password)
        self.sim = QSpinBox()
        self.sim.setRange(0, 100)
        self.sim.setValue(self.s.min_similarity)
        self.ysecret = QLineEdit(self.s.youtube_client_secret_file)
        self.lid = QLineEdit(self.s.lnkbio_client_id)
        self.lsec = QLineEdit(self.s.lnkbio_client_secret)
        self.lsec.setEchoMode(QLineEdit.Password)

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
        self.setting_pairs = []
        for name, widget in rows:
            rowbox = QFrame()
            rowbox.setProperty('settingRow118', True)
            rowbox.setMinimumHeight(48)
            rowbox.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            h = QHBoxLayout(rowbox)
            h.setContentsMargins(10, 5, 9, 5)
            h.setSpacing(12)
            lab = QLabel(name)
            lab.setProperty('settingLabel118', True)
            lab.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            lab.setMinimumWidth(150)
            lab.setMaximumWidth(190)
            widget.setProperty('setting118', True)
            widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            h.addWidget(lab)
            h.addWidget(widget, 1)
            form.addWidget(rowbox)
            self.setting_pairs.append((lab, widget))

        options = QFrame()
        options.setProperty('settingOptions118', True)
        oh = QHBoxLayout(options)
        oh.setContentsMargins(12, 7, 12, 7)
        oh.setSpacing(16)
        self.skip = QCheckBox('저유사도 자동 제외')
        self.skip.setProperty('settingCheck118', True)
        self.skip.setChecked(self.s.auto_skip_low_similarity)
        self.gplan = QCheckBox('Gemini 검색계획')
        self.gplan.setProperty('settingCheck118', True)
        self.gplan.setChecked(self.s.use_gemini_query_planning)
        oh.addWidget(self.skip)
        oh.addWidget(self.gplan)
        oh.addStretch()
        form.addWidget(options)

        save_row = QHBoxLayout()
        save_row.addStretch()
        bs = QPushButton('설정 저장')
        bs.setMinimumHeight(38)
        bs.setMinimumWidth(170)
        bs.clicked.connect(self.save)
        save_row.addWidget(bs)
        form.addLayout(save_row)
        v.addWidget(card)

        diag = QFrame()
        diag.setObjectName('settingsCard118')
        dv = QVBoxLayout(diag)
        dv.setContentsMargins(14, 12, 14, 12)
        dv.setSpacing(7)
        dt = QLabel('런타임 진단')
        dt.setObjectName('settingsTitle118')
        dv.addWidget(dt)
        self.diagbox = QPlainTextEdit()
        self.diagbox.setObjectName('diag118')
        self.diagbox.setReadOnly(True)
        self.diagbox.setMinimumHeight(85)
        dv.addWidget(self.diagbox)
        bd = QPushButton('다시 진단')
        bd.clicked.connect(self.refresh_diag)
        dv.addWidget(bd)
        v.addWidget(diag)
        v.addStretch()

        scroll.setWidget(host)
        ov.addWidget(scroll, 1)
        return outer

    def queue_panel(self):
        g = QGroupBox('작업 대기열')
        self.queue_group118 = g
        g.setFixedHeight(172)
        v = QVBoxLayout(g)
        v.setSpacing(5)
        top = QHBoxLayout()
        top.addStretch()
        start = QPushButton('▶ 모두 시작')
        start.clicked.connect(self.resume_jobs)
        stop = QPushButton('■ 모두 중지')
        stop.setProperty('danger', True)
        stop.clicked.connect(self.stop_jobs)
        clear = QPushButton('목록 비우기')
        clear.setProperty('secondary', True)
        clear.clicked.connect(self.clear_queue)
        top.addWidget(start)
        top.addWidget(stop)
        top.addWidget(clear)
        v.addLayout(top)
        self.queue = QTableWidget(0, 5)
        self.queue.setHorizontalHeaderLabels(['작업명', '상태', '진행률', '시작 시간', '작업'])
        self.queue.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for c in [1, 2, 3, 4]:
            self.queue.horizontalHeader().setSectionResizeMode(c, QHeaderView.ResizeToContents)
        self.queue.verticalHeader().setVisible(False)
        self.queue.setMinimumHeight(68)
        v.addWidget(self.queue)
        return g


if __name__ == '__main__':
    app = QApplication([])
    app.setApplicationName('NovaShorts')
    app.setFont(QFont('Malgun Gothic', 10))
    win = Nova()
    win.show()
    app.exec()
