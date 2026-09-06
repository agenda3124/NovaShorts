from __future__ import annotations

import json
import uuid
from pathlib import Path

import main_v119 as base
import main_v113
from PySide6.QtCore import QObject, Signal, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import *

from bridge import TASKS, extension_recent, wait_for_result
from engine import download_video, save_settings
from pipeline_v120 import (
    compose_final,
    generate_tts_bundle,
    run_processing_pipeline,
    smart_subtitle_remove,
)

VERSION = '1.20'

for mod in [base, getattr(base, 'base', None), getattr(getattr(base, 'base', None), 'base', None)]:
    try:
        if mod is not None:
            mod.VERSION = VERSION
    except Exception:
        pass

V120_CSS = r'''
QFrame#autoPipeline120 {
    background:#111b30;
    border:1px solid #36517a;
    border-radius:12px;
}
QLabel#autoTitle120 {
    background:transparent;
    color:#f5f8ff;
    font-size:14px;
    font-weight:850;
}
QLabel#autoStatus120 {
    background:transparent;
    color:#8fa4c7;
    font-size:11px;
}
QPushButton[autoPrimary120="true"] {
    background:#315cff;
    border:1px solid #6a84ff;
    border-radius:9px;
    min-height:34px;
    padding:0 15px;
    color:white;
    font-weight:800;
}
QPushButton[autoPrimary120="true"]:hover { background:#4b6fff; }
QPushButton[autoSecondary120="true"] {
    background:#17243c;
    border:1px solid #36517a;
    border-radius:9px;
    min-height:34px;
    padding:0 14px;
    color:#dbe5f7;
    font-weight:750;
}
QPushButton[autoSecondary120="true"]:hover { background:#20304d; border-color:#6380ad; }
QFrame[pipelineSetting120="true"] {
    background:#111b30;
    border:1px solid #263a58;
    border-radius:9px;
}
QLabel[pipelineLabel120="true"] {
    background:transparent;
    color:#dce5f5;
    font-size:12px;
    font-weight:650;
}
'''


class PipelineBus120(QObject):
    progress = Signal(int, str)
    done = Signal(dict)


