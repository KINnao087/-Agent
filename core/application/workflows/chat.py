from __future__ import annotations

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from core.application.agent.tools import TOOLS
from core.infrastructure.ai import build_chat_model
from core.infrastructure.ai.prompts import CLI_AGENT_PROMPT


def build_chat_graph():
    model = build_chat_model().bind_tools(TOOLS)

    def call_model(state: MessagesState):
        messages = CLI_AGENT_PROMPT.invoke(
            {"messages": state["messages"]}
        ).to_messages()
        return {"messages": [model.invoke(messages)]}

    graph = StateGraph(MessagesState)
    graph.add_node("assistant", call_model)
    graph.add_node("tools", ToolNode(TOOLS, handle_tool_errors=False))
    graph.add_edge(START, "assistant")
    graph.add_conditional_edges(
        "assistant",
        tools_condition,
        {"tools": "tools", END: END},
    )
    graph.add_edge("tools", "assistant")
    return graph.compile(checkpointer=InMemorySaver())
