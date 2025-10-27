# EBK Plugin Architecture

## Overview

The plugin architecture allows EBK to be extended without modifying core code. Plugins can add new functionality, modify behavior, and integrate with external services.

## Plugin Types

### 1. MetadataExtractor
Extract or enhance metadata from various sources.

```python
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from ebk.plugins.base import Plugin

class MetadataExtractor(Plugin, ABC):
    """Base class for metadata extraction plugins."""
    
    @abstractmethod
    async def extract(self, 
                     file_path: Optional[str] = None,
                     url: Optional[str] = None,
                     isbn: Optional[str] = None,
                     content: Optional[bytes] = None) -> Dict[str, Any]:
        """
        Extract metadata from various sources.
        
        Returns:
            Dictionary with metadata fields like:
            - title, creators, subjects, description
            - publisher, date, language
            - isbn, doi, other identifiers
            - cover_url, thumbnail_url
        """
        pass
    
    @abstractmethod
    def supported_formats(self) -> List[str]:
        """Return list of supported file formats."""
        pass
```

### 2. TagSuggester
Generate tags based on content analysis.

```python
class TagSuggester(Plugin, ABC):
    """Base class for tag suggestion plugins."""
    
    @abstractmethod
    async def suggest_tags(self, 
                          entry: Entry,
                          max_tags: int = 10,
                          confidence_threshold: float = 0.5) -> List[TagSuggestion]:
        """
        Suggest tags for an entry.
        
        Returns:
            List of TagSuggestion objects with tag and confidence score.
        """
        pass
    
    @abstractmethod
    def requires_content(self) -> bool:
        """Whether this suggester needs file content."""
        pass

class TagSuggestion:
    tag: str
    confidence: float
    source: str  # Which plugin suggested it
    reason: Optional[str]  # Why this tag was suggested
```

### 3. ContentAnalyzer
Analyze content for various metrics.

```python
class ContentAnalyzer(Plugin, ABC):
    """Base class for content analysis plugins."""
    
    @abstractmethod
    async def analyze(self, entry: Entry) -> ContentAnalysis:
        """Analyze entry content."""
        pass

class ContentAnalysis:
    reading_time: Optional[int]  # minutes
    difficulty_level: Optional[str]  # easy/medium/hard
    word_count: Optional[int]
    page_count: Optional[int]
    language: Optional[str]
    summary: Optional[str]
    key_topics: List[str]
    sentiment: Optional[float]  # -1 to 1
    quality_score: Optional[float]  # 0 to 1
```

### 4. Deduplicator
Strategies for finding and handling duplicates.

```python
class Deduplicator(Plugin, ABC):
    """Base class for deduplication plugins."""
    
    @abstractmethod
    def find_duplicates(self, 
                       entries: List[Entry],
                       threshold: float = 0.9) -> List[DuplicateGroup]:
        """Find duplicate entries."""
        pass
    
    @abstractmethod
    def merge_duplicates(self, 
                        duplicates: DuplicateGroup,
                        strategy: str = "newest") -> Entry:
        """Merge duplicate entries into one."""
        pass

class DuplicateGroup:
    entries: List[Entry]
    similarity_score: float
    match_reason: str  # "isbn", "title_author", "content_hash", etc.
```

### 5. Validator
Validate entries for correctness and completeness.

```python
class Validator(Plugin, ABC):
    """Base class for validation plugins."""
    
    @abstractmethod
    def validate(self, entry: Entry) -> ValidationResult:
        """Validate an entry."""
        pass

class ValidationResult:
    is_valid: bool
    errors: List[ValidationError]
    warnings: List[ValidationWarning]
    completeness_score: float  # 0 to 1

class ValidationError:
    field: str
    message: str
    severity: str  # "error", "warning", "info"
```

### 6. Exporter
Export to various formats.

```python
class Exporter(Plugin, ABC):
    """Base class for export plugins."""
    
    @abstractmethod
    async def export(self,
                    entries: List[Entry],
                    output_path: str,
                    options: Dict[str, Any]) -> ExportResult:
        """Export entries to a specific format."""
        pass
    
    @abstractmethod
    def supported_formats(self) -> List[str]:
        """Return list of supported export formats."""
        pass
```

## Plugin Implementation Examples

### Example 1: Google Books Plugin

```python
# ebk/plugins/google_books.py
import aiohttp
from ebk.plugins.base import MetadataExtractor

class GoogleBooksExtractor(MetadataExtractor):
    """Extract metadata from Google Books API."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GOOGLE_BOOKS_API_KEY")
        self.base_url = "https://www.googleapis.com/books/v1/volumes"
    
    async def extract(self, isbn: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        if not isbn:
            return {}
        
        async with aiohttp.ClientSession() as session:
            params = {"q": f"isbn:{isbn}"}
            if self.api_key:
                params["key"] = self.api_key
            
            async with session.get(self.base_url, params=params) as resp:
                data = await resp.json()
                
        if data.get("totalItems", 0) == 0:
            return {}
        
        item = data["items"][0]["volumeInfo"]
        
        return {
            "title": item.get("title"),
            "creators": item.get("authors", []),
            "publisher": item.get("publisher"),
            "date": item.get("publishedDate"),
            "description": item.get("description"),
            "subjects": item.get("categories", []),
            "language": item.get("language"),
            "page_count": item.get("pageCount"),
            "cover_url": item.get("imageLinks", {}).get("thumbnail")
        }
    
    def supported_formats(self) -> List[str]:
        return []  # Works with ISBN, not files
    
    @property
    def name(self) -> str:
        return "google_books"
    
    @property
    def version(self) -> str:
        return "1.0.0"
```

