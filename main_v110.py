from __future__ import annotations

import main_v19 as base
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import *

VERSION = '1.10'
base.VERSION = VERSION
try:
    base.base.VERSION = VERSION
except Exception:
    pass

POLISH_CSS = r'''
/* Left navigation: distinct cards, hover and active state */
QPushButton[nav="true"]{
    text-align:left;
    background:#0f192b;
    border:1px solid #213552;
    border-left:3px solid #213552;
    border-radius:10px;
    padding:11px 15px;
    min-height:27px;
    color:#cdd8ec;
    font-size:14px;
    font-weight:650;
}
QPushButton[nav="true"]:hover{
    background:#172640;
    border:1px solid #3b5680;
    border-left:3px solid #6b86ff;
    color:#ffffff;
}
QPushButton[nav="true"]:checked{
    background:#294fc4;
    border:1px solid #5b78e8;
    border-left:4px solid #9fb0ff;
    color:#ffffff;
}
QPushButton[nav="true"]:checked:hover{
    background:#3159d3;
    border-color:#7890f4;
}

/* Platform icon cards */
QPushButton[platform="true"]{
    background:#121e34;
    border:1px solid #2c4264;
    border-radius:12px;
    min-width:116px;
    min-height:58px;
    padding:5px 10px;
    color:#d8e2f4;
    font-size:13px;
    font-weight:700;
}
QPushButton[platform="true"]:hover{
    background:#1a2b49;
    border:1px solid #5575aa;
    color:#ffffff;
}
QPushButton[platform="true"]:checked{
    background:#315cff;
    border:1px solid #8299ff;
    color:#ffffff;
}
QPushButton[platform="true"]:checked:hover{
    background:#4169ff;
    border-color:#a0b0ff;
}

/* More polished scrollbars */
QScrollBar:horizontal{background:#0b1322;height:8px;margin:0;border-radius:4px}
QScrollBar::handle:horizontal{background:#354866;min-width:60px;border-radius:4px}
QScrollBar::handle:horizontal:hover{background:#50678d}
QScrollBar::add-line:horizontal,QScrollBar::sub-line:horizontal{width:0;background:none}
QScrollBar:vertical{background:#0b1322;width:8px;margin:0;border-radius:4px}
QScrollBar::handle:vertical{background:#354866;min-height:50px;border-radius:4px}
QScrollBar::handle:vertical:hover{background:#50678d}
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;background:none}

QLineEdit,QComboBox,QSpinBox{min-height:24px}
QPushButton[secondary="true"]:hover{background:#22324e;border-color:#50698f}
QTableWidget::item{padding:5px}
'''

PLATFORM_VIEW = {
    'TikTok': ('♪', 'TikTok'),
    'Douyin': ('▶', 'Douyin'),
    'Xiaohongshu': ('小', 'Xiaohongshu'),
    'Kuaishou': ('∞', 'Kuaishou'),
    '1688': ('1688', '1688'),
}


def platform_button(name: str, checked: bool = True) -> QPushButton:
    icon, label = PLATFORM_VIEW.get(name, ('●', name))
    b = QPushButton(f'{icon}\n{label}')
    b.setProperty('platform', True)
    b.setCheckable(True)
    b.setChecked(checked)
    b.setCursor(Qt.PointingHandCursor)
    return b


