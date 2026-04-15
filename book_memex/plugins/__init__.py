"""
EBK Plugin System

This module provides the plugin architecture for EBK, allowing extensions
to add functionality without modifying core code.
"""

from .base import (
    Plugin,
    MetadataExtractor,
    TagSuggester,
    ContentAnalyzer,
    SimilarityFinder,
    Deduplicator,
    Validator,
    Exporter
)

from .registry import PluginRegistry, plugin_registry
from .hooks import HookRegistry, hooks, hook

# Initialize global registries
__all__ = [
    # Base classes
    'Plugin',
    'MetadataExtractor',
    'TagSuggester',
    'ContentAnalyzer',
    'SimilarityFinder',
    'Deduplicator',
    'Validator',
    'Exporter',
    
    # Registry
    'PluginRegistry',
    'plugin_registry',
    
    # Hooks
    'HookRegistry',
    'hooks',
    'hook'
]