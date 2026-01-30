"""A2A (Agent-to-Agent) 集成模块"""

from .agent_executor import GraphAgentExecutor
from .integration import setup_a2a_routes

__all__ = ['GraphAgentExecutor', 'setup_a2a_routes']
