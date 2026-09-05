from __future__ import annotations
import json, os, threading, time, webbrowser
from pathlib import Path
from PySide6.QtCore import Qt, QObject, Signal
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import *
from engine import *
from bridge import start_bridge, TASKS, RESULTS
from features import make_thumbnail, auto_cut_vertical

CSS='''
QWidget{background:#0b1020;color:#eef2ff;font-family:"Malgun Gothic";font-size:13px}QMainWindow{background:#080d19}QFrame#sidebar{background:#10182b;border-right:1px solid #22304c}QFrame#topbar{background:#0e1629;border-bottom:1px solid #22304c}QFrame#card,QGroupBox{background:#111a2e;border:1px solid #253452;border-radius:14px}QGroupBox{margin-top:12px;padding:13px;font-weight:700}QGroupBox::title{subcontrol-origin:margin;left:12px;padding:0 6px;color:#dce6ff}QLineEdit,QPlainTextEdit,QComboBox,QSpinBox,QListWidget{background:#0d1527;border:1px solid #314363;border-radius:9px;padding:8px;color:#f5f7ff}QPushButton{background:#315cff;border:0;border-radius:9px;padding:9px 14px;color:white;font-weight:700;min-height:24px}QPushButton:hover{background:#4b6fff}QPushButton[secondary="true"]{background:#17233b;border:1px solid #30415f}QPushButton[nav="true"]{text-align:left;background:transparent;border:0;padding:11px 14px;font-size:14px}QPushButton[nav="true"]:checked{background:#2448b8;border-radius:10px}QCheckBox{spacing:8px}QProgressBar{background:#111a2e;border:1px solid #30415f;border-radius:7px;text-align:center;height:12px}QProgressBar::chunk{background:#3b63ff;border-radius:6px}QScrollArea{border:0;background:transparent}QTableWidget{background:#10182b;border:1px solid #253452;border-radius:10px;gridline-color:#22304c}QHeaderView::section{background:#17233b;color:#d8e1f3;padding:8px;border:0}QLabel#muted{color:#8fa2c6}QLabel#title{font-size:26px;font-weight:900}QLabel#section{font-size:17px;font-weight:800}QLabel#brand{font-size:22px;font-weight:900}QFrame#hero{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #2449d8,stop:.55 #6d32e8,stop:1 #a53cf0);border-radius:15px}QLabel#heroTitle{font-size:30px;font-weight:900;background:transparent}QLabel#heroSub{font-size:14px;background:transparent}'''

class Bus(QObject):
    log=Signal(str); err=Signal(str); plan=Signal(dict); candidates=Signal(list); downloaded=Signal(str); ocr=Signal(list); tts=Signal(str); rendered=Signal(str); thumb=Signal(str); queued=Signal(str,str,int)

