from langchain_core.messages import HumanMessage, AIMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import MessagesState, StateGraph, START

from apps.backend.services.llm import build_llm


def build_graph(llm=None):
    if llm is None:
        llm = build_llm()
    memory = MemorySaver()

    def chatbot(state: MessagesState):
        messages = state["messages"]
        response = llm.invoke(messages)
        return {"messages": [response]}

    graph = StateGraph(MessagesState)
    graph.add_node("chatbot", chatbot)
    graph.add_edge(START, "chatbot")
    return graph.compile(checkpointer=memory)


app_graph = build_graph()