### Example 2: OpenAI Tagger Plugin

```python
# ebk/plugins/openai_tagger.py
import openai
from ebk.plugins.base import TagSuggester

class OpenAITagger(TagSuggester):
    """Generate tags using OpenAI GPT."""
    
    def __init__(self, api_key: str, model: str = "gpt-3.5-turbo"):
        self.client = openai.Client(api_key=api_key)
        self.model = model
    
    async def suggest_tags(self, 
                          entry: Entry,
                          max_tags: int = 10,
                          confidence_threshold: float = 0.5) -> List[TagSuggestion]:
        
        prompt = f"""
        Suggest up to {max_tags} relevant tags for this book:
        Title: {entry.title}
        Authors: {', '.join(entry.creators)}
        Description: {entry.description[:500] if entry.description else 'N/A'}
        Current subjects: {', '.join(entry.subjects)}
        
        Return tags as a JSON list with confidence scores.
        """
        
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        
        suggestions = []
        for tag_data in response.choices[0].message.content:
            if tag_data["confidence"] >= confidence_threshold:
                suggestions.append(TagSuggestion(
                    tag=tag_data["tag"],
                    confidence=tag_data["confidence"],
                    source="openai",
                    reason=tag_data.get("reason")
                ))
        
        return suggestions
    
    def requires_content(self) -> bool:
        return False  # Can work with just metadata
    
    @property
    def name(self) -> str:
        return "openai_tagger"
```

## Plugin Discovery and Registration

### Automatic Discovery

```python
# ebk/plugins/discovery.py
import importlib
import pkgutil
from typing import Dict, List, Type

class PluginRegistry:
    def __init__(self):
        self._plugins: Dict[str, List[Plugin]] = {}
        self._hooks: Dict[str, List[Callable]] = {}
    
    def discover_plugins(self):
        """Discover plugins from installed packages."""
        # 1. Check entry points
        self._discover_entry_points()
        
        # 2. Check plugins directory
        self._discover_local_plugins()
        
        # 3. Check environment variable
        self._discover_env_plugins()
    
    def _discover_entry_points(self):
        """Discover plugins via setuptools entry points."""
        import importlib.metadata
        
        for ep in importlib.metadata.entry_points().get("ebk.plugins", []):
            try:
                plugin_class = ep.load()
                self.register(plugin_class())
            except Exception as e:
                logger.error(f"Failed to load plugin {ep.name}: {e}")
    
    def _discover_local_plugins(self):
        """Discover plugins in the plugins directory."""
        plugins_dir = Path(__file__).parent
        
        for module_info in pkgutil.iter_modules([str(plugins_dir)]):
            if module_info.name.startswith("_"):
                continue
            
            try:
                module = importlib.import_module(f"ebk.plugins.{module_info.name}")
                
                for name, obj in inspect.getmembers(module):
                    if inspect.isclass(obj) and issubclass(obj, Plugin):
                        self.register(obj())
            except Exception as e:
                logger.error(f"Failed to load plugin module {module_info.name}: {e}")
    
    def register(self, plugin: Plugin):
        """Register a plugin instance."""
        plugin_type = type(plugin).__bases__[0].__name__
        
        if plugin_type not in self._plugins:
            self._plugins[plugin_type] = []
        
        self._plugins[plugin_type].append(plugin)
        logger.info(f"Registered plugin: {plugin.name} ({plugin_type})")
    
    def get_plugins(self, plugin_type: str) -> List[Plugin]:
        """Get all plugins of a specific type."""
        return self._plugins.get(plugin_type, [])
    
    def get_plugin(self, name: str) -> Optional[Plugin]:
        """Get a specific plugin by name."""
        for plugins in self._plugins.values():
            for plugin in plugins:
                if plugin.name == name:
                    return plugin
        return None
```

### Manual Registration

```python
from ebk import plugin_registry
from my_plugins import CustomTagger

# Register a plugin instance
registry.register(CustomTagger())

# Or via decorator
@register_plugin
class MyExtractor(MetadataExtractor):
    pass
```

## Hook System

### Defining Hooks

