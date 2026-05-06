"""智能体核心推理层。

Keep this package initializer lightweight. Several low-level modules import
``src.core.config`` during startup; eager imports here can create circular
imports through ``src.utils``.
"""

__all__ = ["Agent", "AgentState", "build_graph"]


def __getattr__(name):
    if name == "Agent":
        from .agent import Agent
        return Agent
    if name == "AgentState":
        from .state import AgentState
        return AgentState
    if name == "build_graph":
        from .graph import build_graph
        return build_graph
    raise AttributeError(name)
