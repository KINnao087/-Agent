from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from langchain_core.messages import HumanMessage
from langgraph.graph.state import CompiledStateGraph

from core.application.workflows.chat import build_chat_graph


@dataclass(slots=True)
class CliChatService:
    graph: CompiledStateGraph
    thread_id: str

    def ask(self, message: str) -> str:
        state = self.graph.invoke(
            {"messages": [HumanMessage(content=message)]},
            config={"configurable": {"thread_id": self.thread_id}},
        )
        content = state["messages"][-1].content
        return content if isinstance(content, str) else str(content)


def create_cli_chat_service() -> CliChatService:
    return CliChatService(
        graph=build_chat_graph(),
        thread_id=str(uuid4()),
    )