```python
# ebk/hooks.py
from typing import Callable, Any, List

class HookRegistry:
    def __init__(self):
        self._hooks: Dict[str, List[Callable]] = {}
    
    def register_hook(self, event: str, callback: Callable):
        """Register a hook callback."""
        if event not in self._hooks:
            self._hooks[event] = []
        self._hooks[event].append(callback)
    
    def trigger(self, event: str, *args, **kwargs) -> List[Any]:
        """Trigger all callbacks for an event."""
        results = []
        for callback in self._hooks.get(event, []):
            try:
                result = callback(*args, **kwargs)
                if result is not None:
                    results.append(result)
            except Exception as e:
                logger.error(f"Hook {callback.__name__} failed: {e}")
        return results

# Global hook registry
hooks = HookRegistry()

# Decorator for registering hooks
def hook(event: str):
    def decorator(func: Callable):
        hooks.register_hook(event, func)
        return func
    return decorator
```

### Using Hooks

```python
# In plugins or user code
@hook("entry.added")
def on_entry_added(entry: Entry, library: Library):
    """Auto-tag new entries."""
    if not entry.tags:
        tags = suggest_tags(entry)
        entry.add_tags(tags)

@hook("before_export")
def validate_before_export(entries: List[Entry], format: str):
    """Validate entries before export."""
    for entry in entries:
        if not entry.is_valid():
            raise ValidationError(f"Invalid entry: {entry.unique_id}")

# In core code
def add_entry(self, entry: Entry):
    # ... add logic ...
    hooks.trigger("entry.added", entry, self)
```

## Plugin Configuration

### Configuration Schema

```python
# ebk/plugins/config.py
from pydantic import BaseModel

class PluginConfig(BaseModel):
    """Base configuration for plugins."""
    enabled: bool = True
    priority: int = 0  # Higher priority plugins run first

class GoogleBooksConfig(PluginConfig):
    api_key: Optional[str] = None
    rate_limit: int = 100  # requests per minute
    cache_ttl: int = 3600  # seconds

class OpenAIConfig(PluginConfig):
    api_key: str
    model: str = "gpt-3.5-turbo"
    temperature: float = 0.7
    max_tokens: int = 150
```

### Loading Configuration

```python
# ebk/config.py
import yaml
from pathlib import Path

def load_plugin_config() -> Dict[str, PluginConfig]:
    """Load plugin configuration from file."""
    config_paths = [
        Path.home() / ".config" / "ebk" / "plugins.yaml",
        Path.home() / ".ebk" / "plugins.yaml",
        Path("./ebk_plugins.yaml")
    ]
    
    for path in config_paths:
        if path.exists():
            with open(path) as f:
                data = yaml.safe_load(f)
                return parse_plugin_config(data)
    
    return {}
```

## Plugin Testing

### Test Utilities

```python
# ebk/plugins/testing.py
from unittest.mock import Mock, AsyncMock

class PluginTestCase:
    """Base test case for plugins."""
    
    def create_mock_entry(self, **kwargs) -> Entry:
        """Create a mock entry for testing."""
        defaults = {
            "unique_id": "test123",
            "title": "Test Book",
            "creators": ["Test Author"],
            "subjects": ["Testing"],
            "language": "en"
        }
        defaults.update(kwargs)
        return Entry(**defaults)
    
    def create_mock_plugin(self, plugin_class: Type[Plugin]) -> Mock:
        """Create a mock plugin."""
        mock = Mock(spec=plugin_class)
        mock.name = f"mock_{plugin_class.__name__}"
        return mock

# Example test
def test_google_books_extractor():
    extractor = GoogleBooksExtractor(api_key="test_key")
    
    with patch("aiohttp.ClientSession") as mock_session:
        mock_response = AsyncMock()
        mock_response.json.return_value = {
            "totalItems": 1,
            "items": [{
                "volumeInfo": {
                    "title": "Test Book",
                    "authors": ["Test Author"]
                }
            }]
        }
        mock_session.get.return_value.__aenter__.return_value = mock_response
        
        result = await extractor.extract(isbn="1234567890")
        assert result["title"] == "Test Book"
```

## Plugin Packaging

### Directory Structure

```
my-ebk-plugin/
├── pyproject.toml
├── README.md
├── LICENSE
├── src/
│   └── my_plugin/
│       ├── __init__.py
│       ├── extractor.py
│       ├── tagger.py
│       └── config.py
└── tests/
    └── test_plugin.py
```

### Setup Configuration

```toml
# pyproject.toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "ebk-my-plugin"
version = "1.0.0"
dependencies = [
    "ebk>=2.0.0",
    "aiohttp>=3.8.0"
]

[project.entry-points."ebk.plugins"]
my_extractor = "my_plugin:MyExtractor"
my_tagger = "my_plugin:MyTagger"
```

## Best Practices

1. **Async First**: Make plugins async for better performance
2. **Error Handling**: Never let plugin errors crash the main app
3. **Logging**: Use structured logging for debugging
4. **Caching**: Cache expensive operations
5. **Rate Limiting**: Respect API rate limits
6. **Configuration**: Make everything configurable
7. **Testing**: Provide comprehensive tests
8. **Documentation**: Document all plugin capabilities
9. **Versioning**: Use semantic versioning
10. **Dependencies**: Keep dependencies minimal

This plugin architecture provides a robust, extensible foundation for EBK that allows users and developers to add functionality without modifying core code.