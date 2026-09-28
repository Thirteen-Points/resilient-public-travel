"""Optional, failure-tolerant AI assistance.

This package never owns routing or operational calculations.  It only invokes
registered deterministic tools and turns their results into language.
"""

from .llm_client import LLMClient, LLMConfig, LLMResult
from .tools import ToolRegistry, build_default_registry
from .handlers import build_engine_handlers
from .query import NoLLMQueryService

__all__ = ["LLMClient", "LLMConfig", "LLMResult", "ToolRegistry", "build_default_registry", "build_engine_handlers", "NoLLMQueryService"]
