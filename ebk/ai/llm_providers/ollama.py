"""
Ollama LLM Provider.

Supports both local and remote Ollama instances.
"""

import json
from typing import Dict, Any, List, Optional, AsyncIterator
import httpx

from .base import BaseLLMProvider, LLMConfig, LLMResponse, ModelCapability


class OllamaProvider(BaseLLMProvider):
    """
    Ollama LLM provider.

    Supports:
    - Local Ollama (default: http://localhost:11434)
    - Remote Ollama (e.g., basement GPU server)
    - Streaming completions
    - JSON mode
    - Embeddings
    """

    def __init__(self, config: LLMConfig):
        """
        Initialize Ollama provider.

        Args:
            config: LLM configuration with base_url pointing to Ollama
        """
        super().__init__(config)

    @property
    def name(self) -> str:
        return "ollama"

    @property
    def supported_capabilities(self) -> List[ModelCapability]:
        return [
            ModelCapability.TEXT_GENERATION,
            ModelCapability.JSON_MODE,
            ModelCapability.STREAMING,
            ModelCapability.EMBEDDINGS,
        ]

    @classmethod
    def local(cls, model: str = "llama3.2", **kwargs) -> 'OllamaProvider':
        """
        Create provider for local Ollama instance.

        Args:
            model: Model name (e.g., 'llama3.2', 'mistral', 'codellama')
            **kwargs: Additional config parameters

        Returns:
            Configured OllamaProvider
        """
        config = LLMConfig(
            base_url="http://localhost:11434",
            model=model,
            **kwargs
        )
        return cls(config)

    @classmethod
    def remote(
        cls,
        host: str,
        port: int = 11434,
        model: str = "llama3.2",
        **kwargs
    ) -> 'OllamaProvider':
        """
        Create provider for remote Ollama instance.

        Args:
            host: Remote host (e.g., '192.168.1.100', 'basement-gpu.local')
            port: Ollama port (default: 11434)
            model: Model name
            **kwargs: Additional config parameters

        Returns:
            Configured OllamaProvider

        Example:
            >>> provider = OllamaProvider.remote(
            ...     host='192.168.1.100',
            ...     model='llama3.2'
            ... )
        """
        config = LLMConfig(
            base_url=f"http://{host}:{port}",
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

    async def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Generate completion using Ollama.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            **kwargs: Additional parameters (temperature, max_tokens, etc.)

        Returns:
            LLMResponse with generated text
        """
        if not self._client:
            await self.initialize()

        # Build request payload
        data = {
            "model": self.config.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": kwargs.get("temperature", self.config.temperature),
                "top_p": kwargs.get("top_p", self.config.top_p),
            }
        }

        if system_prompt:
            data["system"] = system_prompt

        if self.config.max_tokens:
            data["options"]["num_predict"] = self.config.max_tokens

        # Make request
        response = await self._client.post("/api/generate", json=data)
        response.raise_for_status()

        result = response.json()

        return LLMResponse(
            content=result["response"],
            model=result.get("model", self.config.model),
            finish_reason=result.get("done_reason"),
            usage={
                "prompt_tokens": result.get("prompt_eval_count", 0),
                "completion_tokens": result.get("eval_count", 0),
            },
            raw_response=result,
        )

    async def complete_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        schema: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate JSON completion using Ollama's JSON format mode.

        Overrides base to set Ollama's format="json" parameter
        before delegating to the shared prompt-building logic.
        """
        # Use Ollama's JSON format mode if available
        kwargs["format"] = "json"
        return await super().complete_json(prompt, system_prompt=system_prompt, schema=schema, **kwargs)

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
            "prompt": prompt,
            "stream": True,
            "options": {
                "temperature": kwargs.get("temperature", self.config.temperature),
                "top_p": kwargs.get("top_p", self.config.top_p),
            }
        }

        if system_prompt:
            data["system"] = system_prompt

        async with self._client.stream("POST", "/api/generate", json=data) as response:
            response.raise_for_status()

            async for line in response.aiter_lines():
                if line.strip():
                    try:
                        chunk = json.loads(line)
                        if "response" in chunk:
                            yield chunk["response"]
                        if chunk.get("done", False):
                            break
                    except json.JSONDecodeError:
                        continue

    async def get_embeddings(
        self,
        texts: List[str],
        **kwargs
    ) -> List[List[float]]:
        """
        Get embeddings using Ollama.

        Args:
            texts: List of texts to embed
            **kwargs: Additional parameters

        Returns:
            List of embedding vectors
        """
        if not self._client:
            await self.initialize()

        embeddings = []

        for text in texts:
            data = {
                "model": self.config.model,
                "prompt": text,
            }

            response = await self._client.post("/api/embeddings", json=data)
            response.raise_for_status()

            result = response.json()
            embeddings.append(result["embedding"])

        return embeddings

    async def list_models(self) -> List[str]:
        """
        List available models on Ollama server.

        Returns:
            List of model names
        """
        if not self._client:
            await self.initialize()

        response = await self._client.get("/api/tags")
        response.raise_for_status()

        result = response.json()
        return [model["name"] for model in result.get("models", [])]

    async def pull_model(self, model_name: str) -> None:
        """
        Pull a model from Ollama registry.

        Args:
            model_name: Name of model to pull (e.g., 'llama3.2', 'mistral')
        """
        if not self._client:
            await self.initialize()

        data = {"name": model_name, "stream": False}

        response = await self._client.post("/api/pull", json=data)
        response.raise_for_status()
