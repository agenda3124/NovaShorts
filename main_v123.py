from __future__ import annotations

import main_v122 as base
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from sourcing_v123 import PLATFORMS, sourcing_pipeline

VERSION = '1.23'

# Propagate visible version text through the inherited UI layers.
for mod in [base, getattr(base, 'base', None), getattr(getattr(base, 'base', None), 'base', None), getattr(getattr(getattr(base, 'base', None), 'base', None), 'base', None)]:
    try:
        if mod is not None:
            mod.VERSION = VERSION
    except Exception:
        pass


class Nova(base.Nova):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f'NovaShorts Studio v{VERSION}')
        try:
            self.status.setText(f'NovaShorts v{VERSION} 시작 · 소싱 진단/재시도 개선')
            self.browser_state121.setText('Chrome/Edge 전용 프로필 · 자동 로그인 유지')
        except Exception:
            pass

    def build(self):
        super().build()
        self.setWindowTitle(f'NovaShorts Studio v{VERSION}')

    def _enabled_platforms123(self) -> list[str]:
        enabled = [p for p in (getattr(self.s, 'platform_sources', None) or PLATFORMS) if p in PLATFORMS]
        return enabled or PLATFORMS[:]

    def _run_sourcing123(self, profile: dict, enabled: list[str] | None = None):
        return sourcing_pipeline(
            profile,
            getattr(self.s, 'gemini_api_key', ''),
            enabled or self._enabled_platforms123(),
            lambda pct, msg: self.pipeline_bus120.progress.emit(min(84, pct), msg),
        )

    def _start_product_source121(self):
        profile = dict(self.home_product_profile121 or {})
        if not profile.get('title'):
            self.bus.err.emit('상품명을 확인하지 못했습니다.')
            return
        self.product_profile = profile
        self.product.setText(str(profile.get('title') or ''))
        self.product_url.setText(self.home_product_url121.text().strip())
        mode = 'Gemini 다국어 검색어' if str(getattr(self.s, 'gemini_api_key', '') or '').strip() else '브랜드/모델 폴백 검색어'
        self.home_result_status121.setText(f'관련 영상 수집 시작 · {mode}')

        def run():
            self.parity_bus122.sourcing.emit(self._run_sourcing123(profile))

        self.work('상품 영상 정밀 소싱', run)

    def bridge_collect(self):
        profile = dict(getattr(self, 'product_profile', {}) or {'title': self.product.text().strip()})
        if not profile.get('title'):
            self.bus.err.emit('상품명을 먼저 입력하세요.')
            return
        enabled = [p for p, ctl in self.pchecks.items() if ctl.isChecked()] if hasattr(self, 'pchecks') else self._enabled_platforms123()

        def run():
            self.parity_bus122.sourcing.emit(self._run_sourcing123(profile, enabled))

        self.work('플랫폼 통합 소싱', run)

    @staticmethod
    def _state_label123(state: str) -> str:
        return {
            'ok': '정상',
            'empty': '결과 없음',
            'login_required': '로그인/인증 확인',
            'blocked': '접근 차단',
            'error': '오류',
        }.get(str(state or ''), str(state or '확인 필요'))

    def _diagnostic_lines123(self, payload: dict) -> list[str]:
        counts = dict(payload.get('counts') or {})
        diagnostics = dict(payload.get('diagnostics') or {})
        lines = []
        for p in self._enabled_platforms123():
            d = diagnostics.get(p) or {}
            count = int(counts.get(p, d.get('count', 0)) or 0)
            state = self._state_label123(str(d.get('state') or ('ok' if count else 'empty')))
            lines.append(f'{p}: {count}건 · {state}')
        return lines

    def _append_plan_diagnostics123(self, payload: dict):
        try:
            plan = dict(payload.get('plan') or {})
            blocks = []
            for p in self._enabled_platforms123():
                qs = plan.get(p) or []
                if qs:
                    blocks.append(f'[{p}]\n' + '\n'.join('• ' + str(q) for q in qs[:6]))
            blocks.append('[수집 결과]\n' + '\n'.join(self._diagnostic_lines123(payload)))
            blocks.append('[검색어 모드]\n' + ('Gemini 다국어 검색어 사용' if payload.get('gemini_used') else 'Gemini 키 없음 · 브랜드/모델/식별토큰 폴백 사용'))
            self.planbox.setPlainText('\n\n'.join(blocks))
        except Exception:
            pass

    def _sourcing_ready122(self, payload: dict):
        self.query_plan = dict(payload.get('plan') or {})
        self._append_plan_diagnostics123(payload)

        rows = list(payload.get('candidates') or [])
        limit = int(getattr(self.s, 'source_candidate_limit', 60) or 60)
        rows = rows[:max(1, limit)]
        self.auto_pipeline_requested120 = False
        self.bus.candidates.emit(rows)

        counts = dict(payload.get('counts') or {})
        total_collected = sum(int(v or 0) for v in counts.values())
        summary = ' · '.join(f'{p} {int(counts.get(p,0) or 0)}' for p in self._enabled_platforms123())

        if total_collected <= 0 or not rows:
            self.home_result_status121.setText('영상 수집 0건 · 유사도 계산을 실행하지 않았습니다.')
            diagnostics = dict(payload.get('diagnostics') or {})
            hints = []
            if any(str((diagnostics.get(p) or {}).get('state')) == 'login_required' for p in diagnostics):
                hints.append('NovaShorts가 띄운 전용 Chrome/Edge 창에서 해당 플랫폼에 로그인한 뒤 다시 시도하세요.')
            if any(str((diagnostics.get(p) or {}).get('state')) == 'blocked' for p in diagnostics):
                hints.append('일부 플랫폼이 접근 검증 페이지를 표시했습니다. 전용 브라우저에서 검증을 완료한 뒤 다시 시도하세요.')
            if not str(getattr(self.s, 'gemini_api_key', '') or '').strip():
                hints.append('Gemini API 키가 없어 브랜드/모델 기반 폴백 검색어를 사용했습니다. 모델명이 없는 한국 상품은 Gemini 키를 넣으면 중국어/영문 검색 정확도가 더 좋아집니다.')
            msg = '관련 영상 수집 결과가 0건입니다.\n\n' + '\n'.join(self._diagnostic_lines123(payload))
            if hints:
                msg += '\n\n' + '\n'.join('• ' + h for h in hints)
            msg += '\n\n※ 이번 실패는 유사도 기준 때문이 아닙니다. 검색 결과 자체가 수집되지 않은 상태입니다.'
            self.bus.err.emit(msg)
            return

        threshold = int(getattr(self.s, 'min_similarity', 55) or 55)
        good = [x for x in rows if int(x.get('_score', 0) or 0) >= threshold]
        best = rows[0]
        best_score = int(best.get('_score', 0) or 0)

        if bool(getattr(self.s, 'auto_skip_low_similarity', True)) and not good:
            self.home_result_status121.setText(f'영상 {total_collected}건 수집 · 최고 관련도 {best_score}% · 기준 {threshold}% 미달')
            self.bus.err.emit(
                '영상은 정상적으로 수집됐지만 상품 관련도가 기준에 못 미쳤습니다.\n\n'
                + summary
                + f'\n\n최고 관련도: {best_score}%\n현재 최소 기준: {threshold}%\n\n'
                + '소싱 화면에서 후보 제목/URL을 확인하세요. 단순히 기준을 낮추기보다 상품명·브랜드·모델 정보가 맞는지 먼저 확인하는 것이 안전합니다.'
            )
            return

        best = (good or rows)[0]
        score = int(best.get('_score', 0) or 0)
        self.home_result_status121.setText(f'영상 {total_collected}건 수집 · 관련도 {score}% 후보 선택 · 제작 시작')
        self._start_pipeline_row120(best)


if __name__ == '__main__':
    app = QApplication([])
    app.setApplicationName('NovaShorts')
    app.setFont(QFont('Malgun Gothic', 10))
    win = Nova()
    win.show()
    app.exec()
