"""
Plugin registry and discovery system for EBK.

This module handles plugin registration, discovery, and management.
"""

import importlib
import importlib.metadata
import inspect
import logging
import pkgutil
from pathlib import Path
from typing import Dict, List, Optional, Type, Any, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

from .base import Plugin

logger = logging.getLogger(__name__)


class PluginRegistry:
    """Central registry for all EBK plugins."""
    
    def __init__(self):
        self._plugins: Dict[str, List[Plugin]] = {}
        self._plugin_classes: Dict[str, Type[Plugin]] = {}
        self._plugin_instances: Dict[str, Plugin] = {}
        self._config: Dict[str, Dict[str, Any]] = {}
        self._enabled: Dict[str, bool] = {}
        
    def discover_plugins(self, 
                        search_paths: Optional[List[Path]] = None,
                        entry_point_group: str = "ebk.plugins") -> None:
        """
        Discover plugins from various sources.
        
        Args:
            search_paths: Additional paths to search for plugins
            entry_point_group: Entry point group name for installed plugins
        """
        # 1. Discover from entry points (installed packages)
        self._discover_entry_points(entry_point_group)
        
        # 2. Discover from local plugins directory
        self._discover_local_plugins()
        
        # 3. Discover from additional search paths
        if search_paths:
            for path in search_paths:
                self._discover_path_plugins(path)
        
        # 4. Discover from environment variable
        self._discover_env_plugins()
        
        logger.info(f"Discovered {len(self._plugin_instances)} plugins")
    
    def _discover_entry_points(self, group: str) -> None:
        """
        Discover plugins via setuptools entry points.
        
        Args:
            group: Entry point group name
        """
        try:
            # Get entry points for the group
            if hasattr(importlib.metadata, 'entry_points'):
                # Python 3.10+
                eps = importlib.metadata.entry_points()
                if hasattr(eps, 'select'):
                    # Python 3.10+
                    entry_points = eps.select(group=group)
                else:
                    # Python 3.9
                    entry_points = eps.get(group, [])
            else:
                # Fallback for older versions
                entry_points = []
            
            for ep in entry_points:
                try:
                    plugin_class = ep.load()
                    if self._is_valid_plugin_class(plugin_class):
                        self._register_class(plugin_class)
                        logger.info(f"Loaded plugin from entry point: {ep.name}")
                except Exception as e:
                    logger.error(f"Failed to load plugin {ep.name}: {e}")
                    
        except Exception as e:
            logger.warning(f"Could not discover entry point plugins: {e}")
    
    def _discover_local_plugins(self) -> None:
        """Discover plugins in the local plugins directory."""
        plugins_dir = Path(__file__).parent
        self._discover_path_plugins(plugins_dir)
    
    def _discover_path_plugins(self, path: Path) -> None:
        """
        Discover plugins in a specific directory.
        
        Args:
            path: Directory to search for plugins
        """
        if not path.exists() or not path.is_dir():
            return
        
        # Skip __pycache__ and other special directories
        if path.name.startswith('__'):
            return
        
        # Look for Python modules
        for module_info in pkgutil.iter_modules([str(path)]):
            if module_info.name.startswith('_'):
                continue
            
            try:
                # Import the module
                if path.parent in Path(__file__).parents:
                    # It's within the ebk package
                    module_path = f"ebk.plugins.{module_info.name}"
                else:
                    # It's an external path
                    module_path = module_info.name
                    
                module = importlib.import_module(module_path)
                
                # Find plugin classes in the module
                for name, obj in inspect.getmembers(module):
                    if self._is_valid_plugin_class(obj):
                        self._register_class(obj)
                        logger.info(f"Loaded plugin class: {name} from {module_path}")
                        
            except Exception as e:
                logger.error(f"Failed to load plugin module {module_info.name}: {e}")
    
    def _discover_env_plugins(self) -> None:
        """Discover plugins from environment variable."""
        import os
        plugin_paths = os.environ.get('EBK_PLUGIN_PATH', '')
        
        if plugin_paths:
            for path_str in plugin_paths.split(':'):
                path = Path(path_str).expanduser()
                if path.exists():
                    self._discover_path_plugins(path)
    
    def _is_valid_plugin_class(self, obj: Any) -> bool:
        """
        Check if an object is a valid plugin class.
        
        Args:
            obj: Object to check
            
        Returns:
            True if it's a valid plugin class
        """
        return (
            inspect.isclass(obj) and
            issubclass(obj, Plugin) and
            obj is not Plugin and
            not inspect.isabstract(obj) and
            obj.__module__ != 'ebk.plugins.base'  # Skip base classes
        )
    
    def _register_class(self, plugin_class: Type[Plugin]) -> None:
        """
        Register a plugin class.
        
        Args:
            plugin_class: Plugin class to register
        """
        try:
            # Create an instance to get the name
            instance = plugin_class()
            name = instance.name
            
            if name in self._plugin_classes:
                logger.warning(f"Plugin {name} already registered, skipping")
                return
            
            self._plugin_classes[name] = plugin_class
            
            # Determine plugin type from base class
            plugin_type = self._get_plugin_type(plugin_class)
            if plugin_type:
                if plugin_type not in self._plugins:
                    self._plugins[plugin_type] = []
                
                # Store the class for lazy instantiation
                self._plugins[plugin_type].append(instance)
                self._plugin_instances[name] = instance
                
                logger.debug(f"Registered plugin: {name} (type: {plugin_type})")
                
        except Exception as e:
            logger.error(f"Failed to register plugin class {plugin_class.__name__}: {e}")
    
    def _get_plugin_type(self, plugin_class: Type[Plugin]) -> Optional[str]:
        """
        Determine the plugin type from its base class.
        
        Args:
            plugin_class: Plugin class
            
        Returns:
            Plugin type name or None
        """
        from . import base
        
        # Map base classes to type names
        type_map = {
            base.MetadataExtractor: 'metadata_extractor',
            base.TagSuggester: 'tag_suggester',
            base.ContentAnalyzer: 'content_analyzer',
            base.SimilarityFinder: 'similarity_finder',
            base.Deduplicator: 'deduplicator',
            base.Validator: 'validator',
            base.Exporter: 'exporter'
        }
        
        for base_class, type_name in type_map.items():
            if issubclass(plugin_class, base_class):
                return type_name
        
        return None
    
    def register(self, plugin: Plugin) -> None:
        """
        Register a plugin instance.
        
        Args:
            plugin: Plugin instance to register
        """
        name = plugin.name
        
        if name in self._plugin_instances:
            logger.warning(f"Plugin {name} already registered, replacing")
        
        self._plugin_instances[name] = plugin
        
        # Determine plugin type
        plugin_type = self._get_plugin_type(type(plugin))
        if plugin_type:
            if plugin_type not in self._plugins:
                self._plugins[plugin_type] = []
            
            # Remove old instance if exists
            self._plugins[plugin_type] = [
                p for p in self._plugins[plugin_type] if p.name != name
            ]
            self._plugins[plugin_type].append(plugin)
            
        logger.info(f"Registered plugin instance: {name}")
    
    def unregister(self, name: str) -> bool:
        """
        Unregister a plugin.
        
        Args:
            name: Plugin name
            
        Returns:
            True if plugin was unregistered
        """
        if name not in self._plugin_instances:
            return False
        
        plugin = self._plugin_instances[name]
        del self._plugin_instances[name]
        
        # Remove from type list
        for plugin_list in self._plugins.values():
            plugin_list[:] = [p for p in plugin_list if p.name != name]
        
        # Cleanup
        try:
            plugin.cleanup()
        except Exception as e:
            logger.error(f"Error during plugin cleanup: {e}")
        
        logger.info(f"Unregistered plugin: {name}")
        return True
    
    def get_plugins(self, plugin_type: str) -> List[Plugin]:
        """
        Get all plugins of a specific type.
        
        Args:
            plugin_type: Type of plugins to get
            
        Returns:
            List of plugin instances
        """
        plugins = self._plugins.get(plugin_type, [])
        
        # Filter by enabled status
        return [p for p in plugins if self._enabled.get(p.name, True)]
    
    def get_plugin(self, name: str) -> Optional[Plugin]:
        """
        Get a specific plugin by name.
        
        Args:
            name: Plugin name
            
        Returns:
            Plugin instance or None
        """
        plugin = self._plugin_instances.get(name)
        
        # Check if enabled
        if plugin and not self._enabled.get(name, True):
            return None
        
        return plugin
    
    def configure_plugin(self, name: str, config: Dict[str, Any]) -> bool:
        """
        Configure a plugin.
        
        Args:
            name: Plugin name
            config: Configuration dictionary
            
        Returns:
            True if configuration was successful
        """
        plugin = self._plugin_instances.get(name)
        if not plugin:
            logger.error(f"Plugin {name} not found")
            return False
        
        try:
            self._config[name] = config
            plugin.initialize(config)
            
            if not plugin.validate_config():
                logger.error(f"Invalid configuration for plugin {name}")
                return False
            
            logger.info(f"Configured plugin: {name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to configure plugin {name}: {e}")
            return False
    
    def enable_plugin(self, name: str) -> bool:
        """
        Enable a plugin.
        
        Args:
            name: Plugin name
            
        Returns:
            True if plugin was enabled
        """
        if name not in self._plugin_instances:
            logger.error(f"Plugin {name} not found")
            return False
        
        self._enabled[name] = True
        logger.info(f"Enabled plugin: {name}")
        return True
    
    def disable_plugin(self, name: str) -> bool:
        """
        Disable a plugin.
        
        Args:
            name: Plugin name
            
        Returns:
            True if plugin was disabled
        """
        if name not in self._plugin_instances:
            logger.error(f"Plugin {name} not found")
            return False
        
        self._enabled[name] = False
        logger.info(f"Disabled plugin: {name}")
        return True
    
    def list_plugins(self) -> Dict[str, List[str]]:
        """
        List all registered plugins by type.
        
        Returns:
            Dictionary mapping plugin types to plugin names
        """
        result = {}
        for plugin_type, plugins in self._plugins.items():
            result[plugin_type] = [p.name for p in plugins]
        return result
    
    def get_plugin_info(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a plugin.
        
        Args:
            name: Plugin name
            
        Returns:
            Plugin information dictionary
        """
        plugin = self._plugin_instances.get(name)
        if not plugin:
            return None
        
        return {
            'name': plugin.name,
            'version': plugin.version,
            'description': plugin.description,
            'author': plugin.author,
            'type': self._get_plugin_type(type(plugin)),
            'enabled': self._enabled.get(name, True),
            'configured': name in self._config,
            'requires': plugin.requires
        }
    
    def cleanup(self) -> None:
        """Cleanup all plugins."""
        for plugin in self._plugin_instances.values():
            try:
                plugin.cleanup()
            except Exception as e:
                logger.error(f"Error cleaning up plugin {plugin.name}: {e}")
        
        self._plugins.clear()
        self._plugin_instances.clear()
        self._plugin_classes.clear()
        self._config.clear()
        self._enabled.clear()


# Global plugin registry instance
plugin_registry = PluginRegistry()


def register_plugin(plugin_or_class):
    """
    Decorator or function to register a plugin.
    
    Can be used as:
    - @register_plugin on a class
    - register_plugin(plugin_instance)
    
    Args:
        plugin_or_class: Plugin class or instance
        
    Returns:
        The plugin class (for decorator usage)
    """
    if inspect.isclass(plugin_or_class):
        # Used as decorator on a class
        plugin_registry._register_class(plugin_or_class)
        return plugin_or_class
    else:
        # Used as function with instance
        plugin_registry.register(plugin_or_class)
        return plugin_or_class


def get_plugins(plugin_type: str) -> List[Plugin]:
    """
    Get all plugins of a specific type.
    
    Args:
        plugin_type: Type of plugins to get
        
    Returns:
        List of plugin instances
    """
    return plugin_registry.get_plugins(plugin_type)


def get_plugin(name: str) -> Optional[Plugin]:
    """
    Get a specific plugin by name.
    
    Args:
        name: Plugin name
        
    Returns:
        Plugin instance or None
    """
    return plugin_registry.get_plugin(name)


def configure_plugin(name: str, config: Dict[str, Any]) -> bool:
    """
    Configure a plugin.
    
    Args:
        name: Plugin name
        config: Configuration dictionary
        
    Returns:
        True if configuration was successful
    """
    return plugin_registry.configure_plugin(name, config)