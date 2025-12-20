"""
Comprehensive tests for the Views DSL.

Tests cover:
- Selector evaluation (all, none, filter, ids, view, union, intersect, difference)
- Transform evaluation (identity, override)
- Ordering evaluation (by field, desc, custom, then)
- ViewService CRUD operations
- ViewService membership management
- ViewService override management
- ViewService import/export
- Built-in views
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

from ebk.library_db import Library
from ebk.db.models import Book, Author, Subject, PersonalMetadata, View, ViewOverride
from ebk.views.dsl import (
    ViewEvaluator,
    TransformedBook,
    BUILTIN_VIEWS,
    get_builtin_view,
    is_builtin_view,
)
from ebk.views.service import ViewService


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def temp_library():
    """Create a temporary library for testing."""
    temp_dir = tempfile.mkdtemp()
    lib = Library.open(Path(temp_dir))

    yield lib

    lib.close()
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def populated_library(temp_library):
    """Library with diverse test data for view testing."""
    lib = temp_library

    # Book 1: Python Programming - favorited, reading, rated 5
    test_file1 = lib.library_path / "python.txt"
    test_file1.write_text("Python programming content")
    book1 = lib.add_book(
        test_file1,
        metadata={
            "title": "Python Programming",
            "creators": ["John Doe"],
            "subjects": ["Programming", "Python"],
            "language": "en",
            "date": "2020",
        },
        extract_text=False,
        extract_cover=False,
    )
    lib.set_favorite(book1.id, True)
    lib.update_reading_status(book1.id, "reading", rating=5)

    # Book 2: Data Science Handbook - completed, rated 4
    test_file2 = lib.library_path / "datascience.txt"
    test_file2.write_text("Data science content")
    book2 = lib.add_book(
        test_file2,
        metadata={
            "title": "Data Science Handbook",
            "creators": ["Jane Smith", "Bob Johnson"],
            "subjects": ["Data Science", "Python", "Statistics"],
            "language": "en",
            "date": "2021",
        },
        extract_text=False,
        extract_cover=False,
    )
    lib.update_reading_status(book2.id, "read", rating=4)

    # Book 3: Machine Learning Guide - favorited, unread, rated 3
    test_file3 = lib.library_path / "ml.txt"
    test_file3.write_text("Machine learning content")
    book3 = lib.add_book(
        test_file3,
        metadata={
            "title": "Machine Learning Guide",
            "creators": ["Alice Brown"],
            "subjects": ["Machine Learning", "AI"],
            "language": "en",
            "date": "2022",
        },
        extract_text=False,
        extract_cover=False,
    )
    lib.set_favorite(book3.id, True)
    lib.update_reading_status(book3.id, "unread", rating=3)

    # Book 4: Spanish Literature - different language, no rating
    test_file4 = lib.library_path / "spanish.txt"
    test_file4.write_text("Spanish literature content")
    book4 = lib.add_book(
        test_file4,
        metadata={
            "title": "Literatura Espanola",
            "creators": ["Carlos Garcia"],
            "subjects": ["Literature", "Spanish"],
            "language": "es",
            "date": "2019",
        },
        extract_text=False,
        extract_cover=False,
    )

    return lib


@pytest.fixture
def view_service(populated_library):
    """ViewService instance for the populated library."""
    return ViewService(populated_library.session)


@pytest.fixture
def evaluator(populated_library):
    """ViewEvaluator instance for the populated library."""
    return ViewEvaluator(populated_library.session)


# =============================================================================
# Selector Evaluation Tests
# =============================================================================


class TestSelectorAll:
    """Test the 'all' selector."""

    def test_all_returns_all_books(self, evaluator, populated_library):
        """Given a library with books, when selecting 'all', then all books are returned."""
        # Given: A library with 4 books
        all_books = populated_library.get_all_books()

        # When: Evaluating 'all' selector
        result = evaluator.evaluate({"select": "all"})

        # Then: All books should be returned
        assert len(result) == len(all_books)
        result_ids = {tb.id for tb in result}
        expected_ids = {b.id for b in all_books}
        assert result_ids == expected_ids


class TestSelectorNone:
    """Test the 'none' selector."""

    def test_none_returns_empty_set(self, evaluator):
        """Given any library, when selecting 'none', then empty result is returned."""
        # When: Evaluating 'none' selector
        result = evaluator.evaluate({"select": "none"})

        # Then: Result should be empty
        assert len(result) == 0


class TestSelectorFilter:
    """Test the 'filter' selector with various predicates."""

    def test_filter_by_subject(self, evaluator, populated_library):
        """Given books with subjects, when filtering by subject, then matching books are returned."""
        # When: Filtering by subject "Python"
        result = evaluator.evaluate({"select": {"filter": {"subject": "Python"}}})

        # Then: Should return books with Python subject
        assert len(result) == 2
        for tb in result:
            subject_names = [s.name for s in tb.book.subjects]
            assert any("Python" in name for name in subject_names)

    def test_filter_by_author(self, evaluator, populated_library):
        """Given books with authors, when filtering by author, then matching books are returned."""
        # When: Filtering by author "Alice" (unique author name)
        result = evaluator.evaluate({"select": {"filter": {"author": "Alice"}}})

        # Then: Should return books by Alice Brown
        assert len(result) == 1
        assert result[0].title == "Machine Learning Guide"

    def test_filter_by_language(self, evaluator, populated_library):
        """Given books in different languages, when filtering by language, then matching books are returned."""
        # When: Filtering by Spanish language
        result = evaluator.evaluate({"select": {"filter": {"language": "es"}}})

        # Then: Should return only Spanish book
        assert len(result) == 1
        assert result[0].title == "Literatura Espanola"

    def test_filter_by_favorite_true(self, evaluator, populated_library):
        """Given favorited books, when filtering by favorite=True, then favorited books are returned."""
        # When: Filtering by favorite
        result = evaluator.evaluate({"select": {"filter": {"favorite": True}}})

        # Then: Should return favorited books
        assert len(result) == 2
        titles = {tb.title for tb in result}
        assert "Python Programming" in titles
        assert "Machine Learning Guide" in titles

    def test_filter_by_favorite_false(self, evaluator, populated_library):
        """Given non-favorited books, when filtering by favorite=False, then non-favorites are returned."""
        # When: Filtering by not favorite
        result = evaluator.evaluate({"select": {"filter": {"favorite": False}}})

        # Then: Should return non-favorited books
        assert len(result) == 2
        titles = {tb.title for tb in result}
        assert "Data Science Handbook" in titles
        assert "Literatura Espanola" in titles

    def test_filter_by_reading_status(self, evaluator, populated_library):
        """Given books with reading status, when filtering by status, then matching books are returned."""
        # When: Filtering by reading status
        result = evaluator.evaluate({"select": {"filter": {"reading_status": "reading"}}})

        # Then: Should return books being read
        assert len(result) == 1
        assert result[0].title == "Python Programming"

    def test_filter_by_rating_exact(self, evaluator, populated_library):
        """Given rated books, when filtering by exact rating, then matching books are returned."""
        # When: Filtering by exact rating
        result = evaluator.evaluate({"select": {"filter": {"rating": 5}}})

        # Then: Should return books with rating 5
        assert len(result) == 1
        assert result[0].title == "Python Programming"

    def test_filter_by_year(self, evaluator, populated_library):
        """Given books with publication dates, when filtering by year, then matching books are returned."""
        # When: Filtering by year 2020 (the first book's year)
        result = evaluator.evaluate({"select": {"filter": {"year": 2020}}})

        # Then: Should return books from 2020
        assert len(result) == 1
        assert result[0].title == "Python Programming"

    def test_filter_by_title(self, evaluator, populated_library):
        """Given books with titles, when filtering by title substring, then matching books are returned."""
        # When: Filtering by title
        result = evaluator.evaluate({"select": {"filter": {"title": "Learning"}}})

        # Then: Should return books with "Learning" in title
        assert len(result) == 1
        assert result[0].title == "Machine Learning Guide"


class TestSelectorIds:
    """Test the 'ids' selector."""

    def test_ids_with_existing_books(self, evaluator, populated_library):
        """Given specific book IDs, when selecting by ids, then those books are returned."""
        # Given: Specific book IDs
        all_books = populated_library.get_all_books()
        target_ids = [all_books[0].id, all_books[1].id]

        # When: Selecting by IDs
        result = evaluator.evaluate({"select": {"ids": target_ids}})

        # Then: Should return those specific books
        assert len(result) == 2
        result_ids = {tb.id for tb in result}
        assert result_ids == set(target_ids)

    def test_ids_with_nonexistent_books(self, evaluator):
        """Given nonexistent book IDs, when selecting by ids, then empty result is returned."""
        # When: Selecting by nonexistent IDs
        result = evaluator.evaluate({"select": {"ids": [99999, 99998]}})

        # Then: Should return empty
        assert len(result) == 0

    def test_ids_with_empty_list(self, evaluator):
        """Given empty ID list, when selecting by ids, then empty result is returned."""
        # When: Selecting by empty list
        result = evaluator.evaluate({"select": {"ids": []}})

        # Then: Should return empty
        assert len(result) == 0


class TestSelectorViewReference:
    """Test the 'view' reference selector."""

    def test_view_reference_to_user_view(self, evaluator, view_service, populated_library):
        """Given a named view, when referencing it in selector, then its books are returned."""
        # Given: A named view that selects favorites
        view_service.create(
            "my-favorites",
            definition={"select": {"filter": {"favorite": True}}},
        )

        # Clear evaluator cache to pick up new view
        evaluator._view_cache.clear()

        # When: Referencing the view
        result = evaluator.evaluate({"select": {"view": "my-favorites"}})

        # Then: Should return favorites
        assert len(result) == 2

    def test_view_reference_nonexistent_raises(self, evaluator):
        """Given nonexistent view name, when referencing it, then ValueError is raised."""
        # When/Then: Referencing nonexistent view raises error
        with pytest.raises(ValueError, match="not found"):
            evaluator.evaluate({"select": {"view": "nonexistent-view"}})


class TestSelectorUnion:
    """Test the 'union' combinator."""

    def test_union_of_disjoint_selectors(self, evaluator, populated_library):
        """Given disjoint selectors, when unioning them, then all matching books are returned."""
        # When: Union of favorites and Spanish books
        result = evaluator.evaluate(
            {
                "select": {
                    "union": [
                        {"filter": {"favorite": True}},
                        {"filter": {"language": "es"}},
                    ]
                }
            }
        )

        # Then: Should return favorites (2) + Spanish (1) = 3 unique books
        assert len(result) == 3

    def test_union_of_overlapping_selectors(self, evaluator, populated_library):
        """Given overlapping selectors, when unioning them, then duplicates are removed."""
        # When: Union of favorites and Python books (Python Programming is both)
        result = evaluator.evaluate(
            {
                "select": {
                    "union": [
                        {"filter": {"favorite": True}},
                        {"filter": {"subject": "Python"}},
                    ]
                }
            }
        )

        # Then: Should return unique books only
        # Favorites: Python Programming, Machine Learning Guide
        # Python: Python Programming, Data Science Handbook
        # Union: Python Programming, Machine Learning Guide, Data Science Handbook = 3
        assert len(result) == 3

    def test_union_with_none(self, evaluator, populated_library):
        """Given union with none selector, when evaluating, then only non-none results are returned."""
        # When: Union of none and favorites
        result = evaluator.evaluate(
            {"select": {"union": ["none", {"filter": {"favorite": True}}]}}
        )

        # Then: Should return only favorites
        assert len(result) == 2


class TestSelectorIntersect:
    """Test the 'intersect' combinator."""

    def test_intersect_with_overlap(self, evaluator, populated_library):
        """Given overlapping selectors, when intersecting them, then common books are returned."""
        # When: Intersect favorites and Python books
        result = evaluator.evaluate(
            {
                "select": {
                    "intersect": [
                        {"filter": {"favorite": True}},
                        {"filter": {"subject": "Python"}},
                    ]
                }
            }
        )

        # Then: Should return only books that are both favorite AND have Python subject
        # Only "Python Programming" is both
        assert len(result) == 1
        assert result[0].title == "Python Programming"

    def test_intersect_no_overlap(self, evaluator, populated_library):
        """Given non-overlapping selectors, when intersecting them, then empty result is returned."""
        # When: Intersect Spanish books with Python subject
        result = evaluator.evaluate(
            {
                "select": {
                    "intersect": [
                        {"filter": {"language": "es"}},
                        {"filter": {"subject": "Python"}},
                    ]
                }
            }
        )

        # Then: Should return empty (no Spanish Python books)
        assert len(result) == 0

    def test_intersect_with_all(self, evaluator, populated_library):
        """Given intersect with 'all', when evaluating, then all matching subset is returned."""
        # When: Intersect all with favorites
        result = evaluator.evaluate(
            {"select": {"intersect": ["all", {"filter": {"favorite": True}}]}}
        )

        # Then: Should return favorites
        assert len(result) == 2


class TestSelectorDifference:
    """Test the 'difference' combinator."""

    def test_difference_removes_matching(self, evaluator, populated_library):
        """Given two selectors, when taking difference, then second is removed from first."""
        # When: All books minus favorites
        result = evaluator.evaluate(
            {"select": {"difference": ["all", {"filter": {"favorite": True}}]}}
        )

        # Then: Should return non-favorites (4 total - 2 favorites = 2)
        assert len(result) == 2
        titles = {tb.title for tb in result}
        assert "Python Programming" not in titles
        assert "Machine Learning Guide" not in titles

    def test_difference_with_no_overlap(self, evaluator, populated_library):
        """Given non-overlapping selectors, when taking difference, then first is unchanged."""
        # When: Spanish books minus Python books
        result = evaluator.evaluate(
            {
                "select": {
                    "difference": [
                        {"filter": {"language": "es"}},
                        {"filter": {"subject": "Python"}},
                    ]
                }
            }
        )

        # Then: Should return Spanish book unchanged
        assert len(result) == 1
        assert result[0].title == "Literatura Espanola"


class TestBooleanPredicates:
    """Test boolean predicate combinators (and, or, not)."""

    def test_and_combines_predicates(self, evaluator, populated_library):
        """Given AND predicate, when evaluating, then books matching all conditions are returned."""
        # When: Filter by favorite AND English language
        result = evaluator.evaluate(
            {
                "select": {
                    "filter": {"and": [{"favorite": True}, {"language": "en"}]}
                }
            }
        )

        # Then: Should return English favorites
        assert len(result) == 2

    def test_or_combines_predicates(self, evaluator, populated_library):
        """Given OR predicate, when evaluating, then books matching any condition are returned."""
        # When: Filter by Spanish OR reading status
        result = evaluator.evaluate(
            {
                "select": {
                    "filter": {
                        "or": [{"language": "es"}, {"reading_status": "reading"}]
                    }
                }
            }
        )

        # Then: Should return Spanish books OR books being read
        assert len(result) == 2

    def test_not_inverts_predicate(self, evaluator, populated_library):
        """Given NOT predicate, when evaluating, then books NOT matching are returned."""
        # When: Filter by NOT favorite
        result = evaluator.evaluate(
            {"select": {"filter": {"not": {"favorite": True}}}}
        )

        # Then: Should return non-favorites
        assert len(result) == 2


class TestComparisonOperators:
    """Test comparison operators (gte, lte, gt, lt, contains, in, between)."""

    def test_gte_operator(self, evaluator, populated_library):
        """Given gte comparison, when filtering, then books >= value are returned."""
        # When: Rating >= 4
        result = evaluator.evaluate(
            {"select": {"filter": {"rating": {"gte": 4}}}}
        )

        # Then: Should return books with rating 4 or 5
        assert len(result) == 2

    def test_lte_operator(self, evaluator, populated_library):
        """Given lte comparison, when filtering, then books <= value are returned."""
        # When: Rating <= 3
        result = evaluator.evaluate(
            {"select": {"filter": {"rating": {"lte": 3}}}}
        )

        # Then: Should return books with rating 3 or less
        assert len(result) == 1

    def test_gt_operator(self, evaluator, populated_library):
        """Given gt comparison, when filtering, then books > value are returned."""
        # When: Rating > 4
        result = evaluator.evaluate(
            {"select": {"filter": {"rating": {"gt": 4}}}}
        )

        # Then: Should return only rating 5
        assert len(result) == 1
        assert result[0].title == "Python Programming"

    def test_lt_operator(self, evaluator, populated_library):
        """Given lt comparison, when filtering, then books < value are returned."""
        # When: Rating < 4
        result = evaluator.evaluate(
            {"select": {"filter": {"rating": {"lt": 4}}}}
        )

        # Then: Should return only rating 3
        assert len(result) == 1
        assert result[0].title == "Machine Learning Guide"

    def test_in_operator_for_language(self, evaluator, populated_library):
        """Given in comparison for language, when filtering, then matching books are returned."""
        # When: Language in [en, es]
        result = evaluator.evaluate(
            {"select": {"filter": {"language": {"in": ["en", "es"]}}}}
        )

        # Then: Should return all books
        assert len(result) == 4

    def test_between_operator_for_rating(self, evaluator, populated_library):
        """Given between comparison, when filtering, then books in range are returned."""
        # When: Rating between 3 and 4
        result = evaluator.evaluate(
            {"select": {"filter": {"rating": {"between": [3, 4]}}}}
        )

        # Then: Should return books with rating 3 or 4
        assert len(result) == 2

    def test_contains_operator(self, evaluator, populated_library):
        """Given contains comparison, when filtering, then matching substring books are returned."""
        # When: Title contains "Guide"
        result = evaluator.evaluate(
            {"select": {"filter": {"title": {"contains": "Guide"}}}}
        )

        # Then: Should return books with "Guide" in title
        assert len(result) == 1
        assert "Guide" in result[0].title


# =============================================================================
# Transform Evaluation Tests
# =============================================================================


class TestTransformIdentity:
    """Test the 'identity' transform."""

    def test_identity_preserves_original_data(self, evaluator, populated_library):
        """Given identity transform, when evaluating, then original data is preserved."""
        # When: Evaluating with identity transform
        result = evaluator.evaluate({"select": "all", "transform": "identity"})

        # Then: All books should have no overrides
        for tb in result:
            assert tb.title_override is None
            assert tb.description_override is None
            assert tb.title == tb.book.title


class TestTransformOverride:
    """Test the 'override' transform."""

    def test_override_changes_title(self, evaluator, populated_library):
        """Given title override, when evaluating, then TransformedBook uses override."""
        # Given: A specific book ID
        all_books = populated_library.get_all_books()
        book_id = all_books[0].id
        original_title = all_books[0].title

        # When: Evaluating with title override
        result = evaluator.evaluate(
            {
                "select": {"ids": [book_id]},
                "transform": {"override": {book_id: {"title": "Overridden Title"}}},
            }
        )

        # Then: TransformedBook should use overridden title
        assert len(result) == 1
        assert result[0].title == "Overridden Title"
        assert result[0].title_override == "Overridden Title"
        assert result[0].book.title == original_title  # Original unchanged

    def test_override_changes_description(self, evaluator, populated_library):
        """Given description override, when evaluating, then TransformedBook uses override."""
        # Given: A specific book ID
        all_books = populated_library.get_all_books()
        book_id = all_books[0].id

        # When: Evaluating with description override
        result = evaluator.evaluate(
            {
                "select": {"ids": [book_id]},
                "transform": {
                    "override": {book_id: {"description": "Custom description"}}
                },
            }
        )

        # Then: TransformedBook should use overridden description
        assert len(result) == 1
        assert result[0].description == "Custom description"

    def test_override_with_position(self, evaluator, populated_library):
        """Given position override, when evaluating, then position is set."""
        # Given: A specific book ID
        all_books = populated_library.get_all_books()
        book_id = all_books[0].id

        # When: Evaluating with position override
        result = evaluator.evaluate(
            {
                "select": {"ids": [book_id]},
                "transform": {"override": {book_id: {"position": 5}}},
            }
        )

        # Then: Position should be set
        assert len(result) == 1
        assert result[0].position == 5


class TestTransformedBook:
    """Test TransformedBook properties."""

    def test_transformed_book_returns_override_when_set(self, populated_library):
        """Given overrides, when accessing properties, then overrides are returned."""
        # Given: A book with overrides
        book = populated_library.get_all_books()[0]
        tb = TransformedBook(
            book=book,
            title_override="Custom Title",
            description_override="Custom Desc",
        )

        # Then: Properties return overrides
        assert tb.title == "Custom Title"
        assert tb.description == "Custom Desc"
        assert tb.id == book.id

    def test_transformed_book_returns_original_when_no_override(
        self, populated_library
    ):
        """Given no overrides, when accessing properties, then original values are returned."""
        # Given: A book without overrides
        book = populated_library.get_all_books()[0]
        tb = TransformedBook(book=book)

        # Then: Properties return original values
        assert tb.title == book.title
        assert tb.description == book.description

    def test_transformed_book_passthrough_properties(self, populated_library):
        """Given TransformedBook, when accessing passthrough properties, then book properties are returned."""
        # Given: A book
        book = populated_library.get_all_books()[0]
        tb = TransformedBook(book=book)

        # Then: Passthrough properties work
        assert tb.authors == book.authors
        assert tb.subjects == book.subjects
        assert tb.language == book.language
        assert tb.files == book.files
        assert tb.covers == book.covers
        assert tb.personal == book.personal


# =============================================================================
# Ordering Evaluation Tests
# =============================================================================


class TestOrderingByField:
    """Test ordering by various fields."""

    def test_order_by_title(self, evaluator, populated_library):
        """Given order by title, when evaluating, then books are sorted by title."""
        # When: Ordering by title
        result = evaluator.evaluate({"select": "all", "order": {"by": "title"}})

        # Then: Books should be sorted by title ascending
        titles = [tb.title for tb in result]
        assert titles == sorted(titles, key=str.lower)

    def test_order_by_title_descending(self, evaluator, populated_library):
        """Given order by title desc, when evaluating, then books are sorted descending."""
        # When: Ordering by title descending
        result = evaluator.evaluate(
            {"select": "all", "order": {"by": "title", "desc": True}}
        )

        # Then: Books should be sorted by title descending
        titles = [tb.title for tb in result]
        assert titles == sorted(titles, key=str.lower, reverse=True)

    def test_order_by_author(self, evaluator, populated_library):
        """Given order by author, when evaluating, then books are sorted by author name."""
        # When: Ordering by author
        result = evaluator.evaluate({"select": "all", "order": {"by": "author"}})

        # Then: Books should be sorted by first author name
        # Extract first author names
        author_names = []
        for tb in result:
            if tb.book.authors:
                author_names.append(tb.book.authors[0].name.lower())
            else:
                author_names.append("")

        assert author_names == sorted(author_names)

    def test_order_by_date(self, evaluator, populated_library):
        """Given order by date, when evaluating, then books are sorted by publication date."""
        # When: Ordering by date
        result = evaluator.evaluate({"select": "all", "order": {"by": "date"}})

        # Then: Books should be sorted by publication date
        dates = [tb.book.publication_date or "" for tb in result]
        assert dates == sorted(dates)

    def test_order_by_rating(self, evaluator, populated_library):
        """Given order by rating, when evaluating, then books are sorted by rating."""
        # Filter to only rated books for cleaner test
        result = evaluator.evaluate(
            {
                "select": {"filter": {"rating": {"gte": 1}}},
                "order": {"by": "rating", "desc": True},
            }
        )

        # Then: Books should be sorted by rating descending
        ratings = [
            tb.book.personal.rating if tb.book.personal else 0 for tb in result
        ]
        assert ratings == sorted(ratings, reverse=True)


class TestCustomOrdering:
    """Test custom ordering with explicit IDs."""

    def test_custom_order_explicit_ids(self, evaluator, populated_library):
        """Given custom order with IDs, when evaluating, then books are in that order."""
        # Given: Specific book IDs in desired order
        all_books = populated_library.get_all_books()
        custom_ids = [all_books[2].id, all_books[0].id, all_books[1].id]

        # When: Using custom order
        result = evaluator.evaluate(
            {"select": {"ids": custom_ids}, "order": {"custom": custom_ids}}
        )

        # Then: Books should be in custom order
        result_ids = [tb.id for tb in result]
        assert result_ids == custom_ids

    def test_custom_order_partial_ids(self, evaluator, populated_library):
        """Given partial custom order, when evaluating, then specified are first, rest follow."""
        # Given: Custom order with only some IDs
        all_books = populated_library.get_all_books()
        custom_ids = [all_books[1].id]  # Only one ID specified

        # When: Using custom order with all books selected
        result = evaluator.evaluate(
            {"select": "all", "order": {"custom": custom_ids}}
        )

        # Then: Specified book should be first
        assert result[0].id == custom_ids[0]


class TestCompoundOrdering:
    """Test compound ordering with 'then'."""

    def test_then_compound_ordering(self, evaluator, populated_library):
        """Given compound ordering, when evaluating, then ordering is applied in sequence."""
        # When: Order by language then by title
        result = evaluator.evaluate(
            {
                "select": "all",
                "order": {"then": [{"by": "language"}, {"by": "title"}]},
            }
        )

        # Then: Books should be sorted by language, then title within language
        # en books should come before es, and within en should be sorted by title
        prev_lang = ""
        prev_title = ""
        for tb in result:
            lang = tb.book.language or ""
            title = tb.title.lower()
            if lang == prev_lang:
                assert title >= prev_title
            prev_lang = lang
            prev_title = title


# =============================================================================
# ViewService CRUD Tests
# =============================================================================


class TestViewServiceCreate:
    """Test ViewService create operations."""

    def test_create_with_filter_kwargs(self, view_service):
        """Given filter kwargs, when creating view, then definition is built correctly."""
        # When: Creating view with kwargs
        view = view_service.create("my-view", subject="Python", favorite=True)

        # Then: View should have correct definition
        assert view.name == "my-view"
        assert view.definition["select"]["filter"]["subject"] == "Python"
        assert view.definition["select"]["filter"]["favorite"] is True

    def test_create_with_full_definition(self, view_service):
        """Given full definition, when creating view, then definition is stored."""
        # When: Creating view with full definition
        definition = {
            "select": {"union": [{"filter": {"favorite": True}}, {"ids": [1, 2]}]},
            "order": {"by": "rating", "desc": True},
        }
        view = view_service.create("complex-view", definition=definition)

        # Then: Definition should be stored exactly
        assert view.definition == definition

    def test_create_with_description(self, view_service):
        """Given description, when creating view, then description is stored."""
        # When: Creating view with description
        view = view_service.create(
            "my-view",
            definition={"select": "all"},
            description="My test view",
        )

        # Then: Description should be stored
        assert view.description == "My test view"

    def test_create_duplicate_raises(self, view_service):
        """Given existing view, when creating with same name, then ValueError is raised."""
        # Given: An existing view
        view_service.create("existing-view", definition={"select": "all"})

        # When/Then: Creating duplicate raises
        with pytest.raises(ValueError, match="already exists"):
            view_service.create("existing-view", definition={"select": "none"})

    def test_create_with_builtin_name_raises(self, view_service):
        """Given built-in name, when creating view, then ValueError is raised."""
        # When/Then: Creating with reserved name raises
        with pytest.raises(ValueError, match="reserved name"):
            view_service.create("favorites", definition={"select": "all"})


class TestViewServiceGet:
    """Test ViewService get operations."""

    def test_get_existing_view(self, view_service):
        """Given existing view, when getting by name, then view is returned."""
        # Given: An existing view
        view_service.create("my-view", definition={"select": "all"})

        # When: Getting by name
        view = view_service.get("my-view")

        # Then: View should be returned
        assert view is not None
        assert view.name == "my-view"

    def test_get_nonexistent_view(self, view_service):
        """Given nonexistent view, when getting by name, then None is returned."""
        # When: Getting nonexistent view
        view = view_service.get("nonexistent")

        # Then: None should be returned
        assert view is None


class TestViewServiceList:
    """Test ViewService list operations."""

    def test_list_with_builtins(self, view_service):
        """Given views, when listing with builtins, then all are returned."""
        # Given: A user view
        view_service.create("user-view", definition={"select": "all"})

        # When: Listing with builtins
        views = view_service.list(include_builtin=True)

        # Then: Should include builtins and user view
        names = {v["name"] for v in views}
        assert "favorites" in names  # builtin
        assert "user-view" in names

    def test_list_without_builtins(self, view_service):
        """Given views, when listing without builtins, then only user views are returned."""
        # Given: A user view
        view_service.create("user-view", definition={"select": "all"})

        # When: Listing without builtins
        views = view_service.list(include_builtin=False)

        # Then: Should include only user views
        names = {v["name"] for v in views}
        assert "favorites" not in names
        assert "user-view" in names

    def test_list_metadata(self, view_service):
        """Given views, when listing, then metadata is included."""
        # Given: A user view with description
        view_service.create(
            "user-view",
            definition={"select": "all"},
            description="Test description",
        )

        # When: Listing
        views = view_service.list(include_builtin=False)

        # Then: Metadata should be included
        user_view = next(v for v in views if v["name"] == "user-view")
        assert user_view["description"] == "Test description"
        assert user_view["builtin"] is False
        assert "created_at" in user_view


class TestViewServiceUpdate:
    """Test ViewService update operations."""

    def test_update_definition(self, view_service):
        """Given view, when updating definition, then definition is changed."""
        # Given: An existing view
        view_service.create("my-view", definition={"select": "all"})

        # When: Updating definition
        new_definition = {"select": "none"}
        view = view_service.update("my-view", definition=new_definition)

        # Then: Definition should be updated
        assert view.definition == new_definition
        assert view.cached_count is None  # Cache invalidated

    def test_update_description(self, view_service):
        """Given view, when updating description, then description is changed."""
        # Given: An existing view
        view_service.create("my-view", definition={"select": "all"})

        # When: Updating description
        view = view_service.update("my-view", description="New description")

        # Then: Description should be updated
        assert view.description == "New description"

    def test_update_nonexistent_raises(self, view_service):
        """Given nonexistent view, when updating, then ValueError is raised."""
        # When/Then: Updating nonexistent raises
        with pytest.raises(ValueError, match="not found"):
            view_service.update("nonexistent", description="test")


class TestViewServiceDelete:
    """Test ViewService delete operations."""

    def test_delete_existing_view(self, view_service):
        """Given existing view, when deleting, then True is returned."""
        # Given: An existing view
        view_service.create("my-view", definition={"select": "all"})

        # When: Deleting
        result = view_service.delete("my-view")

        # Then: True should be returned and view should be gone
        assert result is True
        assert view_service.get("my-view") is None

    def test_delete_nonexistent_view(self, view_service):
        """Given nonexistent view, when deleting, then False is returned."""
        # When: Deleting nonexistent
        result = view_service.delete("nonexistent")

        # Then: False should be returned
        assert result is False

    def test_delete_builtin_raises(self, view_service):
        """Given built-in view, when deleting, then ValueError is raised."""
        # When/Then: Deleting builtin raises
        with pytest.raises(ValueError, match="Cannot delete built-in"):
            view_service.delete("favorites")


class TestViewServiceRename:
    """Test ViewService rename operations."""

    def test_rename_view(self, view_service):
        """Given view, when renaming, then name is changed."""
        # Given: An existing view
        view_service.create("old-name", definition={"select": "all"})

        # When: Renaming
        view = view_service.rename("old-name", "new-name")

        # Then: Name should be changed
        assert view.name == "new-name"
        assert view_service.get("old-name") is None
        assert view_service.get("new-name") is not None

    def test_rename_to_existing_raises(self, view_service):
        """Given existing target name, when renaming, then ValueError is raised."""
        # Given: Two views
        view_service.create("view1", definition={"select": "all"})
        view_service.create("view2", definition={"select": "none"})

        # When/Then: Renaming to existing raises
        with pytest.raises(ValueError, match="already exists"):
            view_service.rename("view1", "view2")

    def test_rename_builtin_raises(self, view_service):
        """Given built-in view, when renaming, then ValueError is raised."""
        # When/Then: Renaming builtin raises
        with pytest.raises(ValueError, match="Cannot rename built-in"):
            view_service.rename("favorites", "my-favorites")


# =============================================================================
# ViewService Membership Tests
# =============================================================================


class TestViewServiceAddBook:
    """Test adding books to views."""

    def test_add_book_to_all_view(self, view_service, populated_library):
        """Given view with 'all' selector, when adding book, then view uses union with ids."""
        # Given: A view with 'all' selector
        all_books = populated_library.get_all_books()
        first_book_id = all_books[0].id
        view_service.create("all-view", definition={"select": "all"})

        # When: Adding a specific book (even though all are already included)
        view_service.add_book("all-view", first_book_id)

        # Then: View selector should be wrapped in union
        view = view_service.get("all-view")
        selector = view.definition["select"]
        assert "union" in selector
        # And the ids should include the added book
        ids_selector = [s for s in selector["union"] if isinstance(s, dict) and "ids" in s]
        assert len(ids_selector) == 1
        assert first_book_id in ids_selector[0]["ids"]

    def test_add_book_to_filter_view(self, view_service, populated_library):
        """Given view with filter selector, when adding book, then view is wrapped in union."""
        # Given: A view with filter
        all_books = populated_library.get_all_books()
        view_service.create(
            "filter-view", definition={"select": {"filter": {"favorite": True}}}
        )

        # When: Adding a specific book
        view_service.add_book("filter-view", all_books[3].id)  # Spanish book

        # Then: View should have union selector
        view = view_service.get("filter-view")
        selector = view.definition["select"]
        assert "union" in selector

    def test_add_book_nonexistent_view_raises(self, view_service, populated_library):
        """Given nonexistent view, when adding book, then ValueError is raised."""
        # When/Then: Adding to nonexistent raises
        with pytest.raises(ValueError, match="not found"):
            view_service.add_book("nonexistent", 1)


class TestViewServiceRemoveBook:
    """Test removing books from views."""

    def test_remove_book_from_view(self, view_service, populated_library):
        """Given view with book, when removing book, then book is excluded."""
        # Given: A view with all books
        all_books = populated_library.get_all_books()
        view_service.create("my-view", definition={"select": "all"})

        # When: Removing a book
        view_service.remove_book("my-view", all_books[0].id)

        # Then: View selector should use difference
        view = view_service.get("my-view")
        assert "difference" in view.definition["select"]

    def test_remove_book_nonexistent_view_raises(self, view_service, populated_library):
        """Given nonexistent view, when removing book, then ValueError is raised."""
        # When/Then: Removing from nonexistent raises
        with pytest.raises(ValueError, match="not found"):
            view_service.remove_book("nonexistent", 1)


# =============================================================================
# ViewService Override Tests
# =============================================================================


class TestViewServiceSetOverride:
    """Test setting overrides."""

    def test_set_title_override(self, view_service, populated_library):
        """Given view and book, when setting title override, then override is stored."""
        # Given: A view and book
        all_books = populated_library.get_all_books()
        view_service.create("my-view", definition={"select": "all"})

        # When: Setting title override
        override = view_service.set_override("my-view", all_books[0].id, title="Custom")

        # Then: Override should be stored
        assert override.title == "Custom"
        assert override.book_id == all_books[0].id

    def test_set_description_override(self, view_service, populated_library):
        """Given view and book, when setting description override, then override is stored."""
        # Given: A view and book
        all_books = populated_library.get_all_books()
        view_service.create("my-view", definition={"select": "all"})

        # When: Setting description override
        override = view_service.set_override(
            "my-view", all_books[0].id, description="Custom desc"
        )

        # Then: Override should be stored
        assert override.description == "Custom desc"

    def test_set_position_override(self, view_service, populated_library):
        """Given view and book, when setting position override, then override is stored."""
        # Given: A view and book
        all_books = populated_library.get_all_books()
        view_service.create("my-view", definition={"select": "all"})

        # When: Setting position override
        override = view_service.set_override("my-view", all_books[0].id, position=1)

        # Then: Override should be stored
        assert override.position == 1

    def test_set_multiple_overrides(self, view_service, populated_library):
        """Given view and book, when setting multiple overrides, then all are stored."""
        # Given: A view and book
        all_books = populated_library.get_all_books()
        view_service.create("my-view", definition={"select": "all"})

        # When: Setting multiple overrides
        override = view_service.set_override(
            "my-view",
            all_books[0].id,
            title="Custom",
            description="Custom desc",
            position=5,
        )

        # Then: All overrides should be stored
        assert override.title == "Custom"
        assert override.description == "Custom desc"
        assert override.position == 5

    def test_set_override_updates_existing(self, view_service, populated_library):
        """Given existing override, when setting again, then override is updated."""
        # Given: An existing override
        all_books = populated_library.get_all_books()
        view_service.create("my-view", definition={"select": "all"})
        view_service.set_override("my-view", all_books[0].id, title="First")

        # When: Setting again
        override = view_service.set_override("my-view", all_books[0].id, title="Second")

        # Then: Override should be updated
        assert override.title == "Second"

    def test_set_override_nonexistent_view_raises(self, view_service, populated_library):
        """Given nonexistent view, when setting override, then ValueError is raised."""
        # When/Then: Setting on nonexistent raises
        with pytest.raises(ValueError, match="not found"):
            view_service.set_override("nonexistent", 1, title="Test")

    def test_set_override_nonexistent_book_raises(self, view_service, populated_library):
        """Given nonexistent book, when setting override, then ValueError is raised."""
        # Given: A view
        view_service.create("my-view", definition={"select": "all"})

        # When/Then: Setting on nonexistent book raises
        with pytest.raises(ValueError, match="Book .* not found"):
            view_service.set_override("my-view", 99999, title="Test")


class TestViewServiceUnsetOverride:
    """Test unsetting overrides."""

    def test_unset_specific_field(self, view_service, populated_library):
        """Given override with multiple fields, when unsetting one, then only that is removed."""
        # Given: An override with multiple fields
        all_books = populated_library.get_all_books()
        view_service.create("my-view", definition={"select": "all"})
        view_service.set_override(
            "my-view", all_books[0].id, title="Custom", description="Desc"
        )

        # When: Unsetting title
        result = view_service.unset_override("my-view", all_books[0].id, field="title")

        # Then: Title should be None, description preserved
        assert result is True
        overrides = view_service.get_overrides("my-view")
        override = next(o for o in overrides if o.book_id == all_books[0].id)
        assert override.title is None
        assert override.description == "Desc"

    def test_unset_all_fields(self, view_service, populated_library):
        """Given override, when unsetting all fields, then override is deleted."""
        # Given: An override
        all_books = populated_library.get_all_books()
        view_service.create("my-view", definition={"select": "all"})
        view_service.set_override("my-view", all_books[0].id, title="Custom")

        # When: Unsetting all (no field specified)
        result = view_service.unset_override("my-view", all_books[0].id)

        # Then: Override should be deleted
        assert result is True
        overrides = view_service.get_overrides("my-view")
        assert not any(o.book_id == all_books[0].id for o in overrides)

    def test_unset_nonexistent_override(self, view_service, populated_library):
        """Given no override exists, when unsetting, then False is returned."""
        # Given: A view with no overrides
        all_books = populated_library.get_all_books()
        view_service.create("my-view", definition={"select": "all"})

        # When: Unsetting nonexistent
        result = view_service.unset_override("my-view", all_books[0].id)

        # Then: False should be returned
        assert result is False


class TestViewServiceGetOverrides:
    """Test getting overrides."""

    def test_get_overrides(self, view_service, populated_library):
        """Given view with overrides, when getting overrides, then all are returned."""
        # Given: A view with overrides
        all_books = populated_library.get_all_books()
        view_service.create("my-view", definition={"select": "all"})
        view_service.set_override("my-view", all_books[0].id, title="Custom 1")
        view_service.set_override("my-view", all_books[1].id, title="Custom 2")

        # When: Getting overrides
        overrides = view_service.get_overrides("my-view")

        # Then: All overrides should be returned
        assert len(overrides) == 2

    def test_get_overrides_empty(self, view_service, populated_library):
        """Given view with no overrides, when getting overrides, then empty list is returned."""
        # Given: A view with no overrides
        view_service.create("my-view", definition={"select": "all"})

        # When: Getting overrides
        overrides = view_service.get_overrides("my-view")

        # Then: Empty list should be returned
        assert overrides == []


# =============================================================================
# ViewService Import/Export Tests
# =============================================================================


class TestViewServiceExportYaml:
    """Test exporting views to YAML."""

    def test_export_user_view(self, view_service, populated_library):
        """Given user view, when exporting, then YAML includes definition."""
        # Given: A user view
        view_service.create(
            "my-view",
            definition={"select": {"filter": {"favorite": True}}},
            description="My favorites",
        )

        # When: Exporting
        yaml_content = view_service.export_yaml("my-view")

        # Then: YAML should include definition
        assert "my-view" in yaml_content
        assert "My favorites" in yaml_content
        assert "favorite" in yaml_content

    def test_export_with_overrides(self, view_service, populated_library):
        """Given view with overrides, when exporting, then overrides are included."""
        # Given: A view with overrides
        all_books = populated_library.get_all_books()
        view_service.create("my-view", definition={"select": "all"})
        view_service.set_override("my-view", all_books[0].id, title="Custom Title")

        # When: Exporting
        yaml_content = view_service.export_yaml("my-view")

        # Then: Overrides should be included
        assert "overrides" in yaml_content
        assert "Custom Title" in yaml_content

    def test_export_builtin_view(self, view_service):
        """Given built-in view, when exporting, then definition is exported."""
        # When: Exporting builtin
        yaml_content = view_service.export_yaml("favorites")

        # Then: Should include builtin definition
        assert "favorites" in yaml_content
        assert "builtin" in yaml_content


class TestViewServiceImportYaml:
    """Test importing views from YAML."""

    def test_import_new_view(self, view_service):
        """Given YAML content, when importing, then view is created."""
        # Given: YAML content
        yaml_content = """
