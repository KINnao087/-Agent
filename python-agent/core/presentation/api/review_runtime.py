from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from core.application.agent.chat_service import CliChatService, TraceEvent
from core.application.reviews import (
    ContractReviewService,
    set_contract_review_service,
)
from core.application.workflows.chat import build_chat_graph
from core.shared.logging import get_logger
from core.shared.path_utils import ensure_parent_dir

_logger = get_logger("api.review_runtime")

TERMINAL_EVENT_KINDS = {"final", "error"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True, slots=True)
class PersistedTraceEvent:
    seq: int
    timestamp: str
    review_id: str
    kind: str
    summary: str
    detail: str
    node: str
    tool_call_id: str
    tool_name: str
    elapsed_ms: float | None
    is_error: bool


class ReviewEventStore:
    def __init__(self, root: str | Path = "artifacts/reviews") -> None:
        self.root = Path(root).resolve()
        self._locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()
        self._seq_cache: dict[str, int] = {}

    def events_path(self, review_id: str) -> Path:
        return self.root / review_id / "events.jsonl"

    def append(self, review_id: str, event: TraceEvent) -> dict[str, Any]:
        with self._lock_for(review_id):
            seq = self._next_seq_locked(review_id)
            record = PersistedTraceEvent(
                seq=seq,
                timestamp=_utc_now(),
                review_id=review_id,
                kind=event.kind,
                summary=event.summary,
                detail=event.detail,
                node=event.node,
                tool_call_id=event.tool_call_id,
                tool_name=event.tool_name,
                elapsed_ms=event.elapsed_ms,
                is_error=event.is_error,
            )
            target = ensure_parent_dir(self.events_path(review_id))
            with target.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(asdict(record), ensure_ascii=False))
                handle.write("\n")
            self._seq_cache[review_id] = seq
            return asdict(record)

    def read_after(self, review_id: str, after_seq: int = 0) -> list[dict[str, Any]]:
        path = self.events_path(review_id)
        if not path.exists():
            return []
        events: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                payload = json.loads(line)
                if int(payload.get("seq", 0)) > after_seq:
                    events.append(payload)
        return events

    def last_seq(self, review_id: str) -> int:
        with self._lock_for(review_id):
            return self._load_last_seq_locked(review_id)

    def has_events(self, review_id: str) -> bool:
        return self.events_path(review_id).exists()

    def _lock_for(self, review_id: str) -> threading.Lock:
        with self._locks_guard:
            if review_id not in self._locks:
                self._locks[review_id] = threading.Lock()
            return self._locks[review_id]

    def _next_seq_locked(self, review_id: str) -> int:
        return self._load_last_seq_locked(review_id) + 1

    def _load_last_seq_locked(self, review_id: str) -> int:
        cached = self._seq_cache.get(review_id)
        if cached is not None:
            return cached
        path = self.events_path(review_id)
        if not path.exists():
            self._seq_cache[review_id] = 0
            return 0

        last_seq = 0
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                payload = json.loads(line)
                last_seq = int(payload.get("seq", last_seq))
        self._seq_cache[review_id] = last_seq
        return last_seq


