"""
Google Gemini LLM Provider.

Supports Gemini models via the Google AI API.
"""

import json
from typing import Dict, Any, List, Optional, AsyncIterator
import httpx

from .base import BaseLLMProvider, LLMConfig, LLMResponse, ModelCapability


class GeminiProvider(BaseLLMProvider):
    """
    Google Gemini LLM provider.

    Supports:
    - Gemini 1.5 models (flash, pro)
    - Gemini 2.0 models
    - Streaming completions
    - JSON mode
    - Embeddings
    """

    DEFAULT_MODEL = "gemini-1.5-flash"

    def __init__(self, config: LLMConfig):
        """
        Initialize Gemini provider.

        Args:
            config: LLM configuration with api_key for Google AI
        """
        super().__init__(config)
        if not config.api_key:
            raise ValueError("Google AI API key is required")
        self._cached_auth_headers = {"x-goog-api-key": config.api_key}

    @property
    def name(self) -> str:
        return "gemini"

    @property
    def supported_capabilities(self) -> List[ModelCapability]:
        return [
            ModelCapability.TEXT_GENERATION,
            ModelCapability.JSON_MODE,
            ModelCapability.STREAMING,
            ModelCapability.EMBEDDINGS,
            ModelCapability.VISION,
        ]

    @classmethod
    def create(
        cls,
        api_key: str,
        model: str = DEFAULT_MODEL,
        **kwargs
    ) -> 'GeminiProvider':
        """
        Create a Gemini provider.

        Args:
            api_key: Google AI API key
            model: Model name (e.g., 'gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-2.0-flash-exp')
            **kwargs: Additional config parameters

        Returns:
            Configured GeminiProvider

        Example:
            >>> provider = GeminiProvider.create(
            ...     api_key="AIza...",
            ...     model="gemini-1.5-flash"
            ... )
        """
        config = LLMConfig(
            base_url="https://generativelanguage.googleapis.com",
            api_key=api_key,
            model=model,
            **kwargs
        )
        return cls(config)

    async def initialize(self) -> None:
        """Initialize HTTP client."""
        self._client = httpx.AsyncClient(
            base_url=self.config.base_url,
            timeout=self.config.timeout,
        )

    async def cleanup(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _build_endpoint(self, action: str = "generateContent", model: Optional[str] = None) -> str:
        """Build API endpoint for the given action and model."""
        m = model or self.config.model
        return f"/v1beta/models/{m}:{action}"

    def _build_payload(
        self, prompt: str, system_prompt: Optional[str] = None, **kwargs
    ) -> Dict[str, Any]:
        """Build the Gemini API request payload for completion endpoints."""
        data = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": kwargs.get("temperature", self.config.temperature),
                "topP": kwargs.get("top_p", self.config.top_p),
            }
        }
        if system_prompt:
            data["system_instruction"] = {"parts": [{"text": system_prompt}]}
        if self.config.max_tokens or kwargs.get("max_tokens"):
            data["generationConfig"]["maxOutputTokens"] = kwargs.get("max_tokens", self.config.max_tokens)
        return data

    async def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Generate completion using Gemini.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            **kwargs: Additional parameters (temperature, max_tokens, etc.)

        Returns:
            LLMResponse with generated text
        """
        if not self._client:
            await self.initialize()

        data = self._build_payload(prompt, system_prompt, **kwargs)
        endpoint = self._build_endpoint()
        response = await self._client.post(endpoint, json=data, headers=self._cached_auth_headers)
        response.raise_for_status()

        result = response.json()

        # Extract content from response
        content = ""
        candidates = result.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            for part in parts:
                if "text" in part:
                    content += part["text"]

        # Get usage info
        usage_metadata = result.get("usageMetadata", {})

        return LLMResponse(
            content=content,
            model=self.config.model,
            finish_reason=candidates[0].get("finishReason") if candidates else None,
            usage={
                "prompt_tokens": usage_metadata.get("promptTokenCount", 0),
                "completion_tokens": usage_metadata.get("candidatesTokenCount", 0),
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

        data = self._build_payload(prompt, system_prompt, **kwargs)
        endpoint = self._build_endpoint("streamGenerateContent") + "?alt=sse"

        async with self._client.stream("POST", endpoint, json=data, headers=self._cached_auth_headers) as response:
            response.raise_for_status()

            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    try:
                        chunk = json.loads(line[6:])
                        candidates = chunk.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            for part in parts:
                                if "text" in part:
                                    yield part["text"]
                    except json.JSONDecodeError:
                        continue

    async def get_embeddings(
        self,
        texts: List[str],
        **kwargs
    ) -> List[List[float]]:
        """
        Get embeddings using Gemini.

        Args:
            texts: List of texts to embed
            **kwargs: Additional parameters

        Returns:
            List of embedding vectors
        """
        if not self._client:
            await self.initialize()

        embeddings = []
        embed_model = kwargs.get("embed_model", "text-embedding-004")

        for text in texts:
            data = {
                "content": {
                    "parts": [{"text": text}]
                }
            }

            endpoint = self._build_endpoint("embedContent", model=embed_model)
            response = await self._client.post(endpoint, json=data, headers=self._cached_auth_headers)
            response.raise_for_status()

            result = response.json()
            embeddings.append(result.get("embedding", {}).get("values", []))

        return embeddings
