from __future__ import annotations
import json, os, sys, threading, time, webbrowser
from pathlib import Path
from PySide6.QtCore import Qt, QObject, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import *

from engine import *
from bridge import start_bridge, TASKS, RESULTS

CSS='''
QWidget{background:#0d1117;color:#e6edf3;font-family:"Malgun Gothic";font-size:13px}QGroupBox{border:1px solid #273142;border-radius:12px;margin-top:13px;padding:13px;font-weight:700}QGroupBox::title{subcontrol-origin:margin;left:12px;padding:0 6px}QLineEdit,QPlainTextEdit,QComboBox,QSpinBox,QListWidget{background:#111827;border:1px solid #2f3b52;border-radius:8px;padding:7px}QPushButton{background:#1f6feb;color:white;border:0;border-radius:8px;padding:8px 13px;font-weight:700;min-height:24px}QPushButton:hover{background:#388bfd}QPushButton[secondary="true"]{background:#21262d;border:1px solid #30363d}QTabBar::tab{background:#161b22;padding:10px 15px;margin-right:4px;border-radius:8px}QTabBar::tab:selected{background:#1f6feb}QProgressBar{background:#161b22;border:1px solid #30363d;border-radius:7px;text-align:center}QProgressBar::chunk{background:#238636;border-radius:6px}
'''

class Bus(QObject):
 log=Signal(str);err=Signal(str);plan=Signal(dict);downloaded=Signal(str);ocr=Signal(list);tts=Signal(str);rendered=Signal(str);candidates=Signal(list)

