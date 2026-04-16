"""Unit tests for book_memex.core.fts."""
import pytest

from book_memex.core.fts import safe_fts_query


class TestBasicEscaping:
    def test_single_word_wrapped_as_phrase(self):
        assert safe_fts_query("bayesian") == '"bayesian"'

    def test_multiple_words_wrapped_individually(self):
        # Each token becomes its own phrase; FTS5 AND-joins implicit phrases.
        assert safe_fts_query("bayesian inference") == '"bayesian" "inference"'

    def test_special_chars_inside_phrase(self):
        # Double-quote escaped by doubling (FTS5 convention).
        result = safe_fts_query('foo "bar" baz')
        # tokens: foo, "bar", baz -> "foo" """"bar"""" "baz" (FTS5 embeds " as "")
        # Tokenizer splits on quotes, so we get three phrases: foo, bar, baz
        assert '"foo"' in result
        assert '"bar"' in result
        assert '"baz"' in result

    def test_operator_keywords_escaped(self):
        # AND is an FTS5 operator; when wrapped as phrase, it is treated literally.
        result = safe_fts_query("foo AND bar")
        assert result == '"foo" "AND" "bar"'

    def test_wildcard_literal(self):
        assert safe_fts_query("foo*") == '"foo*"'

    def test_hyphen_literal(self):
        assert safe_fts_query("foo-bar") == '"foo-bar"'

    def test_empty_string_returns_empty(self):
        assert safe_fts_query("") == ""

    def test_whitespace_only_returns_empty(self):
        assert safe_fts_query("   \t\n  ") == ""


class TestAdvancedMode:
    def test_advanced_passes_raw(self):
        q = 'quantum NEAR(gravity, 5)'
        assert safe_fts_query(q, advanced=True) == q

    def test_advanced_preserves_operators(self):
        assert safe_fts_query("foo AND bar", advanced=True) == "foo AND bar"


class TestUnicode:
    def test_unicode_passed_through(self):
        assert safe_fts_query("über café") == '"über" "café"'
