"""Compatibility facade for the former combined Ollama module."""

from mafuyu_ai.llm.agent_protocol import agent_step, extract_json, repair_json
from mafuyu_ai.llm.client import (
    call_heavy,
    call_main,
    call_ollama,
    call_ollama_model,
    call_router,
    chat,
)

__all__ = [
    "agent_step",
    "call_heavy",
    "call_main",
    "call_ollama",
    "call_ollama_model",
    "call_router",
    "chat",
    "extract_json",
    "repair_json",
]
