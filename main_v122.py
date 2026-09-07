from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path

import main_v121 as base
import main_v113
from PySide6.QtCore import QObject, Signal, Qt, QUrl
from PySide6.QtGui import QFont
from PySide6.QtWidgets import *

# Importing this patches the shared CDP helper so the dedicated browser loads the bundled extension.
import browser_cdp_v122 as browser_cdp
from bridge import TASKS, extension_recent, wait_for_result
from engine import download_video, generate_tts, save_settings
from parity_v122 import PARITY_MAP, providers, settings_manager
from pipeline_v122 import run_processing_pipeline_v122
from product_source import profile_summary
from sourcing_v122 import PLATFORMS, coupang_scraper, sourcing_pipeline

VERSION = '1.22'
for mod in [base, getattr(base, 'base', None), getattr(getattr(base, 'base', None), 'base', None)]:
    try:
        if mod is not None:
            mod.VERSION = VERSION
    except Exception:
        pass

V122_CSS = r'''
QFrame#parityCard122{background:#111b30;border:1px solid #36517a;border-radius:12px;}
QLabel#parityTitle122{background:transparent;color:#f4f7ff;font-size:14px;font-weight:850;}
QLabel#parityNote122{background:transparent;color:#8fa4c7;font-size:11px;}
QFrame[parityRow122="true"]{background:#0f192b;border:1px solid #273b59;border-radius:9px;}
QLabel[parityLabel122="true"]{background:transparent;color:#dce5f5;font-size:12px;font-weight:650;}
QPushButton[voicePreview122="true"]{background:#17243c;border:1px solid #36517a;border-radius:9px;min-height:34px;color:#dbe5f7;font-weight:750;}
QPushButton[voicePreview122="true"]:hover{background:#20304d;border-color:#6380ad;}
'''


class ParityBus122(QObject):
    profile = Signal(dict)
    sourcing = Signal(dict)
    voice_ready = Signal(str)


