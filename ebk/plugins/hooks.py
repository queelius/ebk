"""
Hook system for EBK plugins.

This module provides a hook system that allows plugins and user code
to register callbacks for various events in the EBK lifecycle.
"""

import asyncio
import inspect
import logging
from typing import Callable, Any, List, Dict, Optional, Union
from functools import wraps
from collections import defaultdict

logger = logging.getLogger(__name__)


class HookRegistry:
    """Registry for managing hook callbacks."""
    
    def __init__(self):
        self._hooks: Dict[str, List[Callable]] = defaultdict(list)
        self._async_hooks: Dict[str, List[Callable]] = defaultdict(list)
        self._hook_priorities: Dict[str, Dict[Callable, int]] = defaultdict(dict)
        self._hook_descriptions: Dict[str, str] = {}
        
    def register_hook(self, 
                     event: str, 
                     callback: Callable,
                     priority: int = 0,
                     description: Optional[str] = None) -> None:
        """
        Register a hook callback.
        
        Args:
            event: Event name to hook into
            callback: Callback function
            priority: Priority (higher runs first)
            description: Optional description of what this hook does
        """
        if asyncio.iscoroutinefunction(callback):
            self._async_hooks[event].append(callback)
        else:
            self._hooks[event].append(callback)
        
        self._hook_priorities[event][callback] = priority
        
        # Sort by priority
        if event in self._hooks:
            self._hooks[event].sort(
                key=lambda cb: self._hook_priorities[event].get(cb, 0),
                reverse=True
            )
        if event in self._async_hooks:
            self._async_hooks[event].sort(
                key=lambda cb: self._hook_priorities[event].get(cb, 0),
                reverse=True
            )
        
        if description:
            hook_id = f"{event}:{callback.__name__}"
            self._hook_descriptions[hook_id] = description
        
        logger.debug(f"Registered hook for {event}: {callback.__name__} (priority: {priority})")
    
    def unregister_hook(self, event: str, callback: Callable) -> bool:
        """
        Unregister a hook callback.
        
        Args:
            event: Event name
            callback: Callback to remove
            
        Returns:
            True if callback was removed
        """
        removed = False
        
        if callback in self._hooks.get(event, []):
            self._hooks[event].remove(callback)
            removed = True
        
        if callback in self._async_hooks.get(event, []):
            self._async_hooks[event].remove(callback)
            removed = True
        
        if removed:
            self._hook_priorities[event].pop(callback, None)
            logger.debug(f"Unregistered hook for {event}: {callback.__name__}")
        
        return removed
    
    def trigger(self, event: str, *args, **kwargs) -> List[Any]:
        """
        Trigger all callbacks for an event (synchronous).
        
        Args:
            event: Event name
            *args: Positional arguments for callbacks
            **kwargs: Keyword arguments for callbacks
            
        Returns:
            List of results from callbacks
        """
        results = []
        
        # Run synchronous hooks
        for callback in self._hooks.get(event, []):
            try:
                result = callback(*args, **kwargs)
                if result is not None:
                    results.append(result)
            except Exception as e:
                logger.error(f"Hook {callback.__name__} failed for event {event}: {e}")
        
        # Handle async hooks in sync context
        if event in self._async_hooks:
            logger.warning(f"Async hooks registered for {event} but triggered synchronously")
        
        return results
    
    async def trigger_async(self, event: str, *args, **kwargs) -> List[Any]:
        """
        Trigger all callbacks for an event (asynchronous).
        
        Args:
            event: Event name
            *args: Positional arguments for callbacks
            **kwargs: Keyword arguments for callbacks
            
        Returns:
            List of results from callbacks
        """
        results = []
        
        # Run synchronous hooks
        for callback in self._hooks.get(event, []):
            try:
                result = callback(*args, **kwargs)
                if result is not None:
                    results.append(result)
            except Exception as e:
                logger.error(f"Hook {callback.__name__} failed for event {event}: {e}")
        
        # Run async hooks
        tasks = []
        for callback in self._async_hooks.get(event, []):
            tasks.append(self._run_async_hook(callback, event, args, kwargs))
        
        if tasks:
            async_results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in async_results:
                if isinstance(result, Exception):
                    logger.error(f"Async hook failed for event {event}: {result}")
                elif result is not None:
                    results.append(result)
        
        return results
    
    async def _run_async_hook(self, callback: Callable, event: str, args, kwargs) -> Any:
        """
        Run a single async hook with error handling.
        
        Args:
            callback: Async callback function
            event: Event name
            args: Positional arguments
            kwargs: Keyword arguments
            
        Returns:
            Result from callback or None
        """
        try:
            return await callback(*args, **kwargs)
        except Exception as e:
            logger.error(f"Async hook {callback.__name__} failed for event {event}: {e}")
            raise
    
    def trigger_filter(self, event: str, value: Any, *args, **kwargs) -> Any:
        """
        Trigger filter hooks that can modify a value.
        
        Each hook receives the current value and can return a modified version.
        If a hook returns None, the value is unchanged.
        
        Args:
            event: Event name
            value: Initial value to filter
            *args: Additional positional arguments for callbacks
            **kwargs: Additional keyword arguments for callbacks
            
        Returns:
            Final filtered value
        """
        current_value = value
        
        for callback in self._hooks.get(event, []):
            try:
                result = callback(current_value, *args, **kwargs)
                if result is not None:
                    current_value = result
            except Exception as e:
                logger.error(f"Filter hook {callback.__name__} failed for event {event}: {e}")
        
        return current_value
    
    async def trigger_filter_async(self, event: str, value: Any, *args, **kwargs) -> Any:
        """
        Trigger async filter hooks that can modify a value.
        
        Args:
            event: Event name
            value: Initial value to filter
            *args: Additional positional arguments for callbacks
            **kwargs: Additional keyword arguments for callbacks
            
        Returns:
            Final filtered value
        """
        current_value = value
        
        # Run synchronous hooks first
        current_value = self.trigger_filter(event, current_value, *args, **kwargs)
        
        # Run async hooks
        for callback in self._async_hooks.get(event, []):
            try:
                result = await callback(current_value, *args, **kwargs)
                if result is not None:
                    current_value = result
            except Exception as e:
                logger.error(f"Async filter hook {callback.__name__} failed for event {event}: {e}")
        
        return current_value
    
    def has_hooks(self, event: str) -> bool:
        """
        Check if an event has any hooks registered.
        
        Args:
            event: Event name
            
        Returns:
            True if hooks are registered
        """
        return bool(self._hooks.get(event) or self._async_hooks.get(event))
    
    def list_hooks(self) -> Dict[str, List[str]]:
        """
        List all registered hooks.
        
        Returns:
            Dictionary mapping events to callback names
        """
        result = {}
        
        for event, callbacks in self._hooks.items():
            if event not in result:
                result[event] = []
            result[event].extend([cb.__name__ for cb in callbacks])
        
        for event, callbacks in self._async_hooks.items():
            if event not in result:
                result[event] = []
            result[event].extend([f"{cb.__name__} (async)" for cb in callbacks])
        
        return result
    
    def clear_hooks(self, event: Optional[str] = None) -> None:
        """
        Clear hooks for an event or all events.
        
        Args:
            event: Event name to clear, or None to clear all
        """
        if event:
            self._hooks.pop(event, None)
            self._async_hooks.pop(event, None)
            self._hook_priorities.pop(event, None)
        else:
            self._hooks.clear()
            self._async_hooks.clear()
            self._hook_priorities.clear()
            self._hook_descriptions.clear()


