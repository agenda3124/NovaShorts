from __future__ import annotations

import main_v113 as base
import main_v18 as core_ui
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import *

VERSION = '1.14'
base.VERSION = VERSION
try:
    base.base.VERSION = VERSION
    base.base.base.VERSION = VERSION
    base.base.base.base.VERSION = VERSION
except Exception:
    pass

V114_CSS = r'''
/* v1.14: width-safe / overlap-safe layout */
QFrame#sidebar{background:#0d1729;border-right:1px solid #22324e}
QLabel#brand114{font-size:20px;font-weight:900;color:#f3f6ff}
QLabel#version114{font-size:11px;font-weight:700;color:#91a5c8}
QLabel#sub114{font-size:11px;color:#7386a7}

QPushButton[nav="true"]{
    text-align:left;
    background:#111b2f;
    border:1px solid #263955;
    border-left:3px solid #263955;
    border-radius:9px;
    padding:8px 12px;
    min-height:27px;
    max-height:34px;
    color:#d4dced;
    font-size:13px;
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
QPushButton[nav="true"]:checked:hover{
    background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #3c67eb,stop:1 #6b58ef);
    border-color:#9caaff;
}

QFrame#quickCard114,QFrame#previewCard114{
    background:#151d31;
    border:1px solid #2f4161;
    border-radius:13px;
}
QLabel#quickTitle114{font-size:14px;font-weight:850;color:#f5f7ff}
QLabel[quickRowLabel="true"]{
    background:transparent;
    color:#d2dbec;
    font-size:12px;
    min-height:32px;
    max-height:32px;
}
QComboBox[quick114="true"]{
    background:#101a2d;
    border:1px solid #3a4f72;
    border-radius:8px;
    padding:5px 10px;
    min-height:32px;
    max-height:32px;
    font-size:12px;
    color:#f2f5ff;
}
QComboBox[quick114="true"]:hover{border-color:#6f89bd}
QComboBox[quick114="true"]::drop-down{border:0;width:26px}

QPushButton[toggle="true"]{
    background:#25334b;
    border:1px solid #475c7b;
    border-radius:14px;
    color:#aebbd1;
    min-width:62px;
    max-width:62px;
    min-height:28px;
    max-height:28px;
    padding:0;
    font-size:11px;
    font-weight:900;
}
QPushButton[toggle="true"]:hover{background:#30415e;border-color:#6d84aa;color:#fff}
QPushButton[toggle="true"]:checked{background:#6555f5;border:1px solid #9a91ff;color:#fff}

QGroupBox#settingsCard114{
    background:#121a30;
    border:1px solid #2d3f5e;
    border-radius:12px;
    margin-top:13px;
    padding:10px;
}
QGroupBox#settingsCard114::title{
    subcontrol-origin:margin;
    left:13px;
    padding:0 6px;
    color:#eef2ff;
    font-weight:800;
}
QLabel[settingLabel114="true"]{font-size:12px;color:#d7dfef;min-height:30px;max-height:30px}
QLineEdit[setting114="true"],QSpinBox[setting114="true"]{
    min-height:30px;
    max-height:30px;
    padding:3px 9px;
}
'''