class ReviewRuntimeManager:
    def __init__(
        self,
        *,
        event_store: ReviewEventStore,
        make_service: Callable[[threading.Event | None], ContractReviewService],
        build_prompt: Callable[[str, str, str, dict[str, Any] | None], str],
    ) -> None:
        self.event_store = event_store
        self._make_service = make_service
        self._build_prompt = build_prompt
        self._threads: dict[str, threading.Thread] = {}
        self._cancel_events: dict[str, threading.Event] = {}
        self._states: dict[str, str] = {}
        self._guard = threading.Lock()

    def start(
        self,
        *,
        review_id: str,
        contract_path: str,
        attachments_path: str = "",
        invoice_path: str = "",
        platform_basic_info: dict[str, Any] | None = None,
    ) -> bool:
        with self._guard:
            existing = self._threads.get(review_id)
            if existing and existing.is_alive():
                return False

            cancel_event = self._cancel_events.get(review_id)
            if cancel_event is None:
                cancel_event = threading.Event()
                self._cancel_events[review_id] = cancel_event
            cancel_event.clear()
            self._states[review_id] = "running"

            thread = threading.Thread(
                target=self._run_review,
                kwargs={
                    "review_id": review_id,
                    "contract_path": contract_path,
                    "attachments_path": attachments_path,
                    "invoice_path": invoice_path,
                    "platform_basic_info": platform_basic_info,
                    "cancel_event": cancel_event,
                },
                name=f"review-runtime-{review_id}",
                daemon=True,
            )
            self._threads[review_id] = thread
            thread.start()
            return True

    def cancel(self, review_id: str) -> None:
        with self._guard:
            cancel_event = self._cancel_events.get(review_id)
            if cancel_event is None:
                cancel_event = threading.Event()
                self._cancel_events[review_id] = cancel_event
            cancel_event.set()
            if self._states.get(review_id) == "running":
                self._states[review_id] = "cancelled"

    def is_running(self, review_id: str) -> bool:
        with self._guard:
            thread = self._threads.get(review_id)
            return bool(thread and thread.is_alive())

    def state(self, review_id: str) -> str:
        with self._guard:
            thread = self._threads.get(review_id)
            if thread and thread.is_alive():
                return "running"
            return self._states.get(review_id, "idle")

    def _run_review(
        self,
        *,
        review_id: str,
        contract_path: str,
        attachments_path: str,
        invoice_path: str,
        platform_basic_info: dict[str, Any] | None,
        cancel_event: threading.Event,
    ) -> None:
        service = self._make_service(cancel_event=cancel_event)
        set_contract_review_service(service)
        prompt = self._build_prompt(
            contract_path=contract_path,
            attachments_path=attachments_path,
            invoice_path=invoice_path,
            platform_basic_info=platform_basic_info,
        )
        terminal_kind = ""
        try:
            chat_service = CliChatService(
                graph=build_chat_graph(),
                thread_id=f"api-{review_id}",
                cancel_event=cancel_event,
            )
            for event in chat_service.stream(prompt):
                persisted = self.event_store.append(review_id, event)
                terminal_kind = (
                    persisted["kind"]
                    if persisted["kind"] in TERMINAL_EVENT_KINDS
                    else terminal_kind
                )

            if not terminal_kind:
                status = service.get_review_status(review_id)
                terminal_kind = self.append_terminal_event(
                    review_id=review_id,
                    status=status,
                    cancelled=cancel_event.is_set(),
                )
        except Exception as exc:
            _logger.error("Background review execution failed: review_id={}", review_id)
            error_event = TraceEvent(
                kind="error",
                summary=f"审核任务异常: {exc}",
                detail=f"{type(exc).__name__}: {exc}",
                is_error=True,
            )
            self.event_store.append(review_id, error_event)
            terminal_kind = "error"
        finally:
            set_contract_review_service(None)  # type: ignore[arg-type]
            with self._guard:
                if terminal_kind == "final":
                    self._states[review_id] = "completed"
                elif cancel_event.is_set():
                    self._states[review_id] = "cancelled"
                elif terminal_kind == "error":
                    self._states[review_id] = "failed"
                else:
                    self._states[review_id] = "idle"

    def append_terminal_event(
        self,
        *,
        review_id: str,
        status: dict[str, Any],
        cancelled: bool,
    ) -> str:
        if cancelled:
            event = TraceEvent(
                kind="error",
                summary="审核任务已取消",
                detail="用户主动取消了当前审核任务",
                is_error=True,
            )
            self.event_store.append(review_id, event)
            return "error"

        if status.get("ready_for_report"):
            event = TraceEvent(
                kind="final",
                summary="审核流程已结束",
                detail="审核步骤已完成，可查看报告。",
                is_error=False,
            )
            self.event_store.append(review_id, event)
            return "final"

        event = TraceEvent(
            kind="error",
            summary="审核流程提前结束",
            detail=json.dumps(status, ensure_ascii=False),
            is_error=True,
        )
        self.event_store.append(review_id, event)
        return "error"
