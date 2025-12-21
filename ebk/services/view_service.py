"""
Views Service - High-level API for managing views.

Provides CRUD operations and convenience methods for working with views.
This is a re-export from ebk.views.service for the services layer.
"""

# Re-export ViewService from its original location
# This maintains backward compatibility while providing access via services layer
from ..views.service import ViewService

__all__ = ['ViewService']
