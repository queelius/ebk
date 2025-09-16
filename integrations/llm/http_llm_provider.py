"""
Universal HTTP LLM Provider for EBK.

Works with any OpenAI-compatible API endpoint:
- OpenAI API
- Ollama (local models)
- LocalAI
- vLLM
- LM Studio
- Anthropic (via proxy)
- Any OpenAI-compatible endpoint

This provides a unified interface for all LLM operations in EBK.
"""

import json
from typing import Dict, Any, List, Optional, AsyncIterator
from dataclasses import dataclass
import httpx
from pydantic import BaseModel, Field

from ebk.plugins.base import Plugin, TagSuggester, ContentAnalyzer, TagSuggestion, ContentAnalysis


class LLMConfig(BaseModel):
    """Configuration for LLM provider."""
    base_url: str = Field(default="http://localhost:11434/v1", description="API base URL")
    api_key: Optional[str] = Field(default=None, description="API key if required")
    model: str = Field(default="llama2", description="Model name")
    temperature: float = Field(default=0.7, description="Temperature for generation")
    max_tokens: Optional[int] = Field(default=None, description="Max tokens to generate")
    timeout: float = Field(default=30.0, description="Request timeout in seconds")
    
    # Provider presets
    @classmethod
    def openai(cls, api_key: str, model: str = "gpt-3.5-turbo") -> 'LLMConfig':
        return cls(
            base_url="https://api.openai.com/v1",
            api_key=api_key,
            model=model
        )
    
    @classmethod
    def ollama(cls, model: str = "llama2", host: str = "localhost", port: int = 11434) -> 'LLMConfig':
        return cls(
            base_url=f"http://{host}:{port}/v1",
            model=model
        )
    
    @classmethod
    def local_ai(cls, model: str, host: str = "localhost", port: int = 8080) -> 'LLMConfig':
        return cls(
            base_url=f"http://{host}:{port}/v1",
            model=model
        )


class HTTPLLMProvider(Plugin):
    """
    Universal HTTP-based LLM provider using OpenAI-compatible API.
    """
    
    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or LLMConfig()
        self.client = None
        
    @property
    def name(self) -> str:
        return "http_llm_provider"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def description(self) -> str:
        return "Universal LLM provider for OpenAI-compatible APIs"
    
    def initialize(self, config: Dict[str, Any] = None) -> None:
        """Initialize with configuration."""
        if config:
            self.config = LLMConfig(**config)
        
        # Create HTTP client
        headers = {}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        
        self.client = httpx.AsyncClient(
            base_url=self.config.base_url,
            headers=headers,
            timeout=self.config.timeout
        )
    
    def cleanup(self) -> None:
        """Cleanup resources."""
        if self.client:
            # Note: Should be awaited in async context
            self.client.close()
    
    async def complete(self, prompt: str, **kwargs) -> str:
        """
        Get completion from LLM.
        
        Args:
            prompt: The prompt text
            **kwargs: Additional parameters
            
        Returns:
            Generated text
        """
        if not self.client:
            self.initialize()
        
        # Build request using OpenAI-compatible format
        data = {
            "model": self.config.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": kwargs.get("temperature", self.config.temperature),
        }
        
        if self.config.max_tokens:
            data["max_tokens"] = self.config.max_tokens
        
        response = await self.client.post("/chat/completions", json=data)
        response.raise_for_status()
        
        result = response.json()
        return result["choices"][0]["message"]["content"]
    
    async def complete_json(self, prompt: str, schema: Optional[Dict] = None, **kwargs) -> Dict:
        """
        Get JSON completion from LLM.
        
        Args:
            prompt: The prompt text
            schema: Optional JSON schema to enforce
            **kwargs: Additional parameters
            
        Returns:
            Parsed JSON object
        """
        # Add JSON instruction to prompt
        json_prompt = f"{prompt}\n\nRespond with valid JSON only."
        
        if schema:
            json_prompt += f"\n\nFollow this schema:\n{json.dumps(schema, indent=2)}"
        
        # Some providers support JSON mode directly
        if "response_format" not in kwargs:
            kwargs["response_format"] = {"type": "json_object"}
        
        response = await self.complete(json_prompt, **kwargs)
        
        # Parse JSON from response
        try:
            # Try to extract JSON from response
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            return json.loads(response)
        except json.JSONDecodeError:
            # Fallback: try to fix common issues
            cleaned = response.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            return json.loads(cleaned)


