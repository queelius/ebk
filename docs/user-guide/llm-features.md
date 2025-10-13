# LLM-Powered Features

ebk includes AI-powered features for metadata enrichment using Large Language Models (LLMs). These features can automatically generate tags, categorize books, enhance descriptions, and more.

## Overview

The LLM features are built on an abstract provider system that supports multiple backends:

- **Ollama** - Local and remote models (currently supported)
- **OpenAI** - GPT models (planned)
- **Anthropic** - Claude models (planned)
- **Custom providers** - Extend with your own

## Quick Start

### 1. Install Ollama

First, install Ollama from [https://ollama.com](https://ollama.com)

```bash
# On macOS/Linux
curl https://ollama.ai/install.sh | sh

# Or download installer from website for Windows
```

### 2. Pull a Model

```bash
# Pull the recommended model
ollama pull llama3.2

# Or try other models
ollama pull mistral
ollama pull codellama
ollama pull phi3
```

### 3. Configure ebk

```bash
ebk config init
ebk config set llm.provider ollama
ebk config set llm.model llama3.2
ebk config set llm.host localhost
```

### 4. Enrich Your Library

```bash
# Basic enrichment
ebk enrich ~/my-library

# Full enrichment with all features
ebk enrich ~/my-library \
  --generate-tags \
  --categorize \
  --enhance-descriptions
```

## Metadata Enrichment Features

### Generate Tags

Automatically generate relevant tags based on book metadata and content:

```bash
# Generate tags for all books
ebk enrich ~/library --generate-tags

# Generate tags for specific book
ebk enrich ~/library --book-id 42 --generate-tags
```

**Example output:**
- Input: "Introduction to Algorithms" by Cormen et al.
- Generated tags: `algorithms`, `computer-science`, `textbook`, `data-structures`, `complexity-theory`

### Categorize Books

Automatically assign books to hierarchical categories:

```bash
# Categorize all books
ebk enrich ~/library --categorize

# Categorize specific book
ebk enrich ~/library --book-id 42 --categorize
```

**Example categories:**
- `Technology > Computer Science > Algorithms`
- `Technology > Programming > Python`
- `Science > Mathematics > Statistics`

### Enhance Descriptions

Generate or improve book descriptions based on content samples:

```bash
# Enhance descriptions
ebk enrich ~/library --enhance-descriptions

# For specific book
ebk enrich ~/library --book-id 42 --enhance-descriptions
```

This feature:
- Creates descriptions for books without them
- Expands brief descriptions with more detail
- Extracts key themes and topics
- Maintains professional tone

### Assess Difficulty Level

Automatically determine the reading difficulty level:

```bash
ebk enrich ~/library --assess-difficulty
```

**Difficulty levels:**
- `beginner` - Introductory material
- `intermediate` - Requires some background
- `advanced` - Specialized knowledge required
- `expert` - Research-level content

### Full Enrichment

Run all enrichment features at once:

```bash
# Complete enrichment
ebk enrich ~/library \
  --generate-tags \
  --categorize \
  --enhance-descriptions \
  --assess-difficulty
```

## Provider Configuration

### Local Ollama

The default configuration uses a local Ollama instance:

```bash
ebk config set llm.provider ollama
ebk config set llm.model llama3.2
ebk config set llm.host localhost
ebk config set llm.port 11434
```

### Remote GPU Server

For faster processing, use a remote machine with GPU:

```bash
# By IP address
ebk config set llm.host 192.168.1.100

# Or by hostname
ebk config set llm.host gpu-server.local

# Test connection
curl http://192.168.1.100:11434/api/tags
```

**Setup remote Ollama:**

On the remote machine:

```bash
# Install Ollama
curl https://ollama.ai/install.sh | sh

# Pull models
ollama pull llama3.2

# Ollama automatically listens on 0.0.0.0:11434
```

### CLI Overrides

Override config settings for individual commands:

```bash
# Use different host
ebk enrich ~/library --host 192.168.1.100

# Use different model
ebk enrich ~/library --model mistral

# Combine options
ebk enrich ~/library \
  --host gpu-server.local \
  --model llama3.2:70b \
  --generate-tags \
  --categorize
```

## Model Selection

### Recommended Models

| Model | Size | Speed | Quality | Use Case |
|-------|------|-------|---------|----------|
| `llama3.2` | 7B | Fast | Good | General purpose, recommended |
| `llama3.2:1b` | 1B | Very fast | Fair | Quick processing, limited resources |
| `llama3.2:70b` | 70B | Slow | Excellent | Best quality, requires GPU |
| `mistral` | 7B | Fast | Good | Alternative to llama3.2 |
| `phi3` | 3.8B | Fast | Good | Balanced speed/quality |
| `codellama` | 7B | Fast | Good | Technical books |

### Model Parameters

Adjust model behavior:

```bash
# Lower temperature for consistent results
ebk config set llm.temperature 0.3

# Higher temperature for creative descriptions
ebk config set llm.temperature 0.9

# Limit output length
ebk config set llm.max_tokens 500
```

**Temperature guide:**
- `0.0-0.3` - Very consistent, factual (recommended for tags/categories)
- `0.4-0.7` - Balanced (default)
- `0.8-1.0` - Creative, varied (for descriptions)

## Python API

Use LLM features programmatically:

```python
from ebk.ai.llm_providers.ollama import OllamaProvider
from ebk.ai.metadata_enrichment import MetadataEnrichmentService

# Initialize provider
provider = OllamaProvider.local(model="llama3.2")

# Or remote
provider = OllamaProvider.remote(
    host="192.168.1.100",
    model="llama3.2"
)

# Create enrichment service
service = MetadataEnrichmentService(provider)

# Use async context manager
async with provider:
    # Generate tags
    tags = await service.generate_tags(
        title="The Pragmatic Programmer",
        authors=["Hunt", "Thomas"],
        description="From journeyman to master"
    )
    print(f"Generated tags: {tags}")

    # Categorize
    categories = await service.categorize(
        title="Introduction to Algorithms",
        subjects=["Algorithms", "Computer Science"]
    )
    print(f"Categories: {categories}")

    # Enhance description
    enhanced = await service.enhance_description(
        title="Clean Code",
        text_sample="Chapter 1: Clean Code..."
    )
    print(f"Enhanced: {enhanced}")
```

### Batch Processing

Process multiple books efficiently:

```python
from ebk.library_db import Library
from ebk.ai.llm_providers.ollama import OllamaProvider
from ebk.ai.metadata_enrichment import MetadataEnrichmentService
from pathlib import Path

# Open library
lib = Library.open(Path("~/my-library"))

# Initialize provider
provider = OllamaProvider.local(model="llama3.2")
service = MetadataEnrichmentService(provider)

async with provider:
    # Get books without tags
    books = lib.query().limit(10).all()

    for book in books:
        # Generate tags
        tags = await service.generate_tags(
            title=book.title,
            authors=[a.name for a in book.authors],
            description=book.description
        )

        # Add to library
        lib.add_tags(book.id, tags)
        print(f"Added tags to {book.title}: {tags}")

lib.close()
```

## Advanced Usage

### Dry Run Mode

Preview changes without saving:

```bash
# See what would be changed
ebk enrich ~/library --generate-tags --dry-run
```

This outputs proposed changes but doesn't modify the library.

### Selective Enrichment

Enrich only books matching criteria:

```bash
# Only books without descriptions
ebk enrich ~/library --enhance-descriptions --filter "description:null"

# Only books in specific language
ebk enrich ~/library --generate-tags --filter "language:en"

# Only specific author
ebk enrich ~/library --categorize --filter "author:Knuth"
```

### Custom Prompts

Customize the prompts used for enrichment:

```python
from ebk.ai.metadata_enrichment import MetadataEnrichmentService

service = MetadataEnrichmentService(provider)

# Custom tag generation prompt
custom_prompt = """
Based on this book:
Title: {title}
Authors: {authors}
Description: {description}

Generate 5-7 specific technical tags focusing on:
1. Programming languages mentioned
2. Specific technologies or frameworks
3. Target audience level
4. Book format (reference, tutorial, guide)

Return as comma-separated list.
"""

tags = await service.generate_tags_with_prompt(
    title="Python Crash Course",
    custom_prompt=custom_prompt
)
```

## Performance Optimization

### Use Remote GPU

**10-100x speedup** by using a machine with NVIDIA GPU:

```bash
# Configure remote GPU server
ebk config set llm.host gpu-server.local

# Verify GPU is being used
ssh gpu-server.local nvidia-smi
```

### Batch Size

Process multiple books in parallel:

```bash
# Process 10 books at a time
ebk enrich ~/library --batch-size 10
```

### Model Selection

Choose model based on speed/quality tradeoff:

```bash
# Fastest (1B parameters)
ebk enrich ~/library --model llama3.2:1b

# Balanced (7B parameters, recommended)
ebk enrich ~/library --model llama3.2

# Best quality (70B parameters, slow)
ebk enrich ~/library --model llama3.2:70b
```

### Text Sampling

Limit text analyzed for speed:

```bash
# Use first 5000 chars of extracted text
ebk enrich ~/library --text-sample-size 5000
```

## Troubleshooting

### Connection Refused

If ebk can't connect to Ollama:

```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Start Ollama (if needed)
ollama serve

# Check configuration
ebk config get llm.host
ebk config get llm.port
```

### Model Not Found

If the model isn't available:

```bash
# List available models
ollama list

# Pull the required model
ollama pull llama3.2

# Verify model is available
curl http://localhost:11434/api/tags
```

### Slow Performance

If enrichment is too slow:

1. **Use remote GPU server:**
   ```bash
   ebk config set llm.host gpu-server.local
   ```

2. **Use smaller model:**
   ```bash
   ebk config set llm.model llama3.2:1b
   ```

3. **Reduce text sample size:**
   ```bash
   ebk enrich ~/library --text-sample-size 2000
   ```

4. **Process in batches:**
   ```bash
   ebk enrich ~/library --batch-size 5
   ```

### Out of Memory

If Ollama runs out of memory:

1. **Use smaller model:**
   ```bash
   ollama pull llama3.2:1b
   ebk config set llm.model llama3.2:1b
   ```

2. **Reduce context size:**
   ```bash
   ebk config set llm.max_tokens 500
   ```

3. **Close other applications** consuming memory

4. **Use remote server** with more RAM

## Best Practices

1. **Start with dry run** to preview changes:
   ```bash
   ebk enrich ~/library --generate-tags --dry-run
   ```

2. **Use appropriate temperature**:
   - Tags/categories: 0.3 (consistent)
   - Descriptions: 0.7 (balanced)

3. **Process in batches** for large libraries:
   ```bash
   ebk enrich ~/library --batch-size 10
   ```

4. **Use remote GPU** for speed:
   ```bash
   ebk config set llm.host gpu-server.local
   ```

5. **Review and refine** generated metadata periodically

6. **Backup library** before bulk enrichment:
   ```bash
   ebk export zip ~/library ~/backup.zip
   ```

## Examples

### Enrich New Import

After importing books, enrich their metadata:

```bash
# Import from Calibre
ebk import-calibre ~/Calibre/Library --output ~/my-library

# Generate tags for all books
ebk enrich ~/my-library --generate-tags

# Categorize
ebk enrich ~/my-library --categorize
```

### Improve Existing Metadata

Enhance metadata for existing library:

```bash
# Enhance descriptions for books without them
ebk enrich ~/library --enhance-descriptions --filter "description:null"

# Add tags to all books
ebk enrich ~/library --generate-tags
```

### Target Specific Books

Enrich specific subset of books:

```bash
# Only Python books
ebk enrich ~/library --generate-tags --filter "subject:Python"

# Only books from specific author
ebk enrich ~/library --categorize --filter "author:Knuth"

# Only recent books
ebk enrich ~/library --enhance-descriptions --filter "year:2020-"
```

## Future Features

Planned LLM-powered features:

- **Similarity detection** - Find duplicate books with different metadata
- **Summary generation** - Create book summaries from content
- **Reading level assessment** - Determine appropriate audience
- **Topic extraction** - Identify key topics and themes
- **Citation extraction** - Extract and link referenced works
- **Question generation** - Create study questions
- **Translation** - Translate metadata between languages

## Next Steps

- [Configuration Guide](../getting-started/configuration.md) - Set up LLM provider
- [CLI Reference](cli.md) - Complete command reference
- [Python API](api.md) - Programmatic access
- [LLM Providers README](/home/spinoza/github/beta/ebk/ebk/ai/llm_providers/README.md) - Provider details
