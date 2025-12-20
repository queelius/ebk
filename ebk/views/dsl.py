"""
Views DSL Evaluator.

Implements a composable DSL for selecting, transforming, and ordering books.
The DSL follows SICP principles: primitives, combination, abstraction, closure.

Grammar:
    view := {select?: selector, transform?: transform, order?: ordering}

    selector := 'all' | 'none'
              | {filter: predicate}
              | {ids: [int, ...]}
              | {view: string}
              | {union: [selector, ...]}
              | {intersect: [selector, ...]}
              | {difference: [selector, selector]}

    predicate := {field: value}
               | {field: {op: value}}
               | {and: [predicate, ...]}
               | {or: [predicate, ...]}
               | {not: predicate}

    transform := 'identity'
               | {override: {book_id: {field: value, ...}, ...}}
               | {compose: [transform, ...]}

    ordering := {by: field}
              | {by: field, desc: bool}
              | {custom: [int, ...]}
              | {then: [ordering, ...]}
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Union
from datetime import datetime
import logging

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, not_

from ..db.models import Book, Author, Subject, Tag, File, PersonalMetadata, View

logger = logging.getLogger(__name__)


@dataclass
class TransformedBook:
    """
    A book with optional view-specific overrides applied.

    The original book is preserved; overrides provide a view-specific lens.
    """
    book: Book
    title_override: Optional[str] = None
    description_override: Optional[str] = None
    position: Optional[int] = None

    @property
    def id(self) -> int:
        return self.book.id

    @property
    def title(self) -> str:
        return self.title_override if self.title_override else self.book.title

    @property
    def description(self) -> Optional[str]:
        return self.description_override if self.description_override else self.book.description

    @property
    def authors(self):
        return self.book.authors

    @property
    def subjects(self):
        return self.book.subjects

    @property
    def language(self):
        return self.book.language

    @property
    def files(self):
        return self.book.files

    @property
    def covers(self):
        return self.book.covers

    @property
    def personal(self):
        return self.book.personal

    def __repr__(self):
        override_marker = '*' if self.title_override or self.description_override else ''
        return f"<TransformedBook{override_marker}(id={self.id}, title='{self.title[:50]}')>"


class ViewEvaluator:
    """
    Evaluates view definitions against a library.

    The evaluator implements a small interpreter for the Views DSL,
    following the structure:
        evaluate(view) = order(transform(select(library)))

    Each stage is a pure function operating on sets of books.
    """

    def __init__(self, session: Session):
        self.session = session
        self._view_cache: Dict[str, View] = {}

    def evaluate(
        self,
        definition: Dict[str, Any],
        view_name: Optional[str] = None
    ) -> List[TransformedBook]:
        """
        Evaluate a view definition and return transformed books.

        Args:
            definition: View definition dict with select/transform/order
            view_name: Optional name for error messages

        Returns:
            List of TransformedBook in order
        """
        context = view_name or '<anonymous>'

        # Stage 1: Select - determine which books
        selector = definition.get('select', 'all')
        book_set = self._evaluate_selector(selector, context)

        # Stage 2: Transform - apply overrides
        transform = definition.get('transform', 'identity')
        transformed = self._evaluate_transform(transform, book_set, context)

        # Stage 3: Order - sort the results
        ordering = definition.get('order', {'by': 'title'})
        ordered = self._evaluate_ordering(ordering, transformed, context)

        return ordered

    def evaluate_view(self, view_name: str) -> List[TransformedBook]:
        """
        Evaluate a named view from the database.

        Args:
            view_name: Name of the view

        Returns:
            List of TransformedBook in order

        Raises:
            ValueError: If view not found
        """
        view = self._get_view(view_name)
        if not view:
            raise ValueError(f"View '{view_name}' not found")

        result = self.evaluate(view.definition, view_name)

        # Update cached count
        view.cached_count = len(result)
        view.cached_at = datetime.utcnow()
        self.session.commit()

        return result

    def count(self, definition: Dict[str, Any]) -> int:
        """Count books matching a view definition without full evaluation."""
        selector = definition.get('select', 'all')
        book_set = self._evaluate_selector(selector, '<count>')
        return len(book_set)

    # =========================================================================
    # Selector Evaluation
    # =========================================================================

    def _evaluate_selector(
        self,
        selector: Union[str, Dict[str, Any]],
        context: str
    ) -> Set[Book]:
        """Evaluate a selector and return a set of books."""

        # Primitive: all
        if selector == 'all':
            return set(self.session.query(Book).all())

        # Primitive: none
        if selector == 'none':
            return set()

        if not isinstance(selector, dict):
            raise ValueError(f"Invalid selector in {context}: {selector}")

        # Primitive: filter
        if 'filter' in selector:
            return self._evaluate_filter(selector['filter'], context)

        # Primitive: ids
        if 'ids' in selector:
            ids = selector['ids']
            if not isinstance(ids, list):
                raise ValueError(f"'ids' must be a list in {context}")
            books = self.session.query(Book).filter(Book.id.in_(ids)).all()
            return set(books)

        # Primitive: single id
        if 'id' in selector:
            book = self.session.query(Book).get(selector['id'])
            return {book} if book else set()

        # Abstraction: view reference
        if 'view' in selector:
            view_name = selector['view']
            return self._evaluate_view_reference(view_name, context)

        # Combination: union
        if 'union' in selector:
            selectors = selector['union']
            if not isinstance(selectors, list):
                raise ValueError(f"'union' must be a list in {context}")
            result = set()
            for sel in selectors:
                result = result.union(self._evaluate_selector(sel, context))
            return result

        # Combination: intersect
        if 'intersect' in selector:
            selectors = selector['intersect']
            if not isinstance(selectors, list) or len(selectors) < 2:
                raise ValueError(f"'intersect' must be a list of 2+ selectors in {context}")
            result = self._evaluate_selector(selectors[0], context)
            for sel in selectors[1:]:
                result = result.intersection(self._evaluate_selector(sel, context))
            return result

        # Combination: difference
        if 'difference' in selector:
            selectors = selector['difference']
            if not isinstance(selectors, list) or len(selectors) != 2:
                raise ValueError(f"'difference' must be a list of exactly 2 selectors in {context}")
            a = self._evaluate_selector(selectors[0], context)
            b = self._evaluate_selector(selectors[1], context)
            return a - b

        raise ValueError(f"Unknown selector type in {context}: {list(selector.keys())}")

    def _evaluate_filter(
        self,
        predicate: Dict[str, Any],
        context: str
    ) -> Set[Book]:
        """Evaluate a filter predicate and return matching books."""

        # Boolean combinators
        if 'and' in predicate:
            predicates = predicate['and']
            result = self._evaluate_filter(predicates[0], context)
            for pred in predicates[1:]:
                result = result.intersection(self._evaluate_filter(pred, context))
            return result

        if 'or' in predicate:
            predicates = predicate['or']
            result = set()
            for pred in predicates:
                result = result.union(self._evaluate_filter(pred, context))
            return result

        if 'not' in predicate:
            all_books = set(self.session.query(Book).all())
            excluded = self._evaluate_filter(predicate['not'], context)
            return all_books - excluded

        # Field predicates
        query = self.session.query(Book)
        query = self._apply_field_predicates(query, predicate, context)
        return set(query.all())

    def _apply_field_predicates(
        self,
        query,
        predicate: Dict[str, Any],
        context: str
    ):
        """Apply field predicates to a query."""

        for field, value in predicate.items():
            query = self._apply_single_predicate(query, field, value, context)

        return query

    def _apply_single_predicate(self, query, field: str, value: Any, context: str):
        """Apply a single field predicate to a query."""

        # Handle comparison operators
        if isinstance(value, dict):
            return self._apply_comparison(query, field, value, context)

        # Simple equality checks
        if field == 'subject':
            query = query.join(Book.subjects).filter(Subject.name.ilike(f"%{value}%"))
        elif field == 'author':
            query = query.join(Book.authors).filter(Author.name.ilike(f"%{value}%"))
        elif field == 'tag':
            query = query.join(Book.tags).filter(Tag.path.ilike(f"%{value}%"))
        elif field == 'language':
            query = query.filter(Book.language == value)
        elif field == 'title':
            query = query.filter(Book.title.ilike(f"%{value}%"))
        elif field == 'publisher':
            query = query.filter(Book.publisher.ilike(f"%{value}%"))
        elif field == 'series':
            query = query.filter(Book.series.ilike(f"%{value}%"))
        elif field == 'format':
            query = query.join(Book.files).filter(File.format.ilike(f"%{value}%"))
        elif field == 'favorite':
            if value:
                query = query.join(Book.personal).filter(PersonalMetadata.favorite == True)
            else:
                query = query.outerjoin(Book.personal).filter(
                    or_(PersonalMetadata.favorite == False, PersonalMetadata.favorite.is_(None))
                )
        elif field == 'reading_status' or field == 'status':
            query = query.join(Book.personal).filter(PersonalMetadata.reading_status == value)
        elif field == 'rating':
            query = query.join(Book.personal).filter(PersonalMetadata.rating == value)
        elif field == 'year':
            year_str = str(value)
            query = query.filter(Book.publication_date.like(f"{year_str}%"))
        else:
            logger.warning(f"Unknown filter field '{field}' in {context}")

        return query

    def _apply_comparison(self, query, field: str, comparison: Dict[str, Any], context: str):
        """Apply a comparison operator to a query."""

        # Get the comparison operator and value
        if 'gte' in comparison:
            op, val = '>=', comparison['gte']
        elif 'gt' in comparison:
            op, val = '>', comparison['gt']
        elif 'lte' in comparison:
            op, val = '<=', comparison['lte']
        elif 'lt' in comparison:
            op, val = '<', comparison['lt']
        elif 'eq' in comparison:
            op, val = '==', comparison['eq']
        elif 'ne' in comparison:
            op, val = '!=', comparison['ne']
        elif 'contains' in comparison:
            return self._apply_single_predicate(query, field, comparison['contains'], context)
        elif 'in' in comparison:
            vals = comparison['in']
            if field == 'language':
                query = query.filter(Book.language.in_(vals))
            elif field == 'id':
                query = query.filter(Book.id.in_(vals))
            return query
        elif 'between' in comparison:
            low, high = comparison['between']
            if field == 'rating':
                query = query.join(Book.personal).filter(
                    and_(PersonalMetadata.rating >= low, PersonalMetadata.rating <= high)
                )
            elif field == 'year':
                query = query.filter(
                    and_(Book.publication_date >= str(low), Book.publication_date <= str(high))
                )
            return query
        else:
            raise ValueError(f"Unknown comparison operator in {context}: {comparison}")

        # Apply the comparison
        if field == 'rating':
            query = query.join(Book.personal)
            if op == '>=':
                query = query.filter(PersonalMetadata.rating >= val)
            elif op == '>':
                query = query.filter(PersonalMetadata.rating > val)
            elif op == '<=':
                query = query.filter(PersonalMetadata.rating <= val)
            elif op == '<':
                query = query.filter(PersonalMetadata.rating < val)
            elif op == '==':
                query = query.filter(PersonalMetadata.rating == val)
            elif op == '!=':
                query = query.filter(PersonalMetadata.rating != val)
        elif field == 'year':
            year_str = str(val)
            if op == '>=':
                query = query.filter(Book.publication_date >= year_str)
            elif op == '>':
                query = query.filter(Book.publication_date > year_str)
            elif op == '<=':
                query = query.filter(Book.publication_date <= year_str)
            elif op == '<':
                query = query.filter(Book.publication_date < year_str)
        elif field == 'pages':
            if op == '>=':
                query = query.filter(Book.page_count >= val)
            elif op == '>':
                query = query.filter(Book.page_count > val)
            elif op == '<=':
                query = query.filter(Book.page_count <= val)
            elif op == '<':
                query = query.filter(Book.page_count < val)

        return query

    def _evaluate_view_reference(self, view_name: str, context: str) -> Set[Book]:
        """Evaluate a view reference by name."""
        view = self._get_view(view_name)
        if not view:
            raise ValueError(f"Referenced view '{view_name}' not found in {context}")

        # Recursively evaluate the referenced view's selector
        selector = view.definition.get('select', 'all')
        return self._evaluate_selector(selector, f"{context}→{view_name}")

    def _get_view(self, name: str) -> Optional[View]:
        """Get a view by name with caching."""
        if name not in self._view_cache:
            view = self.session.query(View).filter_by(name=name).first()
            self._view_cache[name] = view
        return self._view_cache[name]

    # =========================================================================
    # Transform Evaluation
    # =========================================================================

    def _evaluate_transform(
        self,
        transform: Union[str, Dict[str, Any]],
        books: Set[Book],
        context: str
    ) -> List[TransformedBook]:
        """Apply transforms to books."""

        # Start with identity transform (no overrides)
        if transform == 'identity':
            return [TransformedBook(book=book) for book in books]

        if not isinstance(transform, dict):
            raise ValueError(f"Invalid transform in {context}: {transform}")

        # Build initial transformed books
        transformed = {book.id: TransformedBook(book=book) for book in books}

        # Apply overrides
        if 'override' in transform:
            overrides = transform['override']
            for book_id_str, fields in overrides.items():
                book_id = int(book_id_str) if isinstance(book_id_str, str) else book_id_str
                if book_id in transformed:
                    tb = transformed[book_id]
                    if 'title' in fields:
                        tb.title_override = fields['title']
                    if 'description' in fields:
                        tb.description_override = fields['description']
                    if 'position' in fields:
                        tb.position = fields['position']

        # Handle compose (chain of transforms)
        if 'compose' in transform:
            transforms = transform['compose']
            result = list(transformed.values())
            for t in transforms:
                # Reapply each transform
                book_set = {tb.book for tb in result}
                result = self._evaluate_transform(t, book_set, context)
            return result

        # Handle view reference (inherit transforms from another view)
        if 'view' in transform:
            view_name = transform['view']
            view = self._get_view(view_name)
            if view and 'transform' in view.definition:
                book_set = {tb.book for tb in transformed.values()}
                return self._evaluate_transform(
                    view.definition['transform'], book_set, f"{context}→{view_name}"
                )

        return list(transformed.values())

    # =========================================================================
    # Ordering Evaluation
    # =========================================================================

    def _evaluate_ordering(
        self,
        ordering: Union[str, Dict[str, Any]],
        books: List[TransformedBook],
        context: str
    ) -> List[TransformedBook]:
        """Apply ordering to transformed books."""

        if isinstance(ordering, str):
            ordering = {'by': ordering}

        if not isinstance(ordering, dict):
            raise ValueError(f"Invalid ordering in {context}: {ordering}")

        # Custom order by IDs
        if 'custom' in ordering:
            custom_order = ordering['custom']
            id_to_book = {tb.id: tb for tb in books}
            ordered = []
            for book_id in custom_order:
                if book_id in id_to_book:
                    ordered.append(id_to_book.pop(book_id))
            # Append remaining books not in custom order
            ordered.extend(id_to_book.values())
            return ordered

        # Compound ordering (then)
        if 'then' in ordering:
            orderings = ordering['then']
            result = books
            # Apply orderings in reverse (most significant last)
            for ord_spec in reversed(orderings):
                result = self._evaluate_ordering(ord_spec, result, context)
            return result

        # Simple field ordering
        field = ordering.get('by', 'title')
        desc = ordering.get('desc', False)

        def get_sort_key(tb: TransformedBook):
            if field == 'title':
                return (tb.title or '').lower()
            elif field == 'author':
                authors = tb.book.authors
                return authors[0].name.lower() if authors else ''
            elif field == 'date' or field == 'publication_date':
                return tb.book.publication_date or ''
            elif field == 'rating':
                pm = tb.book.personal
                return pm.rating if pm and pm.rating else 0
            elif field == 'created_at':
                return tb.book.created_at or datetime.min
            elif field == 'position':
                return tb.position if tb.position is not None else float('inf')
            elif field == 'id':
                return tb.id
            else:
                return (tb.title or '').lower()

        return sorted(books, key=get_sort_key, reverse=desc)


# ============================================================================
# Built-in Virtual Views
# ============================================================================

BUILTIN_VIEWS = {
    'all': {
        'description': 'All books in the library',
        'select': 'all',
        'order': {'by': 'title'}
    },
    'favorites': {
        'description': 'Books marked as favorites',
        'select': {'filter': {'favorite': True}},
        'order': {'by': 'title'}
    },
    'reading': {
        'description': 'Books currently being read',
        'select': {'filter': {'reading_status': 'reading'}},
        'order': {'by': 'title'}
    },
    'completed': {
        'description': 'Books that have been read',
        'select': {'filter': {'reading_status': 'read'}},
        'order': {'by': 'title'}
    },
    'unread': {
        'description': 'Books not yet started',
        'select': {'filter': {'reading_status': 'unread'}},
        'order': {'by': 'title'}
    },
    'recent': {
        'description': 'Recently added books',
        'select': 'all',
        'order': {'by': 'created_at', 'desc': True}
    },
    'top-rated': {
        'description': 'Highest rated books',
        'select': {'filter': {'rating': {'gte': 4}}},
        'order': {'by': 'rating', 'desc': True}
    }
}


def get_builtin_view(name: str) -> Optional[Dict[str, Any]]:
    """Get a built-in virtual view definition."""
    return BUILTIN_VIEWS.get(name)


def is_builtin_view(name: str) -> bool:
    """Check if a view name is a built-in."""
    return name in BUILTIN_VIEWS