name: imported-view
description: Imported view
select:
  filter:
    subject: Python
order:
  by: title
"""

        # When: Importing
        view = view_service.import_yaml(yaml_content)

        # Then: View should be created
        assert view.name == "imported-view"
        assert view.description == "Imported view"
        assert view.definition["select"]["filter"]["subject"] == "Python"

    def test_import_with_overwrite(self, view_service):
        """Given existing view, when importing with overwrite, then view is updated."""
        # Given: An existing view
        view_service.create("my-view", definition={"select": "none"})

        # And: YAML to replace it
        yaml_content = """
name: my-view
select: all
"""

        # When: Importing with overwrite
        view = view_service.import_yaml(yaml_content, overwrite=True)

        # Then: View should be updated
        assert view.definition["select"] == "all"

    def test_import_without_overwrite_raises(self, view_service):
        """Given existing view, when importing without overwrite, then ValueError is raised."""
        # Given: An existing view
        view_service.create("my-view", definition={"select": "none"})

        # And: YAML with same name
        yaml_content = """
name: my-view
select: all
"""

        # When/Then: Importing without overwrite raises
        with pytest.raises(ValueError, match="already exists"):
            view_service.import_yaml(yaml_content, overwrite=False)

    def test_import_builtin_name_raises(self, view_service):
        """Given YAML with builtin name, when importing, then ValueError is raised."""
        # Given: YAML with builtin name
        yaml_content = """
