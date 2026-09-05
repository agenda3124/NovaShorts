from __future__ import annotations

from pathlib import Path

import main_v18 as base
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import *

VERSION = '1.9'
base.VERSION = VERSION

EXTRA_CSS = '''
QLabel{background:transparent}
QLineEdit,QComboBox,QSpinBox{min-height:22px;padding:6px 8px}
QGroupBox{padding:11px;margin-top:10px}
QGroupBox::title{padding:0 6px}
QPushButton{min-height:24px;padding:7px 12px}
QTableWidget{font-size:12px}
'''


class Nova(base.Nova):
    def build(self):
        super().build()
        self.setWindowTitle(f'NovaShorts Studio v{VERSION}')
        self.resize(1600, 930)
        self.setMinimumSize(1200, 720)
        self.setStyleSheet(base.CSS + EXTRA_CSS)

    def home_page(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(9)

        head = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel('영상 소싱')
        title.setObjectName('title')
        sub = QLabel('상품명이나 키워드로 글로벌 플랫폼 영상을 수집합니다.')
        sub.setObjectName('muted')
        title_box.addWidget(title)
        title_box.addWidget(sub)
        head.addLayout(title_box)
        head.addStretch()
        v.addLayout(head)

        g = QGroupBox('소싱하기')
        g.setFixedHeight(118)
        q = QGridLayout(g)
        q.setContentsMargins(14, 15, 14, 12)
        q.setHorizontalSpacing(8)
        q.setVerticalSpacing(8)
        self.home_keyword = QLineEdit()
        self.home_keyword.setPlaceholderText('상품명/검색 키워드를 입력하세요  예: 주방 꿀템, 청소, 홈인테리어')
        b = QPushButton('🔎 소싱 시작')
        b.setMinimumWidth(150)
        b.clicked.connect(self.home_to_source)
        q.addWidget(self.home_keyword, 0, 0, 1, 5)
        q.addWidget(b, 0, 5)
        self.home_checks = {}
        platforms = ['TikTok', 'Douyin', 'Xiaohongshu', 'Kuaishou', '1688']
        for j, p in enumerate(platforms):
            cb = QPushButton(p)
            cb.setProperty('chip', True)
            cb.setCheckable(True)
            cb.setChecked(True)
            cb.setMinimumWidth(112)
            self.home_checks[p] = cb
            q.addWidget(cb, 1, j)
        q.setColumnStretch(0, 1)
        v.addWidget(g)

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
        self.card_layout.setContentsMargins(0, 0, 0, 4)
        self.card_layout.setSpacing(10)
        self.card_area.setWidget(self.card_host)
        v.addWidget(self.card_area, 1)
        self.render_cards([])
        return w

    def render_cards(self, rows):
        while self.card_layout.count():
            item = self.card_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        if not rows:
            for _ in range(5):
                f = QFrame()
                f.setObjectName('videoCard')
                f.setFixedSize(176, 210)
                vl = QVBoxLayout(f)
                vl.setContentsMargins(8, 8, 8, 8)
                img = QLabel('검색 결과')
                img.setAlignment(Qt.AlignCenter)
                img.setFixedHeight(112)
                img.setStyleSheet('background:#172542;border-radius:9px;color:#7086aa')
                vl.addWidget(img)
                txt = QLabel('소싱을 시작하면\n영상 후보가 표시됩니다')
                txt.setObjectName('muted')
                txt.setAlignment(Qt.AlignCenter)
                txt.setWordWrap(True)
                vl.addWidget(txt)
                self.card_layout.addWidget(f)
            self.card_layout.addStretch()
            self.home_count.setText('0')
            return
        for r in rows[:8]:
            card = base.CandidateCard(r, r.get('_score', 0))
            card.setFixedHeight(225)
            card.selected.connect(self.card_select)
            self.card_layout.addWidget(card)
            thumb = r.get('thumbnail', '')
            if thumb and thumb.startswith(('http://', 'https://')):
                self.load_card_thumb(card, thumb)
        self.card_layout.addStretch()
        self.home_count.setText(str(len(rows)))

    def settings_page(self):
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(8)
        t = QLabel('설정')
        t.setObjectName('title')
        outer.addWidget(t)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        host = QWidget()
        v = QVBoxLayout(host)
        v.setContentsMargins(0, 0, 4, 0)
        v.setSpacing(10)

        g = QGroupBox('API / 연동 / 출력')
        q = QGridLayout(g)
        q.setContentsMargins(16, 18, 16, 14)
        q.setHorizontalSpacing(12)
        q.setVerticalSpacing(8)

        self.setout = QLineEdit(self.s.output_folder)
        self.gkey = QLineEdit(self.s.gemini_api_key); self.gkey.setEchoMode(QLineEdit.Password)
        self.cakey = QLineEdit(self.s.coupang_access_key); self.cakey.setEchoMode(QLineEdit.Password)
        self.cskey = QLineEdit(self.s.coupang_secret_key); self.cskey.setEchoMode(QLineEdit.Password)
        self.sim = QSpinBox(); self.sim.setRange(0,100); self.sim.setValue(self.s.min_similarity)
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
        for i, (name, widget) in enumerate(rows):
            lab = QLabel(name)
            lab.setMinimumWidth(190)
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
        bs.setMinimumWidth(180)
        bs.clicked.connect(self.save)
        q.addWidget(bs, len(rows)+1, 1, alignment=Qt.AlignRight)
        v.addWidget(g)

        dg = QGroupBox('런타임 진단')
        dv = QVBoxLayout(dg)
        self.diagbox = QPlainTextEdit()
        self.diagbox.setReadOnly(True)
        self.diagbox.setMinimumHeight(110)
        self.diagbox.setMaximumHeight(145)
        bd = QPushButton('다시 진단')
        bd.clicked.connect(self.refresh_diag)
        dv.addWidget(self.diagbox)
        dv.addWidget(bd)
        v.addWidget(dg)
        v.addStretch()

        scroll.setWidget(host)
        outer.addWidget(scroll, 1)
        return w

    def right_panel(self):
        w = QWidget()
        w.setFixedWidth(342)
        v = QVBoxLayout(w)
        v.setContentsMargins(0,0,0,0)
        v.setSpacing(9)

        g = QGroupBox('빠른 설정')
        g.setFixedHeight(238)
        q = QGridLayout(g)
        q.setContentsMargins(12,16,12,12)
        q.setHorizontalSpacing(10)
        q.setVerticalSpacing(7)
        self.quick_ai = QComboBox(); self.quick_ai.addItems(['Gemini 2.5 Flash','규칙 기반']); self.quick_ai.setCurrentIndex(0 if self.s.use_gemini_query_planning else 1); self.quick_ai.currentIndexChanged.connect(self.quick_save)
        self.quick_voice = QComboBox(); self.quick_voice.addItems(['Edge TTS - SunHi','Edge TTS - InJoon','Edge TTS - Hyunsu']); self.quick_voice.currentIndexChanged.connect(self.quick_voice_changed)
        self.quick_res = QComboBox(); self.quick_res.addItems(['1080 × 1920 (세로)'])
        for combo in [self.quick_ai, self.quick_voice, self.quick_res]: combo.setMinimumWidth(176)
        self.quick_ocr = base.Switch(True)
        self.quick_cut = base.Switch(True)
        self.quick_wm = base.Switch(self.s.watermark_enabled)
        self.quick_wm.toggled.connect(self.quick_save)
        rows = [('AI 모델',self.quick_ai),('TTS 음성',self.quick_voice),('영상 해상도',self.quick_res)]
        for i,(name,widget) in enumerate(rows):
            lab=QLabel(name); lab.setMinimumWidth(105); q.addWidget(lab,i,0); q.addWidget(widget,i,1)
        for i,(name,widget) in enumerate([('자막 제거(OCR)',self.quick_ocr),('자동 컷 편집',self.quick_cut),('워터마크 추가',self.quick_wm)], start=3):
            lab=QLabel(name); q.addWidget(lab,i,0); q.addWidget(widget,i,1,alignment=Qt.AlignRight)
        v.addWidget(g)

        pg = QGroupBox('미리보기')
        pg.setMaximumHeight(330)
        pv = QVBoxLayout(pg)
        self.video_view = base.VideoView()
        self.video_view.setMinimumHeight(205)
        self.player.setVideoOutput(self.video_view.video_item)
        pv.addWidget(self.video_view, 1)
        self.preview_label = QLabel('선택/완성 영상을 불러오세요')
        self.preview_label.setObjectName('muted')
        self.preview_label.setAlignment(Qt.AlignCenter)
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

    def queue_panel(self):
        g = QGroupBox('작업 대기열')
        g.setFixedHeight(148)
        v = QVBoxLayout(g)
        v.setSpacing(5)
        v.setContentsMargins(12, 14, 12, 9)
        top = QHBoxLayout()
        top.addStretch()
        start = QPushButton('▶ 모두 시작'); start.clicked.connect(self.resume_jobs)
        stop = QPushButton('■ 모두 중지'); stop.setProperty('danger',True); stop.clicked.connect(self.stop_jobs)
        clear = QPushButton('목록 비우기'); clear.setProperty('secondary',True); clear.clicked.connect(self.clear_queue)
        top.addWidget(start); top.addWidget(stop); top.addWidget(clear)
        v.addLayout(top)
        self.queue = QTableWidget(0,5)
        self.queue.setHorizontalHeaderLabels(['작업명','상태','진행률','시작 시간','작업'])
        self.queue.horizontalHeader().setSectionResizeMode(0,QHeaderView.Stretch)
        for c in [1,2,3,4]: self.queue.horizontalHeader().setSectionResizeMode(c,QHeaderView.ResizeToContents)
        self.queue.verticalHeader().setVisible(False)
        self.queue.setMinimumHeight(70)
        self.queue.setMaximumHeight(78)
        v.addWidget(self.queue)
        return g


if __name__ == '__main__':
    app = QApplication([])
    app.setApplicationName('NovaShorts')
    app.setFont(QFont('Malgun Gothic', 10))
    win = Nova()
    win.show()
    app.exec()
