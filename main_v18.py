from __future__ import annotations

import json
import threading
import time
import webbrowser
from pathlib import Path

from PySide6.QtCore import Qt, QObject, Signal, QUrl, QSizeF
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest
from PySide6.QtWidgets import *
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QGraphicsVideoItem

from engine import *
from bridge import start_bridge, TASKS, RESULTS
from features import make_thumbnail, auto_cut_vertical

VERSION = '1.8'

CSS = '''
QWidget{background:#09101e;color:#eef3ff;font-family:"Malgun Gothic";font-size:13px}
QMainWindow{background:#080d18}
QFrame#sidebar{background:#10192b;border-right:1px solid #263450}
QFrame#topbar{background:#0d1526;border-bottom:1px solid #263450}
QFrame#hero{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #2851db,stop:.54 #6e39ea,stop:1 #ac38ee);border-radius:16px}
QFrame#card,QFrame#videoCard,QGroupBox{background:#111b30;border:1px solid #283957;border-radius:14px}
QGroupBox{margin-top:11px;padding:13px;font-weight:700}
QGroupBox::title{subcontrol-origin:margin;left:12px;padding:0 7px;color:#e4ebff}
QLineEdit,QPlainTextEdit,QComboBox,QSpinBox,QListWidget{background:#0c1527;border:1px solid #334765;border-radius:9px;padding:8px;color:#f5f7ff;selection-background-color:#315cff}
QPushButton{background:#315cff;border:0;border-radius:9px;padding:9px 14px;color:white;font-weight:700;min-height:26px}
QPushButton:hover{background:#4e72ff}
QPushButton[secondary="true"]{background:#17243c;border:1px solid #334765}
QPushButton[danger="true"]{background:#d83d57}
QPushButton[nav="true"]{text-align:left;background:transparent;border:0;padding:12px 14px;font-size:14px}
QPushButton[nav="true"]:checked{background:#294fc4;border-radius:10px}
QPushButton[chip="true"]{background:#15223a;border:1px solid #314664;border-radius:10px;padding:7px 13px;color:#cfd9ed}
QPushButton[chip="true"]:checked{background:#315cff;border:1px solid #5a78ff;color:white}
QPushButton[switch="true"]{background:#19263c;border:1px solid #41516d;border-radius:12px;padding:0;min-width:44px;max-width:44px;min-height:24px;max-height:24px;color:#91a5c8}
QPushButton[switch="true"]:checked{background:#5c52ff;border:1px solid #8078ff;color:white}
QProgressBar{background:#111a2d;border:1px solid #30425f;border-radius:7px;text-align:center;height:12px}
QProgressBar::chunk{background:#3d63ff;border-radius:6px}
QScrollArea{border:0;background:transparent}
QTableWidget{background:#10192b;border:1px solid #283957;border-radius:10px;gridline-color:#22304b}
QHeaderView::section{background:#17243a;color:#dce5f9;padding:8px;border:0}
QLabel#muted{color:#91a5c8;background:transparent}
QLabel#title{font-size:26px;font-weight:900;background:transparent}
QLabel#section{font-size:17px;font-weight:800;background:transparent}
QLabel#brand{font-size:22px;font-weight:900;background:transparent}
QLabel#heroTitle{font-size:31px;font-weight:900;background:transparent}
QLabel#heroSub{font-size:14px;background:transparent}
'''


class Switch(QPushButton):
    def __init__(self, checked=False, parent=None):
        super().__init__('', parent)
        self.setProperty('switch', True)
        self.setCheckable(True)
        self.setChecked(checked)
        self.toggled.connect(self._paint_text)
        self._paint_text(checked)

    def _paint_text(self, on):
        self.setText('●' if on else '○')


class VideoView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene_obj = QGraphicsScene(self)
        self.video_item = QGraphicsVideoItem()
        self.scene_obj.addItem(self.video_item)
        self.setScene(self.scene_obj)
        self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setStyleSheet('background:#03060b;border:1px solid #23334f;border-radius:12px')

    def resizeEvent(self, event):
        super().resizeEvent(event)
        s = self.viewport().size()
        self.video_item.setSize(QSizeF(max(1, s.width()), max(1, s.height())))
        self.scene_obj.setSceneRect(0, 0, s.width(), s.height())


class CandidateCard(QFrame):
    selected = Signal(dict)

    def __init__(self, row, score, parent=None):
        super().__init__(parent)
        self.row = row
        self.setObjectName('videoCard')
        self.setFixedWidth(182)
        v = QVBoxLayout(self)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(7)
        self.image = QLabel('▶\n' + (row.get('platform') or 'VIDEO'))
        self.image.setAlignment(Qt.AlignCenter)
        self.image.setFixedSize(164, 104)
        self.image.setStyleSheet('background:#172542;border-radius:9px;font-size:16px;font-weight:800;color:#dbe5ff')
        v.addWidget(self.image)
        title = (row.get('title') or row.get('text') or '영상 후보').strip()
        tl = QLabel(title[:48] if title else '제목 없음')
        tl.setWordWrap(True)
        tl.setFixedHeight(44)
        v.addWidget(tl)
        meta = QLabel(f"{row.get('platform','')} · 유사도 {score}%")
        meta.setObjectName('muted')
        v.addWidget(meta)
        b = QPushButton('선택')
        b.clicked.connect(lambda: self.selected.emit(self.row))
        v.addWidget(b)

    def set_thumb(self, pm):
        if pm and not pm.isNull():
            self.image.setText('')
            self.image.setPixmap(pm.scaled(self.image.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))


