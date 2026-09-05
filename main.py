from __future__ import annotations
import json, os, threading, time, webbrowser
from pathlib import Path

from PySide6.QtCore import Qt, QObject, Signal, QUrl
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import *
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget

from engine import *
from bridge import start_bridge, TASKS, RESULTS
from features import make_thumbnail, auto_cut_vertical

VERSION='1.7'

CSS='''
QWidget{background:#09101e;color:#eef3ff;font-family:"Malgun Gothic";font-size:13px}
QMainWindow{background:#080d18}
QFrame#sidebar{background:#10192b;border-right:1px solid #263450}
QFrame#topbar{background:#0d1526;border-bottom:1px solid #263450}
QFrame#card,QGroupBox{background:#111b30;border:1px solid #283957;border-radius:14px}
QGroupBox{margin-top:12px;padding:13px;font-weight:700}
QGroupBox::title{subcontrol-origin:margin;left:12px;padding:0 7px;color:#e4ebff}
QLineEdit,QPlainTextEdit,QComboBox,QSpinBox,QListWidget{background:#0c1527;border:1px solid #334765;border-radius:9px;padding:8px;color:#f5f7ff;selection-background-color:#315cff}
QPushButton{background:#315cff;border:0;border-radius:9px;padding:9px 14px;color:white;font-weight:700;min-height:26px}
QPushButton:hover{background:#4e72ff}
QPushButton[secondary="true"]{background:#17243c;border:1px solid #334765}
QPushButton[danger="true"]{background:#d83d57}
QPushButton[nav="true"]{text-align:left;background:transparent;border:0;padding:12px 14px;font-size:14px}
QPushButton[nav="true"]:checked{background:#294fc4;border-radius:10px}
QCheckBox{spacing:9px;padding:3px;background:transparent}
QCheckBox::indicator{width:18px;height:18px;border-radius:5px;border:1px solid #506281;background:#0b1322}
QCheckBox::indicator:checked{background:#5c52ff;border:1px solid #7f79ff}
QProgressBar{background:#111a2d;border:1px solid #30425f;border-radius:7px;text-align:center;height:12px}
QProgressBar::chunk{background:#3d63ff;border-radius:6px}
QScrollArea{border:0;background:transparent}
QTableWidget{background:#10192b;border:1px solid #283957;border-radius:10px;gridline-color:#22304b}
QHeaderView::section{background:#17243a;color:#dce5f9;padding:8px;border:0}
QLabel#muted{color:#91a5c8;background:transparent}
QLabel#title{font-size:26px;font-weight:900;background:transparent}
QLabel#section{font-size:17px;font-weight:800;background:transparent}
QLabel#brand{font-size:22px;font-weight:900;background:transparent}
QFrame#hero{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #2851db,stop:.54 #6e39ea,stop:1 #ac38ee);border-radius:16px}
QLabel#heroTitle{font-size:31px;font-weight:900;background:transparent}
QLabel#heroSub{font-size:14px;background:transparent}
QFrame#videoCard{background:#111b30;border:1px solid #2a3b5c;border-radius:12px}
'''

class Bus(QObject):
    log=Signal(str)
    err=Signal(str)
    plan=Signal(dict)
    candidates=Signal(list)
    downloaded=Signal(str)
    ocr=Signal(list)
    tts=Signal(str)
    rendered=Signal(str)
    thumb=Signal(str)
    job_done=Signal(int,bool,str)

