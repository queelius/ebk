"""
Tests for the EBK plugin system.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any, List

from ebk.plugins.base import (
    Plugin, MetadataExtractor, TagSuggester, ContentAnalyzer,
    TagSuggestion, ContentAnalysis, ValidationResult, ValidationError
)
from ebk.plugins.registry import PluginRegistry, register_plugin
from ebk.plugins.hooks import HookRegistry, hook, trigger_hook
from integrations.metadata.google_books import GoogleBooksExtractor


class TestPlugin(Plugin):
    """Test plugin implementation."""
    
    @property
    def name(self) -> str:
        return "test_plugin"
    
    @property
    def version(self) -> str:
        return "1.0.0"


class TestMetadataExtractor(MetadataExtractor):
    """Test metadata extractor implementation."""
    
    @property
    def name(self) -> str:
        return "test_extractor"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    async def extract(self, **kwargs) -> Dict[str, Any]:
        return {"title": "Test Book", "creators": ["Test Author"]}
    
    def supported_formats(self) -> List[str]:
        return ["test"]


class TestTagSuggester(TagSuggester):
    """Test tag suggester implementation."""
    
    @property
    def name(self) -> str:
        return "test_suggester"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    async def suggest_tags(self, entry: Dict[str, Any], max_tags: int = 10, 
                          confidence_threshold: float = 0.5) -> List[TagSuggestion]:
        return [
            TagSuggestion(tag="test", confidence=0.9, source="test"),
            TagSuggestion(tag="book", confidence=0.8, source="test")
        ]
    
    def requires_content(self) -> bool:
        return False


class TestPluginBase:
    """Test base plugin functionality."""
    
    def test_plugin_properties(self):
        """Test plugin properties."""
        plugin = TestPlugin()
        assert plugin.name == "test_plugin"
        assert plugin.version == "1.0.0"
        assert plugin.description == ""
        assert plugin.author == ""
        assert plugin.requires == []
    
    def test_plugin_initialization(self):
        """Test plugin initialization."""
        plugin = TestPlugin()
        config = {"key": "value"}
        plugin.initialize(config)
        assert plugin.config == config
    
    def test_plugin_validation(self):
        """Test plugin config validation."""
        plugin = TestPlugin()
        assert plugin.validate_config() is True


class TestPluginRegistry:
    """Test plugin registry functionality."""
    
    def setup_method(self):
        """Setup test registry."""
        self.registry = PluginRegistry()
    
    def test_register_plugin_instance(self):
        """Test registering a plugin instance."""
        plugin = TestPlugin()
        self.registry.register(plugin)
        
        assert self.registry.get_plugin("test_plugin") == plugin
        assert "test_plugin" in self.registry._plugin_instances
    
    def test_register_plugin_class(self):
        """Test registering a plugin class."""
        self.registry._register_class(TestMetadataExtractor)
        
        assert "test_extractor" in self.registry._plugin_instances
        plugins = self.registry.get_plugins("metadata_extractor")
        assert len(plugins) == 1
        assert plugins[0].name == "test_extractor"
    
    def test_unregister_plugin(self):
        """Test unregistering a plugin."""
        plugin = TestPlugin()
        self.registry.register(plugin)
        
        result = self.registry.unregister("test_plugin")
        assert result is True
        assert self.registry.get_plugin("test_plugin") is None
    
    def test_get_plugins_by_type(self):
        """Test getting plugins by type."""
        extractor = TestMetadataExtractor()
        suggester = TestTagSuggester()
        
        self.registry.register(extractor)
        self.registry.register(suggester)
        
        extractors = self.registry.get_plugins("metadata_extractor")
        assert len(extractors) == 1
        assert extractors[0] == extractor
        
        suggesters = self.registry.get_plugins("tag_suggester")
        assert len(suggesters) == 1
        assert suggesters[0] == suggester
    
    def test_configure_plugin(self):
        """Test configuring a plugin."""
        plugin = TestPlugin()
        self.registry.register(plugin)
        
        config = {"setting": "value"}
        result = self.registry.configure_plugin("test_plugin", config)
        
        assert result is True
        assert plugin.config == config
    
    def test_enable_disable_plugin(self):
        """Test enabling and disabling plugins."""
        plugin = TestPlugin()
        self.registry.register(plugin)
        
        # Disable plugin
        self.registry.disable_plugin("test_plugin")
        assert self.registry.get_plugin("test_plugin") is None
        
        # Enable plugin
        self.registry.enable_plugin("test_plugin")
        assert self.registry.get_plugin("test_plugin") == plugin
    
    def test_list_plugins(self):
        """Test listing all plugins."""
        extractor = TestMetadataExtractor()
        suggester = TestTagSuggester()
        
        self.registry.register(extractor)
        self.registry.register(suggester)
        
        plugin_list = self.registry.list_plugins()
        
        assert "metadata_extractor" in plugin_list
        assert "test_extractor" in plugin_list["metadata_extractor"]
        assert "tag_suggester" in plugin_list
        assert "test_suggester" in plugin_list["tag_suggester"]
    
    def test_get_plugin_info(self):
        """Test getting plugin information."""
        plugin = TestMetadataExtractor()
        self.registry.register(plugin)
        
        info = self.registry.get_plugin_info("test_extractor")
        
        assert info["name"] == "test_extractor"
        assert info["version"] == "1.0.0"
        assert info["type"] == "metadata_extractor"
        assert info["enabled"] is True
        assert info["configured"] is False


class TestHookRegistry:
    """Test hook registry functionality."""
    
    def setup_method(self):
        """Setup test hook registry."""
        self.hooks = HookRegistry()
        self.call_count = 0
        self.last_args = None
        self.last_kwargs = None
    
    def test_callback(self, *args, **kwargs):
        """Test callback function."""
        self.call_count += 1
        self.last_args = args
        self.last_kwargs = kwargs
        return "test_result"
    
    async def async_test_callback(self, *args, **kwargs):
        """Async test callback function."""
        self.call_count += 1
        self.last_args = args
        self.last_kwargs = kwargs
        return "async_test_result"
    
    def test_register_hook(self):
        """Test registering a hook."""
        self.hooks.register_hook("test.event", self.test_callback)
        
        assert "test.event" in self.hooks._hooks
        assert self.test_callback in self.hooks._hooks["test.event"]
    
    def test_register_async_hook(self):
        """Test registering an async hook."""
        self.hooks.register_hook("test.event", self.async_test_callback)
        
        assert "test.event" in self.hooks._async_hooks
        assert self.async_test_callback in self.hooks._async_hooks["test.event"]
    
    def test_trigger_hook(self):
        """Test triggering hooks."""
        self.hooks.register_hook("test.event", self.test_callback)
        
        results = self.hooks.trigger("test.event", "arg1", key="value")
        
        assert self.call_count == 1
        assert self.last_args == ("arg1",)
        assert self.last_kwargs == {"key": "value"}
        assert results == ["test_result"]
    
    @pytest.mark.asyncio
    async def test_trigger_async_hook(self):
        """Test triggering async hooks."""
        self.hooks.register_hook("test.event", self.async_test_callback)
        
        results = await self.hooks.trigger_async("test.event", "arg1", key="value")
        
        assert self.call_count == 1
        assert self.last_args == ("arg1",)
        assert self.last_kwargs == {"key": "value"}
        assert results == ["async_test_result"]
    
    def test_hook_priority(self):
        """Test hook priority ordering."""
        results = []
        
        def hook1():
            results.append(1)
        
        def hook2():
            results.append(2)
        
        def hook3():
            results.append(3)
        
        self.hooks.register_hook("test.event", hook2, priority=5)
        self.hooks.register_hook("test.event", hook1, priority=10)
        self.hooks.register_hook("test.event", hook3, priority=0)
        
        self.hooks.trigger("test.event")
        
        # Should be called in priority order (10, 5, 0)
        assert results == [1, 2, 3]
    
    def test_trigger_filter(self):
        """Test filter hooks."""
        def add_one(value):
            return value + 1
        
        def multiply_two(value):
            return value * 2
        
        self.hooks.register_hook("filter.number", add_one)
        self.hooks.register_hook("filter.number", multiply_two)
        
        result = self.hooks.trigger_filter("filter.number", 5)
        
        # 5 + 1 = 6, then 6 * 2 = 12
        assert result == 12
    
    def test_unregister_hook(self):
        """Test unregistering a hook."""
        self.hooks.register_hook("test.event", self.test_callback)
        
        result = self.hooks.unregister_hook("test.event", self.test_callback)
        assert result is True
        
        results = self.hooks.trigger("test.event")
        assert results == []
        assert self.call_count == 0
    
    def test_has_hooks(self):
        """Test checking for hooks."""
        assert self.hooks.has_hooks("test.event") is False
        
        self.hooks.register_hook("test.event", self.test_callback)
        assert self.hooks.has_hooks("test.event") is True
    
    def test_list_hooks(self):
        """Test listing hooks."""
        self.hooks.register_hook("event1", self.test_callback)
        self.hooks.register_hook("event2", self.async_test_callback)
        
        hook_list = self.hooks.list_hooks()
        
        assert "event1" in hook_list
        assert "test_callback" in hook_list["event1"]
        assert "event2" in hook_list
        assert "async_test_callback (async)" in hook_list["event2"]
    
    def test_clear_hooks(self):
        """Test clearing hooks."""
        self.hooks.register_hook("event1", self.test_callback)
        self.hooks.register_hook("event2", self.test_callback)
        
        # Clear specific event
        self.hooks.clear_hooks("event1")
        assert not self.hooks.has_hooks("event1")
        assert self.hooks.has_hooks("event2")
        
        # Clear all
        self.hooks.clear_hooks()
        assert not self.hooks.has_hooks("event2")


class TestHookDecorator:
    """Test hook decorator functionality."""
    
    def setup_method(self):
        """Setup for decorator tests."""
        from ebk.plugins.hooks import hooks
        # Clear any existing hooks
        hooks.clear_hooks()
        self.call_count = 0
    
    def test_hook_decorator(self):
        """Test using hook decorator."""
        from ebk.plugins.hooks import hook, hooks
        
        @hook("test.decorated")
        def decorated_hook(value):
            return value * 2
        
        results = hooks.trigger("test.decorated", 5)
        assert results == [10]
    
    def test_hook_decorator_with_priority(self):
        """Test hook decorator with priority."""
        from ebk.plugins.hooks import hook, hooks
        
        results = []
        
        @hook("test.priority", priority=10)
        def high_priority():
            results.append("high")
        
        @hook("test.priority", priority=5)
        def medium_priority():
            results.append("medium")
        
        @hook("test.priority")
        def low_priority():
            results.append("low")
        
        hooks.trigger("test.priority")
        assert results == ["high", "medium", "low"]


class TestGoogleBooksPlugin:
    """Test Google Books plugin."""
    
    @pytest.mark.asyncio
    async def test_google_books_initialization(self):
        """Test Google Books plugin initialization."""
        plugin = GoogleBooksExtractor()
        
        assert plugin.name == "google_books"
        assert plugin.version == "1.0.0"
        assert plugin.supported_formats() == ["isbn"]
    
    @pytest.mark.asyncio
    async def test_google_books_extract_with_mock(self):
        """Test Google Books extraction with mocked API."""
        plugin = GoogleBooksExtractor()
        
        mock_response = {
            "totalItems": 1,
            "items": [{
                "volumeInfo": {
                    "title": "Test Book",
                    "authors": ["Test Author"],
                    "publisher": "Test Publisher",
                    "publishedDate": "2023-01-01",
                    "description": "Test description",
                    "categories": ["Fiction"],
                    "language": "en",
                    "pageCount": 300
                },
                "selfLink": "https://example.com/book"
            }]
        }
        
        with patch.object(plugin, '_fetch_book_data', return_value=mock_response):
            result = await plugin.extract(isbn="1234567890")
        
        assert result["title"] == "Test Book"
        assert result["creators"] == ["Test Author"]
        assert result["publisher"] == "Test Publisher"
        assert result["date"] == "2023-01-01"
        assert result["year"] == 2023
        assert result["description"] == "Test description"
        assert result["subjects"] == ["Fiction"]
        assert result["language"] == "en"
        assert result["page_count"] == 300
        assert result["source"] == "google_books"
    
    @pytest.mark.asyncio
    async def test_google_books_no_results(self):
        """Test Google Books with no results."""
        plugin = GoogleBooksExtractor()
        
        mock_response = {"totalItems": 0}
        
        with patch.object(plugin, '_fetch_book_data', return_value=mock_response):
            result = await plugin.extract(isbn="0000000000")
        
        assert result == {}
    
    def test_google_books_parse_volume_info(self):
        """Test parsing volume info."""
        plugin = GoogleBooksExtractor()
        
        volume_info = {
            "title": "Sample Book",
            "subtitle": "A Great Read",
            "authors": ["John Doe", "Jane Smith"],
            "publisher": "Example Press",
            "publishedDate": "2022-06-15",
            "description": "A wonderful book about testing.",
            "categories": ["Technology", "Testing"],
            "language": "en",
            "pageCount": 250,
            "industryIdentifiers": [
                {"type": "ISBN_13", "identifier": "9781234567890"},
                {"type": "ISBN_10", "identifier": "1234567890"}
            ],
            "imageLinks": {
                "thumbnail": "https://example.com/thumb.jpg",
                "large": "https://example.com/large.jpg"
            },
            "averageRating": 4.5,
            "ratingsCount": 100
        }
        
        result = plugin._parse_volume_info(volume_info)
        
        assert result["title"] == "Sample Book"
        assert result["subtitle"] == "A Great Read"
        assert result["creators"] == ["John Doe", "Jane Smith"]
        assert result["publisher"] == "Example Press"
        assert result["date"] == "2022-06-15"
        assert result["year"] == 2022
        assert result["description"] == "A wonderful book about testing."
        assert result["subjects"] == ["Technology", "Testing"]
        assert result["language"] == "en"
        assert result["page_count"] == 250
        assert result["identifiers"]["isbn13"] == "9781234567890"
        assert result["identifiers"]["isbn10"] == "1234567890"
        assert result["identifiers"]["isbn"] == "9781234567890"
        assert result["cover_url"] == "https://example.com/large.jpg"
        assert result["thumbnail_url"] == "https://example.com/thumb.jpg"
        assert result["rating"] == 4.5
        assert result["ratings_count"] == 100


class TestTagSuggestion:
    """Test TagSuggestion functionality."""
    
    def test_tag_suggestion_creation(self):
        """Test creating a TagSuggestion."""
        suggestion = TagSuggestion(
            tag="python",
            confidence=0.95,
            source="test",
            reason="Found in title"
        )
        
        assert suggestion.tag == "python"
        assert suggestion.confidence == 0.95
        assert suggestion.source == "test"
        assert suggestion.reason == "Found in title"
    
    def test_filter_suggestions(self):
        """Test filtering tag suggestions."""
        suggester = TestTagSuggester()
        
        suggestions = [
            TagSuggestion(tag="high", confidence=0.9, source="test"),
            TagSuggestion(tag="medium", confidence=0.6, source="test"),
            TagSuggestion(tag="low", confidence=0.3, source="test"),
            TagSuggestion(tag="very_high", confidence=0.95, source="test")
        ]
        
        filtered = suggester.filter_suggestions(suggestions, max_tags=2, confidence_threshold=0.5)
        
        assert len(filtered) == 2
        assert filtered[0].tag == "very_high"
        assert filtered[1].tag == "high"


class TestContentAnalysis:
    """Test ContentAnalysis functionality."""
    
    def test_content_analysis_creation(self):
        """Test creating ContentAnalysis."""
        analysis = ContentAnalysis(
            reading_time=30,
            difficulty_level="medium",
            word_count=7500,
            page_count=25,
            language="en",
            summary="A test book",
            key_topics=["testing", "python"],
            sentiment=0.5,
            quality_score=0.8
        )
        
        assert analysis.reading_time == 30
        assert analysis.difficulty_level == "medium"
        assert analysis.word_count == 7500
        assert analysis.page_count == 25
        assert analysis.language == "en"
        assert analysis.summary == "A test book"
        assert analysis.key_topics == ["testing", "python"]
        assert analysis.sentiment == 0.5
        assert analysis.quality_score == 0.8
    
    def test_content_analysis_defaults(self):
        """Test ContentAnalysis with defaults."""
        analysis = ContentAnalysis()
        
        assert analysis.reading_time is None
        assert analysis.key_topics == []


class TestValidation:
    """Test validation functionality."""
    
    def test_validation_result(self):
        """Test ValidationResult creation."""
        errors = [
            ValidationError(field="title", message="Missing title", severity="error"),
            ValidationError(field="isbn", message="Invalid ISBN", severity="error")
        ]
        
        result = ValidationResult(
            is_valid=False,
            errors=errors,
            warnings=[],
            completeness_score=0.6
        )
        
        assert result.is_valid is False
        assert len(result.errors) == 2
        assert result.errors[0].field == "title"
        assert result.completeness_score == 0.6