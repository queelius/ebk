"""
Enhanced Library class with plugin integration.

This module extends the base Library class with full plugin support,
including metadata extraction, tag suggestion, content analysis, and more.
"""

import asyncio
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Union, Callable
from concurrent.futures import ThreadPoolExecutor

from .library import Library as BaseLibrary, Entry, QueryBuilder
from .plugins.registry import plugin_registry, get_plugins, get_plugin
from .plugins.hooks import trigger_hook, trigger_hook_async, filter_value, hook
from .plugins.base import TagSuggestion

logger = logging.getLogger(__name__)


class EnhancedEntry(Entry):
    """Enhanced Entry class with plugin support."""
    
    async def enrich_metadata(self, sources: Optional[List[str]] = None) -> 'EnhancedEntry':
        """
        Enrich entry metadata using available plugins.
        
        Args:
            sources: Optional list of specific plugin names to use
            
        Returns:
            Self for chaining
        """
        extractors = get_plugins('metadata_extractor')
        
        if sources:
            extractors = [e for e in extractors if e.name in sources]
        
        for extractor in extractors:
            try:
                # Try different extraction methods based on available data
                metadata = None
                
                if self.get('isbn'):
                    metadata = await extractor.extract(isbn=self.get('isbn'))
                elif self.get('file_paths'):
                    # Use first file path
                    file_path = self.get('file_paths')[0]
                    if Path(file_path).exists():
                        metadata = await extractor.extract(file_path=file_path)
                
                if metadata:
                    # Merge extracted metadata (don't overwrite existing)
                    for key, value in metadata.items():
                        if not self.get(key) and value:
                            self.set(key, value)
                    
                    logger.info(f"Enriched entry {self.unique_id} with {extractor.name}")
                    
            except Exception as e:
                logger.error(f"Failed to enrich with {extractor.name}: {e}")
        
        # Trigger hook
        await trigger_hook_async('metadata.enriched', self)
        
        return self
    
    async def suggest_tags(self, max_tags: int = 10, 
                          confidence_threshold: float = 0.5) -> List[TagSuggestion]:
        """
        Get tag suggestions for this entry.
        
        Args:
            max_tags: Maximum number of tags to suggest
            confidence_threshold: Minimum confidence score
            
        Returns:
            List of TagSuggestion objects
        """
        suggesters = get_plugins('tag_suggester')
        all_suggestions = []
        
        for suggester in suggesters:
            try:
                suggestions = await suggester.suggest_tags(
                    self.to_dict(),
                    max_tags=max_tags,
                    confidence_threshold=confidence_threshold
                )
                all_suggestions.extend(suggestions)
                
            except Exception as e:
                logger.error(f"Tag suggester {suggester.name} failed: {e}")
        
        # Deduplicate and sort by confidence
        unique_tags = {}
        for suggestion in all_suggestions:
            if suggestion.tag not in unique_tags or suggestion.confidence > unique_tags[suggestion.tag].confidence:
                unique_tags[suggestion.tag] = suggestion
        
        suggestions = list(unique_tags.values())
        suggestions.sort(key=lambda s: s.confidence, reverse=True)
        
        # Apply filter hook
        suggestions = await filter_value_async('filter.suggested_tags', suggestions, self)
        
        return suggestions[:max_tags]
    
    async def auto_tag(self, max_tags: int = 10, 
                       confidence_threshold: float = 0.5,
                       replace: bool = False) -> 'EnhancedEntry':
        """
        Automatically add tags to this entry.
        
        Args:
            max_tags: Maximum number of tags to add
            confidence_threshold: Minimum confidence score
            replace: If True, replace existing tags
            
        Returns:
            Self for chaining
        """
        suggestions = await self.suggest_tags(max_tags, confidence_threshold)
        
        if suggestions:
            new_tags = [s.tag for s in suggestions]
            
            if replace:
                self.set('tags', new_tags)
            else:
                existing_tags = self.get('tags', [])
                combined_tags = list(set(existing_tags + new_tags))
                self.set('tags', combined_tags)
            
            # Trigger hook
            await trigger_hook_async('tags.added', self, new_tags)
            
            logger.info(f"Added {len(new_tags)} tags to entry {self.unique_id}")
        
        return self
    
    async def analyze_content(self) -> Dict[str, Any]:
        """
        Analyze entry content using available plugins.
        
        Returns:
            Dictionary with analysis results
        """
        analyzers = get_plugins('content_analyzer')
        analysis_results = {}
        
        for analyzer in analyzers:
            try:
                analysis = await analyzer.analyze(self.to_dict())
                
                # Convert to dict
                analysis_dict = {
                    'reading_time': analysis.reading_time,
                    'difficulty_level': analysis.difficulty_level,
                    'word_count': analysis.word_count,
                    'page_count': analysis.page_count,
                    'language': analysis.language,
                    'summary': analysis.summary,
                    'key_topics': analysis.key_topics,
                    'sentiment': analysis.sentiment,
                    'quality_score': analysis.quality_score
                }
                
                # Merge results
                for key, value in analysis_dict.items():
                    if value is not None:
                        analysis_results[key] = value
                
            except Exception as e:
                logger.error(f"Content analyzer {analyzer.name} failed: {e}")
        
        return analysis_results
    
    def validate(self) -> Dict[str, Any]:
        """
        Validate this entry using available validators.
        
        Returns:
            Validation results dictionary
        """
        validators = get_plugins('validator')
        
        all_errors = []
        all_warnings = []
        min_completeness = 1.0
        
        for validator in validators:
            try:
                result = validator.validate(self.to_dict())
                
                all_errors.extend(result.errors)
                all_warnings.extend(result.warnings)
                min_completeness = min(min_completeness, result.completeness_score)
                
            except Exception as e:
                logger.error(f"Validator {validator.name} failed: {e}")
        
        # Trigger hook
        trigger_hook('metadata.validated', self, all_errors, all_warnings)
        
        return {
            'is_valid': len(all_errors) == 0,
            'errors': all_errors,
            'warnings': all_warnings,
            'completeness_score': min_completeness
        }