name: favorites
select: none
"""

        # When/Then: Importing builtin name raises
        with pytest.raises(ValueError, match="reserved name"):
            view_service.import_yaml(yaml_content)

    def test_import_without_name_raises(self, view_service):
        """Given YAML without name, when importing, then ValueError is raised."""
        # Given: YAML without name
        yaml_content = """
select: all
"""

        # When/Then: Importing raises
        with pytest.raises(ValueError, match="must include 'name'"):
            view_service.import_yaml(yaml_content)

    def test_import_with_overrides(self, view_service, populated_library):
        """Given YAML with overrides, when importing, then overrides are created."""
        # Given: YAML with overrides
        all_books = populated_library.get_all_books()
        book_id = all_books[0].id
        yaml_content = f"""
name: imported-view
select: all
overrides:
  {book_id}:
    title: Custom Title
    position: 1
"""

        # When: Importing
        view = view_service.import_yaml(yaml_content)

        # Then: Overrides should be created
        overrides = view_service.get_overrides("imported-view")
        assert len(overrides) == 1
        assert overrides[0].title == "Custom Title"
        assert overrides[0].position == 1


# =============================================================================
# Built-in Views Tests
# =============================================================================


class TestBuiltinViews:
    """Test built-in view definitions and behavior."""

    def test_favorites_builtin(self, view_service, populated_library):
        """Given favorites builtin, when evaluating, then favorited books are returned."""
        # When: Evaluating favorites
        result = view_service.evaluate("favorites")

        # Then: Should return favorited books
        assert len(result) == 2
        for tb in result:
            assert tb.book.personal.favorite is True

    def test_reading_builtin(self, view_service, populated_library):
        """Given reading builtin, when evaluating, then books being read are returned."""
        # When: Evaluating reading
        result = view_service.evaluate("reading")

        # Then: Should return books with reading status
        assert len(result) == 1
        assert result[0].book.personal.reading_status == "reading"

    def test_completed_builtin(self, view_service, populated_library):
        """Given completed builtin, when evaluating, then read books are returned."""
        # When: Evaluating completed
        result = view_service.evaluate("completed")

        # Then: Should return completed books
        assert len(result) == 1
        assert result[0].book.personal.reading_status == "read"

    def test_unread_builtin(self, view_service, populated_library):
        """Given unread builtin, when evaluating, then unread books are returned."""
        # When: Evaluating unread
        result = view_service.evaluate("unread")

        # Then: Should return unread books (including Spanish book with no status)
        assert len(result) >= 1
        for tb in result:
            if tb.book.personal:
                assert tb.book.personal.reading_status == "unread"

    def test_recent_builtin(self, view_service, populated_library):
        """Given recent builtin, when evaluating, then books are sorted by created_at desc."""
        # When: Evaluating recent
        result = view_service.evaluate("recent")

        # Then: Should be sorted by created_at descending
        assert len(result) == 4
        created_dates = [tb.book.created_at for tb in result]
        assert created_dates == sorted(created_dates, reverse=True)

    def test_all_builtin(self, view_service, populated_library):
        """Given all builtin, when evaluating, then all books are returned."""
        # When: Evaluating all
        result = view_service.evaluate("all")

        # Then: Should return all books
        assert len(result) == 4

    def test_top_rated_builtin(self, view_service, populated_library):
        """Given top-rated builtin, when evaluating, then highly rated books are returned."""
        # When: Evaluating top-rated
        result = view_service.evaluate("top-rated")

        # Then: Should return books with rating >= 4
        assert len(result) == 2
        for tb in result:
            assert tb.book.personal.rating >= 4

    def test_is_builtin_view(self):
        """Given builtin names, when checking is_builtin_view, then True is returned."""
        assert is_builtin_view("favorites") is True
        assert is_builtin_view("reading") is True
        assert is_builtin_view("nonexistent") is False

    def test_get_builtin_view(self):
        """Given builtin name, when getting definition, then definition is returned."""
        defn = get_builtin_view("favorites")
        assert defn is not None
        assert "select" in defn

        assert get_builtin_view("nonexistent") is None


# =============================================================================
# ViewService Evaluation Tests
# =============================================================================


class TestViewServiceEvaluate:
    """Test ViewService evaluate method."""

    def test_evaluate_user_view(self, view_service, populated_library):
        """Given user view, when evaluating, then correct books are returned."""
        # Given: A user view
        view_service.create(
            "python-books",
            definition={"select": {"filter": {"subject": "Python"}}},
        )

        # When: Evaluating
        result = view_service.evaluate("python-books")

        # Then: Python books should be returned
        assert len(result) == 2

    def test_evaluate_builtin_view(self, view_service, populated_library):
        """Given builtin view, when evaluating, then correct books are returned."""
        # When: Evaluating builtin
        result = view_service.evaluate("favorites")

        # Then: Favorites should be returned
        assert len(result) == 2

    def test_count_user_view(self, view_service, populated_library):
        """Given user view, when counting, then correct count is returned."""
        # Given: A user view
        view_service.create(
            "python-books",
            definition={"select": {"filter": {"subject": "Python"}}},
        )

        # When: Counting
        count = view_service.count("python-books")

        # Then: Correct count should be returned
        assert count == 2

    def test_books_returns_raw_books(self, view_service, populated_library):
        """Given view, when calling books(), then raw Book objects are returned."""
        # Given: A view
        view_service.create("my-view", definition={"select": "all"})

        # When: Getting books
        books = view_service.books("my-view")

        # Then: Raw Book objects should be returned
        assert len(books) == 4
        assert all(isinstance(b, Book) for b in books)


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Test error handling in Views DSL."""

    def test_invalid_selector_type_raises(self, evaluator):
        """Given invalid selector, when evaluating, then ValueError is raised."""
        # When/Then: Invalid selector raises
        with pytest.raises(ValueError, match="Invalid selector"):
            evaluator.evaluate({"select": 123})  # Not a valid selector

    def test_unknown_selector_key_raises(self, evaluator):
        """Given unknown selector key, when evaluating, then ValueError is raised."""
        # When/Then: Unknown key raises
        with pytest.raises(ValueError, match="Unknown selector type"):
            evaluator.evaluate({"select": {"unknown_key": True}})

    def test_intersect_with_one_selector_raises(self, evaluator):
        """Given intersect with < 2 selectors, when evaluating, then ValueError is raised."""
        # When/Then: Intersect with 1 selector raises
        with pytest.raises(ValueError, match="2\\+ selectors"):
            evaluator.evaluate({"select": {"intersect": [{"filter": {"favorite": True}}]}})

    def test_difference_with_wrong_count_raises(self, evaluator):
        """Given difference with != 2 selectors, when evaluating, then ValueError is raised."""
        # When/Then: Difference with 3 selectors raises
        with pytest.raises(ValueError, match="exactly 2 selectors"):
            evaluator.evaluate(
                {
                    "select": {
                        "difference": [
                            {"filter": {"favorite": True}},
                            {"filter": {"language": "en"}},
                            {"filter": {"language": "es"}},
                        ]
                    }
                }
            )


