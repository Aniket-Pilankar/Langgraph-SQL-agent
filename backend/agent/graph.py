from functools import cache

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage
from langchain_core.runnables import Runnable
from langchain_openai import ChatOpenAI
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from agent.prompts import SYSTEM_PROMPT
from agent.tools import TOOLS

MODEL_NAME = "gpt-4o-mini"
RECURSION_LIMIT = 12


@cache
def get_llm() -> BaseChatModel:
    return ChatOpenAI(model=MODEL_NAME, temperature=0)


@cache
def get_llm_with_tools() -> Runnable:
    return get_llm().bind_tools(TOOLS)


class AgentState(MessagesState):
    pass


async def agent_node(state: AgentState) -> dict:
    response = await get_llm_with_tools().ainvoke([SystemMessage(SYSTEM_PROMPT), *state["messages"]])
    return {"messages": [response]}


def build_graph(checkpointer=None):
    builder = StateGraph(AgentState)
    builder.add_node("agent", agent_node)
    builder.add_node("tools", ToolNode(TOOLS))

    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", tools_condition)
    builder.add_edge("tools", "agent")

    return builder.compile(checkpointer=checkpointer)