# Global hook registry
hooks = HookRegistry()


def hook(event: str, priority: int = 0, description: Optional[str] = None):
    """
    Decorator for registering hook callbacks.
    
    Usage:
        @hook("entry.added")
        def on_entry_added(entry, library):
            print(f"Entry added: {entry['title']}")
        
        @hook("before_export", priority=10)
        async def validate_before_export(entries, format):
            # Async hook
            await validate_entries(entries)
    
    Args:
        event: Event name to hook into
        priority: Priority (higher runs first)
        description: Optional description
        
    Returns:
        Decorator function
    """
    def decorator(func: Callable) -> Callable:
        hooks.register_hook(event, func, priority, description)
        return func
    return decorator


def trigger_hook(event: str, *args, **kwargs) -> List[Any]:
    """
    Trigger all callbacks for an event.
    
    Args:
        event: Event name
        *args: Positional arguments for callbacks
        **kwargs: Keyword arguments for callbacks
        
    Returns:
        List of results from callbacks
    """
    return hooks.trigger(event, *args, **kwargs)


async def trigger_hook_async(event: str, *args, **kwargs) -> List[Any]:
    """
    Trigger all callbacks for an event (async).
    
    Args:
        event: Event name
        *args: Positional arguments for callbacks
        **kwargs: Keyword arguments for callbacks
        
    Returns:
        List of results from callbacks
    """
    return await hooks.trigger_async(event, *args, **kwargs)


