"""
LLM Provider Abstractions for EBK.

Provides a unified interface for various LLM providers including:
- Ollama (local and remote)
- OpenAI
- Anthropic
- Any OpenAI-compatible API

Future: MCP client support for tool calling and web search.
"""

from .base import BaseLLMProvider, LLMConfig, LLMResponse
from .ollama import OllamaProvider

__all__ = [
    'BaseLLMProvider',
    'LLMConfig',
    'LLMResponse',
    'OllamaProvider',
]