class Bus(QObject):
    log = Signal(str)
    err = Signal(str)
    plan = Signal(dict)
    candidates = Signal(list)
    downloaded = Signal(str)
    ocr = Signal(list)
    tts = Signal(str)
    rendered = Signal(str)
    thumb = Signal(str)
    job_done = Signal(int, bool, str)


class Nova(QMainWindow):
    def __init__(self):
        super().__init__()
        self.s = load_settings()
        self.bridge = start_bridge()
        self.bus = Bus()
        self.query_plan = {}
        self.current_video = ''
        self.current_tts = ''
        self.candidate_rows = []
        self.job_counter = 0
        self.jobs = {}
        self.auto_collect_after_plan = False
        self.stop_requested = False
        self.net = QNetworkAccessManager(self)
        self.audio = QAudioOutput(self)
        self.player = QMediaPlayer(self)
        self.player.setAudioOutput(self.audio)
        self.build()
        self.bind()
        self.refresh_diag()
        self.say(f'NovaShorts v{VERSION} 시작')

    def bind(self):
        self.bus.log.connect(self.say)
        self.bus.err.connect(lambda x: QMessageBox.critical(self, 'NovaShorts', x))
        self.bus.plan.connect(self.on_plan)
        self.bus.candidates.connect(self.on_candidates)
        self.bus.downloaded.connect(self.on_downloaded)
        self.bus.ocr.connect(self.on_ocr)
        self.bus.tts.connect(self.on_tts)
        self.bus.rendered.connect(self.on_rendered)
        self.bus.thumb.connect(self.show_thumb)
        self.bus.job_done.connect(self.finish_job)

    def build(self):
        self.setWindowTitle(f'NovaShorts Studio v{VERSION}')
        self.resize(1600, 930)
        self.setMinimumSize(1280, 760)
        self.setStyleSheet(CSS)
        root = QWidget()
        self.setCentralWidget(root)
        main = QHBoxLayout(root)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)
        main.addWidget(self.sidebar())
        body = QWidget()
        bv = QVBoxLayout(body)
        bv.setContentsMargins(0, 0, 0, 0)
        bv.setSpacing(0)
        bv.addWidget(self.topbar())
        content = QWidget()
        ch = QHBoxLayout(content)
        ch.setContentsMargins(16, 12, 16, 8)
        ch.setSpacing(14)
        self.pages = QStackedWidget()
        for page in [self.home_page(), self.source_page(), self.edit_page(), self.voice_page(), self.thumb_page(), self.publish_page(), self.link_page(), self.settings_page()]:
            self.pages.addWidget(page)
        ch.addWidget(self.pages, 1)
        ch.addWidget(self.right_panel())
        bv.addWidget(content, 1)
        bv.addWidget(self.queue_panel())
        bv.addWidget(self.statusbar_panel())
        main.addWidget(body, 1)

    def sidebar(self):
        f = QFrame(); f.setObjectName('sidebar'); f.setFixedWidth(248)
        v = QVBoxLayout(f); v.setContentsMargins(12, 16, 12, 14); v.setSpacing(7)
        brand = QLabel(f'✦  NovaShorts  v{VERSION}'); brand.setObjectName('brand'); brand.setMinimumWidth(215); v.addWidget(brand)
        sub = QLabel('Global Shorts Production'); sub.setObjectName('muted'); v.addWidget(sub); v.addSpacing(12)
        self.nav = []
        items = [('홈','⌂'),('소싱','◎'),('편집','✣'),('AI 음성','◉'),('썸네일','▣'),('업로드','⇧'),('링크 관리','↗'),('설정','⚙')]
        for i, (txt, ico) in enumerate(items):
            b = QPushButton(f'{ico}   {txt}'); b.setProperty('nav', True); b.setCheckable(True)
            b.clicked.connect(lambda _, n=i: self.go(n)); self.nav.append(b); v.addWidget(b)
        self.nav[0].setChecked(True)
        v.addStretch()
        badge = QLabel(f'★ NovaShorts v{VERSION}\n글로벌 쇼츠 제작 스튜디오')
        badge.setStyleSheet('background:#182753;border:1px solid #315cff;border-radius:12px;padding:14px;font-weight:700')
        v.addWidget(badge)
        return f

    def topbar(self):
        f = QFrame(); f.setObjectName('topbar'); f.setFixedHeight(72)
        h = QHBoxLayout(f); h.setContentsMargins(20, 10, 18, 10)
        title = QLabel('NovaShorts'); title.setObjectName('brand'); title.setMinimumWidth(138); h.addWidget(title)
        sub = QLabel('상품 → 글로벌 소싱 → AI 편집 → 자동 게시'); sub.setObjectName('muted'); sub.setMinimumWidth(330); h.addWidget(sub)
        h.addStretch()
        history = QPushButton('▣ 작업 기록'); history.setProperty('secondary', True); history.clicked.connect(lambda: self.queue.setFocus()); h.addWidget(history)
        b = QPushButton('⚙ 설정'); b.setProperty('secondary', True); b.clicked.connect(lambda: self.go(7)); h.addWidget(b)
        return f

    def hero(self):
        f = QFrame(); f.setObjectName('hero'); f.setFixedHeight(205)
        h = QHBoxLayout(f); h.setContentsMargins(30, 22, 30, 22)
        l = QVBoxLayout()
        t = QLabel('세상의 핫한 영상을\n나만의 쇼츠로 🚀'); t.setObjectName('heroTitle'); l.addWidget(t)
        s = QLabel('글로벌 영상 소싱부터 OCR · TTS · 자동 편집 · 업로드까지'); s.setObjectName('heroSub'); l.addWidget(s)
        h.addLayout(l); h.addStretch()
        globe = QLabel('◉\nTikTok  小红书\nDouyin  Kuaishou\n1688'); globe.setAlignment(Qt.AlignCenter)
        globe.setStyleSheet('font-size:20px;font-weight:800;background:rgba(20,25,60,.38);border-radius:58px;padding:20px'); globe.setFixedSize(245, 165)
        h.addWidget(globe)
        return f

    def home_page(self):
        w = QWidget(); v = QVBoxLayout(w); v.setContentsMargins(0,0,0,0); v.setSpacing(10)
        v.addWidget(self.hero())
        g = QGroupBox('소싱하기'); g.setFixedHeight(128); q = QGridLayout(g)
        self.home_keyword = QLineEdit(); self.home_keyword.setPlaceholderText('상품명/검색 키워드를 입력하세요 (예: 주방 꿀템, 청소, 홈인테리어)')
        b = QPushButton('🔎 소싱 시작'); b.clicked.connect(self.home_to_source)
        q.addWidget(self.home_keyword, 0, 0, 1, 5); q.addWidget(b, 0, 5)
        self.home_checks = {}
        for j, p in enumerate(['TikTok','Douyin','Xiaohongshu','Kuaishou','1688']):
            cb = QPushButton(p); cb.setProperty('chip', True); cb.setCheckable(True); cb.setChecked(True); self.home_checks[p] = cb; q.addWidget(cb, 1, j)
        v.addWidget(g)
        row = QHBoxLayout(); label = QLabel('수집된 영상 목록'); label.setObjectName('section'); row.addWidget(label)
        self.home_count = QLabel('0'); self.home_count.setObjectName('muted'); row.addWidget(self.home_count); row.addStretch()
        self.home_edit_btn = QPushButton('선택 영상으로 편집하기 →'); self.home_edit_btn.clicked.connect(self.home_edit_selected); row.addWidget(self.home_edit_btn); v.addLayout(row)
        self.card_area = QScrollArea(); self.card_area.setWidgetResizable(True); self.card_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded); self.card_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.card_host = QWidget(); self.card_layout = QHBoxLayout(self.card_host); self.card_layout.setContentsMargins(0,0,0,0); self.card_layout.setSpacing(10)
        self.card_area.setWidget(self.card_host); v.addWidget(self.card_area, 1)
        self.render_cards([])
        return w

    def source_page(self):
        w = QWidget(); v = QVBoxLayout(w); v.setContentsMargins(0,0,0,0); v.setSpacing(9)
        title = QLabel('글로벌 영상 소싱'); title.setObjectName('title'); v.addWidget(title)
        g = QGroupBox('상품 / 검색어'); g.setFixedHeight(125); q = QGridLayout(g)
        self.product = QLineEdit(); self.product.setPlaceholderText('상품명')
        self.product_url = QLineEdit(); self.product_url.setPlaceholderText('쿠팡/상품 URL')
        b1 = QPushButton('AI 검색어 생성'); b1.clicked.connect(self.make_plan)
        b2 = QPushButton('쿠팡 API 검색'); b2.clicked.connect(self.coupang_lookup)
        q.addWidget(self.product,0,0,1,3); q.addWidget(b1,0,3); q.addWidget(self.product_url,1,0,1,3); q.addWidget(b2,1,3); v.addWidget(g)
        pg = QGroupBox('플랫폼'); pg.setFixedHeight(78); ph = QHBoxLayout(pg); self.pchecks = {}
        for p in PLATFORMS:
            cb = QPushButton(p); cb.setProperty('chip', True); cb.setCheckable(True); cb.setChecked(p in self.s.platform_sources); self.pchecks[p] = cb; ph.addWidget(cb)
        ph.addStretch(); v.addWidget(pg)
        split = QSplitter(Qt.Horizontal)
        qg = QGroupBox('검색 계획'); qv = QVBoxLayout(qg); self.planbox = QPlainTextEdit(); qv.addWidget(self.planbox)
        hh = QHBoxLayout(); bo = QPushButton('검색 페이지 열기'); bo.clicked.connect(self.open_searches); bc = QPushButton('Chrome Bridge 자동수집'); bc.clicked.connect(self.bridge_collect); hh.addWidget(bo); hh.addWidget(bc); qv.addLayout(hh); split.addWidget(qg)
        cg = QGroupBox('수집된 영상 목록'); cv = QVBoxLayout(cg); self.candidates = QListWidget(); self.candidates.itemSelectionChanged.connect(self.candidate_selected); cv.addWidget(self.candidates)
        self.cand_url = QLineEdit(); self.cand_url.setPlaceholderText('선택 후보 URL'); self.cand_text = QLineEdit(); self.cand_text.setPlaceholderText('선택 후보 제목'); cv.addWidget(self.cand_url); cv.addWidget(self.cand_text)
        rh = QHBoxLayout(); self.score = QLabel('유사도 -'); bs = QPushButton('유사도 계산'); bs.clicked.connect(self.score_it); bd = QPushButton('선택 영상 다운로드'); bd.clicked.connect(self.download_it); rh.addWidget(self.score); rh.addStretch(); rh.addWidget(bs); rh.addWidget(bd); cv.addLayout(rh)
        split.addWidget(cg); split.setStretchFactor(0, 1); split.setStretchFactor(1, 2); v.addWidget(split, 1)
        return w

    def edit_page(self):
        w = QWidget(); v = QVBoxLayout(w); v.setContentsMargins(0,0,0,0); v.setSpacing(9)
        t = QLabel('AI 영상 편집'); t.setObjectName('title'); v.addWidget(t)
        src = QGroupBox('소스 영상'); src.setFixedHeight(82); h = QHBoxLayout(src); self.video = QLineEdit(); bf = QPushButton('파일 찾기'); bf.clicked.connect(self.choose_video); h.addWidget(self.video,1); h.addWidget(bf); v.addWidget(src)
        sp = QSplitter(Qt.Horizontal)
        og = QGroupBox('OCR / 자막 제거'); ov = QVBoxLayout(og); self.ocrbox = QPlainTextEdit(); ov.addWidget(self.ocrbox)
        r = QHBoxLayout(); bs = QPushButton('OCR 스캔'); bs.clicked.connect(self.ocr_scan); bc = QPushButton('하단 자막 제거'); bc.clicked.connect(self.clean_sub); r.addWidget(bs); r.addWidget(bc); ov.addLayout(r); sp.addWidget(og)
        ag = QGroupBox('자동 컷 / 렌더'); av = QVBoxLayout(ag); self.target_sec = QSpinBox(); self.target_sec.setRange(4,60); self.target_sec.setValue(18); self.clip_sec = QSpinBox(); self.clip_sec.setRange(1,5); self.clip_sec.setValue(3)
        self.out = QLineEdit(str(Path(self.s.output_folder)/'final_short.mp4')); ba = QPushButton('자동 컷 편집'); ba.clicked.connect(self.auto_cut); br = QPushButton('1080×1920 최종 렌더'); br.clicked.connect(self.render)
        av.addWidget(QLabel('목표 길이(초)')); av.addWidget(self.target_sec); av.addWidget(QLabel('컷 길이(초)')); av.addWidget(self.clip_sec); av.addWidget(self.out); av.addWidget(ba); av.addWidget(br); av.addStretch(); sp.addWidget(ag)
        v.addWidget(sp,1); return w

    def voice_page(self):
        w = QWidget(); v = QVBoxLayout(w); v.setContentsMargins(0,0,0,0); t = QLabel('AI 음성 · TTS'); t.setObjectName('title'); v.addWidget(t)
        g = QGroupBox('대본 / 음성'); q = QVBoxLayout(g); self.script = QPlainTextEdit(); self.script.setPlaceholderText('한국어 대본을 입력하세요')
        self.voice = QComboBox(); self.voice.addItems(['ko-KR-SunHiNeural','ko-KR-InJoonNeural','ko-KR-HyunsuNeural']); self.voice.setCurrentText(self.s.tts_voice)
        b = QPushButton('TTS 생성'); b.clicked.connect(self.make_tts); q.addWidget(self.script); q.addWidget(self.voice); q.addWidget(b); v.addWidget(g,1); return w

    def thumb_page(self):
        w = QWidget(); v = QVBoxLayout(w); v.setContentsMargins(0,0,0,0); t = QLabel('썸네일'); t.setObjectName('title'); v.addWidget(t)
        g = QGroupBox('영상 프레임 + 문구'); q = QGridLayout(g); self.thumb_video = QLineEdit(); self.thumb_text = QLineEdit(); self.thumb_text.setPlaceholderText('썸네일 문구'); self.thumb_out = QLineEdit(str(Path(self.s.output_folder)/'thumbnail.jpg')); b = QPushButton('썸네일 만들기'); b.clicked.connect(self.create_thumb)
        q.addWidget(QLabel('영상'),0,0); q.addWidget(self.thumb_video,0,1,1,3); q.addWidget(QLabel('문구'),1,0); q.addWidget(self.thumb_text,1,1,1,3); q.addWidget(QLabel('저장'),2,0); q.addWidget(self.thumb_out,2,1,1,3); q.addWidget(b,3,3); v.addWidget(g)
        self.thumb_preview = QLabel('썸네일 미리보기'); self.thumb_preview.setAlignment(Qt.AlignCenter); self.thumb_preview.setStyleSheet('background:#050910;border:1px solid #283957;border-radius:14px'); v.addWidget(self.thumb_preview,1); return w

    def publish_page(self):
        w = QWidget(); v = QVBoxLayout(w); v.setContentsMargins(0,0,0,0); t = QLabel('업로드'); t.setObjectName('title'); v.addWidget(t)
        g = QGroupBox('YouTube'); q = QGridLayout(g); self.pubvideo = QLineEdit(); self.ytitle = QLineEdit(); self.ydesc = QPlainTextEdit(); self.ytags = QLineEdit(); self.privacy = QComboBox(); self.privacy.addItems(['private','unlisted','public']); b = QPushButton('YouTube 업로드'); b.clicked.connect(self.upload_youtube)
        q.addWidget(QLabel('영상'),0,0); q.addWidget(self.pubvideo,0,1,1,3); q.addWidget(QLabel('제목'),1,0); q.addWidget(self.ytitle,1,1,1,3); q.addWidget(QLabel('설명'),2,0); q.addWidget(self.ydesc,2,1,1,3); q.addWidget(QLabel('태그'),3,0); q.addWidget(self.ytags,3,1,1,2); q.addWidget(self.privacy,3,3); q.addWidget(b,4,3); v.addWidget(g,1); return w

    def link_page(self):
        w = QWidget(); v = QVBoxLayout(w); v.setContentsMargins(0,0,0,0); t = QLabel('링크 관리'); t.setObjectName('title'); v.addWidget(t)
        g = QGroupBox('Lnk.Bio / X'); q = QGridLayout(g); self.linktitle = QLineEdit(); self.linktitle.setPlaceholderText('링크 제목'); self.linkurl = QLineEdit(); self.linkurl.setPlaceholderText('상품 링크'); bl = QPushButton('Lnk.Bio 추가'); bl.clicked.connect(self.add_lnk); self.xtext = QLineEdit(); self.xtext.setPlaceholderText('X 게시문'); bx = QPushButton('X 작성창 열기'); bx.clicked.connect(lambda: open_x(self.xtext.text()))
        q.addWidget(self.linktitle,0,0,1,3); q.addWidget(self.linkurl,1,0,1,3); q.addWidget(bl,2,2); q.addWidget(self.xtext,3,0,1,3); q.addWidget(bx,4,2); v.addWidget(g); v.addStretch(); return w

    def settings_page(self):
        w = QWidget(); v = QVBoxLayout(w); v.setContentsMargins(0,0,0,0); t = QLabel('설정'); t.setObjectName('title'); v.addWidget(t)
        g = QGroupBox('API / 연동 / 출력'); q = QGridLayout(g)
        self.setout = QLineEdit(self.s.output_folder); self.gkey = QLineEdit(self.s.gemini_api_key); self.gkey.setEchoMode(QLineEdit.Password); self.cakey = QLineEdit(self.s.coupang_access_key); self.cakey.setEchoMode(QLineEdit.Password); self.cskey = QLineEdit(self.s.coupang_secret_key); self.cskey.setEchoMode(QLineEdit.Password); self.sim = QSpinBox(); self.sim.setRange(0,100); self.sim.setValue(self.s.min_similarity); self.ysecret = QLineEdit(self.s.youtube_client_secret_file); self.lid = QLineEdit(self.s.lnkbio_client_id); self.lsec = QLineEdit(self.s.lnkbio_client_secret); self.lsec.setEchoMode(QLineEdit.Password)
        rows = [('출력 폴더',self.setout),('Gemini API Key',self.gkey),('Coupang Access Key',self.cakey),('Coupang Secret Key',self.cskey),('최소 유사도',self.sim),('YouTube client_secret.json',self.ysecret),('Lnk.Bio Client ID',self.lid),('Lnk.Bio Client Secret',self.lsec)]
        for i,(n,x) in enumerate(rows): q.addWidget(QLabel(n),i,0); q.addWidget(x,i,1,1,3)
        self.skip = QCheckBox('저유사도 자동 제외'); self.skip.setChecked(self.s.auto_skip_low_similarity); self.gplan = QCheckBox('Gemini 검색계획'); self.gplan.setChecked(self.s.use_gemini_query_planning); q.addWidget(self.skip,len(rows),1); q.addWidget(self.gplan,len(rows),2)
        bs = QPushButton('설정 저장'); bs.clicked.connect(self.save); q.addWidget(bs,len(rows)+1,3); v.addWidget(g)
        dg = QGroupBox('런타임 진단'); dv = QVBoxLayout(dg); self.diagbox = QPlainTextEdit(); self.diagbox.setReadOnly(True); bd = QPushButton('다시 진단'); bd.clicked.connect(self.refresh_diag); dv.addWidget(self.diagbox); dv.addWidget(bd); v.addWidget(dg,1); return w

    def right_panel(self):
        w = QWidget(); w.setFixedWidth(332); v = QVBoxLayout(w); v.setContentsMargins(0,0,0,0); v.setSpacing(10)
        g = QGroupBox('빠른 설정'); g.setFixedHeight(255); q = QGridLayout(g); q.setVerticalSpacing(8)
        self.quick_ai = QComboBox(); self.quick_ai.addItems(['Gemini 2.5 Flash','규칙 기반']); self.quick_ai.setCurrentIndex(0 if self.s.use_gemini_query_planning else 1); self.quick_ai.currentIndexChanged.connect(self.quick_save)
        self.quick_voice = QComboBox(); self.quick_voice.addItems(['Edge TTS - SunHi','Edge TTS - InJoon','Edge TTS - Hyunsu']); self.quick_voice.currentIndexChanged.connect(self.quick_voice_changed)
        self.quick_res = QComboBox(); self.quick_res.addItems(['1080 × 1920 (세로)'])
        self.quick_ocr = Switch(True); self.quick_cut = Switch(True); self.quick_wm = Switch(self.s.watermark_enabled); self.quick_wm.toggled.connect(self.quick_save)
        rows = [('AI 모델',self.quick_ai),('TTS 음성',self.quick_voice),('영상 해상도',self.quick_res)]
        for i,(name,widget) in enumerate(rows): q.addWidget(QLabel(name),i,0); q.addWidget(widget,i,1)
        for i,(name,widget) in enumerate([('자막 제거(OCR)',self.quick_ocr),('자동 컷 편집',self.quick_cut),('워터마크 추가',self.quick_wm)], start=3): q.addWidget(QLabel(name),i,0); q.addWidget(widget,i,1,alignment=Qt.AlignRight)
        v.addWidget(g)
        pg = QGroupBox('미리보기'); pv = QVBoxLayout(pg); pg.setMaximumHeight(355)
        self.video_view = VideoView(); self.video_view.setMinimumHeight(230); self.player.setVideoOutput(self.video_view.video_item); pv.addWidget(self.video_view,1)
        self.preview_label = QLabel('선택/완성 영상을 불러오세요'); self.preview_label.setObjectName('muted'); self.preview_label.setAlignment(Qt.AlignCenter); pv.addWidget(self.preview_label)
        ctrl = QHBoxLayout(); self.play_btn = QPushButton('▶ 재생'); self.play_btn.clicked.connect(self.toggle_play); op = QPushButton('파일 열기'); op.setProperty('secondary',True); op.clicked.connect(self.preview_pick); ctrl.addWidget(self.play_btn); ctrl.addWidget(op); pv.addLayout(ctrl)
        v.addWidget(pg); v.addStretch(); return w

    def queue_panel(self):
        g = QGroupBox('작업 대기열'); g.setFixedHeight(178); v = QVBoxLayout(g); v.setSpacing(6)
        top = QHBoxLayout(); top.addStretch(); start = QPushButton('▶ 모두 시작'); start.clicked.connect(self.resume_jobs); stop = QPushButton('■ 모두 중지'); stop.setProperty('danger',True); stop.clicked.connect(self.stop_jobs); clear = QPushButton('목록 비우기'); clear.setProperty('secondary',True); clear.clicked.connect(self.clear_queue); top.addWidget(start); top.addWidget(stop); top.addWidget(clear); v.addLayout(top)
        self.queue = QTableWidget(0,5); self.queue.setHorizontalHeaderLabels(['작업명','상태','진행률','시작 시간','작업']); self.queue.horizontalHeader().setSectionResizeMode(0,QHeaderView.Stretch)
        for c in [1,2,3,4]: self.queue.horizontalHeader().setSectionResizeMode(c,QHeaderView.ResizeToContents)
        self.queue.verticalHeader().setVisible(False); self.queue.setMinimumHeight(92); v.addWidget(self.queue); return g

    def statusbar_panel(self):
        f = QFrame(); f.setFixedHeight(34); h = QHBoxLayout(f); h.setContentsMargins(18,3,18,5)
        self.status = QLabel('준비'); self.status.setStyleSheet('color:#65e28a'); h.addWidget(self.status)
        self.progress = QProgressBar(); self.progress.setRange(0,100); self.progress.setValue(0); self.progress.setFixedWidth(245); h.addWidget(self.progress); h.addStretch()
        self.diag = QLabel(); self.diag.setObjectName('muted'); h.addWidget(self.diag); return f

    def go(self, n):
        self.pages.setCurrentIndex(n)
        for i,b in enumerate(self.nav): b.setChecked(i == n)

    def selected(self):
        return [p for p,c in self.pchecks.items() if c.isChecked()]

    def say(self, x):
        log(x); self.status.setText(x[:120])

    def add_job(self, label):
        self.job_counter += 1; jid = self.job_counter; row = self.queue.rowCount(); self.queue.insertRow(row); now = time.strftime('%H:%M:%S')
        vals = [label,'실행 중','0%',now,'●']
        for c,v in enumerate(vals): self.queue.setItem(row,c,QTableWidgetItem(v))
        self.jobs[jid] = row; return jid

    def finish_job(self, jid, ok, msg):
        row = self.jobs.get(jid)
        if row is not None and row < self.queue.rowCount():
            self.queue.item(row,1).setText('완료' if ok else '실패'); self.queue.item(row,2).setText('100%' if ok else '-'); self.queue.item(row,4).setText('✓' if ok else '!')
        self.progress.setRange(0,100); self.progress.setValue(100 if ok else 0); self.say(msg)

    def work(self, label, fn):
        if self.stop_requested:
            self.say('작업이 중지 상태입니다. 모두 시작을 눌러주세요.'); return
        jid = self.add_job(label); self.progress.setRange(0,0); self.status.setText(label)
        def go():
            try:
                fn(); self.bus.job_done.emit(jid,True,label+' 완료')
            except Exception as e:
                self.bus.err.emit(label+'\n'+str(e)); self.bus.job_done.emit(jid,False,'오류: '+str(e))
        threading.Thread(target=go,daemon=True).start()

    def stop_jobs(self):
        self.stop_requested = True; self.say('새 작업 시작을 중지했습니다. 현재 실행 중인 외부 프로세스는 완료 후 정지됩니다.')

    def resume_jobs(self):
        self.stop_requested = False; self.say('작업 시작 가능')

    def clear_queue(self):
        self.queue.setRowCount(0); self.jobs.clear()

    def home_to_source(self):
        text = self.home_keyword.text().strip()
        if not text: return
        self.go(1); self.product.setText(text)
        for p,cb in self.pchecks.items():
            if p in self.home_checks: cb.setChecked(self.home_checks[p].isChecked())
        self.auto_collect_after_plan = True; self.make_plan()

    def make_plan(self):
        title = self.product.text().strip()
        if not title: return
        def f(): self.bus.plan.emit(gemini_query_plan(title,self.s.gemini_api_key) if self.s.use_gemini_query_planning else rule_query_plan(title))
        self.work('AI 검색어 생성', f)

    def on_plan(self, p):
        self.query_plan = p; self.planbox.setPlainText(json.dumps(p,ensure_ascii=False,indent=2)); self.say('검색어 계획 완료')
        if self.auto_collect_after_plan:
            self.auto_collect_after_plan = False; self.bridge_collect()

    def coupang_lookup(self):
        kw = self.product.text().strip()
        if not kw: return
        def f():
            d = coupang_search(kw,self.s.coupang_access_key,self.s.coupang_secret_key); items = d.get('data',{}).get('productData',[]) or d.get('data',[])
            self.bus.candidates.emit([{'url':x.get('productUrl',''),'title':x.get('productName',''),'platform':'Coupang','thumbnail':x.get('productImage','')} for x in items])
        self.work('쿠팡 API 검색', f)

    def open_searches(self):
        if not self.query_plan: return
        for p in self.selected():
            kw = (self.query_plan.get(p) or [''])[0]
            if kw: webbrowser.open(direct_search_url(p,kw))

    def bridge_collect(self):
        if not self.query_plan: return
        count = 0
        for p in self.selected():
            for kw in (self.query_plan.get(p) or [])[:2]:
                TASKS.put({'type':'collect_links','platform':p,'url':direct_search_url(p,kw),'keyword':kw}); count += 1
        if count == 0: return
        self.say(f'Chrome Bridge 작업 {count}개 전송')
        def wait():
            end = time.time()+45; rows = []
            while time.time() < end and not self.stop_requested:
                try:
                    r = RESULTS.get(timeout=1); rows.extend(r.get('items',[]))
                except Exception: pass
            self.bus.candidates.emit(rows)
        self.work('플랫폼 후보 수집', wait)

    def on_candidates(self, rows):
        seen = set(); clean = []
        for r in rows:
            u = r.get('url','')
            if not u or u in seen or r.get('error'): continue
            seen.add(u); title = (r.get('title') or r.get('text') or '').strip(); score = relevance(self.product.text(),title) if self.product.text().strip() and title else 0
            if self.s.auto_skip_low_similarity and title and score < self.s.min_similarity: continue
            r = dict(r); r['_score'] = score; clean.append(r)
        self.candidate_rows = clean; self.candidates.clear()
        for r in clean:
            t = r.get('title','') or r.get('text',''); it = QListWidgetItem(f"[{r.get('platform','')}] {t[:76]}\n유사도 {r.get('_score',0)}%  {r.get('url','')}"); it.setData(Qt.UserRole,r); self.candidates.addItem(it)
        self.render_cards(clean); self.say(f'후보 {len(clean)}개')

    def render_cards(self, rows):
        while self.card_layout.count():
            item = self.card_layout.takeAt(0); w = item.widget()
            if w: w.deleteLater()
        if not rows:
            for i in range(5):
                f = QFrame(); f.setObjectName('videoCard'); f.setFixedWidth(176); vl = QVBoxLayout(f); img = QLabel('검색 결과'); img.setAlignment(Qt.AlignCenter); img.setFixedHeight(105); img.setStyleSheet('background:#172542;border-radius:9px;color:#7086aa'); vl.addWidget(img); txt = QLabel('소싱을 시작하면\n영상 후보가 표시됩니다'); txt.setObjectName('muted'); txt.setAlignment(Qt.AlignCenter); vl.addWidget(txt); self.card_layout.addWidget(f)
            self.card_layout.addStretch(); self.home_count.setText('0'); return
        for r in rows[:8]:
            card = CandidateCard(r, r.get('_score',0)); card.selected.connect(self.card_select); self.card_layout.addWidget(card)
            thumb = r.get('thumbnail','')
            if thumb and thumb.startswith(('http://','https://')): self.load_card_thumb(card, thumb)
        self.card_layout.addStretch(); self.home_count.setText(str(len(rows)))

    def load_card_thumb(self, card, url):
        reply = self.net.get(QNetworkRequest(QUrl(url)))
        def done():
            data = reply.readAll(); pm = QPixmap(); pm.loadFromData(bytes(data)); card.set_thumb(pm); reply.deleteLater()
        reply.finished.connect(done)

    def card_select(self, r):
        self.cand_url.setText(r.get('url','')); self.cand_text.setText(r.get('title','') or r.get('text','')); self.score.setText(f"유사도 {r.get('_score',0)}%"); self.go(1)

    def home_edit_selected(self):
        if self.cand_url.text().strip():
            self.download_it(); self.go(2)
        else:
            self.go(2)

    def candidate_selected(self):
        it = self.candidates.currentItem()
        if not it: return
        r = it.data(Qt.UserRole) or {}; self.cand_url.setText(r.get('url','')); self.cand_text.setText(r.get('title','') or r.get('text','')); self.score.setText(f"유사도 {r.get('_score',0)}%")

    def score_it(self):
        s = relevance(self.product.text(),self.cand_text.text()); self.score.setText(f'유사도 {s}%'); self.score.setStyleSheet('color:#65e28a;font-weight:700' if s>=self.s.min_similarity else 'color:#ff657a;font-weight:700')

    def download_it(self):
        u = self.cand_url.text().strip()
        if not u: return
        def f(): self.bus.downloaded.emit(str(download_video(u,self.s.output_folder,lambda x:self.bus.log.emit(x))))
        self.work('영상 다운로드', f)

    def on_downloaded(self, p):
        self.current_video = p; self.video.setText(p); self.pubvideo.setText(p); self.thumb_video.setText(p); self.load_preview(p); self.say('다운로드 완료: '+p)

    def choose_video(self):
        p,_ = QFileDialog.getOpenFileName(self,'영상 선택','', 'Video (*.mp4 *.mov *.mkv *.webm)')
        if p: self.video.setText(p); self.current_video=p; self.pubvideo.setText(p); self.thumb_video.setText(p); self.load_preview(p)

    def preview_pick(self):
        p,_ = QFileDialog.getOpenFileName(self,'미리보기 영상','', 'Video (*.mp4 *.mov *.mkv *.webm)')
        if p: self.load_preview(p)

    def load_preview(self, p):
        if not p or not Path(p).exists(): return
        self.player.setSource(QUrl.fromLocalFile(str(Path(p).resolve()))); self.preview_label.setText(Path(p).name); self.player.pause(); self.play_btn.setText('▶ 재생')

    def toggle_play(self):
        if self.player.playbackState() == QMediaPlayer.PlayingState: self.player.pause(); self.play_btn.setText('▶ 재생')
        else: self.player.play(); self.play_btn.setText('Ⅱ 일시정지')

    def ocr_scan(self):
        p = self.video.text().strip()
        if not p: return
        workdir = str(Path(self.s.output_folder)/'ocr_work'); self.work('OCR 스캔',lambda:self.bus.ocr.emit(subtitle_scan(p,workdir,lambda x:self.bus.log.emit(x))))

    def on_ocr(self, rows): self.ocrbox.setPlainText(json.dumps(rows,ensure_ascii=False,indent=2)); self.say(f'OCR {len(rows)}건')

    def clean_sub(self):
        p = self.video.text().strip()
        if not p: return
        out = str(Path(self.s.output_folder)/'subtitle_clean.mp4')
        def f(): cleanup_bottom_subtitles(p,out); self.bus.rendered.emit(out)
        self.work('자막 제거', f)

    def make_tts(self):
        text = self.script.toPlainText().strip()
        if not text: return
        out = str(Path(self.s.output_folder)/'tts.mp3'); voice = self.voice.currentText(); self.work('TTS 생성',lambda:(generate_tts(text,voice,out),self.bus.tts.emit(out)))

    def on_tts(self, p): self.current_tts=p; self.say('TTS 완료: '+p)

    def auto_cut(self):
        p = self.video.text().strip()
        if not p: return
        out = str(Path(self.s.output_folder)/'auto_cut.mp4')
        def f(): auto_cut_vertical(p,out,self.target_sec.value(),self.clip_sec.value(),lambda x:self.bus.log.emit(x)); self.bus.rendered.emit(out)
        self.work('자동 컷 편집', f)

    def render(self):
        p = self.video.text().strip(); out = self.out.text().strip()
        if not p or not out: return
        def f():
            compose_vertical(p,self.current_tts or None,out)
            if self.quick_wm.isChecked() and self.s.watermark_text:
                wm = str(Path(out).with_name(Path(out).stem+'_wm.mp4')); watermark(out,self.s.watermark_text,wm,self.s.watermark_position); self.bus.rendered.emit(wm)
            else: self.bus.rendered.emit(out)
        self.work('최종 렌더', f)

    def on_rendered(self, p): self.current_video=p; self.video.setText(p); self.pubvideo.setText(p); self.thumb_video.setText(p); self.load_preview(p); self.say('완성: '+p)

    def create_thumb(self):
        p = self.thumb_video.text().strip() or self.current_video; text = self.thumb_text.text().strip(); out = self.thumb_out.text().strip()
        if not p: return
        self.work('썸네일 생성',lambda:self.bus.thumb.emit(make_thumbnail(p,text,out)))

    def show_thumb(self, p):
        pm = QPixmap(p)
        if not pm.isNull(): self.thumb_preview.setPixmap(pm.scaled(self.thumb_preview.size(),Qt.KeepAspectRatio,Qt.SmoothTransformation))
        self.say('썸네일 저장: '+p)

    def upload_youtube(self):
        p = self.pubvideo.text().strip(); secret = self.s.youtube_client_secret_file
        if not p: return
        if not secret: return self.bus.err.emit('설정에서 YouTube client_secret.json을 지정하세요.')
        title = self.ytitle.text().strip() or 'NovaShorts'; desc = self.ydesc.toPlainText(); tags = [x.strip() for x in self.ytags.text().split(',') if x.strip()]; privacy = self.privacy.currentText()
        def f(): vid = youtube_upload(p,secret,title,desc,tags,privacy); self.bus.log.emit('YouTube 업로드 완료: '+vid)
        self.work('YouTube 업로드', f)

    def add_lnk(self):
        title = self.linktitle.text().strip(); url = self.linkurl.text().strip()
        if not title or not url: return
        def f(): r = lnk_bio_add(self.s.lnkbio_client_id,self.s.lnkbio_client_secret,title,url); self.bus.log.emit('Lnk.Bio 완료: '+str(r)[:300])
        self.work('Lnk.Bio 추가', f)

    def quick_voice_changed(self, idx):
        voices = ['ko-KR-SunHiNeural','ko-KR-InJoonNeural','ko-KR-HyunsuNeural']
        if hasattr(self,'voice'): self.voice.setCurrentText(voices[max(0,min(idx,2))])

    def quick_save(self):
        self.s.watermark_enabled = self.quick_wm.isChecked(); self.s.use_gemini_query_planning = self.quick_ai.currentIndex() == 0; save_settings(self.s)

    def save(self):
        self.s.output_folder=self.setout.text().strip() or self.s.output_folder; self.s.gemini_api_key=self.gkey.text().strip(); self.s.coupang_access_key=self.cakey.text().strip(); self.s.coupang_secret_key=self.cskey.text().strip(); self.s.min_similarity=self.sim.value(); self.s.auto_skip_low_similarity=self.skip.isChecked(); self.s.use_gemini_query_planning=self.gplan.isChecked(); self.s.youtube_client_secret_file=self.ysecret.text().strip(); self.s.lnkbio_client_id=self.lid.text().strip(); self.s.lnkbio_client_secret=self.lsec.text().strip(); self.s.tts_voice=self.voice.currentText(); self.s.watermark_enabled=self.quick_wm.isChecked(); save_settings(self.s); self.say('설정 저장 완료')

    def refresh_diag(self):
        d = diagnostics(); text = ' | '.join(f'{k}:{"정상" if v else "없음"}' for k,v in d.items()); self.diag.setText(text)
        if hasattr(self,'diagbox'): self.diagbox.setPlainText(json.dumps(d,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    app = QApplication([])
    app.setApplicationName('NovaShorts')
    app.setFont(QFont('Malgun Gothic', 10))
    win = Nova()
    win.show()
    app.exec()