# =============================================================================
# ViewService Utility Methods Tests
# =============================================================================


class TestViewServiceDependencies:
    """Test view dependency tracking."""

    def test_dependencies_finds_referenced_views(self, view_service):
        """Given view with references, when getting dependencies, then they are returned."""
        # Given: Views with references
        view_service.create("base-view", definition={"select": "all"})
        view_service.create(
            "derived-view",
            definition={"select": {"view": "base-view"}},
        )

        # When: Getting dependencies
        deps = view_service.dependencies("derived-view")

        # Then: Referenced view should be in dependencies
        assert "base-view" in deps

    def test_dependents_finds_referencing_views(self, view_service):
        """Given view being referenced, when getting dependents, then they are returned."""
        # Given: Views with references
        view_service.create("base-view", definition={"select": "all"})
        view_service.create(
            "derived-view",
            definition={"select": {"view": "base-view"}},
        )

        # When: Getting dependents
        deps = view_service.dependents("base-view")

        # Then: Referencing view should be in dependents
        assert "derived-view" in deps


class TestViewServiceValidate:
    """Test view definition validation."""

    def test_validate_valid_definition(self, view_service):
        """Given valid definition, when validating, then True is returned."""
        # When: Validating valid definition
        is_valid, error = view_service.validate({"select": "all"})

        # Then: Should be valid
        assert is_valid is True
        assert error is None

    def test_validate_invalid_definition(self, view_service):
        """Given invalid definition, when validating, then False and error are returned."""
        # When: Validating invalid definition
        is_valid, error = view_service.validate({"select": {"unknown": True}})

        # Then: Should be invalid with error message
        assert is_valid is False
        assert error is not None


