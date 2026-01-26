
import logging
from langchain_core.messages import AIMessage
from langgraph.graph import StateGraph
from langgraph.types import interrupt
from langgraph.graph import START, END

from .state import DemoState

logger = logging.getLogger(__name__)


async def node_chat(state: DemoState):
    """chat"""
    content = state.get("content", "")

    new_content = content + "[chat]"
    logger.info(f"[Node chat] content: '{content}' -> '{new_content}'")

    msg = AIMessage("你好 will")
    return {"messages": msg, "content": new_content}

def node_hitl(state: DemoState):
    """人工审批"""
    content = state.get("content", "")

    auto_accepted = state.get("auto_accepted", False)
    # 如果不是自动接受，则中断等待人工批准
    approval = None
    if not auto_accepted:
        logger.info(f"[Node hitl] Interrupting for approval, content: '{content}'")
        approval = interrupt({"message": "需要批准", "content": content})
        logger.info(f"[Node hitl] Received approval: {approval}")

    new_content = content + "[hitl]"
    if approval:
        new_content += approval
    logger.info(f"[Node hitl] content: '{content}' -> '{new_content}'")
    return {"content": new_content}

def router_from_hitl(state: DemoState):
    """路由"""
    if "REJECTED" in state["content"]:
        return END
    else:
        return "node_error"

def node_error(state: DemoState):
    """异常中断"""
    content = state.get("content", "")

    if "error" in content:
        raise RuntimeError("error in content")

    new_content = content + "[error]"
    logger.info(f"[Node error] content: '{content}' -> '{new_content}'")
    return {"content": new_content}

def node_normal(state: DemoState):
    """普通逻辑"""
    content = state.get("content", "")

    new_content = content + "[normal]"
    logger.info(f"[Node normal] content: '{content}' -> '{new_content}'")
    return {"content": new_content}

def create_graph():
    """创建图"""
    builder = StateGraph(DemoState)

    # 添加节点
    builder.add_node("node_chat", node_chat)
    builder.add_node("node_hitl", node_hitl)
    builder.add_node("node_error", node_error)
    builder.add_node("node_normal", node_normal)

    # 添加边
    builder.add_edge(START, "node_chat")
    builder.add_edge("node_chat", "node_hitl")
    builder.add_conditional_edges("node_hitl", router_from_hitl)
    builder.add_edge("node_error", "node_normal")
    builder.add_edge("node_normal", END)

    return builder.compile()

def create_graph2():
    """创建图"""
    builder = StateGraph(DemoState)

    # 添加节点
    builder.add_node("node_chat", node_chat)

    # 添加边
    builder.add_edge(START, "node_chat")
    builder.add_edge("node_chat", END)

    return builder.compile()

graph = create_graph()
graph2 = create_graph2()
