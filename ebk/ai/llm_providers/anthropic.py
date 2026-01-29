"""
Anthropic Claude LLM Provider.

Supports Claude models via the Anthropic API.
"""

import json
from typing import Dict, Any, List, Optional, AsyncIterator
import httpx

from .base import BaseLLMProvider, LLMConfig, LLMResponse, ModelCapability


class AnthropicProvider(BaseLLMProvider):
    """
    Anthropic Claude LLM provider.

    Supports:
    - Claude 3 models (haiku, sonnet, opus)
    - Claude 3.5/4 models
    - Streaming completions
    - JSON mode (via prompting)
    """

    API_VERSION = "2023-06-01"
    DEFAULT_MODEL = "claude-sonnet-4-20250514"

    def __init__(self, config: LLMConfig):
        """
        Initialize Anthropic provider.

        Args:
            config: LLM configuration with api_key for Anthropic
        """
        super().__init__(config)
        if not config.api_key:
            raise ValueError("Anthropic API key is required")

    @property
    def name(self) -> str:
        return "anthropic"

    @property
    def supported_capabilities(self) -> List[ModelCapability]:
        return [
            ModelCapability.TEXT_GENERATION,
            ModelCapability.JSON_MODE,
            ModelCapability.STREAMING,
            ModelCapability.VISION,
        ]

    @classmethod
    def create(
        cls,
        api_key: str,
        model: str = DEFAULT_MODEL,
        **kwargs
    ) -> 'AnthropicProvider':
        """
        Create an Anthropic provider.

        Args:
            api_key: Anthropic API key
            model: Model name (e.g., 'claude-sonnet-4-20250514', 'claude-3-5-sonnet-20241022')
            **kwargs: Additional config parameters

        Returns:
            Configured AnthropicProvider

        Example:
            >>> provider = AnthropicProvider.create(
            ...     api_key="sk-ant-...",
            ...     model="claude-sonnet-4-20250514"
            ... )
        """
        config = LLMConfig(
            base_url="https://api.anthropic.com",
            api_key=api_key,
            model=model,
            **kwargs
        )
        return cls(config)

    async def initialize(self) -> None:
        """Initialize HTTP client with Anthropic headers."""
        self._client = httpx.AsyncClient(
            base_url=self.config.base_url,
            timeout=self.config.timeout,
            headers={
                "x-api-key": self.config.api_key,
                "anthropic-version": self.API_VERSION,
                "content-type": "application/json",
            }
        )

    async def cleanup(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Generate completion using Anthropic Claude.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            **kwargs: Additional parameters (temperature, max_tokens, etc.)

        Returns:
            LLMResponse with generated text
        """
        if not self._client:
            await self.initialize()

        # Build request payload - Anthropic uses messages format
        data = {
            "model": self.config.model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens or 4096),
            "temperature": kwargs.get("temperature", self.config.temperature),
            "top_p": kwargs.get("top_p", self.config.top_p),
        }

        if system_prompt:
            data["system"] = system_prompt

        # Make request
        response = await self._client.post("/v1/messages", json=data)
        response.raise_for_status()

        result = response.json()

        # Extract content from response
        content = ""
        if result.get("content"):
            for block in result["content"]:
                if block.get("type") == "text":
                    content += block.get("text", "")

        return LLMResponse(
            content=content,
            model=result.get("model", self.config.model),
            finish_reason=result.get("stop_reason"),
            usage={
                "prompt_tokens": result.get("usage", {}).get("input_tokens", 0),
                "completion_tokens": result.get("usage", {}).get("output_tokens", 0),
            },
            raw_response=result,
        )

    async def complete_streaming(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """
        Generate streaming completion.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            **kwargs: Additional parameters

        Yields:
            Text chunks as they are generated
        """
        if not self._client:
            await self.initialize()

        data = {
            "model": self.config.model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens or 4096),
            "temperature": kwargs.get("temperature", self.config.temperature),
            "top_p": kwargs.get("top_p", self.config.top_p),
            "stream": True,
        }

        if system_prompt:
            data["system"] = system_prompt

        async with self._client.stream("POST", "/v1/messages", json=data) as response:
            response.raise_for_status()

            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    try:
                        chunk = json.loads(line[6:])
                        # Handle different event types
                        if chunk.get("type") == "content_block_delta":
                            delta = chunk.get("delta", {})
                            if delta.get("type") == "text_delta":
                                yield delta.get("text", "")
                        elif chunk.get("type") == "message_stop":
                            break
                    except json.JSONDecodeError:
                        continue