def filter_value(event: str, value: Any, *args, **kwargs) -> Any:
    """
    Apply filter hooks to modify a value.
    
    Args:
        event: Event name
        value: Initial value
        *args: Additional arguments for callbacks
        **kwargs: Additional keyword arguments for callbacks
        
    Returns:
        Filtered value
    """
    return hooks.trigger_filter(event, value, *args, **kwargs)


async def filter_value_async(event: str, value: Any, *args, **kwargs) -> Any:
    """
    Apply async filter hooks to modify a value.
    
    Args:
        event: Event name
        value: Initial value
        *args: Additional arguments for callbacks
        **kwargs: Additional keyword arguments for callbacks
        
    Returns:
        Filtered value
    """
    return await hooks.trigger_filter_async(event, value, *args, **kwargs)


# Predefined events that EBK will trigger
EVENTS = {
    # Library events
    'library.opened': 'Library has been opened',
    'library.closed': 'Library has been closed',
    'library.saved': 'Library has been saved',
    
    # Entry events
    'entry.added': 'Entry added to library',
    'entry.updated': 'Entry updated',
    'entry.deleted': 'Entry deleted from library',
    'entry.before_add': 'Before entry is added (can cancel)',
    'entry.before_update': 'Before entry is updated (can cancel)',
    'entry.before_delete': 'Before entry is deleted (can cancel)',
    
    # Metadata events
    'metadata.extracted': 'Metadata extracted from source',
    'metadata.enriched': 'Metadata enriched from external source',
    'metadata.validated': 'Metadata validated',
    
    # Tag events
    'tags.suggested': 'Tags suggested for entry',
    'tags.added': 'Tags added to entry',
    'tags.removed': 'Tags removed from entry',
    
    # Import/Export events
    'import.started': 'Import operation started',
    'import.progress': 'Import operation progress',
    'import.completed': 'Import operation completed',
    'import.failed': 'Import operation failed',
    'export.started': 'Export operation started',
    'export.progress': 'Export operation progress',
    'export.completed': 'Export operation completed',
    'export.failed': 'Export operation failed',
    
    # Search events
    'search.started': 'Search operation started',
    'search.completed': 'Search operation completed',
    'search.results_filtered': 'Search results filtered',
    
    # Plugin events
    'plugin.registered': 'Plugin registered',
    'plugin.unregistered': 'Plugin unregistered',
    'plugin.enabled': 'Plugin enabled',
    'plugin.disabled': 'Plugin disabled',
    'plugin.configured': 'Plugin configured',
    
    # Filter events (value can be modified)
    'filter.entry_data': 'Filter entry data before save',
    'filter.search_query': 'Filter search query before execution',
    'filter.export_entries': 'Filter entries before export',
    'filter.import_entry': 'Filter entry during import',
    'filter.suggested_tags': 'Filter suggested tags',
}


def list_available_events() -> Dict[str, str]:
    """
    List all available events with descriptions.
    
    Returns:
        Dictionary mapping event names to descriptions
    """
    return EVENTS.copy()