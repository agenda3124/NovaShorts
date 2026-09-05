from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import traceback
import webbrowser
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtGui import QFont, QAction
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QLineEdit, QTextEdit, QPlainTextEdit, QComboBox,
    QCheckBox, QSpinBox, QFileDialog, QMessageBox, QTabWidget, QGroupBox,
    QListWidget, QListWidgetItem, QSplitter, QProgressBar
)

from bridge_server import start_bridge, TASKS, RESULTS
from nova_core import (
    APP_NAME, APP_VERSION, PLATFORMS, Settings, load_settings, save_settings,
    log, runtime_diagnostics, gemini_query_plan, rule_based_query_plan,
    direct_search_url, external_search_url, candidate_relevance_score,
    download_video, subtitle_scan, create_blurred_subtitle_cleanup,
    generate_tts, compose_vertical, apply_watermark, youtube_upload,
    lnk_bio_add, open_x_compose, BatchQueue
)


STYLE = """
QWidget { background:#0d1117; color:#e6edf3; font-family:'Malgun Gothic'; font-size:13px; }
QMainWindow { background:#0d1117; }
QGroupBox { border:1px solid #273142; border-radius:12px; margin-top:14px; padding:14px; font-weight:700; }
QGroupBox::title { subcontrol-origin:margin; left:14px; padding:0 6px; color:#f0f6fc; }
QLineEdit,QTextEdit,QPlainTextEdit,QComboBox,QSpinBox,QListWidget { background:#111827; border:1px solid #2f3b52; border-radius:8px; padding:7px; selection-background-color:#3157d5; }
QPushButton { background:#1f6feb; color:white; border:0; border-radius:8px; padding:8px 14px; font-weight:700; min-height:22px; }
QPushButton:hover { background:#388bfd; }
QPushButton:disabled { background:#30363d; color:#8b949e; }
QPushButton#secondary { background:#21262d; border:1px solid #30363d; }
QPushButton#danger { background:#8b1e2d; }
QTabWidget::pane { border:0; }
QTabBar::tab { background:#161b22; padding:10px 16px; margin-right:4px; border-radius:8px; }
QTabBar::tab:selected { background:#1f6feb; }
QProgressBar { background:#161b22; border:1px solid #30363d; border-radius:7px; text-align:center; min-height:18px; }
QProgressBar::chunk { background:#238636; border-radius:6px; }
"""


class Bus(QObject):
    logline = Signal(str)
    done = Signal(str)
    error = Signal(str)
    progress = Signal(int)


class NovaShortsWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = load_settings()
        self.bus = Bus()
        self.bus.logline.connect(self.append_log)
        self.bus.error.connect(self.show_error)
        self.bus.progress.connect(self.progress.setValue if hasattr(self, 'progress') else lambda x: None)
        self.batch = BatchQueue()
        self.bridge = None
        self.current_video = ""
        self.current_clean_video = ""
        self.current_tts = ""
        self.query_plan = {}

        self.setWindowTitle(f"NovaShorts Studio v{APP_VERSION}")
        self.resize(1360, 820)
        self.setMinimumSize(1100, 700)
        self.build_ui()
        self.bridge = start_bridge()
        self.refresh_diagnostics()
        self.append_log("NovaShorts 시작")
        if self.bridge:
            self.append_log("Chrome Bridge: 127.0.0.1:38471")

    def build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        main = QVBoxLayout(root)
        main.setContentsMargins(18, 14, 18, 14)
        main.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("NovaShorts Studio")
        title.setFont(QFont("Malgun Gothic", 20, QFont.Bold))
        subtitle = QLabel("상품 → 소싱 → 편집 → TTS → 게시")
        subtitle.setStyleSheet("color:#8b949e")
        header.addWidget(title)
        header.addWidget(subtitle)
        header.addStretch(1)
        self.diag_label = QLabel("진단 중...")
        header.addWidget(self.diag_label)
        main.addLayout(header)

        self.tabs = QTabWidget()
        main.addWidget(self.tabs, 1)
        self.tabs.addTab(self.make_sourcing_tab(), "① 상품/영상 소싱")
        self.tabs.addTab(self.make_edit_tab(), "② 영상 편집")
        self.tabs.addTab(self.make_publish_tab(), "③ 게시")
        self.tabs.addTab(self.make_settings_tab(), "④ 설정")
        self.tabs.addTab(self.make_log_tab(), "로그")

        footer = QHBoxLayout()
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        footer.addWidget(self.progress, 1)
        self.status = QLabel("준비")
        self.status.setMinimumWidth(300)
        footer.addWidget(self.status)
        main.addLayout(footer)

    def make_sourcing_tab(self):
        w = QWidget(); v = QVBoxLayout(w)
        top = QGroupBox("상품 입력")
        g = QGridLayout(top)
        self.product_url = QLineEdit(); self.product_url.setPlaceholderText("쿠팡 상품 URL 또는 상품 페이지 주소")
        self.product_title = QLineEdit(); self.product_title.setPlaceholderText("상품명 직접 입력 가능")
        self.btn_plan = QPushButton("검색어 생성")
        self.btn_plan.clicked.connect(self.plan_queries)
        self.btn_open = QPushButton("플랫폼 검색 열기"); self.btn_open.setObjectName("secondary")
        self.btn_open.clicked.connect(self.open_searches)
        g.addWidget(QLabel("상품 URL"),0,0); g.addWidget(self.product_url,0,1,1,3)
        g.addWidget(QLabel("상품명"),1,0); g.addWidget(self.product_title,1,1,1,2); g.addWidget(self.btn_plan,1,3)
        g.addWidget(self.btn_open,2,3)
        v.addWidget(top)

        mid = QSplitter(Qt.Horizontal)
        pbox = QGroupBox("플랫폼")
        pv = QVBoxLayout(pbox)
        self.platform_checks = {}
        for p in PLATFORMS:
            cb = QCheckBox(p); cb.setChecked(p in self.settings.platform_video_sources)
            self.platform_checks[p] = cb; pv.addWidget(cb)
        pv.addStretch(1)
        mid.addWidget(pbox)

        qbox = QGroupBox("생성된 검색 계획")
        qv = QVBoxLayout(qbox)
        self.query_text = QPlainTextEdit(); self.query_text.setPlaceholderText("검색어 생성 결과가 표시됩니다.")
        qv.addWidget(self.query_text)
        buttons = QHBoxLayout()
        self.btn_external = QPushButton("외부 검색 열기"); self.btn_external.setObjectName("secondary")
        self.btn_external.clicked.connect(self.open_external_search)
        buttons.addWidget(self.btn_external); buttons.addStretch(1)
        qv.addLayout(buttons)
        mid.addWidget(qbox)

        cbox = QGroupBox("후보 검증 / 다운로드")
        cv = QGridLayout(cbox)
        self.candidate_url = QLineEdit(); self.candidate_url.setPlaceholderText("찾은 영상 URL")
        self.candidate_text = QLineEdit(); self.candidate_text.setPlaceholderText("후보 제목/설명")
        self.score_label = QLabel("유사도 -")
        self.btn_score = QPushButton("유사도 계산"); self.btn_score.clicked.connect(self.score_candidate)
        self.btn_download = QPushButton("영상 다운로드"); self.btn_download.clicked.connect(self.download_candidate)
        cv.addWidget(self.candidate_url,0,0,1,3)
        cv.addWidget(self.candidate_text,1,0,1,3)
        cv.addWidget(self.score_label,2,0); cv.addWidget(self.btn_score,2,1); cv.addWidget(self.btn_download,2,2)
        mid.addWidget(cbox)
        mid.setStretchFactor(0,0); mid.setStretchFactor(1,2); mid.setStretchFactor(2,2)
        v.addWidget(mid,1)
        return w

    def make_edit_tab(self):
        w=QWidget(); v=QVBoxLayout(w)
        filebox=QGroupBox("소스 영상")
        fh=QHBoxLayout(filebox)
        self.video_path=QLineEdit(); self.video_path.setPlaceholderText("소스 영상 파일")
        b=QPushButton("찾기"); b.setObjectName("secondary"); b.clicked.connect(self.pick_video)
        fh.addWidget(self.video_path,1); fh.addWidget(b)
        v.addWidget(filebox)

        split=QSplitter(Qt.Horizontal)
        ocr=QGroupBox("자막/OCR")
        ov=QVBoxLayout(ocr)
        self.ocr_result=QPlainTextEdit(); self.ocr_result.setPlaceholderText("중국어/한국어/영어 OCR 결과")
        ob=QHBoxLayout()
        btn_scan=QPushButton("OCR 스캔"); btn_scan.clicked.connect(self.run_ocr_scan)
        btn_clean=QPushButton("자막 영역 제거"); btn_clean.clicked.connect(self.run_cleanup)
        ob.addWidget(btn_scan); ob.addWidget(btn_clean)
        ov.addLayout(ob); ov.addWidget(self.ocr_result)
        split.addWidget(ocr)

        tts=QGroupBox("대본 / TTS")
        tv=QVBoxLayout(tts)
        self.script_text=QPlainTextEdit(); self.script_text.setPlaceholderText("한국어 대본 입력")
        row=QHBoxLayout(); self.voice_combo=QComboBox(); self.voice_combo.addItems(["ko-KR-SunHiNeural","ko-KR-InJoonNeural","ko-KR-HyunsuNeural"]); self.voice_combo.setCurrentText(self.settings.tts_voice)
        btn_tts=QPushButton("TTS 생성"); btn_tts.clicked.connect(self.run_tts)
        row.addWidget(self.voice_combo,1); row.addWidget(btn_tts)
        tv.addWidget(self.script_text); tv.addLayout(row)
        split.addWidget(tts)

        render=QGroupBox("최종 렌더")
        rv=QVBoxLayout(render)
        self.render_output=QLineEdit(str(Path(self.settings.output_folder)/"final_short.mp4"))
        self.chk_vertical=QCheckBox("1080×1920 세로 영상"); self.chk_vertical.setChecked(True)
        self.chk_watermark=QCheckBox("워터마크 적용"); self.chk_watermark.setChecked(self.settings.watermark_enabled)
        self.watermark_text=QLineEdit(self.settings.watermark_channel_name); self.watermark_text.setPlaceholderText("워터마크 문구")
        btn_render=QPushButton("최종 영상 만들기"); btn_render.clicked.connect(self.run_render)
        rv.addWidget(self.render_output); rv.addWidget(self.chk_vertical); rv.addWidget(self.chk_watermark); rv.addWidget(self.watermark_text); rv.addStretch(1); rv.addWidget(btn_render)
        split.addWidget(render)
        v.addWidget(split,1)
        return w

    def make_publish_tab(self):
        w=QWidget(); v=QVBoxLayout(w)
        y=QGroupBox("YouTube 업로드")
        g=QGridLayout(y)
        self.pub_video=QLineEdit(); self.pub_video.setPlaceholderText("업로드할 영상")
        bf=QPushButton("찾기"); bf.setObjectName("secondary"); bf.clicked.connect(lambda:self.pick_file_into(self.pub_video,"Video (*.mp4 *.mov *.mkv)"))
        self.yt_title=QLineEdit(); self.yt_title.setPlaceholderText("제목")
        self.yt_desc=QPlainTextEdit(); self.yt_desc.setPlaceholderText("설명")
        self.yt_tags=QLineEdit(); self.yt_tags.setPlaceholderText("태그, 쉼표 구분")
        self.yt_privacy=QComboBox(); self.yt_privacy.addItems(["private","unlisted","public"])
        bu=QPushButton("YouTube 업로드"); bu.clicked.connect(self.run_youtube_upload)
        g.addWidget(self.pub_video,0,0,1,3); g.addWidget(bf,0,3)
        g.addWidget(self.yt_title,1,0,1,4); g.addWidget(self.yt_desc,2,0,1,4); g.addWidget(self.yt_tags,3,0,1,3); g.addWidget(self.yt_privacy,3,3); g.addWidget(bu,4,3)
        v.addWidget(y)

        share=QGroupBox("링크 / X")
        sg=QGridLayout(share)
        self.share_title=QLineEdit(); self.share_title.setPlaceholderText("링크 제목")
        self.share_url=QLineEdit(); self.share_url.setPlaceholderText("상품/프로필 링크")
        self.x_text=QLineEdit(); self.x_text.setPlaceholderText("X 게시 문구")
        b_lnk=QPushButton("Lnk.Bio 추가"); b_lnk.clicked.connect(self.run_lnk)
        b_x=QPushButton("X 작성창 열기"); b_x.clicked.connect(lambda: open_x_compose(self.x_text.text()))
        sg.addWidget(self.share_title,0,0,1,2); sg.addWidget(self.share_url,1,0,1,2); sg.addWidget(b_lnk,2,0); sg.addWidget(self.x_text,3,0,1,2); sg.addWidget(b_x,4,0)
        v.addWidget(share); v.addStretch(1)
        return w

    def make_settings_tab(self):
        w=QWidget(); v=QVBoxLayout(w)
        s=QGroupBox("API / 저장 / 소싱 설정")
        g=QGridLayout(s)
        self.set_output=QLineEdit(self.settings.output_folder); bo=QPushButton("폴더"); bo.setObjectName("secondary"); bo.clicked.connect(self.pick_output)
        self.set_gemini=QLineEdit(self.settings.gemini_api_key); self.set_gemini.setEchoMode(QLineEdit.Password)
        self.set_coupang_a=QLineEdit(self.settings.coupang_access_key); self.set_coupang_a.setEchoMode(QLineEdit.Password)
        self.set_coupang_s=QLineEdit(self.settings.coupang_secret_key); self.set_coupang_s.setEchoMode(QLineEdit.Password)
        self.set_similarity=QSpinBox(); self.set_similarity.setRange(0,100); self.set_similarity.setValue(self.settings.sourcing_min_similarity_percent)
        self.set_skip=QCheckBox("낮은 유사도 자동 제외"); self.set_skip.setChecked(self.settings.sourcing_auto_skip_low_similarity)
        self.set_gemini_plan=QCheckBox("Gemini 검색어 계획 사용"); self.set_gemini_plan.setChecked(self.settings.sourcing_use_gemini_query_planning)
        self.set_yt_secret=QLineEdit(self.settings.youtube_client_secret_file); by=QPushButton("파일"); by.setObjectName("secondary"); by.clicked.connect(lambda:self.pick_file_into(self.set_yt_secret,"JSON (*.json)"))
        self.set_lnk_id=QLineEdit(self.settings.lnkbio_client_id)
        self.set_lnk_secret=QLineEdit(self.settings.lnkbio_client_secret); self.set_lnk_secret.setEchoMode(QLineEdit.Password)
        save=QPushButton("설정 저장"); save.clicked.connect(self.save_all_settings)
        labels=[("출력 폴더",self.set_output,bo),("Gemini API Key",self.set_gemini,None),("Coupang Access Key",self.set_coupang_a,None),("Coupang Secret Key",self.set_coupang_s,None),("최소 유사도",self.set_similarity,None),("YouTube client_secret.json",self.set_yt_secret,by),("Lnk.Bio Client ID",self.set_lnk_id,None),("Lnk.Bio Client Secret",self.set_lnk_secret,None)]
        r=0
        for name,widget,extra in labels:
            g.addWidget(QLabel(name),r,0); g.addWidget(widget,r,1,1,2)
            if extra: g.addWidget(extra,r,3)
            r+=1
        g.addWidget(self.set_skip,r,1); g.addWidget(self.set_gemini_plan,r,2); r+=1; g.addWidget(save,r,3)
        v.addWidget(s)

        d=QGroupBox("런타임 진단")
        dv=QVBoxLayout(d)
        self.diag_text=QPlainTextEdit(); self.diag_text.setReadOnly(True)
        bd=QPushButton("다시 진단"); bd.setObjectName("secondary"); bd.clicked.connect(self.refresh_diagnostics)
        dv.addWidget(self.diag_text); dv.addWidget(bd)
        v.addWidget(d,1)
        return w

    def make_log_tab(self):
        w=QWidget(); v=QVBoxLayout(w)
        self.log_text=QPlainTextEdit(); self.log_text.setReadOnly(True)
        v.addWidget(self.log_text)
        row=QHBoxLayout(); b=QPushButton("로그 폴더 열기"); b.setObjectName("secondary"); b.clicked.connect(self.open_log_folder); row.addWidget(b); row.addStretch(1); v.addLayout(row)
        return w

    def append_log(self, text:str):
        log(text)
        if hasattr(self,'log_text'): self.log_text.appendPlainText(text)
        if hasattr(self,'status'): self.status.setText(text[:120])

    def show_error(self, text:str):
        self.append_log("오류: "+text)
        QMessageBox.critical(self,"NovaShorts",text)

    def async_job(self, name, fn):
        self.progress.setRange(0,0); self.status.setText(name)
        def run():
            try:
                fn()
            except Exception as e:
                self.bus.error.emit(f"{name}: {e}")
                log(traceback.format_exc())
            finally:
                self.bus.progress.emit(100)
        def wrap():
            run(); self.progress.setRange(0,100)
        threading.Thread(target=wrap,daemon=True).start()

    def plan_queries(self):
        title=self.product_title.text().strip()
        if not title:
            QMessageBox.information(self,"상품명 필요","상품명을 입력해 주세요."); return
        def work():
            if self.settings.sourcing_use_gemini_query_planning and self.settings.gemini_api_key:
                plan=gemini_query_plan(title,self.settings.gemini_api_key)
            else:
                plan=rule_based_query_plan(title)
            self.query_plan=plan
            self.bus.logline.emit("검색어 계획 생성 완료")
            self.query_text.setPlainText(json.dumps(plan,ensure_ascii=False,indent=2))
        self.async_job("검색어 생성",work)

    def selected_platforms(self):
        return [p for p,c in self.platform_checks.items() if c.isChecked()]

    def open_searches(self):
        if not self.query_plan:
            self.plan_queries(); return
        for p in self.selected_platforms():
            kws=self.query_plan.get(p,[])
            if kws: webbrowser.open(direct_search_url(p,kws[0]))

    def open_external_search(self):
        if not self.query_plan: return
        for p in self.selected_platforms():
            kws=self.query_plan.get(p,[])
            if kws: webbrowser.open(external_search_url(p,kws[0]))

    def score_candidate(self):
        title=self.product_title.text().strip(); text=self.candidate_text.text().strip()
        score=candidate_relevance_score(title,text)
        self.score_label.setText(f"유사도 {score}%")
        if self.settings.sourcing_auto_skip_low_similarity and score < self.settings.sourcing_min_similarity_percent:
            self.score_label.setStyleSheet("color:#f85149;font-weight:700")
        else: self.score_label.setStyleSheet("color:#3fb950;font-weight:700")

    def download_candidate(self):
        url=self.candidate_url.text().strip()
        if not url: return
        out=self.settings.output_folder
        def work():
            path=download_video(url,out,lambda m:self.bus.logline.emit(m))
            self.current_video=str(path); self.video_path.setText(str(path)); self.pub_video.setText(str(path)); self.bus.logline.emit(f"다운로드 완료: {path}")
        self.async_job("영상 다운로드",work)

    def pick_video(self): self.pick_file_into(self.video_path,"Video (*.mp4 *.mov *.mkv *.webm)")
    def pick_file_into(self, widget, filt):
        p,_=QFileDialog.getOpenFileName(self,"파일 선택","",filt)
        if p: widget.setText(p)
    def pick_output(self):
        p=QFileDialog.getExistingDirectory(self,"출력 폴더",self.set_output.text())
        if p: self.set_output.setText(p)

    def run_ocr_scan(self):
        video=self.video_path.text().strip()
        if not video: return
        workdir=str(Path(self.settings.output_folder)/"ocr_work")
        def work():
            hits=subtitle_scan(video,workdir,lambda m:self.bus.logline.emit(m))
            self.ocr_result.setPlainText(json.dumps(hits,ensure_ascii=False,indent=2))
            self.bus.logline.emit(f"OCR 완료 · {len(hits)}개 텍스트 프레임")
        self.async_job("OCR 분석",work)

    def run_cleanup(self):
        video=self.video_path.text().strip()
        if not video: return
        out=str(Path(self.settings.output_folder)/"subtitle_clean.mp4")
        def work():
            create_blurred_subtitle_cleanup(video,out,62)
            self.current_clean_video=out; self.video_path.setText(out); self.bus.logline.emit("자막 영역 제거 완료: "+out)
        self.async_job("자막 제거",work)

    def run_tts(self):
        text=self.script_text.toPlainText().strip()
        if not text: return
        out=str(Path(self.settings.output_folder)/"tts.mp3")
        voice=self.voice_combo.currentText()
        def work():
            generate_tts(text,voice,out); self.current_tts=out; self.bus.logline.emit("TTS 생성 완료: "+out)
        self.async_job("TTS 생성",work)

    def run_render(self):
        video=self.video_path.text().strip(); out=self.render_output.text().strip()
        if not video or not out: return
        def work():
            source=video
            temp=str(Path(out).with_name("_render_base.mp4"))
            compose_vertical(source,self.current_tts or None,temp)
            if self.chk_watermark.isChecked() and self.watermark_text.text().strip():
                apply_watermark(temp,self.watermark_text.text().strip(),out,self.settings.watermark_position)
                try: os.remove(temp)
                except: pass
            else:
                os.replace(temp,out)
            self.pub_video.setText(out); self.bus.logline.emit("최종 렌더 완료: "+out)
        self.async_job("최종 렌더",work)

    def run_youtube_upload(self):
        video=self.pub_video.text().strip(); secret=self.settings.youtube_client_secret_file
        if not video or not secret:
            QMessageBox.information(self,"설정 필요","영상과 YouTube client_secret.json을 설정해 주세요."); return
        title=self.yt_title.text().strip() or "NovaShorts"
        desc=self.yt_desc.toPlainText(); tags=[x.strip() for x in self.yt_tags.text().split(',') if x.strip()]
        privacy=self.yt_privacy.currentText()
        def work():
            vid=youtube_upload(video,secret,title,desc,tags,privacy); self.bus.logline.emit("YouTube 업로드 완료: "+vid)
        self.async_job("YouTube 업로드",work)

    def run_lnk(self):
        title=self.share_title.text().strip(); url=self.share_url.text().strip()
        if not title or not url: return
        def work():
            r=lnk_bio_add(self.settings.lnkbio_client_id,self.settings.lnkbio_client_secret,title,url); self.bus.logline.emit("Lnk.Bio 등록 완료: "+str(r)[:400])
        self.async_job("Lnk.Bio 등록",work)

    def save_all_settings(self):
        s=self.settings
        s.output_folder=self.set_output.text().strip()
        s.gemini_api_key=self.set_gemini.text().strip()
        s.coupang_access_key=self.set_coupang_a.text().strip()
        s.coupang_secret_key=self.set_coupang_s.text().strip()
        s.sourcing_min_similarity_percent=self.set_similarity.value()
        s.sourcing_auto_skip_low_similarity=self.set_skip.isChecked()
        s.sourcing_use_gemini_query_planning=self.set_gemini_plan.isChecked()
        s.youtube_client_secret_file=self.set_yt_secret.text().strip()
        s.lnkbio_client_id=self.set_lnk_id.text().strip(); s.lnkbio_client_secret=self.set_lnk_secret.text().strip()
        s.tts_voice=self.voice_combo.currentText(); s.platform_video_sources=self.selected_platforms()
        s.watermark_enabled=self.chk_watermark.isChecked(); s.watermark_channel_name=self.watermark_text.text().strip()
        save_settings(s); Path(s.output_folder).mkdir(parents=True,exist_ok=True); self.append_log("설정 저장 완료")

    def refresh_diagnostics(self):
        d=runtime_diagnostics()
        if hasattr(self,'diag_text'): self.diag_text.setPlainText(json.dumps(d,ensure_ascii=False,indent=2))
        ok=sum(bool(v) for v in d.values()); self.diag_label.setText(f"런타임 {ok}/{len(d)}")
        self.diag_label.setStyleSheet("color:#3fb950" if ok==len(d) else "color:#d29922")

    def open_log_folder(self):
        p=Path.home()/".novashorts"/"logs"; p.mkdir(parents=True,exist_ok=True)
        os.startfile(str(p)) if os.name=='nt' else webbrowser.open(p.as_uri())

    def closeEvent(self,event):
        try:
            if self.bridge: self.bridge.shutdown()
            self.batch.stop()
        finally: event.accept()


def main():
    app=QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setStyleSheet(STYLE)
    win=NovaShortsWindow(); win.show()
    sys.exit(app.exec())


if __name__=="__main__":
    main()
