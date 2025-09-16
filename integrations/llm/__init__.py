"""
LLM integration for EBK.

Provides AI-powered features using any OpenAI-compatible API:
- Tag suggestion
- Content analysis
- Metadata enrichment
- Summary generation

Supports:
- OpenAI API
- Ollama (local models)
- LocalAI
- vLLM
- LM Studio
- Any OpenAI-compatible endpoint

Installation:
    pip install ebk[llm]

Configuration:
    # For Ollama (local)
    from integrations.llm import LLMConfig, HTTPLLMProvider
    config = LLMConfig.ollama(model="llama2")
    
    # For OpenAI
    config = LLMConfig.openai(api_key="sk-...", model="gpt-3.5-turbo")
    
    # For custom endpoint
    config = LLMConfig(base_url="http://localhost:8080/v1", model="my-model")
"""

from .http_llm_provider import (
    HTTPLLMProvider,
    LLMConfig,
    LLMTagSuggester,
    LLMContentAnalyzer
)

__all__ = [
    'HTTPLLMProvider',
    'LLMConfig', 
    'LLMTagSuggester',
    'LLMContentAnalyzer'
]