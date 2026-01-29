"""
LLM Provider Abstractions for EBK.

Provides a unified interface for various LLM providers including:
- Ollama (local and remote)
- OpenAI (via compatible API)
- Anthropic Claude
- Google Gemini

Future: MCP client support for tool calling and web search.
"""

from .base import BaseLLMProvider, LLMConfig, LLMResponse, ModelCapability
from .ollama import OllamaProvider
from .anthropic import AnthropicProvider
from .gemini import GeminiProvider

__all__ = [
    'BaseLLMProvider',
    'LLMConfig',
    'LLMResponse',
    'ModelCapability',
    'OllamaProvider',
    'AnthropicProvider',
    'GeminiProvider',
]