class Nova(QMainWindow):
    def __init__(self):
        super().__init__()
        self.s=load_settings()
        self.bridge=start_bridge()
        self.bus=Bus()
        self.query_plan={}
        self.current_video=''
        self.current_tts=''
        self.candidate_rows=[]
        self.job_counter=0
        self.jobs={}
        self.audio=QAudioOutput(self)
        self.player=QMediaPlayer(self)
        self.player.setAudioOutput(self.audio)
        self.build()
        self.bind()
        self.refresh_diag()
        self.say(f'NovaShorts v{VERSION} 시작')

    def bind(self):
        self.bus.log.connect(self.say)
        self.bus.err.connect(lambda x:QMessageBox.critical(self,'NovaShorts',x))
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
        self.resize(1560,950)
        self.setMinimumSize(1220,760)
        self.setStyleSheet(CSS)

        root=QWidget(); self.setCentralWidget(root)
        main=QHBoxLayout(root); main.setContentsMargins(0,0,0,0); main.setSpacing(0)
        main.addWidget(self.sidebar())

        body=QWidget(); bv=QVBoxLayout(body); bv.setContentsMargins(0,0,0,0); bv.setSpacing(0)
        bv.addWidget(self.topbar())
        content=QWidget(); ch=QHBoxLayout(content); ch.setContentsMargins(16,14,16,10); ch.setSpacing(14)
        self.pages=QStackedWidget()
        self.pages.addWidget(self.home_page())
        self.pages.addWidget(self.source_page())
        self.pages.addWidget(self.edit_page())
        self.pages.addWidget(self.voice_page())
        self.pages.addWidget(self.thumb_page())
        self.pages.addWidget(self.publish_page())
        self.pages.addWidget(self.link_page())
        self.pages.addWidget(self.settings_page())
        ch.addWidget(self.pages,1)
        ch.addWidget(self.right_panel())
        bv.addWidget(content,1)
        bv.addWidget(self.queue_panel())
        bv.addWidget(self.statusbar_panel())
        main.addWidget(body,1)

    def sidebar(self):
        f=QFrame(); f.setObjectName('sidebar'); f.setFixedWidth(238)
        v=QVBoxLayout(f); v.setContentsMargins(12,16,12,14); v.setSpacing(7)
        brand=QLabel(f'✦  NovaShorts  v{VERSION}'); brand.setObjectName('brand'); brand.setMinimumWidth(205); v.addWidget(brand)
        sub=QLabel('Global Shorts Production'); sub.setObjectName('muted'); v.addWidget(sub); v.addSpacing(12)
        self.nav=[]
        items=[('홈','⌂'),('소싱','◎'),('편집','✣'),('AI 음성','◉'),('썸네일','▣'),('업로드','⇧'),('링크 관리','↗'),('설정','⚙')]
        for i,(txt,ico) in enumerate(items):
            b=QPushButton(f'{ico}   {txt}'); b.setProperty('nav',True); b.setCheckable(True)
            b.clicked.connect(lambda _,n=i:self.go(n)); self.nav.append(b); v.addWidget(b)
        self.nav[0].setChecked(True)
        v.addStretch()
        badge=QLabel(f'★ NovaShorts v{VERSION}\n글로벌 쇼츠 제작 스튜디오')
        badge.setStyleSheet('background:#182753;border:1px solid #315cff;border-radius:12px;padding:14px;font-weight:700')
        v.addWidget(badge)
        return f

    def topbar(self):
        f=QFrame(); f.setObjectName('topbar'); f.setFixedHeight(76)
        h=QHBoxLayout(f); h.setContentsMargins(20,10,18,10)
        title=QLabel('NovaShorts'); title.setObjectName('brand'); title.setMinimumWidth(138); h.addWidget(title)
        sub=QLabel('상품 → 글로벌 소싱 → AI 편집 → 자동 게시'); sub.setObjectName('muted'); sub.setMinimumWidth(320); h.addWidget(sub)
        h.addStretch()
        history=QPushButton('▣ 작업 기록'); history.setProperty('secondary',True); history.clicked.connect(lambda:self.queue.setFocus()); h.addWidget(history)
        b=QPushButton('⚙ 설정'); b.setProperty('secondary',True); b.clicked.connect(lambda:self.go(7)); h.addWidget(b)
        return f

    def hero(self):
        f=QFrame(); f.setObjectName('hero'); f.setMinimumHeight(210)
        h=QHBoxLayout(f); h.setContentsMargins(30,24,30,24)
        l=QVBoxLayout(); t=QLabel('세상의 핫한 영상을\n나만의 쇼츠로 🚀'); t.setObjectName('heroTitle'); l.addWidget(t)
        s=QLabel('글로벌 영상 소싱부터 OCR · TTS · 자동 편집 · 업로드까지'); s.setObjectName('heroSub'); l.addWidget(s); h.addLayout(l)
        h.addStretch()
        globe=QLabel('◉\nTikTok  小红书\nDouyin  Kuaishou\n1688'); globe.setAlignment(Qt.AlignCenter)
        globe.setStyleSheet('font-size:20px;font-weight:800;background:rgba(20,25,60,.38);border-radius:62px;padding:22px')
        globe.setMinimumWidth(245); h.addWidget(globe)
        return f

    def home_page(self):
        w=QWidget(); v=QVBoxLayout(w); v.setContentsMargins(0,0,0,0); v.setSpacing(12)
        v.addWidget(self.hero())
        g=QGroupBox('소싱하기'); q=QGridLayout(g)
        self.home_keyword=QLineEdit(); self.home_keyword.setPlaceholderText('상품명/검색 키워드를 입력하세요 (예: 주방 꿀템, 청소, 홈인테리어)')
        b=QPushButton('🔎 소싱 시작'); b.clicked.connect(self.home_to_source)
        q.addWidget(self.home_keyword,0,0,1,4); q.addWidget(b,0,4)
        self.home_checks={}
        for j,p in enumerate(['TikTok','Douyin','Xiaohongshu','Kuaishou','1688']):
            cb=QCheckBox(p); cb.setChecked(True); self.home_checks[p]=cb; q.addWidget(cb,1,j)
        v.addWidget(g)

        row=QHBoxLayout(); label=QLabel('수집된 영상 목록'); label.setObjectName('section'); row.addWidget(label); self.home_count=QLabel('0'); self.home_count.setObjectName('muted'); row.addWidget(self.home_count); row.addStretch()
        toedit=QPushButton('선택 영상으로 편집하기 →'); toedit.clicked.connect(lambda:self.go(2)); row.addWidget(toedit); v.addLayout(row)
        self.card_area=QScrollArea(); self.card_area.setWidgetResizable(True); self.card_area.setMinimumHeight(230)
        self.card_host=QWidget(); self.card_layout=QHBoxLayout(self.card_host); self.card_layout.setContentsMargins(0,0,0,0); self.card_layout.setSpacing(10); self.card_layout.addStretch()
        self.card_area.setWidget(self.card_host); v.addWidget(self.card_area)
        return w

    def source_page(self):
        w=QWidget(); v=QVBoxLayout(w); v.setContentsMargins(0,0,0,0)
        title=QLabel('글로벌 영상 소싱'); title.setObjectName('title'); v.addWidget(title)
        g=QGroupBox('상품 / 검색어'); q=QGridLayout(g)
        self.product=QLineEdit(); self.product.setPlaceholderText('상품명')
        self.product_url=QLineEdit(); self.product_url.setPlaceholderText('쿠팡/상품 URL')
        b1=QPushButton('AI 검색어 생성'); b1.clicked.connect(self.make_plan)
        b2=QPushButton('쿠팡 API 검색'); b2.clicked.connect(self.coupang_lookup)
        q.addWidget(self.product,0,0,1,3); q.addWidget(b1,0,3); q.addWidget(self.product_url,1,0,1,3); q.addWidget(b2,1,3); v.addWidget(g)
        pg=QGroupBox('플랫폼'); ph=QHBoxLayout(pg); self.pchecks={}
        for p in PLATFORMS:
            cb=QCheckBox(p); cb.setChecked(p in self.s.platform_sources); self.pchecks[p]=cb; ph.addWidget(cb)
        ph.addStretch(); v.addWidget(pg)
        split=QSplitter(Qt.Horizontal)
        qg=QGroupBox('검색 계획'); qv=QVBoxLayout(qg); self.planbox=QPlainTextEdit(); qv.addWidget(self.planbox)
        hh=QHBoxLayout(); bo=QPushButton('검색 페이지 열기'); bo.clicked.connect(self.open_searches); bc=QPushButton('Chrome Bridge 자동수집'); bc.clicked.connect(self.bridge_collect); hh.addWidget(bo); hh.addWidget(bc); qv.addLayout(hh); split.addWidget(qg)
        cg=QGroupBox('수집된 영상 목록'); cv=QVBoxLayout(cg); self.candidates=QListWidget(); self.candidates.itemSelectionChanged.connect(self.candidate_selected); cv.addWidget(self.candidates)
        self.cand_url=QLineEdit(); self.cand_text=QLineEdit(); cv.addWidget(self.cand_url); cv.addWidget(self.cand_text)
        rh=QHBoxLayout(); self.score=QLabel('유사도 -'); bs=QPushButton('유사도 계산'); bs.clicked.connect(self.score_it); bd=QPushButton('선택 영상 다운로드'); bd.clicked.connect(self.download_it); rh.addWidget(self.score); rh.addStretch(); rh.addWidget(bs); rh.addWidget(bd); cv.addLayout(rh)
        split.addWidget(cg); split.setStretchFactor(1,2); v.addWidget(split,1)
        return w

    def edit_page(self):
        w=QWidget(); v=QVBoxLayout(w); t=QLabel('AI 영상 편집'); t.setObjectName('title'); v.addWidget(t)
        src=QGroupBox('소스 영상'); h=QHBoxLayout(src); self.video=QLineEdit(); bf=QPushButton('파일 찾기'); bf.clicked.connect(self.choose_video); h.addWidget(self.video,1); h.addWidget(bf); v.addWidget(src)
        sp=QSplitter(Qt.Horizontal)
        og=QGroupBox('OCR / 자막 제거'); ov=QVBoxLayout(og); self.ocrbox=QPlainTextEdit(); ov.addWidget(self.ocrbox)
        r=QHBoxLayout(); bs=QPushButton('OCR 스캔'); bs.clicked.connect(self.ocr_scan); bc=QPushButton('하단 자막 제거'); bc.clicked.connect(self.clean_sub); r.addWidget(bs); r.addWidget(bc); ov.addLayout(r); sp.addWidget(og)
        ag=QGroupBox('자동 컷 / 렌더'); av=QVBoxLayout(ag); self.target_sec=QSpinBox(); self.target_sec.setRange(4,60); self.target_sec.setValue(18); self.clip_sec=QSpinBox(); self.clip_sec.setRange(1,5); self.clip_sec.setValue(3)
        self.out=QLineEdit(str(Path(self.s.output_folder)/'final_short.mp4')); ba=QPushButton('자동 컷 편집'); ba.clicked.connect(self.auto_cut); br=QPushButton('1080×1920 최종 렌더'); br.clicked.connect(self.render)
        av.addWidget(QLabel('목표 길이(초)')); av.addWidget(self.target_sec); av.addWidget(QLabel('컷 길이(초)')); av.addWidget(self.clip_sec); av.addWidget(self.out); av.addWidget(ba); av.addWidget(br); av.addStretch(); sp.addWidget(ag); v.addWidget(sp,1)
        return w

    def voice_page(self):
        w=QWidget(); v=QVBoxLayout(w); t=QLabel('AI 음성 · TTS'); t.setObjectName('title'); v.addWidget(t)
        g=QGroupBox('대본 / 음성'); q=QVBoxLayout(g); self.script=QPlainTextEdit(); self.script.setPlaceholderText('한국어 대본을 입력하세요')
        self.voice=QComboBox(); self.voice.addItems(['ko-KR-SunHiNeural','ko-KR-InJoonNeural','ko-KR-HyunsuNeural']); self.voice.setCurrentText(self.s.tts_voice)
        b=QPushButton('TTS 생성'); b.clicked.connect(self.make_tts); q.addWidget(self.script); q.addWidget(self.voice); q.addWidget(b); v.addWidget(g,1); return w

    def thumb_page(self):
        w=QWidget(); v=QVBoxLayout(w); t=QLabel('썸네일'); t.setObjectName('title'); v.addWidget(t)
        g=QGroupBox('영상 프레임 + 문구'); q=QGridLayout(g); self.thumb_video=QLineEdit(); self.thumb_text=QLineEdit(); self.thumb_text.setPlaceholderText('썸네일 문구'); self.thumb_out=QLineEdit(str(Path(self.s.output_folder)/'thumbnail.jpg')); b=QPushButton('썸네일 만들기'); b.clicked.connect(self.create_thumb)
        q.addWidget(QLabel('영상'),0,0); q.addWidget(self.thumb_video,0,1,1,2); q.addWidget(QLabel('문구'),1,0); q.addWidget(self.thumb_text,1,1,1,2); q.addWidget(QLabel('저장'),2,0); q.addWidget(self.thumb_out,2,1,1,2); q.addWidget(b,3,2); v.addWidget(g)
        self.thumb_preview=QLabel('썸네일 미리보기'); self.thumb_preview.setAlignment(Qt.AlignCenter); self.thumb_preview.setMinimumHeight(400); self.thumb_preview.setStyleSheet('background:#111a2e;border:1px solid #253452;border-radius:14px'); v.addWidget(self.thumb_preview,1); return w

    def publish_page(self):
        w=QWidget(); v=QVBoxLayout(w); t=QLabel('업로드'); t.setObjectName('title'); v.addWidget(t)
        g=QGroupBox('YouTube'); q=QGridLayout(g); self.pubvideo=QLineEdit(); self.ytitle=QLineEdit(); self.ydesc=QPlainTextEdit(); self.ytags=QLineEdit(); self.privacy=QComboBox(); self.privacy.addItems(['private','unlisted','public']); b=QPushButton('YouTube 업로드'); b.clicked.connect(self.upload_youtube)
        q.addWidget(QLabel('영상'),0,0); q.addWidget(self.pubvideo,0,1,1,3); q.addWidget(QLabel('제목'),1,0); q.addWidget(self.ytitle,1,1,1,3); q.addWidget(QLabel('설명'),2,0); q.addWidget(self.ydesc,2,1,1,3); q.addWidget(QLabel('태그'),3,0); q.addWidget(self.ytags,3,1,1,2); q.addWidget(self.privacy,3,3); q.addWidget(b,4,3); v.addWidget(g,1); return w

    def link_page(self):
        w=QWidget(); v=QVBoxLayout(w); t=QLabel('링크 관리'); t.setObjectName('title'); v.addWidget(t)
        g=QGroupBox('Lnk.Bio / X'); q=QGridLayout(g); self.linktitle=QLineEdit(); self.linkurl=QLineEdit(); self.xtext=QLineEdit(); bl=QPushButton('Lnk.Bio 추가'); bl.clicked.connect(self.add_lnk); bx=QPushButton('X 작성창'); bx.clicked.connect(lambda:open_x(self.xtext.text()))
        self.linktitle.setPlaceholderText('링크 제목'); self.linkurl.setPlaceholderText('상품/제휴 링크'); self.xtext.setPlaceholderText('X 게시문')
        q.addWidget(self.linktitle,0,0,1,2); q.addWidget(self.linkurl,1,0,1,2); q.addWidget(bl,2,1); q.addWidget(self.xtext,3,0,1,2); q.addWidget(bx,4,1); v.addWidget(g); v.addStretch(); return w

    def settings_page(self):
        w=QWidget(); v=QVBoxLayout(w); t=QLabel('설정'); t.setObjectName('title'); v.addWidget(t)
        g=QGroupBox('API / 환경 설정'); q=QGridLayout(g); self.setout=QLineEdit(self.s.output_folder); self.gkey=QLineEdit(self.s.gemini_api_key); self.gkey.setEchoMode(QLineEdit.Password); self.cakey=QLineEdit(self.s.coupang_access_key); self.cakey.setEchoMode(QLineEdit.Password); self.cskey=QLineEdit(self.s.coupang_secret_key); self.cskey.setEchoMode(QLineEdit.Password); self.sim=QSpinBox(); self.sim.setRange(0,100); self.sim.setValue(self.s.min_similarity); self.ysecret=QLineEdit(self.s.youtube_client_secret_file); self.lid=QLineEdit(self.s.lnkbio_client_id); self.lsec=QLineEdit(self.s.lnkbio_client_secret); self.lsec.setEchoMode(QLineEdit.Password)
        rows=[('출력 폴더',self.setout),('Gemini API Key',self.gkey),('Coupang Access Key',self.cakey),('Coupang Secret Key',self.cskey),('최소 유사도',self.sim),('YouTube client_secret.json',self.ysecret),('Lnk.Bio Client ID',self.lid),('Lnk.Bio Client Secret',self.lsec)]
        for i,(n,x) in enumerate(rows): q.addWidget(QLabel(n),i,0); q.addWidget(x,i,1,1,3)
        self.skip=QCheckBox('저유사도 자동 제외'); self.skip.setChecked(self.s.auto_skip_low_similarity); self.gplan=QCheckBox('Gemini 검색계획'); self.gplan.setChecked(self.s.use_gemini_query_planning); q.addWidget(self.skip,len(rows),1); q.addWidget(self.gplan,len(rows),2)
        bs=QPushButton('설정 저장'); bs.clicked.connect(self.save); q.addWidget(bs,len(rows)+1,3); v.addWidget(g)
        dg=QGroupBox('런타임 진단'); dv=QVBoxLayout(dg); self.diagbox=QPlainTextEdit(); self.diagbox.setReadOnly(True); dv.addWidget(self.diagbox); bd=QPushButton('다시 진단'); bd.clicked.connect(self.refresh_diag); dv.addWidget(bd); v.addWidget(dg,1); return w

    def right_panel(self):
        w=QWidget(); w.setFixedWidth(316); v=QVBoxLayout(w); v.setContentsMargins(0,0,0,0); v.setSpacing(12)
        g=QGroupBox('빠른 설정'); q=QGridLayout(g)
        self.quick_ai=QComboBox(); self.quick_ai.addItems(['Gemini 2.5 Flash','규칙 기반'])
        self.quick_voice=QComboBox(); self.quick_voice.addItems(['Edge TTS - SunHi','Edge TTS - InJoon','Edge TTS - Hyunsu'])
        self.quick_res=QComboBox(); self.quick_res.addItems(['1080 × 1920 (세로)'])
        self.quick_ocr=QCheckBox('자막 제거(OCR)'); self.quick_ocr.setChecked(True)
        self.quick_cut=QCheckBox('자동 컷 편집'); self.quick_cut.setChecked(True)
        self.quick_wm=QCheckBox('워터마크 추가'); self.quick_wm.setChecked(self.s.watermark_enabled)
        q.addWidget(QLabel('AI 모델'),0,0); q.addWidget(self.quick_ai,0,1); q.addWidget(QLabel('TTS 음성'),1,0); q.addWidget(self.quick_voice,1,1); q.addWidget(QLabel('영상 해상도'),2,0); q.addWidget(self.quick_res,2,1); q.addWidget(self.quick_ocr,3,0,1,2); q.addWidget(self.quick_cut,4,0,1,2); q.addWidget(self.quick_wm,5,0,1,2)
        self.quick_wm.toggled.connect(self.quick_save); v.addWidget(g)
        pg=QGroupBox('미리보기'); pv=QVBoxLayout(pg)
        self.video_widget=QVideoWidget(); self.video_widget.setMinimumHeight(355); self.video_widget.setStyleSheet('background:#050910;border-radius:12px'); self.player.setVideoOutput(self.video_widget); pv.addWidget(self.video_widget,1)
        self.preview_label=QLabel('선택/완성 영상을 불러오세요'); self.preview_label.setObjectName('muted'); self.preview_label.setAlignment(Qt.AlignCenter); pv.addWidget(self.preview_label)
        ctrl=QHBoxLayout(); self.play_btn=QPushButton('▶ 재생'); self.play_btn.clicked.connect(self.toggle_play); op=QPushButton('파일 열기'); op.setProperty('secondary',True); op.clicked.connect(self.preview_pick); ctrl.addWidget(self.play_btn); ctrl.addWidget(op); pv.addLayout(ctrl); v.addWidget(pg,1)
        return w

    def queue_panel(self):
        g=QGroupBox('작업 대기열'); g.setMaximumHeight(190); v=QVBoxLayout(g)
        self.queue=QTableWidget(0,5); self.queue.setHorizontalHeaderLabels(['작업명','상태','진행률','시작 시간','작업']); self.queue.horizontalHeader().setSectionResizeMode(0,QHeaderView.Stretch); self.queue.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeToContents); self.queue.horizontalHeader().setSectionResizeMode(2,QHeaderView.ResizeToContents); self.queue.horizontalHeader().setSectionResizeMode(3,QHeaderView.ResizeToContents); self.queue.horizontalHeader().setSectionResizeMode(4,QHeaderView.ResizeToContents); self.queue.verticalHeader().setVisible(False); v.addWidget(self.queue)
        h=QHBoxLayout(); h.addStretch(); clear=QPushButton('목록 비우기'); clear.setProperty('secondary',True); clear.clicked.connect(lambda:self.queue.setRowCount(0)); h.addWidget(clear); v.addLayout(h); return g

    def statusbar_panel(self):
        f=QFrame(); h=QHBoxLayout(f); h.setContentsMargins(18,4,18,8); self.status=QLabel('준비'); self.status.setStyleSheet('color:#65e28a'); h.addWidget(self.status); self.progress=QProgressBar(); self.progress.setRange(0,100); self.progress.setValue(0); self.progress.setFixedWidth(245); h.addWidget(self.progress); h.addStretch(); self.diag=QLabel(); self.diag.setObjectName('muted'); h.addWidget(self.diag); return f

    def go(self,n):
        self.pages.setCurrentIndex(n)
        for i,b in enumerate(self.nav): b.setChecked(i==n)

    def selected(self):
        return [p for p,c in self.pchecks.items() if c.isChecked()]

    def say(self,x):
        log(x); self.status.setText(x[:120])

    def add_job(self,label):
        self.job_counter+=1; jid=self.job_counter; row=self.queue.rowCount(); self.queue.insertRow(row); now=time.strftime('%H:%M:%S')
        vals=[label,'실행 중','0%',now,'●']
        for c,v in enumerate(vals): self.queue.setItem(row,c,QTableWidgetItem(v))
        self.jobs[jid]=row; return jid

    def finish_job(self,jid,ok,msg):
        row=self.jobs.get(jid)
        if row is not None and row < self.queue.rowCount():
            self.queue.item(row,1).setText('완료' if ok else '실패'); self.queue.item(row,2).setText('100%' if ok else '-'); self.queue.item(row,4).setText('✓' if ok else '!')
        self.progress.setRange(0,100); self.progress.setValue(100 if ok else 0); self.say(msg)

    def work(self,label,fn):
        jid=self.add_job(label); self.progress.setRange(0,0); self.status.setText(label)
        def go():
            try:
                fn(); self.bus.job_done.emit(jid,True,label+' 완료')
            except Exception as e:
                self.bus.err.emit(label+'\n'+str(e)); self.bus.job_done.emit(jid,False,'오류: '+str(e))
        threading.Thread(target=go,daemon=True).start()

    def home_to_source(self):
        text=self.home_keyword.text().strip()
        if not text: return
        self.go(1); self.product.setText(text)
        for p,cb in self.pchecks.items(): cb.setChecked(self.home_checks.get(p,QCheckBox()).isChecked() if p in self.home_checks else True)
        self.make_plan()

    def make_plan(self):
        title=self.product.text().strip()
        if not title:return
        def f(): self.bus.plan.emit(gemini_query_plan(title,self.s.gemini_api_key) if self.s.use_gemini_query_planning else rule_query_plan(title))
        self.work('AI 검색어 생성',f)

    def on_plan(self,p):
        self.query_plan=p; self.planbox.setPlainText(json.dumps(p,ensure_ascii=False,indent=2)); self.say('검색어 계획 완료')

    def coupang_lookup(self):
        kw=self.product.text().strip()
        if not kw:return
        def f():
            d=coupang_search(kw,self.s.coupang_access_key,self.s.coupang_secret_key); items=d.get('data',{}).get('productData',[]) or d.get('data',[])
            self.bus.candidates.emit([{'url':x.get('productUrl',''),'title':x.get('productName',''),'platform':'Coupang'} for x in items])
        self.work('쿠팡 API 검색',f)

    def open_searches(self):
        if not self.query_plan:return
        for p in self.selected():
            kw=(self.query_plan.get(p) or [''])[0]
            if kw:webbrowser.open(direct_search_url(p,kw))

    def bridge_collect(self):
        if not self.query_plan:return
        count=0
        for p in self.selected():
            for kw in (self.query_plan.get(p) or [])[:2]: TASKS.put({'type':'collect_links','platform':p,'url':direct_search_url(p,kw),'keyword':kw}); count+=1
        self.say(f'Chrome Bridge 작업 {count}개 전송')
        def wait():
            end=time.time()+45; rows=[]
            while time.time()<end:
                try:
                    r=RESULTS.get(timeout=1); rows.extend(r.get('items',[]))
                except Exception: pass
            self.bus.candidates.emit(rows)
        self.work('플랫폼 후보 수집',wait)

    def on_candidates(self,rows):
        self.candidate_rows=rows; self.candidates.clear()
        for r in rows:
            u=r.get('url',''); t=r.get('title','') or r.get('text',''); p=r.get('platform','')
            score=relevance(self.product.text(),t) if self.product.text().strip() else 0
            it=QListWidgetItem(f'[{p}] {t[:76]}\n유사도 {score}%  {u}'); it.setData(Qt.UserRole,r); self.candidates.addItem(it)
        self.render_cards(rows); self.say(f'후보 {len(rows)}개')

    def render_cards(self,rows):
        while self.card_layout.count()>0:
            item=self.card_layout.takeAt(0); w=item.widget()
            if w: w.deleteLater()
        for r in rows[:6]:
            f=QFrame(); f.setObjectName('videoCard'); f.setFixedWidth(185); v=QVBoxLayout(f); v.setContentsMargins(8,8,8,8)
            p=r.get('platform','Video'); thumb=QLabel(f'▶\n{p}'); thumb.setAlignment(Qt.AlignCenter); thumb.setFixedHeight(105); thumb.setStyleSheet('background:#172542;border-radius:9px;font-size:18px;font-weight:800'); v.addWidget(thumb)
            t=(r.get('title','') or r.get('text','') or '영상 후보').strip(); tl=QLabel(t[:40]); tl.setWordWrap(True); tl.setFixedHeight(45); v.addWidget(tl)
            sc=relevance(self.product.text(),t) if self.product.text().strip() else 0; meta=QLabel(f'유사도 {sc}%'); meta.setObjectName('muted'); v.addWidget(meta)
            b=QPushButton('선택'); b.clicked.connect(lambda _,x=r:self.card_select(x)); v.addWidget(b); self.card_layout.addWidget(f)
        self.card_layout.addStretch(); self.home_count.setText(str(len(rows)))

    def card_select(self,r):
        self.cand_url.setText(r.get('url','')); self.cand_text.setText(r.get('title','') or r.get('text','')); self.go(1)

    def candidate_selected(self):
        it=self.candidates.currentItem()
        if not it:return
        r=it.data(Qt.UserRole) or {}; self.cand_url.setText(r.get('url','')); self.cand_text.setText(r.get('title','') or r.get('text',''))

    def score_it(self):
        s=relevance(self.product.text(),self.cand_text.text()); self.score.setText(f'유사도 {s}%'); self.score.setStyleSheet('color:#65e28a;font-weight:700' if s>=self.s.min_similarity else 'color:#ff657a;font-weight:700')

    def download_it(self):
        u=self.cand_url.text().strip()
        if not u:return
        def f(): self.bus.downloaded.emit(str(download_video(u,self.s.output_folder,lambda x:self.bus.log.emit(x))))
        self.work('영상 다운로드',f)

    def on_downloaded(self,p):
        self.current_video=p; self.video.setText(p); self.pubvideo.setText(p); self.thumb_video.setText(p); self.load_preview(p); self.say('다운로드 완료: '+p)

    def choose_video(self):
        p,_=QFileDialog.getOpenFileName(self,'영상 선택','', 'Video (*.mp4 *.mov *.mkv *.webm)')
        if p: self.video.setText(p); self.current_video=p; self.pubvideo.setText(p); self.thumb_video.setText(p); self.load_preview(p)

    def preview_pick(self):
        p,_=QFileDialog.getOpenFileName(self,'미리보기 영상','', 'Video (*.mp4 *.mov *.mkv *.webm)')
        if p:self.load_preview(p)

    def load_preview(self,p):
        if not p or not Path(p).exists():return
        self.player.setSource(QUrl.fromLocalFile(str(Path(p).resolve()))); self.preview_label.setText(Path(p).name); self.player.pause(); self.play_btn.setText('▶ 재생')

    def toggle_play(self):
        if self.player.playbackState()==QMediaPlayer.PlayingState: self.player.pause(); self.play_btn.setText('▶ 재생')
        else: self.player.play(); self.play_btn.setText('Ⅱ 일시정지')

    def ocr_scan(self):
        p=self.video.text().strip()
        if not p:return
        workdir=str(Path(self.s.output_folder)/'ocr_work')
        self.work('OCR 스캔',lambda:self.bus.ocr.emit(subtitle_scan(p,workdir,lambda x:self.bus.log.emit(x))))

    def on_ocr(self,rows): self.ocrbox.setPlainText(json.dumps(rows,ensure_ascii=False,indent=2)); self.say(f'OCR {len(rows)}건')

    def clean_sub(self):
        p=self.video.text().strip()
        if not p:return
        out=str(Path(self.s.output_folder)/'subtitle_clean.mp4')
        def f(): cleanup_bottom_subtitles(p,out); self.bus.rendered.emit(out)
        self.work('자막 제거',f)

    def make_tts(self):
        text=self.script.toPlainText().strip()
        if not text:return
        out=str(Path(self.s.output_folder)/'tts.mp3'); voice=self.voice.currentText()
        self.work('TTS 생성',lambda:(generate_tts(text,voice,out),self.bus.tts.emit(out)))

    def on_tts(self,p): self.current_tts=p; self.say('TTS 완료: '+p)

    def auto_cut(self):
        p=self.video.text().strip()
        if not p:return
        out=str(Path(self.s.output_folder)/'auto_cut.mp4')
        def f(): auto_cut_vertical(p,out,self.target_sec.value(),self.clip_sec.value(),lambda x:self.bus.log.emit(x)); self.bus.rendered.emit(out)
        self.work('자동 컷 편집',f)

    def render(self):
        p=self.video.text().strip(); out=self.out.text().strip()
        if not p or not out:return
        def f():
            compose_vertical(p,self.current_tts or None,out)
            if self.quick_wm.isChecked() and self.s.watermark_text:
                wm=str(Path(out).with_name(Path(out).stem+'_wm.mp4')); watermark(out,self.s.watermark_text,wm,self.s.watermark_position); self.bus.rendered.emit(wm)
            else:self.bus.rendered.emit(out)
        self.work('최종 렌더',f)

    def on_rendered(self,p): self.current_video=p; self.video.setText(p); self.pubvideo.setText(p); self.thumb_video.setText(p); self.load_preview(p); self.say('완성: '+p)

    def create_thumb(self):
        p=self.thumb_video.text().strip() or self.current_video; text=self.thumb_text.text().strip(); out=self.thumb_out.text().strip()
        if not p:return
        self.work('썸네일 생성',lambda:self.bus.thumb.emit(make_thumbnail(p,text,out)))

    def show_thumb(self,p):
        pm=QPixmap(p)
        if not pm.isNull(): self.thumb_preview.setPixmap(pm.scaled(self.thumb_preview.size(),Qt.KeepAspectRatio,Qt.SmoothTransformation))
        self.say('썸네일 저장: '+p)

    def upload_youtube(self):
        p=self.pubvideo.text().strip(); secret=self.s.youtube_client_secret_file
        if not p:return
        if not secret:return self.bus.err.emit('설정에서 YouTube client_secret.json을 지정하세요.')
        title=self.ytitle.text().strip() or 'NovaShorts'; desc=self.ydesc.toPlainText(); tags=[x.strip() for x in self.ytags.text().split(',') if x.strip()]; privacy=self.privacy.currentText()
        def f(): vid=youtube_upload(p,secret,title,desc,tags,privacy); self.bus.log.emit('YouTube 업로드 완료: '+vid)
        self.work('YouTube 업로드',f)

    def add_lnk(self):
        title=self.linktitle.text().strip(); url=self.linkurl.text().strip()
        if not title or not url:return
        def f(): r=lnk_bio_add(self.s.lnkbio_client_id,self.s.lnkbio_client_secret,title,url); self.bus.log.emit('Lnk.Bio 완료: '+str(r)[:300])
        self.work('Lnk.Bio 추가',f)

    def quick_save(self): self.s.watermark_enabled=self.quick_wm.isChecked(); save_settings(self.s)

    def save(self):
        self.s.output_folder=self.setout.text().strip() or self.s.output_folder; self.s.gemini_api_key=self.gkey.text().strip(); self.s.coupang_access_key=self.cakey.text().strip(); self.s.coupang_secret_key=self.cskey.text().strip(); self.s.min_similarity=self.sim.value(); self.s.auto_skip_low_similarity=self.skip.isChecked(); self.s.use_gemini_query_planning=self.gplan.isChecked(); self.s.youtube_client_secret_file=self.ysecret.text().strip(); self.s.lnkbio_client_id=self.lid.text().strip(); self.s.lnkbio_client_secret=self.lsec.text().strip(); self.s.tts_voice=self.voice.currentText(); self.s.watermark_enabled=self.quick_wm.isChecked(); save_settings(self.s); self.say('설정 저장 완료')

    def refresh_diag(self):
        d=diagnostics(); text=' | '.join(f'{k}:{"정상" if v else "없음"}' for k,v in d.items()); self.diag.setText(text)
        if hasattr(self,'diagbox'): self.diagbox.setPlainText(json.dumps(d,ensure_ascii=False,indent=2))

if __name__=='__main__':
    app=QApplication([]); app.setApplicationName('NovaShorts'); app.setFont(QFont('Malgun Gothic',10)); win=Nova(); win.show(); app.exec()
