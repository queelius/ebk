# LLM Providers

Abstract provider interface for Large Language Models in EBK.

## Architecture

```
BaseLLMProvider (abstract)
├── OllamaProvider (local & remote)
├── OpenAIProvider (TODO)
├── AnthropicProvider (TODO)
└── MCPProvider (TODO - for tool calling)
```

## Usage

### Local Ollama

```python
from ebk.ai.llm_providers.ollama import OllamaProvider

# Use local Ollama instance
provider = OllamaProvider.local(model="llama3.2")

async with provider:
    response = await provider.complete("What is Python?")
    print(response.content)
```

### Remote Ollama (GPU Server)

```python
# Connect to basement GPU server
provider = OllamaProvider.remote(
    host="192.168.1.100",  # or "basement-gpu.local"
    port=11434,
    model="llama3.2"
)

async with provider:
    # Generate tags
    tags_json = await provider.complete_json(
        prompt="Generate tags for: The Pragmatic Programmer"
    )
```

### With Metadata Enrichment Service

```python
from ebk.ai.llm_providers.ollama import OllamaProvider
from ebk.ai.metadata_enrichment import MetadataEnrichmentService

provider = OllamaProvider.remote(host="192.168.1.100", model="llama3.2")
service = MetadataEnrichmentService(provider)

async with provider:
    # Generate tags
    tags = await service.generate_tags(
        title="Introduction to Algorithms",
        authors=["Cormen", "Leiserson"],
        description="Comprehensive algorithms textbook"
    )

    # Categorize
    categories = await service.categorize(
        title="Introduction to Algorithms",
        subjects=["Algorithms", "Data Structures"]
    )

    # Enhance description
    description = await service.enhance_description(
        title="Introduction to Algorithms",
        text_sample="Chapter 1: The Role of Algorithms..."
    )
```

## CLI Usage

### Enrich Library Metadata

```bash
# Use local Ollama
ebk enrich ~/my-library

# Use remote GPU server
ebk enrich ~/my-library --host 192.168.1.100

# With specific model
ebk enrich ~/my-library --model mistral

# Enrich specific book
ebk enrich ~/my-library --book-id 42

# Generate tags and enhance descriptions
ebk enrich ~/my-library --enhance-descriptions

# Dry run (no changes saved)
ebk enrich ~/my-library --dry-run

# Full enrichment with all features
ebk enrich ~/my-library \
  --generate-tags \
  --categorize \
  --enhance-descriptions \
  --assess-difficulty
```

## Supported Models

### Ollama Models (Local/Remote)

- `llama3.2` - Meta's Llama 3.2 (recommended)
- `llama3.2:1b` - Smaller, faster version
- `mistral` - Mistral 7B
- `codellama` - Code-specialized
- `phi3` - Microsoft's Phi-3
- `gemma2` - Google's Gemma 2

Pull models: `ollama pull llama3.2`

## Provider Capabilities

| Provider | Text | JSON | Streaming | Embeddings | Functions |
|----------|------|------|-----------|------------|-----------|
| Ollama   | ✅   | ✅   | ✅        | ✅         | ❌        |
| OpenAI   | TODO | TODO | TODO      | TODO       | TODO      |
| Anthropic| TODO | TODO | TODO      | TODO       | TODO      |
| MCP      | TODO | TODO | TODO      | TODO       | ✅        |

## Configuration

### Environment Variables

```bash
# Ollama
export OLLAMA_HOST=192.168.1.100
export OLLAMA_PORT=11434

# OpenAI (when implemented)
export OPENAI_API_KEY=sk-...
export OPENAI_MODEL=gpt-4
```

### Config File

Create `~/.ebk/llm.json`:

```json
{
  "provider": "ollama",
  "model": "llama3.2",
  "host": "192.168.1.100",
  "port": 11434,
  "temperature": 0.7,
  "max_tokens": 2000
}
```

## Future: MCP Integration

The provider system is designed to support MCP (Model Context Protocol) for:
- Tool calling (web search, calculations)
- Context sharing across tools
- Multi-agent workflows

```python
# Future API
mcp_provider = MCPProvider(
    tools=["web_search", "calculator"],
    context_servers=["file_system", "browser"]
)
```

## Adding New Providers

1. Subclass `BaseLLMProvider`
2. Implement required abstract methods
3. Add to `__init__.py`
4. Update CLI to support new provider

Example:

```python
from .base import BaseLLMProvider, LLMConfig, LLMResponse

class MyProvider(BaseLLMProvider):
    @property
    def name(self) -> str:
        return "my_provider"

    async def complete(self, prompt: str, **kwargs) -> LLMResponse:
        # Implementation
        pass
```

## Error Handling

All providers raise standard exceptions:

```python
try:
    response = await provider.complete("Hello")
except httpx.HTTPError as e:
    print(f"Connection failed: {e}")
except json.JSONDecodeError as e:
    print(f"Invalid JSON response: {e}")
except Exception as e:
    print(f"Provider error: {e}")
```

## Performance Tips

1. **Use remote GPU** for faster inference (10-100x speedup)
2. **Lower temperature** (0.3) for consistent metadata
3. **Limit text length** to 5000 chars for faster processing
4. **Batch requests** when enriching many books
5. **Use specific models**: `llama3.2:1b` for speed, `llama3.2:70b` for quality