class Nova(base.Nova):
    def build(self):
        super().build()
        self.setWindowTitle(f'NovaShorts Studio v{VERSION}')
        self.resize(1600, 930)
        self.setMinimumSize(1200, 760)
        self.setStyleSheet(base.base.base.base.CSS + base.base.base.EXTRA_CSS + base.base.UI_CSS + base.V113_CSS + V114_CSS)

    def sidebar(self):
        f = QFrame()
        f.setObjectName('sidebar')
        f.setFixedWidth(220)
        v = QVBoxLayout(f)
        v.setContentsMargins(10, 14, 10, 12)
        v.setSpacing(6)

        brand = QLabel('✦  NovaShorts')
        brand.setObjectName('brand114')
        brand.setFixedHeight(28)
        v.addWidget(brand)

        version = QLabel(f'Version {VERSION}')
        version.setObjectName('version114')
        version.setFixedHeight(17)
        v.addWidget(version)

        sub = QLabel('Global Shorts Production')
        sub.setObjectName('sub114')
        sub.setFixedHeight(17)
        v.addWidget(sub)
        v.addSpacing(7)

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
            'background:#182451;border:1px solid #405bd0;border-radius:11px;'
            'padding:10px;color:#edf1ff;font-size:11px;font-weight:700'
        )
        v.addWidget(badge)
        return f

    def right_panel(self):
        w = QWidget()
        w.setFixedWidth(360)
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(9)

        quick = QFrame()
        quick.setObjectName('quickCard114')
        quick.setFixedHeight(354)
        q = QGridLayout(quick)
        q.setContentsMargins(14, 10, 14, 12)
        q.setHorizontalSpacing(10)
        q.setVerticalSpacing(5)
        q.setColumnMinimumWidth(0, 104)
        q.setColumnStretch(1, 1)

        head = QLabel('⚙  빠른 설정')
        head.setObjectName('quickTitle114')
        head.setFixedHeight(24)
        q.addWidget(head, 0, 0, 1, 2)

        self.quick_field_pairs = []

        def combo_row(row, label, items):
            lab = QLabel(label)
            lab.setProperty('quickRowLabel', True)
            lab.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            combo = QComboBox()
            combo.setProperty('quick114', True)
            combo.addItems(items)
            combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
            combo.setMinimumWidth(205)
            q.addWidget(lab, row, 0)
            q.addWidget(combo, row, 1)
            q.setRowMinimumHeight(row, 40)
            self.quick_field_pairs.append((lab, combo))
            return combo

        self.quick_ai = combo_row(1, 'AI 모델', ['Gemini 2.5 Flash (기본)', '규칙 기반'])
        self.quick_ai.setCurrentIndex(0 if self.s.use_gemini_query_planning else 1)
        self.quick_ai.currentIndexChanged.connect(self.quick_save)

        self.quick_voice = combo_row(2, 'TTS 음성', ['Edge TTS - SunHi', 'Edge TTS - InJoon', 'Edge TTS - Hyunsu'])
        voices = ['ko-KR-SunHiNeural', 'ko-KR-InJoonNeural', 'ko-KR-HyunsuNeural']
        self.quick_voice.setCurrentIndex(voices.index(self.s.tts_voice) if self.s.tts_voice in voices else 0)
        self.quick_voice.currentIndexChanged.connect(self.quick_voice_changed)

        self.quick_res = combo_row(3, '영상 해상도', ['1080 × 1920 (세로)'])

        self.quick_ocr = base.OnOffButton(True)
        self.quick_cut = base.OnOffButton(True)
        self.quick_wm = base.OnOffButton(self.s.watermark_enabled)
        self.quick_link = base.OnOffButton(self.s.lnkbio_auto_publish)
        self.quick_wm.toggled.connect(self.quick_save)
        self.quick_link.toggled.connect(self.quick_save)

        self.quick_toggle_pairs = []
        for row, label, sw in [
            (4, '자막 제거 (OCR)', self.quick_ocr),
            (5, '자동 컷 편집', self.quick_cut),
            (6, '워터마크 추가', self.quick_wm),
            (7, '업로드 후 링크 생성', self.quick_link),
        ]:
            lab = QLabel(label)
            lab.setProperty('quickRowLabel', True)
            lab.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            q.addWidget(lab, row, 0)
            q.addWidget(sw, row, 1, alignment=Qt.AlignRight | Qt.AlignVCenter)
            q.setRowMinimumHeight(row, 36)
            self.quick_toggle_pairs.append((lab, sw))

        v.addWidget(quick)

        preview = QFrame()
        preview.setObjectName('previewCard114')
        preview.setMinimumHeight(250)
        preview.setMaximumHeight(278)
        pv = QVBoxLayout(preview)
        pv.setContentsMargins(12, 9, 12, 10)
        pv.setSpacing(6)
        ph = QLabel('미리보기')
        ph.setObjectName('panelTitle')
        ph.setFixedHeight(22)
        pv.addWidget(ph)
        self.video_view = core_ui.VideoView()
        self.video_view.setMinimumHeight(164)
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
        v.addWidget(preview)
        v.addStretch()
        return w

    def settings_page(self):
        outer = QWidget()
        ov = QVBoxLayout(outer)
        ov.setContentsMargins(0, 0, 0, 0)
        ov.setSpacing(6)

        title = QLabel('설정')
        title.setObjectName('title')
        title.setFixedHeight(36)
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
        g.setObjectName('settingsCard114')
        form = QVBoxLayout(g)
        form.setContentsMargins(14, 17, 14, 12)
        form.setSpacing(5)

        self.setout = QLineEdit(self.s.output_folder)
        self.gkey = QLineEdit(self.s.gemini_api_key); self.gkey.setEchoMode(QLineEdit.Password)
        self.cakey = QLineEdit(self.s.coupang_access_key); self.cakey.setEchoMode(QLineEdit.Password)
        self.cskey = QLineEdit(self.s.coupang_secret_key); self.cskey.setEchoMode(QLineEdit.Password)
        self.sim = QSpinBox(); self.sim.setRange(0, 100); self.sim.setValue(self.s.min_similarity)
        self.ysecret = QLineEdit(self.s.youtube_client_secret_file)
        self.lid = QLineEdit(self.s.lnkbio_client_id)
        self.lsec = QLineEdit(self.s.lnkbio_client_secret); self.lsec.setEchoMode(QLineEdit.Password)

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
            rowbox = QWidget()
            rowbox.setFixedHeight(38)
            h = QHBoxLayout(rowbox)
            h.setContentsMargins(0, 0, 0, 0)
            h.setSpacing(12)
            lab = QLabel(name)
            lab.setProperty('settingLabel114', True)
            lab.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            lab.setFixedWidth(178)
            widget.setProperty('setting114', True)
            h.addWidget(lab)
            h.addWidget(widget, 1)
            form.addWidget(rowbox)
            self.setting_pairs.append((lab, widget))

        checks = QHBoxLayout()
        checks.setSpacing(14)
        checks.setContentsMargins(190, 2, 0, 0)
        self.skip = QCheckBox('저유사도 자동 제외')
        self.skip.setChecked(self.s.auto_skip_low_similarity)
        self.gplan = QCheckBox('Gemini 검색계획')
        self.gplan.setChecked(self.s.use_gemini_query_planning)
        checks.addWidget(self.skip)
        checks.addWidget(self.gplan)
        checks.addStretch()
        form.addLayout(checks)

        save_row = QHBoxLayout()
        save_row.addStretch()
        bs = QPushButton('설정 저장')
        bs.setFixedHeight(36)
        bs.setMinimumWidth(170)
        bs.clicked.connect(self.save)
        save_row.addWidget(bs)
        form.addLayout(save_row)
        v.addWidget(g)

        dg = QGroupBox('런타임 진단')
        dg.setObjectName('settingsCard114')
        dv = QVBoxLayout(dg)
        dv.setContentsMargins(13, 16, 13, 10)
        dv.setSpacing(6)
        self.diagbox = QPlainTextEdit()
        self.diagbox.setReadOnly(True)
        self.diagbox.setFixedHeight(78)
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


if __name__ == '__main__':
    app = QApplication([])
    app.setApplicationName('NovaShorts')
    app.setFont(QFont('Malgun Gothic', 10))
    win = Nova()
    win.show()
    app.exec()
