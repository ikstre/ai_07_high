"""긴 동기 API 호출 동안 실시간 경과 게이지를 그리는 helper.

기존 생성 버튼들은 클릭 후 단계형(25%→60%) 고정 게이지를 쓰는데, 실제 호출이
블로킹이라 호출 내내 게이지가 멈춰 있었다(2026-06-12 QA 2). HTTP 호출을 워커
스레드로 옮기고 메인 스레드가 경과 시간 기반으로 게이지를 갱신한다.
"""
from __future__ import annotations

import threading
import time
from typing import Any, Callable

_TICK_SECONDS = 0.5


def run_with_live_progress(
    slot,
    work: Callable[[], Any],
    *,
    label: str,
    expected_seconds: float,
) -> Any:
    """`work`를 백그라운드 스레드로 실행하며 slot 자리에 진행 게이지를 그린다.

    - `slot`: 보통 버튼을 담았던 st.empty() — 실행 중 버튼 대신 게이지가 보인다.
    - `work`: streamlit/session_state를 만지지 않는 순수 함수(HTTP 호출 등)여야
      한다. session_state 읽기/쓰기는 호출 전후 메인 스레드에서 처리할 것.
    - `expected_seconds`: 통상 소요 기준선. 게이지는 97%에서 멈춰 완료를 단정하지
      않는다(이미지 폴링 게이지와 동일한 규칙).
    - 예외는 메인 스레드에서 그대로 재발생한다.
    """
    outcome: dict[str, Any] = {}

    def _target() -> None:
        try:
            outcome["value"] = work()
        except BaseException as exc:  # noqa: BLE001 — 메인 스레드에서 재발생
            outcome["error"] = exc

    thread = threading.Thread(target=_target, daemon=True, name=f"live-progress-{label[:12]}")
    started = time.monotonic()
    thread.start()
    bar = slot.progress(0.0, text=f"{label} · 시작")
    while thread.is_alive():
        elapsed = time.monotonic() - started
        bar.progress(
            min(elapsed / max(expected_seconds, 1.0), 0.97),
            text=f"{label} · {int(elapsed)}초 경과 (시간 추정 · 보통 ~{int(expected_seconds)}초)",
        )
        thread.join(timeout=_TICK_SECONDS)
    if "error" in outcome:
        slot.empty()
        raise outcome["error"]
    bar.progress(1.0, text=f"{label} · 완료")
    return outcome.get("value")
