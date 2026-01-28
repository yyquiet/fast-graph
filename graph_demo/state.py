from langgraph.graph import MessagesState

class DemoState(MessagesState):
    """状态"""
    content: str
    auto_accepted: bool
    not_throw_error: bool