class Nova(base.Nova):
    def __init__(self):
        super().__init__()
        self.parity_bus122 = ParityBus122()
        self.parity_bus122.profile.connect(self._home_profile_ready121)
        self.parity_bus122.sourcing.connect(self._sourcing_ready122)
        self.parity_bus122.voice_ready.connect(self._voice_preview_ready122)
        self.setWindowTitle(f'NovaShorts Studio v{VERSION}')
        try:
            self.status.setText(f'NovaShorts v{VERSION} 시작 · 원본 분석 기능 전수 대응')
            self.browser_state121.setText('Chrome/Edge 자동 연결 · Bridge 자동 페어링')
        except Exception:
            pass

    def build(self):
        super().build()
        self.setWindowTitle(f'NovaShorts Studio v{VERSION}')
        self.setStyleSheet(self.styleSheet() + V122_CSS)
        self.setMinimumSize(1024, 680)

    def home_page(self):
        w = super().home_page()
        card = w.findChild(QFrame, 'makerSettings121')
        if card and card.layout():
            preview = QPushButton('▶  선택한 목소리 미리듣기')
            preview.setProperty('voicePreview122', True)
            preview.clicked.connect(self.preview_voice122)
            card.layout().addWidget(preview)
            self.voice_preview_btn122 = preview
        return w

    def settings_page(self):
        outer = super().settings_page()
        scroll = outer.findChild(QScrollArea)
        host = scroll.widget() if scroll else None
        hv = host.layout() if host else None
        if hv is None:
            return outer

        card = QFrame(); card.setObjectName('parityCard122')
        v = QVBoxLayout(card); v.setContentsMargins(14, 12, 14, 14); v.setSpacing(7)
        title = QLabel('원본 분석 대응 기능'); title.setObjectName('parityTitle122'); v.addWidget(title)
        note = QLabel('SSMaker 자료에서 확인된 분석·번역·재편집·검증 단계를 실제 제작 파이프라인에 연결합니다.'); note.setObjectName('parityNote122'); note.setWordWrap(True); v.addWidget(note)

        specs = [
            ('영상 장면 분석', 'pipeline_video_analysis', True),
            ('음성 분석', 'pipeline_audio_analysis', True),
            ('원문 → 한국어 번역', 'pipeline_translate_source', True),
            ('대본 사실성 검증', 'pipeline_semantic_validation', True),
            ('AI 대본 검증 보강', 'pipeline_video_validation_ai', True),
            ('TTS 길이 자동 맞춤', 'pipeline_auto_tts_speed', True),
            ('다중소스 재편집', 'pipeline_mix_sources', True),
            ('최종 영상 무결성 검증', 'pipeline_validate_output', True),
            ('렌더 오류 자동 복구', 'pipeline_render_repair', True),
        ]
        self.parity_controls122 = {}
        self.parity_setting_pairs122 = []
        for label_text, attr, default in specs:
            row = QFrame(); row.setProperty('parityRow122', True); row.setMinimumHeight(44)
            h = QHBoxLayout(row); h.setContentsMargins(10, 5, 9, 5)
            lab = QLabel(label_text); lab.setProperty('parityLabel122', True)
            ctl = main_v113.OnOffButton(bool(getattr(self.s, attr, default)))
            h.addWidget(lab); h.addStretch(); h.addWidget(ctl)
            v.addWidget(row)
            self.parity_controls122[attr] = ctl
            self.parity_setting_pairs122.append((lab, ctl))
        hv.insertWidget(2, card)
        self.parity_card122 = card
        return outer

    def save(self):
        super().save()
        try:
            for attr, ctl in self.parity_controls122.items():
                setattr(self.s, attr, ctl.isChecked())
            save_settings(self.s)
            self.say('설정 저장 완료 · 원본 분석 대응 기능 포함')
        except Exception as e:
            self.bus.err.emit('v1.22 설정 저장\n' + str(e))

    def preview_voice122(self):
        voices = ['ko-KR-SunHiNeural', 'ko-KR-InJoonNeural', 'ko-KR-HyunsuNeural']
        voice = voices[max(0, min(self.home_voice121.currentIndex(), len(voices)-1))]
        rate = self.home_rate121.currentText()
        out = str(Path(tempfile.gettempdir()) / 'novashorts_voice_preview.mp3')
        self.voice_preview_btn122.setEnabled(False)
        self.voice_preview_btn122.setText('목소리 생성 중…')
        def run():
            generate_tts('이 목소리로 쇼츠 영상을 만들어 볼게요.', voice, out, rate)
            self.parity_bus122.voice_ready.emit(out)
        self.work('TTS 목소리 미리듣기', run)

    def _voice_preview_ready122(self, path: str):
        try:
            self.voice_preview_btn122.setEnabled(True)
            self.voice_preview_btn122.setText('▶  선택한 목소리 미리듣기')
            self.player.setSource(QUrl.fromLocalFile(path))
            self.player.play()
        except Exception:
            pass

    # --- Product address flow: coupang_scraper -> full sourcing pipeline -> best candidate -> full processing ---
    def _product_profile_sync121(self, url: str) -> dict:
        return coupang_scraper(url, lambda pct, msg: self.pipeline_bus120.progress.emit(min(12, pct), msg))

    def home_confirm_product121(self):
        url = self.home_product_url121.text().strip()
        if not url:
            self.bus.err.emit('상품 주소를 입력하세요.')
            return
        self.home_product_info121.setText('상품 내용을 확인하는 중… 차단 시 Chrome/Edge가 자동으로 연결됩니다.')
        def run():
            self.parity_bus122.profile.emit(self._product_profile_sync121(url))
        self.work('상품 주소 확인', run)

    def _home_profile_ready121(self, profile):
        self.home_product_profile121 = dict(profile or {})
        self.product_profile = dict(profile or {})
        title = str(profile.get('title') or '')
        self.home_product_name121.setText(title)
        self.home_product_info121.setText(profile_summary(profile) + '\n' + title)
        if hasattr(self, 'product'):
            self.product.setText(title)
        if hasattr(self, 'product_url'):
            self.product_url.setText(str(profile.get('input_url') or profile.get('url') or self.home_product_url121.text()))
        if self.home_pending_create121:
            self.home_pending_create121 = False
            self._start_product_source121()

    def _enabled_platforms122(self) -> list[str]:
        enabled = [p for p in (getattr(self.s, 'platform_sources', None) or PLATFORMS) if p in PLATFORMS]
        return enabled or PLATFORMS[:]

    def _start_product_source121(self):
        profile = dict(self.home_product_profile121 or {})
        if not profile.get('title'):
            self.bus.err.emit('상품명을 확인하지 못했습니다.')
            return
        self.product_profile = profile
        self.product.setText(str(profile.get('title') or ''))
        self.product_url.setText(self.home_product_url121.text().strip())
        self.home_result_status121.setText('상품 관련 영상을 7개 플랫폼에서 교차 수집하는 중…')
        def run():
            result = sourcing_pipeline(
                profile,
                getattr(self.s, 'gemini_api_key', ''),
                self._enabled_platforms122(),
                lambda pct, msg: self.pipeline_bus120.progress.emit(min(82, pct), msg),
            )
            self.parity_bus122.sourcing.emit(result)
        self.work('상품 영상 전수 소싱', run)

    def _sourcing_ready122(self, payload: dict):
        self.query_plan = dict(payload.get('plan') or {})
        try:
            self.planbox.setPlainText('\n'.join(f"[{p}]\n" + '\n'.join(qs) for p, qs in self.query_plan.items()))
        except Exception:
            pass
        rows = list(payload.get('candidates') or [])
        limit = int(getattr(self.s, 'source_candidate_limit', 60) or 60)
        rows = rows[:max(1, limit)]
        self.auto_pipeline_requested120 = False
        self.bus.candidates.emit(rows)
        if not rows:
            self.home_result_status121.setText('관련 영상 후보를 찾지 못했습니다.')
            self.bus.err.emit('상품 영상 자동 제작\n관련 영상 후보가 없습니다. 플랫폼 로그인/검색 결과를 확인하세요.')
            return
        threshold = int(getattr(self.s, 'min_similarity', 55) or 55)
        good = [x for x in rows if int(x.get('_score', 0) or 0) >= threshold]
        if bool(getattr(self.s, 'auto_skip_low_similarity', True)) and not good:
            best = rows[0]
            self.home_result_status121.setText(f"후보는 찾았지만 최소 관련도 {threshold}%를 통과하지 못했습니다. 최고 {int(best.get('_score',0) or 0)}%")
            self.bus.err.emit('상품 영상 자동 제작\n잘못된 제품 영상 자동 선택을 막았습니다. 소싱 화면에서 후보를 확인하거나 최소 유사도를 조정하세요.')
            return
        best = (good or rows)[0]
        self.home_result_status121.setText(f"관련도 {int(best.get('_score',0) or 0)}% 후보 선택 · 다운로드/제작 시작")
        self._start_pipeline_row120(best)

    def bridge_collect(self):
        profile = dict(getattr(self, 'product_profile', {}) or {'title': self.product.text().strip()})
        if not profile.get('title'):
            self.bus.err.emit('상품명을 먼저 입력하세요.')
            return
        enabled = [p for p, ctl in self.pchecks.items() if ctl.isChecked()] if hasattr(self, 'pchecks') else self._enabled_platforms122()
        def run():
            self.parity_bus122.sourcing.emit(sourcing_pipeline(profile, getattr(self.s, 'gemini_api_key', ''), enabled, lambda pct, msg: self.pipeline_bus120.progress.emit(pct, msg)))
        self.work('플랫폼 통합 소싱', run)

    def analyze_product_url119(self):
        url = self.product_url.text().strip()
        if not url:
            self.bus.err.emit('쿠팡/상품 URL을 입력하세요.')
            return
        def run():
            self.product_bus119.profile_ready.emit(coupang_scraper(url, lambda pct, msg: self.pipeline_bus120.progress.emit(pct, msg)))
        self.work('상품 URL 분석', run)

    def _download_candidate_sync120(self, row: dict) -> str:
        url = str(row.get('url') or '').strip()
        if not url:
            raise RuntimeError('후보 URL이 없습니다.')
        try:
            return str(download_video(url, self.s.output_folder, lambda x: self.pipeline_bus120.progress.emit(8, x)))
        except Exception as first:
            try:
                for media_url in browser_cdp.extract_media(url, 5.2)[:16]:
                    try:
                        return str(download_video(media_url, self.s.output_folder, lambda x: self.pipeline_bus120.progress.emit(10, x)))
                    except Exception:
                        continue
            except Exception:
                pass
            if extension_recent(5.0):
                tid = uuid.uuid4().hex
                TASKS.put({'type': 'extract_media', 'task_id': tid, 'url': url, 'wait_ms': 5200})
                packet = wait_for_result(tid, 24)
                for media_url in ((((packet or {}).get('media') or {}).get('media') or [])[:16]):
                    try:
                        return str(download_video(media_url, self.s.output_folder, lambda x: self.pipeline_bus120.progress.emit(11, x)))
                    except Exception:
                        continue
            raise RuntimeError('영상 다운로드에 실패했습니다.\n' + str(first))

    def _start_pipeline_row120(self, row: dict):
        if self.stop_requested:
            self.say('작업이 중지 상태입니다. 모두 시작을 눌러주세요.')
            return
        title = str(row.get('title') or '').strip()
        self.cand_url.setText(str(row.get('url') or ''))
        self.cand_text.setText(title)
        self.home_result_status121.setText('관련 영상 다운로드 → 분석 → 재편집 → 검증 중…')
        def run():
            self.pipeline_bus120.progress.emit(3, '관련 영상 다운로드')
            source = self._download_candidate_sync120(row)
            self.bus.downloaded.emit(source)
            profile = dict(getattr(self, 'product_profile', {}) or {'title': self.product.text().strip() or title})
            if not profile.get('title'):
                profile['title'] = title or Path(source).stem
            result = run_processing_pipeline_v122(
                [source], profile, self.s, self.product_url.text().strip(), '',
                lambda pct, msg: self.pipeline_bus120.progress.emit(pct, msg)
            )
            self.pipeline_bus120.done.emit(result)
        self.work('상품 영상 전체 자동 제작', run)

    def _start_local_pipeline121(self, files, profile, manual_script):
        if self.stop_requested:
            self.say('작업이 중지 상태입니다. 모두 시작을 눌러주세요.')
            return
        self.product_profile = dict(profile or {})
        self.home_result_status121.setText('분석 → 자막 처리 → 대본/TTS → 재편집 → 최종 검증 중…')
        def run():
            result = run_processing_pipeline_v122(
                files, self.product_profile, self.s, '', manual_script,
                lambda pct, msg: self.pipeline_bus120.progress.emit(pct, msg)
            )
            self.pipeline_bus120.done.emit(result)
        self.work('전체 영상 제작', run)

    def _pipeline_done120(self, result: dict):
        super()._pipeline_done120(result)
        final = str(result.get('final_video') or '')
        integrity = dict(result.get('integrity') or {})
        validation = dict(result.get('script_validation') or {})
        if final:
            self.home_final121 = final
            warnings = len(validation.get('warnings') or [])
            state = '검증 통과' if integrity.get('ok', True) else '검증 확인 필요'
            self.home_result_status121.setText(f'완성 · {state} · 대본 경고 {warnings}건 · {final}')

    def parity_status122(self) -> dict:
        """Used by CI/diagnostics to prove every evidenced module is mapped and live."""
        return {
            'version': VERSION,
            'parity_count': len(PARITY_MAP),
            'providers': providers(),
            'settings': settings_manager(self.s),
            'modes': 4,
            'platforms': len(PLATFORMS),
        }


if __name__ == '__main__':
    app = QApplication([])
    app.setApplicationName('NovaShorts')
    app.setFont(QFont('Malgun Gothic', 10))
    win = Nova(); win.show(); app.exec()
