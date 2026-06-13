from __future__ import annotations

import json

from langchain_core.messages import AIMessage, ToolMessage

from core.application.agent.chat_service import CliChatService


class FakeGraph:
    def __init__(self, updates=None, error: Exception | None = None) -> None:
        self.updates = updates or []
        self.error = error
        self.calls = []

    def stream(self, input, config, stream_mode):
        self.calls.append((input, config, stream_mode))
        if self.error:
            raise self.error
        yield from self.updates


def test_stream_emits_tool_decision_result_and_final_answer() -> None:
    graph = FakeGraph(
        [
            {
                "assistant": {
                    "messages": [
                        AIMessage(
                            content="",
                            tool_calls=[
                                {
                                    "name": "prepare_contract",
                                    "args": {"contract_path": "D:/contract.pdf"},
                                    "id": "call-1",
                                    "type": "tool_call",
                                }
                            ],
                        )
                    ]
                }
            },
            {
                "tools": {
                    "messages": [
                        ToolMessage(
                            content=json.dumps(
                                {
                                    "review_id": "review-1",
                                    "cached": False,
                                }
                            ),
                            tool_call_id="call-1",
                            name="prepare_contract",
                        )
                    ]
                }
            },
            {
                "assistant": {
                    "messages": [AIMessage(content="审核任务已准备完成。")]
                }
            },
        ]
    )
    service = CliChatService(graph=graph, thread_id="thread-1")

    events = list(service.stream("审核合同"))

    assert [event.kind for event in events] == [
        "turn_start",
        "decision",
        "tool_start",
        "tool_result",
        "final",
    ]
    assert events[2].tool_call_id == "call-1"
    assert '"contract_path": "D:/contract.pdf"' in events[2].detail
    assert events[3].tool_name == "prepare_contract"
    assert events[3].elapsed_ms is not None
    assert events[3].is_error is False
    assert events[-1].detail == "审核任务已准备完成。"
    assert graph.calls[0][2] == "updates"


def test_stream_tracks_parallel_tools_by_call_id() -> None:
    graph = FakeGraph(
        [
            {
                "assistant": {
                    "messages": [
                        AIMessage(
                            content="",
                            tool_calls=[
                                {
                                    "name": "first",
                                    "args": {"value": 1},
                                    "id": "call-1",
                                    "type": "tool_call",
                                },
                                {
                                    "name": "second",
                                    "args": {"value": 2},
                                    "id": "call-2",
                                    "type": "tool_call",
                                },
                            ],
                        )
                    ]
                }
            },
            {
                "tools": {
                    "messages": [
                        ToolMessage(
                            content='{"status": "ok"}',
                            tool_call_id="call-2",
                            name="second",
                        ),
                        ToolMessage(
                            content='{"status": "ok"}',
                            tool_call_id="call-1",
                            name="first",
                        ),
                    ]
                }
            },
            {"assistant": {"messages": [AIMessage(content="done")]}},
        ]
    )

    events = list(CliChatService(graph=graph, thread_id="t").stream("run"))
    results = [event for event in events if event.kind == "tool_result"]

    assert [(event.tool_call_id, event.tool_name) for event in results] == [
        ("call-2", "second"),
        ("call-1", "first"),
    ]


def test_stream_marks_structured_tool_error() -> None:
    graph = FakeGraph(
        [
            {
                "assistant": {
                    "messages": [
                        AIMessage(
                            content="",
                            tool_calls=[
                                {
                                    "name": "read_text_file",
                                    "args": {"path": "missing.txt"},
                                    "id": "call-1",
                                    "type": "tool_call",
                                }
                            ],
                        )
                    ]
                }
            },
            {
                "tools": {
                    "messages": [
                        ToolMessage(
                            content='{"error": true, "message": "文件不存在"}',
                            tool_call_id="call-1",
                            name="read_text_file",
                        )
                    ]
                }
            },
            {"assistant": {"messages": [AIMessage(content="无法读取文件。")]}},
        ]
    )

    events = list(CliChatService(graph=graph, thread_id="t").stream("read"))
    result = next(event for event in events if event.kind == "tool_result")

    assert result.is_error is True
    assert result.summary == "文件不存在"


def test_stream_converts_graph_exception_to_error_event() -> None:
    service = CliChatService(
        graph=FakeGraph(error=ValueError("graph failed")),
        thread_id="t",
    )

    events = list(service.stream("run"))

    assert events[-1].kind == "error"
    assert events[-1].is_error is True
    assert "graph failed" in events[-1].detail


def test_ask_remains_compatible_with_final_answer() -> None:
    graph = FakeGraph(
        [{"assistant": {"messages": [AIMessage(content="final answer")]}}]
    )

    assert CliChatService(graph=graph, thread_id="t").ask("hello") == "final answer"
