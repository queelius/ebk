# EBK Plugin System and Integrations

## Overview

EBK uses a plugin architecture to keep the core lightweight while allowing powerful extensions.

## Structure

- **`ebk/plugins/`** - Core plugin infrastructure
  - `base.py` - Abstract base classes all plugins inherit from
  - `registry.py` - Plugin discovery and management
  - `hooks.py` - Event system for plugin interaction
  
- **`integrations/`** - Bundled plugin implementations
  - `metadata/` - Metadata extractors (Google Books, OpenLibrary, etc.)
  - `network/` - Graph/network analysis
  - `mcp/` - Model Context Protocol for AI assistants
  - `streamlit-dashboard/` - Web UI

## Installation

```bash
# Core EBK (no plugins)
pip install ebk

# With specific integrations
pip install ebk[metadata]        # Metadata extractors
pip install ebk[network]         # Network analysis
pip install ebk[network-advanced] # + NetworkX for advanced features
pip install ebk[streamlit]       # Web dashboard

# All integrations
pip install ebk[all]

# Development (includes testing tools)
pip install ebk[dev]
```

## Creating a Plugin

### 1. Choose a Base Class

```python
from ebk.plugins.base import (
    MetadataExtractor,  # Extract metadata from sources
    TagSuggester,       # Suggest tags for entries
    ContentAnalyzer,    # Analyze entry content
    SimilarityFinder,   # Find similar entries
    Deduplicator,       # Find/merge duplicates
    Validator,          # Validate entry data
    Exporter            # Export to custom formats
)
```

### 2. Implement Required Methods

```python
from ebk.plugins.base import TagSuggester
from typing import List, Dict, Any

class MyTagger(TagSuggester):
    @property
    def name(self) -> str:
        return "my_tagger"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    async def suggest_tags(self, 
                          entry: Dict[str, Any],
                          max_tags: int = 10,
                          confidence_threshold: float = 0.5) -> List[TagSuggestion]:
        # Your implementation
        tags = analyze_entry(entry)
        return [TagSuggestion(tag=t, confidence=0.8, source=self.name) 
                for t in tags]
    
    def requires_content(self) -> bool:
        return False  # Doesn't need file content
```

### 3. Register Your Plugin

#### Option A: Entry Points (for pip-installable plugins)

In your `setup.py`:
```python
setup(
    name="ebk-my-plugin",
    entry_points={
        "ebk.plugins": [
            "my_tagger = my_plugin:MyTagger",
        ]
    }
)
```

#### Option B: Manual Registration

```python
from ebk.plugins.registry import plugin_registry
from my_plugin import MyTagger

plugin_registry.register(MyTagger())
```

#### Option C: Environment Variable

```bash
export EBK_PLUGIN_PATH=/path/to/my/plugins
```

## Using Plugins

### From Python

```python
from ebk.library_enhanced import open_library

# Open library with plugin support
lib = open_library("~/ebooks")

# Configure a plugin
lib.use_plugin("google_books", config={"api_key": "..."})

# Use plugins
await lib.enrich_all_metadata(sources=["google_books"])
await lib.auto_tag_all(confidence_threshold=0.7)

# Find similar books
entry = lib.get("some-id")
similar = lib.find_similar(entry, threshold=0.8)

# Export with network plugin
graph_data = lib.build_coauthor_graph(min_connections=2)
lib.export_graph(graph_data, "coauthors.json")
```

### From CLI (future)

```bash
# List available plugins
ebk plugins list

# Enable a plugin
ebk plugins enable google_books

# Configure a plugin
ebk plugins config google_books --api-key="..."

# Use plugin features
ebk enrich --plugin=google_books ~/ebooks
ebk auto-tag --confidence=0.7 ~/ebooks
```

## Hook System

Plugins can interact via hooks:

```python
from ebk.plugins.hooks import hook

@hook("entry.added", priority=10)
def on_entry_added(entry, library):
    """Auto-tag new entries."""
    if not entry.tags:
        tags = suggest_tags(entry)
        entry.add_tags(tags)

@hook("before_export")
def validate_before_export(entries, format):
    """Validate entries before export."""
    for entry in entries:
        if not entry.is_valid():
            raise ValidationError(f"Invalid: {entry.id}")
```

## Available Hooks

- `library.opened` - Library opened
- `library.closed` - Library closed  
- `library.saved` - Library saved
- `entry.added` - Entry added
- `entry.updated` - Entry updated
- `entry.deleted` - Entry deleted
- `metadata.enriched` - Metadata enriched
- `tags.suggested` - Tags suggested
- `export.started` - Export started
- `export.completed` - Export completed

## Best Practices

1. **Keep plugins focused** - Do one thing well
2. **Handle errors gracefully** - Never crash the main app
3. **Make dependencies optional** - Use try/except for imports
4. **Document configuration** - Clear config schema
5. **Version your plugin** - Use semantic versioning
6. **Test thoroughly** - Include unit tests
7. **Async when possible** - For better performance

## Example Plugins

### Bundled with EBK

- **GoogleBooksExtractor** - Fetch metadata from Google Books API
- **NetworkAnalyzer** - Build co-author and subject graphs
- **MCPServer** - Interface with AI assistants

### Community Plugins (future)

- `ebk-openai-tagger` - AI-powered tag suggestions
- `ebk-calibre-sync` - Bi-directional Calibre sync
- `ebk-goodreads` - Goodreads integration
- `ebk-citation` - Citation network analysis