# =============================================================================
# Additional Edge Case Tests
# =============================================================================


class TestSelectorSingleId:
    """Test the single 'id' selector."""

    def test_single_id_selector(self, evaluator, populated_library):
        """Given single id selector, when evaluating, then that book is returned."""
        # Given: A specific book ID
        all_books = populated_library.get_all_books()
        target_id = all_books[0].id

        # When: Selecting by single id
        result = evaluator.evaluate({"select": {"id": target_id}})

        # Then: Should return that book
        assert len(result) == 1
        assert result[0].id == target_id

    def test_single_id_nonexistent(self, evaluator):
        """Given nonexistent single id, when evaluating, then empty result is returned."""
        # When: Selecting nonexistent ID
        result = evaluator.evaluate({"select": {"id": 99999}})

        # Then: Should return empty
        assert len(result) == 0


class TestOrderingEdgeCases:
    """Test additional ordering edge cases."""

    def test_order_by_position(self, evaluator, populated_library):
        """Given books with positions, when ordering by position, then sorted correctly."""
        # Given: Definitions with explicit positions
        all_books = populated_library.get_all_books()
        definition = {
            "select": {"ids": [all_books[0].id, all_books[1].id]},
            "transform": {
                "override": {
                    all_books[0].id: {"position": 2},
                    all_books[1].id: {"position": 1},
                }
            },
            "order": {"by": "position"},
        }

        # When: Ordering by position
        result = evaluator.evaluate(definition)

        # Then: Books should be ordered by position
        assert len(result) == 2
        assert result[0].id == all_books[1].id  # Position 1 first
        assert result[1].id == all_books[0].id  # Position 2 second

    def test_order_by_id(self, evaluator, populated_library):
        """Given books, when ordering by id, then sorted by id."""
        # When: Ordering by id
        result = evaluator.evaluate({"select": "all", "order": {"by": "id"}})

        # Then: Should be sorted by ID
        ids = [tb.id for tb in result]
        assert ids == sorted(ids)

    def test_order_by_created_at(self, evaluator, populated_library):
        """Given books, when ordering by created_at, then sorted correctly."""
        # When: Ordering by created_at
        result = evaluator.evaluate(
            {"select": "all", "order": {"by": "created_at"}}
        )

        # Then: Should be sorted by created_at
        dates = [tb.book.created_at for tb in result]
        assert dates == sorted(dates)

    def test_order_string_shorthand(self, evaluator, populated_library):
        """Given string ordering, when evaluating, then treated as field name."""
        # When: Using string shorthand for ordering
        result = evaluator.evaluate({"select": "all", "order": "title"})

        # Then: Should be sorted by title
        titles = [tb.title for tb in result]
        assert titles == sorted(titles, key=str.lower)