class Nova(base.Nova):
    def build(self):
        super().build()
        self.setWindowTitle(f'NovaShorts Studio v{VERSION}')
        self.resize(1600, 930)
        self.setMinimumSize(1200, 720)
        self.setStyleSheet(base.base.CSS + base.EXTRA_CSS + POLISH_CSS)

    def sidebar(self):
        f = QFrame()
        f.setObjectName('sidebar')
        f.setFixedWidth(260)
        v = QVBoxLayout(f)
        v.setContentsMargins(12, 16, 12, 14)
        v.setSpacing(8)

        brand = QLabel(f'✦  NovaShorts   v{VERSION}')
        brand.setObjectName('brand')
        brand.setMinimumWidth(225)
        v.addWidget(brand)
        sub = QLabel('Global Shorts Production')
        sub.setObjectName('muted')
        v.addWidget(sub)
        v.addSpacing(10)

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
        badge = QLabel(f'★ NovaShorts v{VERSION}\n글로벌 쇼츠 제작 스튜디오')
        badge.setStyleSheet(
            'background:#152348;border:1px solid #3b5fd1;border-radius:12px;'
            'padding:13px;color:#e9eeff;font-weight:700'
        )
        v.addWidget(badge)
        return f

    def home_page(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(9)

        title = QLabel('영상 소싱')
        title.setObjectName('title')
        sub = QLabel('상품명이나 키워드로 글로벌 플랫폼 영상을 수집합니다.')
        sub.setObjectName('muted')
        v.addWidget(title)
        v.addWidget(sub)

        g = QGroupBox('소싱하기')
        g.setFixedHeight(150)
        q = QGridLayout(g)
        q.setContentsMargins(14, 16, 14, 12)
        q.setHorizontalSpacing(9)
        q.setVerticalSpacing(9)

        self.home_keyword = QLineEdit()
        self.home_keyword.setPlaceholderText('상품명/검색 키워드를 입력하세요  예: 주방 꿀템, 청소, 홈인테리어')
        start = QPushButton('🔎  소싱 시작')
        start.setMinimumWidth(148)
        start.clicked.connect(self.home_to_source)
        q.addWidget(self.home_keyword, 0, 0, 1, 5)
        q.addWidget(start, 0, 5)

        self.home_checks = {}
        for j, p in enumerate(['TikTok', 'Douyin', 'Xiaohongshu', 'Kuaishou', '1688']):
            b = platform_button(p, True)
            self.home_checks[p] = b
            q.addWidget(b, 1, j)
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
        self.card_area.setMinimumHeight(230)
        self.card_host = QWidget()
        self.card_layout = QHBoxLayout(self.card_host)
        self.card_layout.setContentsMargins(0, 0, 0, 4)
        self.card_layout.setSpacing(10)
        self.card_area.setWidget(self.card_host)
        v.addWidget(self.card_area, 1)
        self.render_cards([])
        return w

    def source_page(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(9)
        title = QLabel('글로벌 영상 소싱')
        title.setObjectName('title')
        v.addWidget(title)

        g = QGroupBox('상품 / 검색어')
        g.setFixedHeight(125)
        q = QGridLayout(g)
        self.product = QLineEdit(); self.product.setPlaceholderText('상품명')
        self.product_url = QLineEdit(); self.product_url.setPlaceholderText('쿠팡/상품 URL')
        b1 = QPushButton('AI 검색어 생성'); b1.clicked.connect(self.make_plan)
        b2 = QPushButton('쿠팡 API 검색'); b2.clicked.connect(self.coupang_lookup)
        q.addWidget(self.product, 0, 0, 1, 3); q.addWidget(b1, 0, 3)
        q.addWidget(self.product_url, 1, 0, 1, 3); q.addWidget(b2, 1, 3)
        v.addWidget(g)

        pg = QGroupBox('플랫폼')
        pg.setFixedHeight(104)
        ph = QHBoxLayout(pg)
        ph.setContentsMargins(14, 16, 14, 10)
        ph.setSpacing(9)
        self.pchecks = {}
        for p in PLATFORMS:
            b = platform_button(p, p in self.s.platform_sources)
            self.pchecks[p] = b
            ph.addWidget(b)
        ph.addStretch()
        v.addWidget(pg)

        split = QSplitter(Qt.Horizontal)
        qg = QGroupBox('검색 계획')
        qv = QVBoxLayout(qg)
        self.planbox = QPlainTextEdit()
        qv.addWidget(self.planbox)
        hh = QHBoxLayout()
        bo = QPushButton('검색 페이지 열기'); bo.clicked.connect(self.open_searches)
        bc = QPushButton('Chrome Bridge 자동수집'); bc.clicked.connect(self.bridge_collect)
        hh.addWidget(bo); hh.addWidget(bc)
        qv.addLayout(hh)
        split.addWidget(qg)

        cg = QGroupBox('수집된 영상 목록')
        cv = QVBoxLayout(cg)
        self.candidates = QListWidget()
        self.candidates.itemSelectionChanged.connect(self.candidate_selected)
        cv.addWidget(self.candidates)
        self.cand_url = QLineEdit(); self.cand_url.setPlaceholderText('선택 후보 URL')
        self.cand_text = QLineEdit(); self.cand_text.setPlaceholderText('선택 후보 제목')
        cv.addWidget(self.cand_url); cv.addWidget(self.cand_text)
        rh = QHBoxLayout()
        self.score = QLabel('유사도 -')
        bs = QPushButton('유사도 계산'); bs.clicked.connect(self.score_it)
        bd = QPushButton('선택 영상 다운로드'); bd.clicked.connect(self.download_it)
        rh.addWidget(self.score); rh.addStretch(); rh.addWidget(bs); rh.addWidget(bd)
        cv.addLayout(rh)
        split.addWidget(cg)
        split.setStretchFactor(0, 1); split.setStretchFactor(1, 2)
        v.addWidget(split, 1)
        return w

    def render_cards(self, rows):
        while self.card_layout.count():
            item = self.card_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        if not rows:
            # Four placeholders keep the home view clean without a needless scrollbar.
            for _ in range(4):
                f = QFrame(); f.setObjectName('videoCard'); f.setFixedSize(190, 205)
                vl = QVBoxLayout(f); vl.setContentsMargins(8, 8, 8, 8)
                img = QLabel('영상 후보')
                img.setAlignment(Qt.AlignCenter)
                img.setFixedHeight(112)
                img.setStyleSheet('background:#172542;border-radius:9px;color:#7890b5;font-weight:700')
                vl.addWidget(img)
                txt = QLabel('소싱을 시작하면\n검색 결과가 표시됩니다')
                txt.setObjectName('muted'); txt.setAlignment(Qt.AlignCenter); txt.setWordWrap(True)
                vl.addWidget(txt)
                self.card_layout.addWidget(f)
            self.card_layout.addStretch()
            self.home_count.setText('0')
            return
        for r in rows[:8]:
            card = base.base.CandidateCard(r, r.get('_score', 0))
            card.setFixedHeight(225)
            card.selected.connect(self.card_select)
            self.card_layout.addWidget(card)
            thumb = r.get('thumbnail', '')
            if thumb and thumb.startswith(('http://', 'https://')):
                self.load_card_thumb(card, thumb)
        self.card_layout.addStretch()
        self.home_count.setText(str(len(rows)))


if __name__ == '__main__':
    app = QApplication([])
    app.setApplicationName('NovaShorts')
    app.setFont(QFont('Malgun Gothic', 10))
    win = Nova()
    win.show()
    app.exec()