class Nova(QMainWindow):
    def __init__(self):
        super().__init__(); self.s=load_settings(); self.bridge=start_bridge(); self.bus=Bus(); self.query_plan={}; self.current_video=''; self.current_tts=''; self.queue_rows=[]
        self.build(); self.bind(); self.refresh_diag(); self.say('NovaShorts v1.6 시작')
    def bind(self):
        self.bus.log.connect(self.say); self.bus.err.connect(lambda x:QMessageBox.critical(self,'NovaShorts',x)); self.bus.plan.connect(self.on_plan); self.bus.candidates.connect(self.on_candidates); self.bus.downloaded.connect(self.on_downloaded); self.bus.ocr.connect(self.on_ocr); self.bus.tts.connect(self.on_tts); self.bus.rendered.connect(self.on_rendered); self.bus.thumb.connect(self.show_preview); self.bus.queued.connect(self.queue_update)
    def build(self):
        self.setWindowTitle('NovaShorts Studio v1.6'); self.resize(1520,930); self.setMinimumSize(1180,720); self.setStyleSheet(CSS)
        root=QWidget(); self.setCentralWidget(root); main=QHBoxLayout(root); main.setContentsMargins(0,0,0,0); main.setSpacing(0)
        main.addWidget(self.sidebar())
        body=QWidget(); bv=QVBoxLayout(body); bv.setContentsMargins(0,0,0,0); bv.setSpacing(0); bv.addWidget(self.topbar())
        content=QWidget(); ch=QHBoxLayout(content); ch.setContentsMargins(16,14,16,10); ch.setSpacing(14)
        self.pages=QStackedWidget(); self.pages.addWidget(self.home_page()); self.pages.addWidget(self.source_page()); self.pages.addWidget(self.edit_page()); self.pages.addWidget(self.voice_page()); self.pages.addWidget(self.thumb_page()); self.pages.addWidget(self.publish_page()); self.pages.addWidget(self.link_page()); self.pages.addWidget(self.settings_page())
        ch.addWidget(self.pages,1); ch.addWidget(self.right_panel()); bv.addWidget(content,1); bv.addWidget(self.queue_panel()); bv.addWidget(self.statusbar_panel()); main.addWidget(body,1)
    def sidebar(self):
        f=QFrame(); f.setObjectName('sidebar'); f.setFixedWidth(218); v=QVBoxLayout(f); v.setContentsMargins(10,16,10,14); v.setSpacing(7)
        brand=QLabel('✦  NovaShorts  v1.6'); brand.setObjectName('brand'); v.addWidget(brand); sub=QLabel('Global Shorts Production'); sub.setObjectName('muted'); v.addWidget(sub); v.addSpacing(12)
        self.nav=[]
        for i,(txt,ico) in enumerate([('홈','⌂'),('소싱','◎'),('편집','✣'),('AI 음성','◉'),('썸네일','▣'),('업로드','⇧'),('링크 관리','↗'),('설정','⚙')]):
            b=QPushButton(f'{ico}   {txt}'); b.setProperty('nav',True); b.setCheckable(True); b.clicked.connect(lambda _,n=i:self.go(n)); self.nav.append(b); v.addWidget(b)
        self.nav[0].setChecked(True); v.addStretch(); badge=QLabel('★ NovaShorts\n빠르고 강력한 쇼츠 제작'); badge.setStyleSheet('background:#182653;border:1px solid #315cff;border-radius:12px;padding:14px;font-weight:700'); v.addWidget(badge); return f
    def topbar(self):
        f=QFrame(); f.setObjectName('topbar'); f.setFixedHeight(70); h=QHBoxLayout(f); h.setContentsMargins(20,10,18,10); title=QLabel('NovaShorts'); title.setObjectName('brand'); h.addWidget(title); h.addWidget(QLabel('상품 → 글로벌 소싱 → AI 편집 → 자동 게시')); h.addStretch(); b=QPushButton('⚙ 설정'); b.setProperty('secondary',True); b.clicked.connect(lambda:self.go(7)); h.addWidget(b); return f
    def hero(self):
        f=QFrame(); f.setObjectName('hero'); h=QHBoxLayout(f); h.setContentsMargins(28,24,28,24); l=QVBoxLayout(); t=QLabel('세상의 핫한 영상을\n나만의 쇼츠로 🚀'); t.setObjectName('heroTitle'); l.addWidget(t); s=QLabel('글로벌 영상 소싱부터 OCR · TTS · 자동 편집 · 업로드까지'); s.setObjectName('heroSub'); l.addWidget(s); h.addLayout(l); h.addStretch(); globe=QLabel('◉\nTikTok  小红书\nDouyin  Kuaishou\n1688'); globe.setAlignment(Qt.AlignCenter); globe.setStyleSheet('font-size:20px;font-weight:800;background:rgba(20,25,60,.35);border-radius:60px;padding:20px'); h.addWidget(globe); return f
    def home_page(self):
        w=QWidget(); v=QVBoxLayout(w); v.setContentsMargins(0,0,0,0); v.addWidget(self.hero()); v.addSpacing(12); g=QGroupBox('빠른 시작'); q=QGridLayout(g)
        self.home_keyword=QLineEdit(); self.home_keyword.setPlaceholderText('상품명/검색 키워드를 입력하세요'); b=QPushButton('소싱 시작'); b.clicked.connect(self.home_to_source); q.addWidget(self.home_keyword,0,0,1,3); q.addWidget(b,0,3)
        for j,txt in enumerate(['TikTok','Douyin','Xiaohongshu','Kuaishou','1688']): q.addWidget(QLabel('● '+txt),1,j)
        v.addWidget(g); d=QGroupBox('현재 기능'); dl=QGridLayout(d); feats=['쿠팡 API','Gemini 검색계획','5개 플랫폼 수집','유사도 필터','yt-dlp 다운로드','OCR/Tesseract','자막 블러 제거','Edge TTS','자동 컷 편집','1080×1920 렌더','워터마크','YouTube 업로드','Lnk.Bio','X 작성'];
        for i,x in enumerate(feats): dl.addWidget(QLabel('✓ '+x),i//4,i%4)
        v.addWidget(d); v.addStretch(); return w
    def source_page(self):
        w=QWidget(); v=QVBoxLayout(w); v.setContentsMargins(0,0,0,0); title=QLabel('글로벌 영상 소싱'); title.setObjectName('title'); v.addWidget(title)
        g=QGroupBox('상품 / 검색어'); q=QGridLayout(g); self.product=QLineEdit(); self.product.setPlaceholderText('상품명'); self.product_url=QLineEdit(); self.product_url.setPlaceholderText('쿠팡/상품 URL'); b1=QPushButton('AI 검색어 생성'); b1.clicked.connect(self.make_plan); b2=QPushButton('쿠팡 API 검색'); b2.clicked.connect(self.coupang_lookup); q.addWidget(self.product,0,0,1,3); q.addWidget(b1,0,3); q.addWidget(self.product_url,1,0,1,3); q.addWidget(b2,1,3); v.addWidget(g)
        pg=QGroupBox('플랫폼'); ph=QHBoxLayout(pg); self.pchecks={}
        for p in PLATFORMS: cb=QCheckBox(p); cb.setChecked(p in self.s.platform_sources); self.pchecks[p]=cb; ph.addWidget(cb)
        v.addWidget(pg)
        split=QSplitter(Qt.Horizontal); qg=QGroupBox('검색 계획'); qv=QVBoxLayout(qg); self.planbox=QPlainTextEdit(); qv.addWidget(self.planbox); hh=QHBoxLayout(); bo=QPushButton('검색 페이지 열기'); bo.clicked.connect(self.open_searches); bc=QPushButton('Chrome Bridge 자동수집'); bc.clicked.connect(self.bridge_collect); hh.addWidget(bo); hh.addWidget(bc); qv.addLayout(hh); split.addWidget(qg)
        cg=QGroupBox('수집된 영상 목록'); cv=QVBoxLayout(cg); self.candidates=QListWidget(); self.candidates.itemSelectionChanged.connect(self.candidate_selected); cv.addWidget(self.candidates); self.cand_url=QLineEdit(); self.cand_text=QLineEdit(); cv.addWidget(self.cand_url); cv.addWidget(self.cand_text); rh=QHBoxLayout(); self.score=QLabel('유사도 -'); bs=QPushButton('유사도 계산'); bs.clicked.connect(self.score_it); bd=QPushButton('선택 영상 다운로드'); bd.clicked.connect(self.download_it); rh.addWidget(self.score); rh.addStretch(); rh.addWidget(bs); rh.addWidget(bd); cv.addLayout(rh); split.addWidget(cg); split.setStretchFactor(1,2); v.addWidget(split,1); return w
    def edit_page(self):
        w=QWidget(); v=QVBoxLayout(w); title=QLabel('AI 영상 편집'); title.setObjectName('title'); v.addWidget(title); src=QGroupBox('소스 영상'); h=QHBoxLayout(src); self.video=QLineEdit(); bf=QPushButton('파일 찾기'); bf.clicked.connect(lambda:self.pick(self.video,'Video (*.mp4 *.mov *.mkv *.webm)')); h.addWidget(self.video,1); h.addWidget(bf); v.addWidget(src)
        sp=QSplitter(Qt.Horizontal); og=QGroupBox('OCR / 자막 제거'); ov=QVBoxLayout(og); self.ocrbox=QPlainTextEdit(); ov.addWidget(self.ocrbox); r=QHBoxLayout(); bs=QPushButton('OCR 스캔'); bs.clicked.connect(self.ocr_scan); bc=QPushButton('하단 자막 제거'); bc.clicked.connect(self.clean_sub); r.addWidget(bs); r.addWidget(bc); ov.addLayout(r); sp.addWidget(og)
        ag=QGroupBox('자동 컷 / 렌더'); av=QVBoxLayout(ag); self.target_sec=QSpinBox(); self.target_sec.setRange(4,60); self.target_sec.setValue(18); self.clip_sec=QSpinBox(); self.clip_sec.setRange(1,5); self.clip_sec.setValue(3); self.out=QLineEdit(str(Path(self.s.output_folder)/'final_short.mp4')); ba=QPushButton('자동 컷 편집'); ba.clicked.connect(self.auto_cut); br=QPushButton('1080×1920 최종 렌더'); br.clicked.connect(self.render); av.addWidget(QLabel('목표 길이(초)')); av.addWidget(self.target_sec); av.addWidget(QLabel('컷 길이(초)')); av.addWidget(self.clip_sec); av.addWidget(self.out); av.addWidget(ba); av.addWidget(br); av.addStretch(); sp.addWidget(ag); v.addWidget(sp,1); return w
    def voice_page(self):
        w=QWidget(); v=QVBoxLayout(w); t=QLabel('AI 음성 · TTS'); t.setObjectName('title'); v.addWidget(t); g=QGroupBox('대본 / 음성'); q=QVBoxLayout(g); self.script=QPlainTextEdit(); self.script.setPlaceholderText('한국어 대본을 입력하세요'); self.voice=QComboBox(); self.voice.addItems(['ko-KR-SunHiNeural','ko-KR-InJoonNeural','ko-KR-HyunsuNeural']); self.voice.setCurrentText(self.s.tts_voice); b=QPushButton('TTS 생성'); b.clicked.connect(self.make_tts); q.addWidget(self.script); q.addWidget(self.voice); q.addWidget(b); v.addWidget(g,1); return w
    def thumb_page(self):
        w=QWidget(); v=QVBoxLayout(w); t=QLabel('썸네일'); t.setObjectName('title'); v.addWidget(t); g=QGroupBox('영상 프레임 + 문구'); q=QGridLayout(g); self.thumb_video=QLineEdit(); self.thumb_text=QLineEdit(); self.thumb_text.setPlaceholderText('썸네일 문구'); self.thumb_out=QLineEdit(str(Path(self.s.output_folder)/'thumbnail.jpg')); b=QPushButton('썸네일 만들기'); b.clicked.connect(self.create_thumb); q.addWidget(QLabel('영상'),0,0); q.addWidget(self.thumb_video,0,1,1,2); q.addWidget(QLabel('문구'),1,0); q.addWidget(self.thumb_text,1,1,1,2); q.addWidget(QLabel('저장'),2,0); q.addWidget(self.thumb_out,2,1,1,2); q.addWidget(b,3,2); v.addWidget(g); self.thumb_preview=QLabel('썸네일 미리보기'); self.thumb_preview.setAlignment(Qt.AlignCenter); self.thumb_preview.setMinimumHeight(380); self.thumb_preview.setStyleSheet('background:#111a2e;border:1px solid #253452;border-radius:14px'); v.addWidget(self.thumb_preview,1); return w
    def publish_page(self):
        w=QWidget(); v=QVBoxLayout(w); t=QLabel('업로드'); t.setObjectName('title'); v.addWidget(t); g=QGroupBox('YouTube'); q=QGridLayout(g); self.pubvideo=QLineEdit(); self.ytitle=QLineEdit(); self.ydesc=QPlainTextEdit(); self.ytags=QLineEdit(); self.privacy=QComboBox(); self.privacy.addItems(['private','unlisted','public']); b=QPushButton('YouTube 업로드'); b.clicked.connect(self.upload_youtube); q.addWidget(QLabel('영상'),0,0); q.addWidget(self.pubvideo,0,1,1,3); q.addWidget(QLabel('제목'),1,0); q.addWidget(self.ytitle,1,1,1,3); q.addWidget(QLabel('설명'),2,0); q.addWidget(self.ydesc,2,1,1,3); q.addWidget(QLabel('태그'),3,0); q.addWidget(self.ytags,3,1,1,2); q.addWidget(self.privacy,3,3); q.addWidget(b,4,3); v.addWidget(g,1); return w
    def link_page(self):
        w=QWidget(); v=QVBoxLayout(w); t=QLabel('링크 관리'); t.setObjectName('title'); v.addWidget(t); g=QGroupBox('Lnk.Bio / X'); q=QGridLayout(g); self.linktitle=QLineEdit(); self.linkurl=QLineEdit(); self.xtext=QLineEdit(); bl=QPushButton('Lnk.Bio 추가'); bl.clicked.connect(self.add_lnk); bx=QPushButton('X 작성창 열기'); bx.clicked.connect(lambda:open_x(self.xtext.text())); q.addWidget(QLabel('제목'),0,0); q.addWidget(self.linktitle,0,1,1,2); q.addWidget(QLabel('링크'),1,0); q.addWidget(self.linkurl,1,1,1,2); q.addWidget(bl,2,2); q.addWidget(QLabel('X 문구'),3,0); q.addWidget(self.xtext,3,1,1,2); q.addWidget(bx,4,2); v.addWidget(g); v.addStretch(); return w
    def settings_page(self):
        w=QWidget(); v=QVBoxLayout(w); t=QLabel('설정'); t.setObjectName('title'); v.addWidget(t); g=QGroupBox('API / 환경'); q=QGridLayout(g); self.setout=QLineEdit(self.s.output_folder); self.gkey=QLineEdit(self.s.gemini_api_key); self.gkey.setEchoMode(QLineEdit.Password); self.cakey=QLineEdit(self.s.coupang_access_key); self.cakey.setEchoMode(QLineEdit.Password); self.cskey=QLineEdit(self.s.coupang_secret_key); self.cskey.setEchoMode(QLineEdit.Password); self.ysecret=QLineEdit(self.s.youtube_client_secret_file); self.lid=QLineEdit(self.s.lnkbio_client_id); self.lsec=QLineEdit(self.s.lnkbio_client_secret); self.lsec.setEchoMode(QLineEdit.Password); self.sim=QSpinBox(); self.sim.setRange(0,100); self.sim.setValue(self.s.min_similarity); self.skip=QCheckBox('저유사도 자동 제외'); self.skip.setChecked(self.s.auto_skip_low_similarity); self.gplan=QCheckBox('Gemini 검색계획'); self.gplan.setChecked(self.s.use_gemini_query_planning)
        rows=[('출력 폴더',self.setout),('Gemini API Key',self.gkey),('Coupang Access Key',self.cakey),('Coupang Secret Key',self.cskey),('YouTube client_secret.json',self.ysecret),('Lnk.Bio Client ID',self.lid),('Lnk.Bio Client Secret',self.lsec),('최소 유사도',self.sim)]
        for i,(n,x) in enumerate(rows): q.addWidget(QLabel(n),i,0); q.addWidget(x,i,1,1,3)
        q.addWidget(self.skip,len(rows),1); q.addWidget(self.gplan,len(rows),2); b=QPushButton('설정 저장'); b.clicked.connect(self.save); q.addWidget(b,len(rows)+1,3); v.addWidget(g); dg=QGroupBox('런타임 진단'); dv=QVBoxLayout(dg); self.diagbox=QPlainTextEdit(); self.diagbox.setReadOnly(True); dv.addWidget(self.diagbox); bd=QPushButton('다시 진단'); bd.clicked.connect(self.refresh_diag); dv.addWidget(bd); v.addWidget(dg,1); return w
    def right_panel(self):
        f=QFrame(); f.setFixedWidth(285); v=QVBoxLayout(f); v.setContentsMargins(0,0,0,0); quick=QGroupBox('빠른 설정'); q=QFormLayout(quick); self.quick_voice=QComboBox(); self.quick_voice.addItems(['Edge TTS - SunHi','Edge TTS - InJoon','Edge TTS - Hyunsu']); self.quick_res=QComboBox(); self.quick_res.addItems(['1080 × 1920 (세로)']); self.quick_ocr=QCheckBox(); self.quick_ocr.setChecked(True); self.quick_cut=QCheckBox(); self.quick_cut.setChecked(True); self.quick_wm=QCheckBox(); self.quick_wm.setChecked(self.s.watermark_enabled); q.addRow('TTS 음성',self.quick_voice); q.addRow('영상 해상도',self.quick_res); q.addRow('자막 제거(OCR)',self.quick_ocr); q.addRow('자동 컷 편집',self.quick_cut); q.addRow('워터마크',self.quick_wm); v.addWidget(quick)
        prev=QGroupBox('미리보기'); pv=QVBoxLayout(prev); self.preview=QLabel('선택/완성 영상의 프레임이\n여기에 표시됩니다'); self.preview.setAlignment(Qt.AlignCenter); self.preview.setMinimumHeight(360); self.preview.setStyleSheet('background:#070b13;border-radius:12px;color:#8fa2c6'); pv.addWidget(self.preview); bo=QPushButton('파일 열기'); bo.setProperty('secondary',True); bo.clicked.connect(self.open_current); pv.addWidget(bo); v.addWidget(prev,1); return f
    def queue_panel(self):
        g=QGroupBox('작업 대기열'); g.setMaximumHeight(205); v=QVBoxLayout(g); self.queue=QTableWidget(0,4); self.queue.setHorizontalHeaderLabels(['작업명','상태','진행률','시각']); self.queue.horizontalHeader().setSectionResizeMode(0,QHeaderView.Stretch); self.queue.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeToContents); self.queue.horizontalHeader().setSectionResizeMode(2,QHeaderView.ResizeToContents); self.queue.horizontalHeader().setSectionResizeMode(3,QHeaderView.ResizeToContents); v.addWidget(self.queue); return g
    def statusbar_panel(self):
        f=QFrame(); h=QHBoxLayout(f); h.setContentsMargins(16,5,16,8); self.status=QLabel('● 준비됨'); self.status.setStyleSheet('color:#73e28b'); self.progress=QProgressBar(); self.progress.setRange(0,100); self.progress.setValue(0); self.progress.setFixedWidth(220); self.diag=QLabel(); h.addWidget(self.status); h.addWidget(self.progress); h.addStretch(); h.addWidget(self.diag); return f
    def go(self,n):
        self.pages.setCurrentIndex(n)
        for i,b in enumerate(self.nav): b.setChecked(i==n)
    def home_to_source(self): self.product.setText(self.home_keyword.text()); self.go(1); self.make_plan()
    def selected(self): return [p for p,c in self.pchecks.items() if c.isChecked()]
    def say(self,x): log(x); self.status.setText('● '+x[:100])
    def queue_update(self,name,state,pct):
        row=None
        for r in range(self.queue.rowCount()):
            if self.queue.item(r,0) and self.queue.item(r,0).text()==name: row=r; break
        if row is None: row=self.queue.rowCount(); self.queue.insertRow(row); self.queue.setItem(row,0,QTableWidgetItem(name)); self.queue.setItem(row,3,QTableWidgetItem(time.strftime('%H:%M:%S')))
        self.queue.setItem(row,1,QTableWidgetItem(state)); self.queue.setItem(row,2,QTableWidgetItem(str(pct)+'%'))
    def work(self,label,fn):
        self.progress.setRange(0,0); self.bus.queued.emit(label,'진행 중',0)
        def run():
            try: fn(); self.bus.queued.emit(label,'완료',100)
            except Exception as e: self.bus.err.emit(label+'\n'+str(e)); self.bus.log.emit('오류: '+str(e)); self.bus.queued.emit(label,'오류',0)
            finally: self.progress.setRange(0,100); self.progress.setValue(100)
        threading.Thread(target=run,daemon=True).start()
    def make_plan(self):
        t=self.product.text().strip()
        if not t:return
        self.work('검색어 생성',lambda:self.bus.plan.emit(gemini_query_plan(t,self.s.gemini_api_key) if self.s.use_gemini_query_planning else rule_query_plan(t)))
    def on_plan(self,p): self.query_plan=p; self.planbox.setPlainText(json.dumps(p,ensure_ascii=False,indent=2)); self.say('검색계획 완료')
    def coupang_lookup(self):
        kw=self.product.text().strip()
        if not kw:return
        def f():
            d=coupang_search(kw,self.s.coupang_access_key,self.s.coupang_secret_key); data=d.get('data',{}); items=data.get('productData',[]) if isinstance(data,dict) else []
            self.bus.candidates.emit([{'url':x.get('productUrl',''),'title':x.get('productName',''),'platform':'Coupang'} for x in items])
        self.work('쿠팡 검색',f)
    def open_searches(self):
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
            rows=[]; end=time.time()+45
            while time.time()<end:
                try:r=RESULTS.get(timeout=1); rows.extend(r.get('items',[]))
                except:pass
            self.bus.candidates.emit(rows)
        self.work('플랫폼 자동수집',wait)
    def on_candidates(self,rows):
        self.candidates.clear(); kept=0
        for r in rows:
            t=r.get('title','') or r.get('text',''); s=relevance(self.product.text(),t); r['score']=s
            if self.s.auto_skip_low_similarity and s<self.s.min_similarity and r.get('platform')!='Coupang': continue
            it=QListWidgetItem(f"[{r.get('platform','')}] 유사도 {s}%  {t[:70]}\n{r.get('url','')}"); it.setData(Qt.UserRole,r); self.candidates.addItem(it); kept+=1
        self.say(f'후보 {kept}개 표시')
    def candidate_selected(self):
        it=self.candidates.currentItem()
        if not it:return
        r=it.data(Qt.UserRole) or {}; self.cand_url.setText(r.get('url','')); self.cand_text.setText(r.get('title','') or r.get('text','')); self.score.setText(f"유사도 {r.get('score',0)}%")
    def score_it(self): self.score.setText(f'유사도 {relevance(self.product.text(),self.cand_text.text())}%')
    def download_it(self):
        u=self.cand_url.text().strip()
        if not u:return
        self.work('영상 다운로드',lambda:self.bus.downloaded.emit(str(download_video(u,self.s.output_folder,lambda x:self.bus.log.emit(x)))))
    def on_downloaded(self,p):
        self.current_video=p; self.video.setText(p); self.thumb_video.setText(p); self.pubvideo.setText(p); self.say('다운로드 완료'); self.preview_frame(p)
    def preview_frame(self,p):
        try:
            out=str(Path(self.s.output_folder)/'_preview.jpg'); make_thumbnail(p,'',out,1.0); self.bus.thumb.emit(out)
        except Exception: pass
    def show_preview(self,p):
        pm=QPixmap(p)
        if pm.isNull():return
        self.preview.setPixmap(pm.scaled(self.preview.size(),Qt.KeepAspectRatio,Qt.SmoothTransformation))
        if hasattr(self,'thumb_preview'): self.thumb_preview.setPixmap(pm.scaled(self.thumb_preview.size(),Qt.KeepAspectRatio,Qt.SmoothTransformation))
    def pick(self,w,filt):
        p,_=QFileDialog.getOpenFileName(self,'파일 선택','',filt)
        if p:w.setText(p); self.current_video=p; self.preview_frame(p)
    def ocr_scan(self):
        p=self.video.text().strip()
        if p:self.work('OCR 스캔',lambda:self.bus.ocr.emit(subtitle_scan(p,str(Path(self.s.output_folder)/'ocr'),lambda x:self.bus.log.emit(x))))
    def on_ocr(self,x): self.ocrbox.setPlainText(json.dumps(x,ensure_ascii=False,indent=2)); self.say(f'OCR {len(x)}개 구간')
    def clean_sub(self):
        p=self.video.text().strip(); out=str(Path(self.s.output_folder)/'subtitle_clean.mp4')
        if p:self.work('자막 제거',lambda:self.bus.rendered.emit(cleanup_bottom_subtitles(p,out)))
    def make_tts(self):
        text=self.script.toPlainText().strip()
        if not text:return
        out=str(Path(self.s.output_folder)/'voice.mp3'); self.work('TTS 생성',lambda:self.bus.tts.emit(generate_tts(text,self.voice.currentText(),out)))
    def on_tts(self,p): self.current_tts=p; self.say('TTS 생성 완료')
    def auto_cut(self):
        p=self.video.text().strip(); out=str(Path(self.s.output_folder)/'auto_cut.mp4')
        if p:self.work('자동 컷 편집',lambda:self.bus.rendered.emit(auto_cut_vertical(p,out,self.target_sec.value(),self.clip_sec.value(),lambda x:self.bus.log.emit(x))))
    def render(self):
        p=self.video.text().strip(); out=self.out.text().strip()
        if p:self.work('최종 렌더',lambda:self.bus.rendered.emit(compose_vertical(p,self.current_tts or None,out)))
    def on_rendered(self,p): self.current_video=p; self.video.setText(p); self.pubvideo.setText(p); self.thumb_video.setText(p); self.say('영상 처리 완료'); self.preview_frame(p)
    def create_thumb(self):
        p=self.thumb_video.text().strip(); out=self.thumb_out.text().strip()
        if p:self.work('썸네일 생성',lambda:self.bus.thumb.emit(make_thumbnail(p,self.thumb_text.text(),out,1.0)))
    def upload_youtube(self):
        p=self.pubvideo.text().strip(); sec=self.s.youtube_client_secret_file
        if not p:return
        self.work('YouTube 업로드',lambda:self.bus.log.emit('YouTube ID: '+youtube_upload(p,sec,self.ytitle.text(),self.ydesc.toPlainText(),[x.strip() for x in self.ytags.text().split(',') if x.strip()],self.privacy.currentText())))
    def add_lnk(self): self.work('Lnk.Bio 추가',lambda:self.bus.log.emit(str(lnk_bio_add(self.s.lnkbio_client_id,self.s.lnkbio_client_secret,self.linktitle.text(),self.linkurl.text()))))
    def save(self):
        self.s.output_folder=self.setout.text().strip() or self.s.output_folder; self.s.gemini_api_key=self.gkey.text().strip(); self.s.coupang_access_key=self.cakey.text().strip(); self.s.coupang_secret_key=self.cskey.text().strip(); self.s.youtube_client_secret_file=self.ysecret.text().strip(); self.s.lnkbio_client_id=self.lid.text().strip(); self.s.lnkbio_client_secret=self.lsec.text().strip(); self.s.min_similarity=self.sim.value(); self.s.auto_skip_low_similarity=self.skip.isChecked(); self.s.use_gemini_query_planning=self.gplan.isChecked(); self.s.platform_sources=self.selected() if hasattr(self,'pchecks') else self.s.platform_sources; save_settings(self.s); self.say('설정 저장 완료')
    def refresh_diag(self):
        d=diagnostics(); txt='  |  '.join([f'{k}:{"정상" if v else "없음"}' for k,v in d.items()]); self.diag.setText(txt); self.diagbox.setPlainText(json.dumps(d,ensure_ascii=False,indent=2))
    def open_current(self):
        p=self.current_video or self.video.text().strip()
        if p and Path(p).exists(): os.startfile(p)

def main():
    app=QApplication([]); app.setStyle('Fusion'); w=Nova(); w.show(); app.exec()
if __name__=='__main__': main()
