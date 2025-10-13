"""
Base abstract LLM provider interface.

This module defines the abstract base class that all LLM providers must implement.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, AsyncIterator
from dataclasses import dataclass
from enum import Enum


class ModelCapability(Enum):
    """Capabilities that an LLM model might support."""
    TEXT_GENERATION = "text_generation"
    JSON_MODE = "json_mode"
    FUNCTION_CALLING = "function_calling"
    STREAMING = "streaming"
    VISION = "vision"
    EMBEDDINGS = "embeddings"


@dataclass
class LLMConfig:
    """Configuration for LLM provider."""

    # Connection settings
    base_url: str
    api_key: Optional[str] = None

    # Model settings
    model: str = "default"
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    top_p: float = 0.9

    # Behavior settings
    timeout: float = 60.0
    max_retries: int = 3

    # Additional provider-specific settings
    extra_params: Dict[str, Any] = None

    def __post_init__(self):
        if self.extra_params is None:
            self.extra_params = {}


@dataclass
class LLMResponse:
    """Response from LLM completion."""

    content: str
    model: str
    finish_reason: Optional[str] = None
    usage: Optional[Dict[str, int]] = None  # tokens used
    raw_response: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "content": self.content,
            "model": self.model,
            "finish_reason": self.finish_reason,
            "usage": self.usage,
        }


class BaseLLMProvider(ABC):
    """
    Abstract base class for LLM providers.

    All LLM providers must implement this interface to ensure consistency
    across different backends (Ollama, OpenAI, Anthropic, etc.).
    """

    def __init__(self, config: LLMConfig):
        """
        Initialize the provider with configuration.

        Args:
            config: LLM configuration
        """
        self.config = config
        self._client = None

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name (e.g., 'ollama', 'openai')."""
        pass

    @property
    @abstractmethod
    def supported_capabilities(self) -> List[ModelCapability]:
        """List of capabilities supported by this provider."""
        pass

    @abstractmethod
    async def initialize(self) -> None:
        """
        Initialize the provider (establish connections, etc.).

        This is called once before first use.
        """
        pass

    @abstractmethod
    async def cleanup(self) -> None:
        """
        Cleanup resources (close connections, etc.).

        This is called when the provider is no longer needed.
        """
        pass

    @abstractmethod
    async def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Generate a text completion.

        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt to set context
            **kwargs: Additional provider-specific parameters

        Returns:
            LLMResponse with generated text

        Raises:
            Exception: If completion fails
        """
        pass

    @abstractmethod
    async def complete_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        schema: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate a JSON completion.

        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt
            schema: Optional JSON schema to validate against
            **kwargs: Additional parameters

        Returns:
            Parsed JSON object

        Raises:
            Exception: If completion or parsing fails
        """
        pass

    async def complete_streaming(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """
        Generate a streaming text completion.

        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt
            **kwargs: Additional parameters

        Yields:
            Text chunks as they are generated

        Raises:
            NotImplementedError: If streaming is not supported
        """
        raise NotImplementedError(
            f"{self.name} does not support streaming completions"
        )

    async def get_embeddings(
        self,
        texts: List[str],
        **kwargs
    ) -> List[List[float]]:
        """
        Get embeddings for text inputs.

        Args:
            texts: List of texts to embed
            **kwargs: Additional parameters

        Returns:
            List of embedding vectors

        Raises:
            NotImplementedError: If embeddings are not supported
        """
        raise NotImplementedError(
            f"{self.name} does not support embeddings"
        )

    def supports_capability(self, capability: ModelCapability) -> bool:
        """
        Check if provider supports a specific capability.

        Args:
            capability: The capability to check

        Returns:
            True if supported
        """
        return capability in self.supported_capabilities

    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.cleanup()