class Nova(base.Nova):
    def __init__(self):
        self.auto_pipeline_requested120 = False
        self.pipeline_srt120 = ''
        super().__init__()
        self.pipeline_bus120 = PipelineBus120()
        self.pipeline_bus120.progress.connect(self._pipeline_progress120)
        self.pipeline_bus120.done.connect(self._pipeline_done120)
        self.setWindowTitle(f'NovaShorts Studio v{VERSION}')
        try:
            self.status.setText(f'NovaShorts v{VERSION} 시작 · 전체 기능 연결')
        except Exception:
            pass

    def build(self):
        super().build()
        self.setWindowTitle(f'NovaShorts Studio v{VERSION}')
        self.setStyleSheet(self.styleSheet() + V120_CSS)

    def source_page(self):
        w = super().source_page()
        v = w.layout()

        auto = QFrame()
        auto.setObjectName('autoPipeline120')
        auto.setFixedHeight(78)
        h = QHBoxLayout(auto)
        h.setContentsMargins(14, 10, 12, 10)
        h.setSpacing(10)
        info = QVBoxLayout()
        info.setSpacing(2)
        title = QLabel('🚀 원클릭 자동 제작')
        title.setObjectName('autoTitle120')
        info.addWidget(title)
        self.pipeline_status120 = QLabel('상품 분석 → 소싱 → 다운로드 → OCR/자막 제거 → 음성분석 → 한국어 대본/TTS → 자동 컷 → 9:16 렌더 → 썸네일')
        self.pipeline_status120.setObjectName('autoStatus120')
        self.pipeline_status120.setWordWrap(True)
        info.addWidget(self.pipeline_status120)
        h.addLayout(info, 1)
        b_all = QPushButton('상품부터 전체 자동 제작')
        b_all.setProperty('autoPrimary120', True)
        b_all.clicked.connect(self.start_product_pipeline120)
        h.addWidget(b_all)
        b_sel = QPushButton('선택 후보 전체 제작')
        b_sel.setProperty('autoSecondary120', True)
        b_sel.clicked.connect(self.start_selected_pipeline120)
        h.addWidget(b_sel)

        # Insert after product/platform cards and before the expanding search/result splitter.
        v.insertWidget(max(0, v.count() - 1), auto)
        self.auto_pipeline_card120 = auto
        return w

    def right_panel(self):
        panel = super().right_panel()
        # The four quick switches now directly control the real processing pipeline.
        try:
            self.quick_ocr.setChecked(bool(getattr(self.s, 'pipeline_remove_subtitles', True)))
            self.quick_cut.setChecked(bool(getattr(self.s, 'pipeline_auto_cut', True)))
            self.quick_link.setChecked(bool(getattr(self.s, 'lnkbio_auto_publish', False)))
            self.quick_ocr.toggled.connect(self.quick_save)
            self.quick_cut.toggled.connect(self.quick_save)
        except Exception:
            pass
        return panel

    def settings_page(self):
        outer = super().settings_page()
        scroll = outer.findChild(QScrollArea)
        host = scroll.widget() if scroll else None
        hv = host.layout() if host else None
        if hv is None:
            return outer

        card = QFrame()
        card.setObjectName('settingsCard118')
        cv = QVBoxLayout(card)
        cv.setContentsMargins(14, 12, 14, 14)
        cv.setSpacing(7)
        title = QLabel('원클릭 자동 제작 / AI 분석')
        title.setObjectName('settingsTitle118')
        cv.addWidget(title)

        self.whisper_model120 = QComboBox()
        self.whisper_model120.addItems(['base (내장)'])
        self.tts_rate120 = QComboBox()
        self.tts_rate120.addItems(['-10%', '+0%', '+10%', '+20%'])
        rate = getattr(self.s, 'tts_rate', '+0%')
        self.tts_rate120.setCurrentText(rate if rate in ['-10%', '+0%', '+10%', '+20%'] else '+0%')
        self.target_seconds120 = QSpinBox()
        self.target_seconds120.setRange(8, 60)
        self.target_seconds120.setValue(int(getattr(self.s, 'pipeline_target_seconds', 20)))
        self.auto_upload120 = main_v113.OnOffButton(bool(getattr(self.s, 'youtube_auto_upload', False)))
        self.add_subs120 = main_v113.OnOffButton(bool(getattr(self.s, 'pipeline_add_korean_subtitles', True)))
        self.auto_thumb120 = main_v113.OnOffButton(bool(getattr(self.s, 'pipeline_auto_thumbnail', True)))
        self.auto_link120 = main_v113.OnOffButton(bool(getattr(self.s, 'lnkbio_auto_publish', False)))

        pairs = [
            ('Whisper 음성 분석', self.whisper_model120),
            ('TTS 속도', self.tts_rate120),
            ('목표 길이(초)', self.target_seconds120),
            ('한국어 자막 자동 삽입', self.add_subs120),
            ('썸네일 자동 생성', self.auto_thumb120),
            ('YouTube 자동 업로드', self.auto_upload120),
            ('Lnk.Bio 자동 링크', self.auto_link120),
        ]
        self.pipeline_setting_pairs120 = []
        for name, ctl in pairs:
            row = QFrame()
            row.setProperty('pipelineSetting120', True)
            row.setMinimumHeight(46)
            rh = QHBoxLayout(row)
            rh.setContentsMargins(10, 5, 9, 5)
            rh.setSpacing(12)
            lab = QLabel(name)
            lab.setProperty('pipelineLabel120', True)
            lab.setMinimumWidth(165)
            ctl.setSizePolicy(QSizePolicy.Expanding if isinstance(ctl, (QComboBox, QSpinBox)) else QSizePolicy.Fixed, QSizePolicy.Fixed)
            rh.addWidget(lab)
            rh.addStretch() if not isinstance(ctl, (QComboBox, QSpinBox)) else None
            rh.addWidget(ctl)
            cv.addWidget(row)
            self.pipeline_setting_pairs120.append((lab, ctl))

        note = QLabel('※ 자동 업로드는 OFF가 기본입니다. ON일 때만 YouTube 외부 업로드를 실행합니다.')
        note.setObjectName('muted')
        note.setWordWrap(True)
        cv.addWidget(note)
        hv.insertWidget(1, card)
        self.pipeline_settings_card120 = card
        return outer

    def quick_save(self):
        try:
            self.s.watermark_enabled = self.quick_wm.isChecked()
            self.s.use_gemini_query_planning = self.quick_ai.currentIndex() == 0
            self.s.pipeline_remove_subtitles = self.quick_ocr.isChecked()
            self.s.pipeline_auto_cut = self.quick_cut.isChecked()
            self.s.lnkbio_auto_publish = self.quick_link.isChecked()
            save_settings(self.s)
        except Exception:
            super().quick_save()

    def save(self):
        super().save()
        try:
            self.s.whisper_model = 'base'
            self.s.tts_rate = self.tts_rate120.currentText()
            self.s.pipeline_target_seconds = self.target_seconds120.value()
            self.s.pipeline_add_korean_subtitles = self.add_subs120.isChecked()
            self.s.pipeline_auto_thumbnail = self.auto_thumb120.isChecked()
            self.s.youtube_auto_upload = self.auto_upload120.isChecked()
            self.s.lnkbio_auto_publish = self.auto_link120.isChecked()
            if hasattr(self, 'quick_link'):
                self.quick_link.setChecked(self.s.lnkbio_auto_publish)
            save_settings(self.s)
            self.say('설정 저장 완료 · 원클릭 자동 제작 설정 포함')
        except Exception as e:
            self.bus.err.emit('원클릭 설정 저장\n' + str(e))

    def start_product_pipeline120(self):
        self.auto_pipeline_requested120 = True
        self.pipeline_status120.setText('상품 분석/검색을 시작합니다. 관련도 1위 후보를 자동 선택해 최종 쇼츠까지 제작합니다.')
        if self.product_url.text().strip():
            self.analyze_product_url119()
            return
        if self.product.text().strip():
            self.source_from_name119()
            return
        self.auto_pipeline_requested120 = False
        self.bus.err.emit('상품명 또는 쿠팡/상품 URL을 입력하세요.')

    def start_selected_pipeline120(self):
        row = None
        it = self.candidates.currentItem() if hasattr(self, 'candidates') else None
        if it:
            row = it.data(Qt.UserRole) or None
        if not row and getattr(self, 'cand_url', None) and self.cand_url.text().strip():
            row = {'url': self.cand_url.text().strip(), 'title': self.cand_text.text().strip(), 'platform': ''}
        if not row:
            self.bus.err.emit('먼저 영상 후보를 선택하세요.')
            return
        self._start_pipeline_row120(row)

    def on_candidates(self, rows):
        super().on_candidates(rows)
        if self.auto_pipeline_requested120:
            self.auto_pipeline_requested120 = False
            candidates = list(getattr(self, 'candidate_rows', []) or [])
            if not candidates:
                self.pipeline_status120.setText('관련 영상 후보가 없습니다. 검색어/플랫폼을 확인하세요.')
                self.bus.err.emit('원클릭 자동 제작\n관련 영상 후보를 찾지 못했습니다.')
                return
            self._start_pipeline_row120(candidates[0])

    def home_edit_selected(self):
        # Home's existing action now uses the connected full pipeline rather than stopping after download.
        if getattr(self, 'cand_url', None) and self.cand_url.text().strip():
            row = {'url': self.cand_url.text().strip(), 'title': self.cand_text.text().strip(), 'platform': ''}
            self._start_pipeline_row120(row)
        else:
            self.go(2)

    def _download_candidate_sync120(self, row: dict) -> str:
        url = str(row.get('url') or '').strip()
        if not url:
            raise RuntimeError('후보 URL이 없습니다.')
        try:
            return str(download_video(url, self.s.output_folder, lambda x: self.pipeline_bus120.progress.emit(10, x)))
        except Exception as first:
            if extension_recent(5.0):
                tid = uuid.uuid4().hex
                TASKS.put({'type': 'extract_media', 'task_id': tid, 'url': url, 'wait_ms': 5000})
                packet = wait_for_result(tid, 24)
                media_urls = (((packet or {}).get('media') or {}).get('media') or [])
                for media_url in media_urls[:12]:
                    try:
                        return str(download_video(media_url, self.s.output_folder, lambda x: self.pipeline_bus120.progress.emit(12, x)))
                    except Exception:
                        continue
            raise RuntimeError('영상 다운로드에 실패했습니다.\n' + str(first))

    def _start_pipeline_row120(self, row: dict):
        if self.stop_requested:
            self.say('작업이 중지 상태입니다. 모두 시작을 눌러주세요.')
            return
        self.pipeline_status120.setText('원클릭 자동 제작 실행 중…')
        title = str(row.get('title') or '').strip()
        self.cand_url.setText(str(row.get('url') or ''))
        self.cand_text.setText(title)

        def run():
            self.pipeline_bus120.progress.emit(4, '관련 영상 다운로드')
            source = self._download_candidate_sync120(row)
            self.bus.downloaded.emit(source)
            profile = dict(getattr(self, 'product_profile', {}) or {'title': self.product.text().strip()})
            if not profile.get('title'):
                profile['title'] = self.product.text().strip() or title
            product_url = self.product_url.text().strip()
            result = run_processing_pipeline(
                source, profile, self.s, product_url,
                lambda pct, msg: self.pipeline_bus120.progress.emit(pct, msg)
            )
            self.pipeline_bus120.done.emit(result)

        self.work('원클릭 전체 자동 제작', run)

    def _pipeline_progress120(self, pct: int, msg: str):
        try:
            self.progress.setRange(0, 100)
            self.progress.setValue(int(pct))
            self.status.setText(msg[:120])
            self.pipeline_status120.setText(f'{pct}% · {msg}')
        except Exception:
            pass

    def _pipeline_done120(self, result: dict):
        final = str(result.get('final_video') or '')
        script = str(result.get('script') or '')
        thumb = str(result.get('thumbnail') or '')
        meta = dict(result.get('metadata') or {})
        self.pipeline_srt120 = str(result.get('subtitle_srt') or '')
        self.current_tts = str(result.get('tts') or '')
        if final:
            self.current_video = final
            self.video.setText(final)
            self.pubvideo.setText(final)
            self.thumb_video.setText(final)
            self.out.setText(final)
            self.load_preview(final)
        if script:
            self.script.setPlainText(script)
        if thumb:
            self.thumb_out.setText(thumb)
            self.show_thumb(thumb)
        self.ytitle.setText(str(meta.get('title') or ''))
        self.ydesc.setPlainText(str(meta.get('description') or ''))
        self.ytags.setText(', '.join(str(x) for x in (meta.get('tags') or [])))
        self.linktitle.setText(str((getattr(self, 'product_profile', {}) or {}).get('title') or self.product.text()))
        self.linkurl.setText(self.product_url.text().strip())
        self.xtext.setText(str(meta.get('title') or ''))
        youtube_id = str(result.get('youtube_id') or '')
        extra = f' · YouTube ID {youtube_id}' if youtube_id else ''
        self.pipeline_status120.setText('100% · 완성 쇼츠 생성 완료' + extra)
        self.say('원클릭 전체 자동 제작 완료: ' + final)

    # Manual feature buttons also use the upgraded implementations, so there are no dead/demo controls.
    def clean_sub(self):
        p = self.video.text().strip()
        if not p:
            return
        out = str(Path(self.s.output_folder) / 'subtitle_clean_smart.mp4')
        def run():
            smart_subtitle_remove(p, out, lambda pct, msg: self.pipeline_bus120.progress.emit(pct, msg))
            self.bus.rendered.emit(out)
        self.work('스마트 자막 제거', run)

    def make_tts(self):
        text = self.script.toPlainText().strip()
        if not text:
            return
        out = str(Path(self.s.output_folder) / 'tts.mp3')
        srt = str(Path(self.s.output_folder) / 'tts_korean.srt')
        voice = self.voice.currentText()
        rate = getattr(self.s, 'tts_rate', '+0%')
        def run():
            generate_tts_bundle(text, voice, rate, out, srt, lambda pct, msg: self.pipeline_bus120.progress.emit(pct, msg))
            self.pipeline_srt120 = srt
            self.bus.tts.emit(out)
        self.work('TTS + 한국어 자막 타이밍 생성', run)

    def render(self):
        p = self.video.text().strip()
        out = self.out.text().strip()
        if not p or not out:
            return
        if not self.current_tts:
            return super().render()
        def run():
            compose_final(p, self.current_tts, out, self.pipeline_srt120 or None, bool(getattr(self.s, 'pipeline_add_korean_subtitles', True)), lambda pct, msg: self.pipeline_bus120.progress.emit(pct, msg))
            final = out
            if self.quick_wm.isChecked() and self.s.watermark_text:
                from engine import watermark
                wm = str(Path(out).with_name(Path(out).stem + '_wm.mp4'))
                watermark(out, self.s.watermark_text, wm, self.s.watermark_position)
                final = wm
            self.bus.rendered.emit(final)
        self.work('최종 렌더 + 한국어 자막', run)


if __name__ == '__main__':
    app = QApplication([])
    app.setApplicationName('NovaShorts')
    app.setFont(QFont('Malgun Gothic', 10))
    win = Nova()
    win.show()
    app.exec()