class TestFilterEdgeCases:
    """Test additional filter edge cases."""

    def test_filter_by_publisher(self, evaluator, temp_library):
        """Given books with publisher, when filtering by publisher, then matching books returned."""
        # Given: A book with a publisher
        test_file = temp_library.library_path / "book.txt"
        test_file.write_text("Test content")
        temp_library.add_book(
            test_file,
            metadata={
                "title": "Test Book",
                "creators": ["Author"],
                "publisher": "O'Reilly",
            },
            extract_text=False,
        )

        # When: Filtering by publisher
        evaluator = ViewEvaluator(temp_library.session)
        result = evaluator.evaluate(
            {"select": {"filter": {"publisher": "O'Reilly"}}}
        )

        # Then: Should return matching book
        assert len(result) == 1
        assert result[0].book.publisher == "O'Reilly"

    def test_filter_by_series(self, evaluator, temp_library):
        """Given books in a series, when filtering by series, then matching books returned."""
        # Given: A book in a series
        test_file = temp_library.library_path / "book.txt"
        test_file.write_text("Test content")
        book = temp_library.add_book(
            test_file,
            metadata={"title": "Test Book", "creators": ["Author"]},
            extract_text=False,
        )
        book.series = "Harry Potter"
        temp_library.session.commit()

        # When: Filtering by series
        evaluator = ViewEvaluator(temp_library.session)
        result = evaluator.evaluate({"select": {"filter": {"series": "Harry"}}})

        # Then: Should return matching book
        assert len(result) == 1
        assert result[0].book.series == "Harry Potter"

    def test_filter_by_format(self, evaluator, temp_library):
        """Given books with different formats, when filtering by format, then matching returned."""
        # Given: A PDF book
        test_file = temp_library.library_path / "book.pdf"
        test_file.write_text("PDF content")
        temp_library.add_book(
            test_file,
            metadata={"title": "PDF Book", "creators": ["Author"]},
            extract_text=False,
        )

        # When: Filtering by format
        evaluator = ViewEvaluator(temp_library.session)
        result = evaluator.evaluate({"select": {"filter": {"format": "pdf"}}})

        # Then: Should return matching book
        assert len(result) == 1
        assert result[0].title == "PDF Book"

    def test_filter_by_tag(self, evaluator, populated_library):
        """Given books with tags, when filtering by tag, then matching books returned."""
        # Given: A book with a tag
        from ebk.db.models import Tag

        all_books = populated_library.get_all_books()
        tag = Tag(name="important", path="important")
        populated_library.session.add(tag)
        all_books[0].tags.append(tag)
        populated_library.session.commit()

        # When: Filtering by tag
        evaluator = ViewEvaluator(populated_library.session)
        result = evaluator.evaluate({"select": {"filter": {"tag": "important"}}})

        # Then: Should return matching book
        assert len(result) == 1
        assert result[0].id == all_books[0].id