class LLMTagSuggester(TagSuggester):
    """
    Tag suggester using LLM.
    """
    
    def __init__(self, provider: HTTPLLMProvider):
        self.provider = provider
        
    @property
    def name(self) -> str:
        return f"llm_tagger_{self.provider.config.model}"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    async def suggest_tags(self, 
                          entry: Dict[str, Any],
                          max_tags: int = 10,
                          confidence_threshold: float = 0.5) -> List[TagSuggestion]:
        """
        Suggest tags using LLM.
        """
        prompt = f"""Suggest up to {max_tags} relevant tags for this book:

Title: {entry.get('title', 'Unknown')}
Authors: {', '.join(entry.get('creators', []))}
Subjects: {', '.join(entry.get('subjects', []))}
Description: {entry.get('description', 'N/A')[:500]}
Language: {entry.get('language', 'Unknown')}

Provide tags that would help someone find this book. Include genre, topics, themes, and reading level.
Return as JSON array with format: [{{"tag": "...", "confidence": 0.0-1.0}}, ...]"""

        try:
            result = await self.provider.complete_json(prompt)
            
            suggestions = []
            for item in result:
                if isinstance(item, dict) and 'tag' in item:
                    confidence = item.get('confidence', 0.8)
                    if confidence >= confidence_threshold:
                        suggestions.append(TagSuggestion(
                            tag=item['tag'],
                            confidence=confidence,
                            source=self.name
                        ))
            
            return suggestions[:max_tags]
            
        except Exception as e:
            # Log error and return empty list
            print(f"LLM tag suggestion failed: {e}")
            return []
    
    def requires_content(self) -> bool:
        return False


class LLMContentAnalyzer(ContentAnalyzer):
    """
    Content analyzer using LLM.
    """
    
    def __init__(self, provider: HTTPLLMProvider):
        self.provider = provider
        
    @property
    def name(self) -> str:
        return f"llm_analyzer_{self.provider.config.model}"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    async def analyze(self, entry: Dict[str, Any]) -> ContentAnalysis:
        """
        Analyze content using LLM.
        """
        prompt = f"""Analyze this book and provide insights:

Title: {entry.get('title', 'Unknown')}
Authors: {', '.join(entry.get('creators', []))}
Subjects: {', '.join(entry.get('subjects', []))}
Description: {entry.get('description', 'N/A')[:1000]}
Page Count: {entry.get('page_count', 'Unknown')}

Provide analysis as JSON with these fields:
- difficulty_level: "beginner", "intermediate", or "advanced"
- estimated_reading_time: minutes (based on ~250 words/minute)
- key_topics: array of main topics covered
- summary: brief 2-3 sentence summary
- quality_score: 0.0-1.0 based on description clarity and subject coverage"""

        try:
            result = await self.provider.complete_json(prompt)
            
            return ContentAnalysis(
                difficulty_level=result.get('difficulty_level'),
                reading_time=result.get('estimated_reading_time'),
                key_topics=result.get('key_topics', []),
                summary=result.get('summary'),
                quality_score=result.get('quality_score')
            )
            
        except Exception as e:
            print(f"LLM content analysis failed: {e}")
            return ContentAnalysis()


# Example usage
async def example():
    """Example of using the LLM provider."""
    
    # Configure for Ollama
    config = LLMConfig.ollama(model="llama2")
    provider = HTTPLLMProvider(config)
    
    # Or configure for OpenAI
    # config = LLMConfig.openai(api_key="sk-...", model="gpt-3.5-turbo")
    # provider = HTTPLLMProvider(config)
    
    # Use for tagging
    tagger = LLMTagSuggester(provider)
    entry = {
        "title": "The Pragmatic Programmer",
        "creators": ["David Thomas", "Andrew Hunt"],
        "subjects": ["Programming", "Software Engineering"],
        "description": "A guide to becoming a better programmer..."
    }
    
    tags = await tagger.suggest_tags(entry)
    for tag in tags:
        print(f"  {tag.tag}: {tag.confidence:.2f}")
    
    # Use for content analysis
    analyzer = LLMContentAnalyzer(provider)
    analysis = await analyzer.analyze(entry)
    print(f"Difficulty: {analysis.difficulty_level}")
    print(f"Topics: {', '.join(analysis.key_topics)}")
    
    # Cleanup
    provider.cleanup()