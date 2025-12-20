"""
Views Service - High-level API for managing views.

Provides CRUD operations and convenience methods for working with views.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import logging
import yaml

from sqlalchemy.orm import Session

from ..db.models import Book, View, ViewOverride
from .dsl import ViewEvaluator, TransformedBook, BUILTIN_VIEWS, is_builtin_view, get_builtin_view

logger = logging.getLogger(__name__)


class ViewService:
    """
    Service for managing views.

    Provides:
    - CRUD operations for views
    - View evaluation
    - Import/export of view definitions
    - Membership management (add/remove books)
    - Override management (set/unset metadata)
    """

    def __init__(self, session: Session):
        self.session = session
        self.evaluator = ViewEvaluator(session)

    # =========================================================================
    # CRUD Operations
    # =========================================================================

    def create(
        self,
        name: str,
        definition: Optional[Dict[str, Any]] = None,
        description: Optional[str] = None,
        **filter_kwargs
    ) -> View:
        """
        Create a new view.

        Can be created with a full definition dict or with filter kwargs.

        Args:
            name: View name (unique)
            definition: Full view definition {select, transform, order}
            description: Human-readable description
            **filter_kwargs: Shorthand filters (subject, author, favorite, etc.)

        Returns:
            Created View instance

        Examples:
            # Full definition
            svc.create('programming', definition={
                'select': {'filter': {'subject': 'programming'}},
                'order': {'by': 'title'}
            })

            # Shorthand filters
            svc.create('favorites', favorite=True, description='My favorites')
        """
        if self.get(name):
            raise ValueError(f"View '{name}' already exists")

        if is_builtin_view(name):
            raise ValueError(f"Cannot create view with reserved name '{name}'")

        # Build definition from kwargs if not provided
        if definition is None:
            definition = self._build_definition_from_kwargs(filter_kwargs)

        view = View(
            name=name,
            description=description,
            definition=definition
        )
        self.session.add(view)
        self.session.commit()

        logger.info(f"Created view '{name}'")
        return view

    def get(self, name: str) -> Optional[View]:
        """Get a view by name."""
        return self.session.query(View).filter_by(name=name).first()

    def list(self, include_builtin: bool = True) -> List[Dict[str, Any]]:
        """
        List all views with metadata.

        Args:
            include_builtin: Whether to include built-in virtual views

        Returns:
            List of view info dicts
        """
        views = []

        # Built-in views
        if include_builtin:
            for name, defn in BUILTIN_VIEWS.items():
                views.append({
                    'name': name,
                    'description': defn.get('description', ''),
                    'builtin': True,
                    'count': None  # Computed on demand
                })

        # User-defined views
        for view in self.session.query(View).order_by(View.name).all():
            views.append({
                'name': view.name,
                'description': view.description or '',
                'builtin': False,
                'count': view.cached_count,
                'created_at': view.created_at,
                'updated_at': view.updated_at
            })

        return views

    def update(
        self,
        name: str,
        definition: Optional[Dict[str, Any]] = None,
        description: Optional[str] = None
    ) -> View:
        """
        Update an existing view.

        Args:
            name: View name
            definition: New definition (replaces existing)
            description: New description

        Returns:
            Updated View instance
        """
        view = self.get(name)
        if not view:
            raise ValueError(f"View '{name}' not found")

        if definition is not None:
            view.definition = definition
            view.cached_count = None  # Invalidate cache
            view.cached_at = None

        if description is not None:
            view.description = description

        self.session.commit()
        logger.info(f"Updated view '{name}'")
        return view

    def delete(self, name: str) -> bool:
        """
        Delete a view.

        Args:
            name: View name

        Returns:
            True if deleted, False if not found
        """
        if is_builtin_view(name):
            raise ValueError(f"Cannot delete built-in view '{name}'")

        view = self.get(name)
        if not view:
            return False

        self.session.delete(view)
        self.session.commit()
        logger.info(f"Deleted view '{name}'")
        return True

    def rename(self, old_name: str, new_name: str) -> View:
        """Rename a view."""
        if is_builtin_view(old_name):
            raise ValueError(f"Cannot rename built-in view '{old_name}'")

        view = self.get(old_name)
        if not view:
            raise ValueError(f"View '{old_name}' not found")

        if self.get(new_name):
            raise ValueError(f"View '{new_name}' already exists")

        view.name = new_name
        self.session.commit()
        logger.info(f"Renamed view '{old_name}' to '{new_name}'")
        return view

    # =========================================================================
    # Evaluation
    # =========================================================================

    def evaluate(self, name: str) -> List[TransformedBook]:
        """
        Evaluate a view and return transformed books.

        Handles both user-defined and built-in views.

        Args:
            name: View name

        Returns:
            List of TransformedBook instances
        """
        # Check for built-in view first
        if is_builtin_view(name):
            defn = get_builtin_view(name)
            return self.evaluator.evaluate(defn, name)

        # User-defined view
        return self.evaluator.evaluate_view(name)

    def count(self, name: str) -> int:
        """Get the book count for a view."""
        if is_builtin_view(name):
            defn = get_builtin_view(name)
            return self.evaluator.count(defn)

        view = self.get(name)
        if not view:
            raise ValueError(f"View '{name}' not found")

        return self.evaluator.count(view.definition)

    def books(self, name: str) -> List[Book]:
        """Get raw books for a view (without transforms)."""
        transformed = self.evaluate(name)
        return [tb.book for tb in transformed]

    # =========================================================================
    # Membership Management
    # =========================================================================

    def add_book(self, view_name: str, book_id: int) -> None:
        """
        Add a book to a view's include list.

        Args:
            view_name: View name
            book_id: Book ID to add
        """
        view = self.get(view_name)
        if not view:
            raise ValueError(f"View '{view_name}' not found")

        defn = view.definition.copy()
        selector = defn.get('select', 'all')

        # If selector is a simple type, wrap it
        if selector == 'all' or selector == 'none':
            # Convert to union with explicit include
            defn['select'] = {
                'union': [
                    selector if selector != 'none' else {'ids': []},
                    {'ids': [book_id]}
                ]
            }
        elif isinstance(selector, dict):
            if 'ids' in selector:
                # Add to existing ids list
                if book_id not in selector['ids']:
                    selector['ids'].append(book_id)
            elif 'union' in selector:
                # Add to existing union
                # Look for an ids selector to add to
                ids_sel = None
                for sel in selector['union']:
                    if isinstance(sel, dict) and 'ids' in sel:
                        ids_sel = sel
                        break
                if ids_sel:
                    if book_id not in ids_sel['ids']:
                        ids_sel['ids'].append(book_id)
                else:
                    selector['union'].append({'ids': [book_id]})
            else:
                # Wrap existing selector in union with ids
                defn['select'] = {
                    'union': [selector, {'ids': [book_id]}]
                }

        view.definition = defn
        view.cached_count = None
        self.session.commit()
        logger.info(f"Added book {book_id} to view '{view_name}'")

    def remove_book(self, view_name: str, book_id: int) -> None:
        """
        Remove a book from a view by adding it to exclusions.

        Args:
            view_name: View name
            book_id: Book ID to remove
        """
        view = self.get(view_name)
        if not view:
            raise ValueError(f"View '{view_name}' not found")

        defn = view.definition.copy()
        selector = defn.get('select', 'all')

        # Wrap in difference to exclude the book
        defn['select'] = {
            'difference': [selector, {'ids': [book_id]}]
        }

        view.definition = defn
        view.cached_count = None
        self.session.commit()
        logger.info(f"Removed book {book_id} from view '{view_name}'")

    # =========================================================================
    # Override Management
    # =========================================================================

    def set_override(
        self,
        view_name: str,
        book_id: int,
        title: Optional[str] = None,
        description: Optional[str] = None,
        position: Optional[int] = None
    ) -> ViewOverride:
        """
        Set metadata overrides for a book within a view.

        Args:
            view_name: View name
            book_id: Book ID
            title: Override title
            description: Override description
            position: Custom position for ordering

        Returns:
            ViewOverride instance
        """
        view = self.get(view_name)
        if not view:
            raise ValueError(f"View '{view_name}' not found")

        # Check book exists
        book = self.session.query(Book).get(book_id)
        if not book:
            raise ValueError(f"Book {book_id} not found")

        # Get or create override
        override = self.session.query(ViewOverride).filter_by(
            view_id=view.id, book_id=book_id
        ).first()

        if not override:
            override = ViewOverride(view_id=view.id, book_id=book_id)
            self.session.add(override)

        if title is not None:
            override.title = title
        if description is not None:
            override.description = description
        if position is not None:
            override.position = position

        self.session.commit()
        logger.info(f"Set override for book {book_id} in view '{view_name}'")
        return override

    def unset_override(
        self,
        view_name: str,
        book_id: int,
        field: Optional[str] = None
    ) -> bool:
        """
        Remove overrides for a book within a view.

        Args:
            view_name: View name
            book_id: Book ID
            field: Specific field to unset (title, description, position)
                   If None, removes all overrides for the book

        Returns:
            True if override existed, False otherwise
        """
        view = self.get(view_name)
        if not view:
            raise ValueError(f"View '{view_name}' not found")

        override = self.session.query(ViewOverride).filter_by(
            view_id=view.id, book_id=book_id
        ).first()

        if not override:
            return False

        if field is None:
            self.session.delete(override)
        elif field == 'title':
            override.title = None
        elif field == 'description':
            override.description = None
        elif field == 'position':
            override.position = None
        else:
            raise ValueError(f"Unknown field '{field}'")

        self.session.commit()
        logger.info(f"Unset override for book {book_id} in view '{view_name}'")
        return True

    def get_overrides(self, view_name: str) -> List[ViewOverride]:
        """Get all overrides for a view."""
        view = self.get(view_name)
        if not view:
            raise ValueError(f"View '{view_name}' not found")
        return view.overrides

    # =========================================================================
    # Import/Export
    # =========================================================================

    def export_yaml(self, name: str) -> str:
        """
        Export a view definition as YAML.

        Args:
            name: View name

        Returns:
            YAML string
        """
        if is_builtin_view(name):
            defn = get_builtin_view(name)
            data = {
                'name': name,
                'builtin': True,
                **defn
            }
        else:
            view = self.get(name)
            if not view:
                raise ValueError(f"View '{name}' not found")

            data = {
                'name': view.name,
                'description': view.description,
                **view.definition
            }

            # Include overrides if any
            if view.overrides:
                data['overrides'] = {
                    ov.book_id: {
                        k: v for k, v in [
                            ('title', ov.title),
                            ('description', ov.description),
                            ('position', ov.position)
                        ] if v is not None
                    }
                    for ov in view.overrides
                }

        return yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)

    def import_yaml(self, yaml_content: str, overwrite: bool = False) -> View:
        """
        Import a view from YAML.

        Args:
            yaml_content: YAML string
            overwrite: If True, overwrite existing view

        Returns:
            Created or updated View instance
        """
        data = yaml.safe_load(yaml_content)

        name = data.get('name')
        if not name:
            raise ValueError("View YAML must include 'name' field")

        if is_builtin_view(name):
            raise ValueError(f"Cannot import view with reserved name '{name}'")

        description = data.get('description')

        # Build definition from remaining fields
        definition = {}
        for key in ['select', 'transform', 'order']:
            if key in data:
                definition[key] = data[key]

        existing = self.get(name)
        if existing:
            if not overwrite:
                raise ValueError(f"View '{name}' already exists. Use overwrite=True to replace.")
            view = self.update(name, definition=definition, description=description)
        else:
            view = self.create(name, definition=definition, description=description)

        # Import overrides if present
        if 'overrides' in data:
            for book_id_str, fields in data['overrides'].items():
                book_id = int(book_id_str)
                self.set_override(
                    name, book_id,
                    title=fields.get('title'),
                    description=fields.get('description'),
                    position=fields.get('position')
                )

        return view

    def import_file(self, path: Path, overwrite: bool = False) -> View:
        """Import a view from a YAML file."""
        with open(path) as f:
            return self.import_yaml(f.read(), overwrite=overwrite)

    def export_file(self, name: str, path: Path) -> None:
        """Export a view to a YAML file."""
        yaml_content = self.export_yaml(name)
        with open(path, 'w') as f:
            f.write(yaml_content)

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def _build_definition_from_kwargs(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Build a view definition from filter keyword arguments."""
        if not kwargs:
            return {'select': 'all'}

        # Build filter predicate from kwargs
        filter_pred = {}
        for key, value in kwargs.items():
            filter_pred[key] = value

        return {
            'select': {'filter': filter_pred},
            'order': {'by': 'title'}
        }

    def dependencies(self, name: str) -> List[str]:
        """
        Get views that this view depends on (references).

        Args:
            name: View name

        Returns:
            List of referenced view names
        """
        view = self.get(name)
        if not view:
            return []

        deps = []
        self._collect_dependencies(view.definition, deps)
        return deps

    def _collect_dependencies(self, obj: Any, deps: List[str]) -> None:
        """Recursively collect view references from a definition."""
        if isinstance(obj, dict):
            if 'view' in obj:
                view_name = obj['view']
                if view_name not in deps:
                    deps.append(view_name)
            for value in obj.values():
                self._collect_dependencies(value, deps)
        elif isinstance(obj, list):
            for item in obj:
                self._collect_dependencies(item, deps)

    def dependents(self, name: str) -> List[str]:
        """
        Get views that depend on (reference) this view.

        Args:
            name: View name

        Returns:
            List of dependent view names
        """
        dependents = []
        for view in self.session.query(View).all():
            if name in self.dependencies(view.name):
                dependents.append(view.name)
        return dependents

    def validate(self, definition: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Validate a view definition without saving.

        Args:
            definition: View definition to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Try to evaluate it
            self.evaluator.evaluate(definition, '<validation>')
            return True, None
        except Exception as e:
            return False, str(e)