class Window(QMainWindow):
 def __init__(self):
  super().__init__();self.s=load_settings();self.bus=Bus();self.bridge=start_bridge();self.query_plan={};self.current_tts='';self.current_video='';self.build();self.bind();self.refresh_diag();self.say('NovaShorts v1.5 시작')
 def bind(self):
  self.bus.log.connect(self.say);self.bus.err.connect(lambda x:QMessageBox.critical(self,'NovaShorts',x));self.bus.plan.connect(self.on_plan);self.bus.downloaded.connect(self.on_downloaded);self.bus.ocr.connect(lambda x:self.ocrbox.setPlainText(json.dumps(x,ensure_ascii=False,indent=2)));self.bus.tts.connect(self.on_tts);self.bus.rendered.connect(self.on_rendered);self.bus.candidates.connect(self.on_candidates)
 def build(self):
  self.setWindowTitle('NovaShorts Studio v1.5');self.resize(1360,820);self.setMinimumSize(1100,700)
  r=QWidget();self.setCentralWidget(r);v=QVBoxLayout(r);v.setContentsMargins(18,14,18,14)
  h=QHBoxLayout();t=QLabel('NovaShorts Studio');t.setFont(QFont('Malgun Gothic',20,QFont.Bold));h.addWidget(t);h.addWidget(QLabel('상품 → 소싱 → 편집 → 게시'));h.addStretch();self.diag=QLabel();h.addWidget(self.diag);v.addLayout(h)
  self.tabs=QTabWidget();v.addWidget(self.tabs,1);self.tabs.addTab(self.tab_source(),'① 상품/영상 소싱');self.tabs.addTab(self.tab_edit(),'② 영상 편집');self.tabs.addTab(self.tab_publish(),'③ 게시');self.tabs.addTab(self.tab_settings(),'④ 설정');self.tabs.addTab(self.tab_log(),'로그')
  f=QHBoxLayout();self.progress=QProgressBar();self.progress.setRange(0,100);self.progress.setValue(0);self.status=QLabel('준비');f.addWidget(self.progress,1);f.addWidget(self.status);v.addLayout(f)
 def group(self,title):g=QGroupBox(title);return g
 def sec(self,b):b.setProperty('secondary',True);return b
 def tab_source(self):
  w=QWidget();v=QVBoxLayout(w);g=self.group('상품 입력 / 쿠팡');q=QGridLayout(g);self.product_url=QLineEdit();self.product_url.setPlaceholderText('쿠팡 URL 또는 상품 페이지 URL');self.product=QLineEdit();self.product.setPlaceholderText('상품명');b1=QPushButton('검색어 생성');b1.clicked.connect(self.make_plan);bcp=QPushButton('쿠팡 API 검색');bcp.clicked.connect(self.coupang_lookup);q.addWidget(QLabel('URL'),0,0);q.addWidget(self.product_url,0,1,1,3);q.addWidget(QLabel('상품명'),1,0);q.addWidget(self.product,1,1,1,2);q.addWidget(b1,1,3);q.addWidget(bcp,2,3);v.addWidget(g)
  split=QSplitter(Qt.Horizontal);pg=self.group('플랫폼');pv=QVBoxLayout(pg);self.pchecks={}
  for p in PLATFORMS:cb=QCheckBox(p);cb.setChecked(p in self.s.platform_sources);self.pchecks[p]=cb;pv.addWidget(cb)
  pv.addStretch();split.addWidget(pg)
  qg=self.group('검색 계획');qv=QVBoxLayout(qg);self.planbox=QPlainTextEdit();qv.addWidget(self.planbox);rh=QHBoxLayout();bo=QPushButton('검색 페이지 열기');bo.clicked.connect(self.open_searches);ba=QPushButton('Chrome Bridge 자동수집');ba.clicked.connect(self.bridge_collect);rh.addWidget(bo);rh.addWidget(ba);qv.addLayout(rh);split.addWidget(qg)
  cg=self.group('후보');cv=QVBoxLayout(cg);self.candidates=QListWidget();self.candidates.itemSelectionChanged.connect(self.candidate_selected);self.cand_url=QLineEdit();self.cand_text=QLineEdit();self.cand_text.setPlaceholderText('후보 제목/설명');rr=QHBoxLayout();self.score=QLabel('유사도 -');bs=QPushButton('유사도 계산');bs.clicked.connect(self.score_it);bd=QPushButton('다운로드');bd.clicked.connect(self.download_it);rr.addWidget(self.score);rr.addWidget(bs);rr.addWidget(bd);cv.addWidget(self.candidates);cv.addWidget(self.cand_url);cv.addWidget(self.cand_text);cv.addLayout(rr);split.addWidget(cg);split.setStretchFactor(1,2);split.setStretchFactor(2,2);v.addWidget(split,1);return w
 def tab_edit(self):
  w=QWidget();v=QVBoxLayout(w);g=self.group('소스 영상');h=QHBoxLayout(g);self.video=QLineEdit();bb=QPushButton('찾기');bb.clicked.connect(lambda:self.pick(self.video,'Video (*.mp4 *.mov *.mkv *.webm)'));h.addWidget(self.video,1);h.addWidget(bb);v.addWidget(g)
  sp=QSplitter(Qt.Horizontal);og=self.group('OCR / 자막 제거');ov=QVBoxLayout(og);self.ocrbox=QPlainTextEdit();r=QHBoxLayout();bscan=QPushButton('OCR 스캔');bscan.clicked.connect(self.ocr_scan);bclean=QPushButton('하단 자막 제거');bclean.clicked.connect(self.clean_sub);r.addWidget(bscan);r.addWidget(bclean);ov.addLayout(r);ov.addWidget(self.ocrbox);sp.addWidget(og)
  tg=self.group('대본 / TTS');tv=QVBoxLayout(tg);self.script=QPlainTextEdit();self.script.setPlaceholderText('한국어 대본');self.voice=QComboBox();self.voice.addItems(['ko-KR-SunHiNeural','ko-KR-InJoonNeural','ko-KR-HyunsuNeural']);self.voice.setCurrentText(self.s.tts_voice);bt=QPushButton('TTS 생성');bt.clicked.connect(self.make_tts);tv.addWidget(self.script);tv.addWidget(self.voice);tv.addWidget(bt);sp.addWidget(tg)
  rg=self.group('최종 렌더');rv=QVBoxLayout(rg);self.out=QLineEdit(str(Path(self.s.output_folder)/'final_short.mp4'));self.wm=QCheckBox('워터마크');self.wm.setChecked(self.s.watermark_enabled);self.wmtext=QLineEdit(self.s.watermark_text);br=QPushButton('1080×1920 최종영상 만들기');br.clicked.connect(self.render);rv.addWidget(self.out);rv.addWidget(self.wm);rv.addWidget(self.wmtext);rv.addStretch();rv.addWidget(br);sp.addWidget(rg);v.addWidget(sp,1);return w
 def tab_publish(self):
  w=QWidget();v=QVBoxLayout(w);yg=self.group('YouTube');q=QGridLayout(yg);self.pubvideo=QLineEdit();bp=QPushButton('찾기');bp.clicked.connect(lambda:self.pick(self.pubvideo,'Video (*.mp4 *.mov *.mkv)'));self.ytitle=QLineEdit();self.ytitle.setPlaceholderText('제목');self.ydesc=QPlainTextEdit();self.ydesc.setPlaceholderText('설명');self.ytags=QLineEdit();self.ytags.setPlaceholderText('태그,쉼표');self.privacy=QComboBox();self.privacy.addItems(['private','unlisted','public']);bu=QPushButton('YouTube 업로드');bu.clicked.connect(self.upload_youtube);q.addWidget(self.pubvideo,0,0,1,3);q.addWidget(bp,0,3);q.addWidget(self.ytitle,1,0,1,4);q.addWidget(self.ydesc,2,0,1,4);q.addWidget(self.ytags,3,0,1,3);q.addWidget(self.privacy,3,3);q.addWidget(bu,4,3);v.addWidget(yg)
  sg=self.group('Lnk.Bio / X');s=QGridLayout(sg);self.linktitle=QLineEdit();self.linktitle.setPlaceholderText('링크 제목');self.linkurl=QLineEdit();self.linkurl.setPlaceholderText('상품 링크');bl=QPushButton('Lnk.Bio 추가');bl.clicked.connect(self.add_lnk);self.xtext=QLineEdit();self.xtext.setPlaceholderText('X 게시문');bx=QPushButton('X 작성창');bx.clicked.connect(lambda:open_x(self.xtext.text()));s.addWidget(self.linktitle,0,0,1,2);s.addWidget(self.linkurl,1,0,1,2);s.addWidget(bl,2,0);s.addWidget(self.xtext,3,0,1,2);s.addWidget(bx,4,0);v.addWidget(sg);v.addStretch();return w
 def tab_settings(self):
  w=QWidget();v=QVBoxLayout(w);g=self.group('연동 / 소싱 설정');q=QGridLayout(g);self.setout=QLineEdit(self.s.output_folder);bout=QPushButton('폴더');bout.clicked.connect(self.pick_out);self.gkey=QLineEdit(self.s.gemini_api_key);self.gkey.setEchoMode(QLineEdit.Password);self.cakey=QLineEdit(self.s.coupang_access_key);self.cakey.setEchoMode(QLineEdit.Password);self.cskey=QLineEdit(self.s.coupang_secret_key);self.cskey.setEchoMode(QLineEdit.Password);self.sim=QSpinBox();self.sim.setRange(0,100);self.sim.setValue(self.s.min_similarity);self.skip=QCheckBox('저유사도 자동 제외');self.skip.setChecked(self.s.auto_skip_low_similarity);self.gplan=QCheckBox('Gemini 검색계획');self.gplan.setChecked(self.s.use_gemini_query_planning);self.ysecret=QLineEdit(self.s.youtube_client_secret_file);by=QPushButton('파일');by.clicked.connect(lambda:self.pick(self.ysecret,'JSON (*.json)'));self.lid=QLineEdit(self.s.lnkbio_client_id);self.lsec=QLineEdit(self.s.lnkbio_client_secret);self.lsec.setEchoMode(QLineEdit.Password)
  rows=[('출력 폴더',self.setout,bout),('Gemini API Key',self.gkey,None),('Coupang Access Key',self.cakey,None),('Coupang Secret Key',self.cskey,None),('최소 유사도',self.sim,None),('YouTube client_secret.json',self.ysecret,by),('Lnk.Bio Client ID',self.lid,None),('Lnk.Bio Client Secret',self.lsec,None)]
  for i,(n,x,b) in enumerate(rows):q.addWidget(QLabel(n),i,0);q.addWidget(x,i,1,1,2);b and q.addWidget(b,i,3)
  q.addWidget(self.skip,len(rows),1);q.addWidget(self.gplan,len(rows),2);bs=QPushButton('설정 저장');bs.clicked.connect(self.save);q.addWidget(bs,len(rows)+1,3);v.addWidget(g)
  dg=self.group('런타임 진단');dv=QVBoxLayout(dg);self.diagbox=QPlainTextEdit();self.diagbox.setReadOnly(True);bd=QPushButton('다시 진단');bd.clicked.connect(self.refresh_diag);dv.addWidget(self.diagbox);dv.addWidget(bd);v.addWidget(dg,1);return w
 def tab_log(self):w=QWidget();v=QVBoxLayout(w);self.logbox=QPlainTextEdit();self.logbox.setReadOnly(True);v.addWidget(self.logbox);return w
 def selected(self):return [p for p,c in self.pchecks.items() if c.isChecked()]
 def say(self,x):log(x);self.logbox.appendPlainText(x);self.status.setText(x[:120])
 def work(self,label,fn):
  self.progress.setRange(0,0);self.status.setText(label)
  def go():
   try:fn()
   except Exception as e:self.bus.err.emit(label+'\n'+str(e));self.bus.log.emit('오류: '+str(e))
   finally:self.progress.setRange(0,100);self.progress.setValue(100)
  threading.Thread(target=go,daemon=True).start()
 def make_plan(self):
  title=self.product.text().strip()
  if not title:return
  self.work('검색어 생성',lambda:self.bus.plan.emit(gemini_query_plan(title,self.s.gemini_api_key) if self.s.use_gemini_query_planning else rule_query_plan(title)))
 def on_plan(self,p):self.query_plan=p;self.planbox.setPlainText(json.dumps(p,ensure_ascii=False,indent=2));self.say('검색어 계획 완료')
 def coupang_lookup(self):
  kw=self.product.text().strip()
  if not kw:return
  def f():
   d=coupang_search(kw,self.s.coupang_access_key,self.s.coupang_secret_key);items=d.get('data',{}).get('productData',[]) or d.get('data',[]);self.bus.candidates.emit([{'url':x.get('productUrl',''),'title':x.get('productName','')} for x in items])
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
   for kw in (self.query_plan.get(p) or [])[:2]:TASKS.put({'type':'collect_links','platform':p,'url':direct_search_url(p,kw),'keyword':kw});count+=1
  self.say(f'Chrome Bridge 작업 {count}개 전송')
  def wait():
   end=time.time()+45;rows=[]
   while time.time()<end:
    try:r=RESULTS.get(timeout=1);rows.extend(r.get('items',[]))
    except:pass
   self.bus.candidates.emit(rows)
  threading.Thread(target=wait,daemon=True).start()
 def on_candidates(self,rows):
  self.candidates.clear()
  for r in rows:
   u=r.get('url','');t=r.get('title','') or r.get('text','');it=QListWidgetItem((t[:70]+'\n'+u) if t else u);it.setData(Qt.UserRole,r);self.candidates.addItem(it)
  self.say(f'후보 {len(rows)}개')
 def candidate_selected(self):
  it=self.candidates.currentItem()
  if not it:return
  r=it.data(Qt.UserRole) or {};self.cand_url.setText(r.get('url',''));self.cand_text.setText(r.get('title','') or r.get('text',''))
 def score_it(self):
  s=relevance(self.product.text(),self.cand_text.text());self.score.setText(f'유사도 {s}%');self.score.setStyleSheet('color:#3fb950;font-weight:700' if s>=self.s.min_similarity else 'color:#f85149;font-weight:700')
 def download_it(self):
  u=self.cand_url.text().strip()
  if not u:return
  self.work('영상 다운로드',lambda:self.bus.downloaded.emit(str(download_video(u,self.s.output_folder,lambda x:self.bus.log.emit(x)))))
 def on_downloaded(self,p):self.current_video=p;self.video.setText(p);self.pubvideo.setText(p);self.say('다운로드 완료: '+p)
 def pick(self,widget,filt):
  p,_=QFileDialog.getOpenFileName(self,'파일 선택','',filt)
  if p:widget.setText(p)
 def pick_out(self):
  p=QFileDialog.getExistingDirectory(self,'출력 폴더',self.setout.text())
  if p:self.setout.setText(p)
 def ocr_scan(self):
  p=self.video.text().strip()
  if p:self.work('OCR 스캔',lambda:self.bus.ocr.emit(subtitle_scan(p,str(Path(self.s.output_folder)/'ocr_work'),lambda x:self.bus.log.emit(x))))
 def clean_sub(self):
  p=self.video.text().strip();o=str(Path(self.s.output_folder)/'subtitle_clean.mp4')
  if p:self.work('자막 제거',lambda:(cleanup_bottom_subtitles(p,o,62),self.bus.downloaded.emit(o)))
 def make_tts(self):
  t=self.script.toPlainText().strip();o=str(Path(self.s.output_folder)/'tts.mp3')
  if t:self.work('TTS 생성',lambda:(generate_tts(t,self.voice.currentText(),o),self.bus.tts.emit(o)))
 def on_tts(self,p):self.current_tts=p;self.say('TTS 완료: '+p)
 def render(self):
  p=self.video.text().strip();o=self.out.text().strip();tmp=str(Path(o).with_name('_base.mp4'))
  def f():
   compose_vertical(p,self.current_tts or None,tmp)
   if self.wm.isChecked() and self.wmtext.text().strip():watermark(tmp,self.wmtext.text().strip(),o,self.s.watermark_position);os.remove(tmp)
   else:os.replace(tmp,o)
   self.bus.rendered.emit(o)
  if p and o:self.work('최종 렌더',f)
 def on_rendered(self,p):self.pubvideo.setText(p);self.say('렌더 완료: '+p)
 def upload_youtube(self):
  p=self.pubvideo.text().strip();secret=self.s.youtube_client_secret_file
  if not p or not secret:return QMessageBox.information(self,'설정 필요','영상과 YouTube client_secret.json을 설정하세요.')
  self.work('YouTube 업로드',lambda:self.bus.log.emit('YouTube video id: '+youtube_upload(p,secret,self.ytitle.text().strip() or 'NovaShorts',self.ydesc.toPlainText(),[x.strip() for x in self.ytags.text().split(',') if x.strip()],self.privacy.currentText())))
 def add_lnk(self):
  self.work('Lnk.Bio 등록',lambda:self.bus.log.emit('Lnk.Bio: '+str(lnk_bio_add(self.s.lnkbio_client_id,self.s.lnkbio_client_secret,self.linktitle.text(),self.linkurl.text()))[:500]))
 def save(self):
  self.s.output_folder=self.setout.text().strip();self.s.gemini_api_key=self.gkey.text().strip();self.s.coupang_access_key=self.cakey.text().strip();self.s.coupang_secret_key=self.cskey.text().strip();self.s.min_similarity=self.sim.value();self.s.auto_skip_low_similarity=self.skip.isChecked();self.s.use_gemini_query_planning=self.gplan.isChecked();self.s.youtube_client_secret_file=self.ysecret.text().strip();self.s.lnkbio_client_id=self.lid.text().strip();self.s.lnkbio_client_secret=self.lsec.text().strip();self.s.platform_sources=self.selected();self.s.tts_voice=self.voice.currentText();self.s.watermark_enabled=self.wm.isChecked();self.s.watermark_text=self.wmtext.text().strip();save_settings(self.s);Path(self.s.output_folder).mkdir(parents=True,exist_ok=True);self.say('설정 저장 완료')
 def refresh_diag(self):
  d=diagnostics();self.diagbox.setPlainText(json.dumps(d,ensure_ascii=False,indent=2));ok=sum(bool(x) for x in d.values());self.diag.setText(f'런타임 {ok}/{len(d)}');self.diag.setStyleSheet('color:#3fb950' if ok==len(d) else 'color:#d29922')
 def closeEvent(self,e):
  if self.bridge:self.bridge.shutdown()
  e.accept()

def main():
 app=QApplication(sys.argv);app.setApplicationName(APP_NAME);app.setStyleSheet(CSS);w=Window();w.show();sys.exit(app.exec())
if __name__=='__main__':main()