class EnhancedLibrary(BaseLibrary):
    """Enhanced Library class with full plugin support."""
    
    def __init__(self, path: Union[str, Path]):
        super().__init__(path)
        self._executor = ThreadPoolExecutor(max_workers=4)
        
        # Initialize plugin system
        plugin_registry.discover_plugins()
        
        # Trigger library opened hook
        trigger_hook('library.opened', self)
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.save()
        self.cleanup()
    
    def cleanup(self):
        """Cleanup resources."""
        trigger_hook('library.closed', self)
        self._executor.shutdown(wait=False)
        plugin_registry.cleanup()
    
    def get_entry(self, unique_id: str) -> Optional[EnhancedEntry]:
        """Get an entry by unique ID."""
        for entry_data in self._entries:
            if entry_data.get('unique_id') == unique_id:
                return EnhancedEntry(entry_data, library=self)
        return None
    
    def add_entry(self, entry: Union[Dict[str, Any], Entry], **kwargs) -> EnhancedEntry:
        """
        Add an entry to the library.
        
        Args:
            entry: Entry data or Entry object
            **kwargs: Additional fields if entry is a dict
            
        Returns:
            Enhanced entry object
        """
        # Apply before_add hook
        entry = filter_value('entry.before_add', entry, self)
        
        if isinstance(entry, Entry):
            entry_data = entry.to_dict()
        else:
            entry_data = dict(entry)
            entry_data.update(kwargs)
        
        # Add to library (base method handles unique_id)
        result = super().add_entry(entry_data)
        
        # Convert to enhanced entry
        enhanced = EnhancedEntry(result._data, library=self)
        
        # Trigger hook
        trigger_hook('entry.added', enhanced, self)
        
        return enhanced
    
    async def enrich_all_metadata(self, 
                                  sources: Optional[List[str]] = None,
                                  batch_size: int = 10) -> 'EnhancedLibrary':
        """
        Enrich metadata for all entries.
        
        Args:
            sources: Optional list of specific plugin names to use
            batch_size: Number of entries to process concurrently
            
        Returns:
            Self for chaining
        """
        entries = [EnhancedEntry(e, library=self) for e in self._entries]
        
        # Process in batches
        for i in range(0, len(entries), batch_size):
            batch = entries[i:i + batch_size]
            tasks = [entry.enrich_metadata(sources) for entry in batch]
            await asyncio.gather(*tasks)
        
        return self
    
    async def auto_tag_all(self, 
                          max_tags: int = 10,
                          confidence_threshold: float = 0.5,
                          replace: bool = False,
                          filter_func: Optional[Callable] = None) -> 'EnhancedLibrary':
        """
        Auto-tag all entries in the library.
        
        Args:
            max_tags: Maximum tags per entry
            confidence_threshold: Minimum confidence score
            replace: If True, replace existing tags
            filter_func: Optional filter to select which entries to tag
            
        Returns:
            Self for chaining
        """
        entries = [EnhancedEntry(e, library=self) for e in self._entries]
        
        if filter_func:
            entries = [e for e in entries if filter_func(e.to_dict())]
        
        # Process all entries
        tasks = [
            entry.auto_tag(max_tags, confidence_threshold, replace)
            for entry in entries
        ]
        
        await asyncio.gather(*tasks)
        
        return self
    
    def find_duplicates(self, threshold: float = 0.9) -> List[List[EnhancedEntry]]:
        """
        Find duplicate entries in the library.
        
        Args:
            threshold: Similarity threshold for duplicates
            
        Returns:
            List of duplicate groups
        """
        deduplicators = get_plugins('deduplicator')
        
        if not deduplicators:
            logger.warning("No deduplicator plugins available")
            return []
        
        # Use first available deduplicator
        deduplicator = deduplicators[0]
        
        try:
            duplicate_groups = deduplicator.find_duplicates(self._entries, threshold)
            
            # Convert to enhanced entries
            result = []
            for group in duplicate_groups:
                enhanced_group = [
                    EnhancedEntry(e, library=self) for e in group.entries
                ]
                result.append(enhanced_group)
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to find duplicates: {e}")
            return []
    
    def merge_duplicates(self, strategy: str = "newest") -> 'EnhancedLibrary':
        """
        Merge duplicate entries.
        
        Args:
            strategy: Merge strategy ("newest", "oldest", "most_complete")
            
        Returns:
            Self for chaining
        """
        deduplicators = get_plugins('deduplicator')
        
        if not deduplicators:
            logger.warning("No deduplicator plugins available")
            return self
        
        deduplicator = deduplicators[0]
        
        try:
            duplicate_groups = deduplicator.find_duplicates(self._entries)
            
            for group in duplicate_groups:
                # Merge the group
                merged = deduplicator.merge_duplicates(group, strategy)
                
                # Remove old entries
                for entry in group.entries:
                    self._entries.remove(entry)
                
                # Add merged entry
                self._entries.append(merged)
                
                logger.info(f"Merged {len(group.entries)} duplicates into one entry")
            
        except Exception as e:
            logger.error(f"Failed to merge duplicates: {e}")
        
        return self
    
    def find_similar(self, entry: Union[str, Dict[str, Any], Entry],
                    threshold: float = 0.8,
                    limit: int = 10) -> List[EnhancedEntry]:
        """
        Find entries similar to a given entry.
        
        Args:
            entry: Entry ID, dict, or Entry object
            threshold: Similarity threshold
            limit: Maximum number of results
            
        Returns:
            List of similar entries
        """
        # Get the entry
        if isinstance(entry, str):
            entry = self.get_entry(entry)
            if not entry:
                return []
            entry = entry.to_dict()
        elif isinstance(entry, Entry):
            entry = entry.to_dict()
        
        finders = get_plugins('similarity_finder')
        
        if not finders:
            logger.warning("No similarity finder plugins available")
            return []
        
        # Use first available finder
        finder = finders[0]
        
        try:
            similar = finder.find_similar(
                entry,
                self._entries,
                threshold,
                limit
            )
            
            # Convert to enhanced entries
            return [
                EnhancedEntry(e[0], library=self)
                for e in similar
            ]
            
        except Exception as e:
            logger.error(f"Failed to find similar entries: {e}")
            return []
    
    async def export_with_plugin(self, 
                                 plugin_name: str,
                                 output_path: str,
                                 options: Optional[Dict[str, Any]] = None) -> bool:
        """
        Export library using a specific plugin.
        
        Args:
            plugin_name: Name of the export plugin
            output_path: Output file or directory
            options: Export options
            
        Returns:
            True if successful
        """
        plugin = get_plugin(plugin_name)
        
        if not plugin:
            logger.error(f"Export plugin {plugin_name} not found")
            return False
        
        try:
            # Apply filter hook
            entries = await filter_value_async('filter.export_entries', self._entries, output_path)
            
            # Trigger export started hook
            await trigger_hook_async('export.started', entries, plugin_name)
            
            # Export
            result = await plugin.export(entries, output_path, options or {})
            
            if result.success:
                # Trigger export completed hook
                await trigger_hook_async('export.completed', result)
                logger.info(f"Exported {result.entries_exported} entries to {output_path}")
            else:
                # Trigger export failed hook
                await trigger_hook_async('export.failed', result)
                logger.error(f"Export failed: {result.errors}")
            
            return result.success
            
        except Exception as e:
            logger.error(f"Export failed: {e}")
            return False
    
    def use_plugin(self, plugin_name: str, config: Optional[Dict[str, Any]] = None) -> bool:
        """
        Configure and enable a plugin for this library.
        
        Args:
            plugin_name: Plugin name
            config: Optional configuration
            
        Returns:
            True if successful
        """
        if config:
            success = plugin_registry.configure_plugin(plugin_name, config)
            if not success:
                return False
        
        return plugin_registry.enable_plugin(plugin_name)
    
    def disable_plugin(self, plugin_name: str) -> bool:
        """
        Disable a plugin for this library.
        
        Args:
            plugin_name: Plugin name
            
        Returns:
            True if successful
        """
        return plugin_registry.disable_plugin(plugin_name)
    
    def list_plugins(self) -> Dict[str, List[str]]:
        """
        List all available plugins.
        
        Returns:
            Dictionary mapping plugin types to plugin names
        """
        return plugin_registry.list_plugins()
    
    def save(self) -> 'EnhancedLibrary':
        """Save library with hook support."""
        # Trigger hook
        trigger_hook('library.saved', self)
        
        # Call base save
        super().save()
        
        return self


# Convenience function to open enhanced library
def open_library(path: Union[str, Path]) -> EnhancedLibrary:
    """
    Open an enhanced library with plugin support.
    
    Args:
        path: Path to library
        
    Returns:
        EnhancedLibrary instance
    """
    return EnhancedLibrary.open(path)


# Register some default hooks
@hook('entry.added', priority=10)
def log_entry_added(entry: Entry, library: EnhancedLibrary):
    """Log when entry is added."""
    logger.debug(f"Entry added to library: {entry.title}")


@hook('library.saved', priority=10)
def log_library_saved(library: EnhancedLibrary):
    """Log when library is saved."""
    logger.debug(f"Library saved: {library.path}")