class TestComparisonEdgeCases:
    """Test additional comparison operator edge cases."""

    def test_eq_operator(self, evaluator, populated_library):
        """Given eq comparison, when filtering, then exact matches returned."""
        # When: Rating == 5
        result = evaluator.evaluate(
            {"select": {"filter": {"rating": {"eq": 5}}}}
        )

        # Then: Should return books with rating exactly 5
        assert len(result) == 1
        assert result[0].title == "Python Programming"

    def test_ne_operator(self, evaluator, populated_library):
        """Given ne comparison, when filtering, then non-matching returned."""
        # When: Rating != 5 (among rated books)
        result = evaluator.evaluate(
            {
                "select": {
                    "filter": {
                        "and": [{"rating": {"gte": 1}}, {"rating": {"ne": 5}}]
                    }
                }
            }
        )

        # Then: Should return books with rating not 5
        assert len(result) == 2  # Rating 4 and 3

    def test_in_operator_for_id(self, evaluator, populated_library):
        """Given in comparison for id, when filtering, then matching books returned."""
        # Given: Specific book IDs
        all_books = populated_library.get_all_books()
        target_ids = [all_books[0].id, all_books[2].id]

        # When: ID in list
        result = evaluator.evaluate(
            {"select": {"filter": {"id": {"in": target_ids}}}}
        )

        # Then: Should return those books
        assert len(result) == 2
        result_ids = {tb.id for tb in result}
        assert result_ids == set(target_ids)


class TestViewServiceCount:
    """Test ViewService count for built-in views."""

    def test_count_builtin_view(self, view_service, populated_library):
        """Given builtin view, when counting, then correct count is returned."""
        # When: Counting builtin view
        count = view_service.count("favorites")

        # Then: Correct count should be returned
        assert count == 2

    def test_count_nonexistent_raises(self, view_service):
        """Given nonexistent view, when counting, then ValueError is raised."""
        # When/Then: Counting nonexistent raises
        with pytest.raises(ValueError, match="not found"):
            view_service.count("nonexistent-view")
