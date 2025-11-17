"""
Comprehensive tests for ebk.search_parser module.

Tests the advanced search query parser's ability to parse field-specific searches,
boolean operators, comparison operators, and generate proper FTS queries and SQL conditions.
"""

import pytest
from ebk.search_parser import (
    SearchQueryParser,
    ParsedQuery,
    SearchToken,
    parse_search_query,
)


class TestSearchQueryParserBasicParsing:
    """Test basic query parsing functionality."""

    def test_parse_empty_query_returns_empty_parsed_query(self):
        # Given: An empty query string
        parser = SearchQueryParser()

        # When: Parsing the empty query
        result = parser.parse("")

        # Then: Returns empty ParsedQuery with no tokens or queries
        assert len(result.tokens) == 0
        assert result.fts_query is None
        assert len(result.filters) == 0
        assert not result.has_fts_terms()
        assert not result.has_filters()

    def test_parse_whitespace_only_query_returns_empty_parsed_query(self):
        # Given: A query with only whitespace
        parser = SearchQueryParser()

        # When: Parsing the whitespace query
        result = parser.parse("   \t\n   ")

        # Then: Returns empty ParsedQuery
        assert len(result.tokens) == 0
        assert not result.has_fts_terms()

    def test_parse_single_word_creates_text_token_and_fts_query(self):
        # Given: A simple single-word query
        parser = SearchQueryParser()

        # When: Parsing the query
        result = parser.parse("python")

        # Then: Creates text token and FTS query
        assert len(result.tokens) == 1
        assert result.tokens[0].type == "text"
        assert result.tokens[0].value == "python"
        assert result.tokens[0].negated is False
        assert result.fts_query == "python"
        assert result.has_fts_terms()

    def test_parse_multiple_words_creates_multiple_text_tokens(self):
        # Given: A multi-word query
        parser = SearchQueryParser()

        # When: Parsing the query
        result = parser.parse("machine learning")

        # Then: Creates separate text tokens for each word
        assert len(result.tokens) == 2
        assert result.tokens[0].value == "machine"
        assert result.tokens[1].value == "learning"
        assert result.fts_query == "machine learning"

    def test_parse_quoted_phrase_creates_phrase_token(self):
        # Given: A query with quoted phrase
        parser = SearchQueryParser()

        # When: Parsing the query
        result = parser.parse('"machine learning"')

        # Then: Creates single phrase token with quotes preserved in FTS
        assert len(result.tokens) == 1
        assert result.tokens[0].type == "phrase"
        assert result.tokens[0].value == "machine learning"
        assert result.fts_query == '"machine learning"'

    def test_parse_mixed_words_and_phrases(self):
        # Given: A query mixing words and phrases
        parser = SearchQueryParser()

        # When: Parsing the query
        result = parser.parse('introduction to "machine learning" basics')

        # Then: Correctly separates words and phrases
        assert len(result.tokens) == 4
        assert result.tokens[0].value == "introduction"
        assert result.tokens[1].value == "to"
        assert result.tokens[2].type == "phrase"
        assert result.tokens[2].value == "machine learning"
        assert result.tokens[3].value == "basics"


class TestSearchQueryParserFieldSearches:
    """Test field-specific search parsing."""

    def test_parse_simple_field_search_creates_field_token(self):
        # Given: A field-specific search query
        parser = SearchQueryParser()

        # When: Parsing field:value syntax
        result = parser.parse("title:Python")

        # Then: Creates field token with correct attributes
        assert len(result.tokens) == 1
        assert result.tokens[0].type == "field"
        assert result.tokens[0].field == "title"
        assert result.tokens[0].value == "Python"
        assert result.tokens[0].operator == "="

    def test_parse_field_with_quoted_value(self):
        # Given: A field search with quoted value
        parser = SearchQueryParser()

        # When: Parsing field:"quoted value" syntax
        result = parser.parse('author:"Donald Knuth"')

        # Then: Correctly extracts quoted value without quotes
        assert result.tokens[0].field == "author"
        assert result.tokens[0].value == "Donald Knuth"

    def test_parse_multiple_field_searches(self):
        # Given: Multiple field searches in one query
        parser = SearchQueryParser()

        # When: Parsing multiple field:value pairs
        result = parser.parse("title:Python format:pdf language:en")

        # Then: Creates separate field tokens for each
        assert len(result.tokens) == 3
        assert result.tokens[0].field == "title"
        assert result.tokens[1].field == "format"
        assert result.tokens[2].field == "language"

    def test_field_aliases_are_normalized(self):
        # Given: Field searches using aliases
        parser = SearchQueryParser()

        # When: Parsing queries with field aliases
        tag_result = parser.parse("tag:programming")
        tags_result = parser.parse("tags:python")
        lang_result = parser.parse("lang:en")
        fmt_result = parser.parse("fmt:pdf")

        # Then: Aliases are mapped to canonical field names
        assert tag_result.tokens[0].field == "subject"
        assert tags_result.tokens[0].field == "subject"
        assert lang_result.tokens[0].field == "language"
        assert fmt_result.tokens[0].field == "format"

    def test_fts_field_search_generates_column_specific_fts_query(self):
        # Given: A search on an FTS field
        parser = SearchQueryParser()

        # When: Parsing title field search
        result = parser.parse("title:Python")

        # Then: Generates FTS query with column prefix
        assert result.fts_query == "title:Python"

    def test_text_field_search_maps_to_extracted_text_column(self):
        # Given: A search on the 'text' field
        parser = SearchQueryParser()

        # When: Parsing text field search
        result = parser.parse("text:algorithm")

        # Then: Maps to extracted_text column in FTS query
        assert result.fts_query == "extracted_text:algorithm"

    def test_author_field_search_adds_to_filters_not_fts(self):
        # Given: An author field search
        parser = SearchQueryParser()

        # When: Parsing author field search
        result = parser.parse("author:Knuth")

        # Then: Adds to filters instead of FTS query
        assert "authors" in result.filters
        assert result.filters["authors"] == [("Knuth", False)]
        assert result.fts_query is None

    def test_subject_field_search_adds_to_filters_not_fts(self):
        # Given: A subject/tag field search
        parser = SearchQueryParser()

        # When: Parsing subject field search
        result = parser.parse("subject:programming")

        # Then: Adds to filters for many-to-many join handling
        assert "subjects" in result.filters
        assert result.filters["subjects"] == [("programming", False)]


class TestSearchQueryParserBooleanOperators:
    """Test boolean logic parsing (AND, OR, NOT)."""

    def test_parse_explicit_or_operator_creates_operator_token(self):
        # Given: A query with explicit OR operator
        parser = SearchQueryParser()

        # When: Parsing OR query
        result = parser.parse("python OR java")

        # Then: Creates operator token between terms
        assert len(result.tokens) == 3
        assert result.tokens[0].value == "python"
        assert result.tokens[1].type == "operator"
        assert result.tokens[1].value == "OR"
        assert result.tokens[2].value == "java"

    def test_or_operator_is_case_insensitive(self):
        # Given: OR operator in various cases
        parser = SearchQueryParser()

        # When: Parsing with different cases
        upper_result = parser.parse("python OR java")
        lower_result = parser.parse("python or java")
        mixed_result = parser.parse("python Or java")

        # Then: All are recognized as OR operators
        assert upper_result.tokens[1].value == "OR"
        assert lower_result.tokens[1].value == "OR"
        assert mixed_result.tokens[1].value == "OR"

    def test_or_operator_in_fts_query(self):
        # Given: A query with OR between text terms
        parser = SearchQueryParser()

        # When: Parsing OR query
        result = parser.parse("python OR java")

        # Then: FTS query includes OR operator
        assert result.fts_query == "python OR java"

    def test_parse_explicit_and_operator_creates_operator_token(self):
        # Given: A query with explicit AND operator
        parser = SearchQueryParser()

        # When: Parsing AND query
        result = parser.parse("python AND programming")

        # Then: Creates operator token
        assert len(result.tokens) == 3
        assert result.tokens[1].type == "operator"
        assert result.tokens[1].value == "AND"

    def test_and_operator_is_case_insensitive(self):
        # Given: AND operator in various cases
        parser = SearchQueryParser()

        # When: Parsing with different cases
        result = parser.parse("python and programming")

        # Then: Recognized as AND operator
        assert result.tokens[1].value == "AND"

    def test_parse_not_operator_with_prefix_negates_token(self):
        # Given: A query with NOT keyword
        parser = SearchQueryParser()

        # When: Parsing NOT query
        result = parser.parse("NOT java")

        # Then: Next token is negated
        assert len(result.tokens) == 1
        assert result.tokens[0].value == "java"
        assert result.tokens[0].negated is True

    def test_parse_dash_prefix_negates_token(self):
        # Given: A query with dash prefix for negation
        parser = SearchQueryParser()

        # When: Parsing -term syntax
        result = parser.parse("-java")

        # Then: Token is negated
        assert result.tokens[0].value == "java"
        assert result.tokens[0].negated is True

    def test_negated_text_appears_in_fts_query(self):
        # Given: A negated term
        parser = SearchQueryParser()

        # When: Parsing negated query
        result = parser.parse("python NOT java")

        # Then: FTS query includes NOT operator
        assert "NOT java" in result.fts_query

    def test_negated_field_search_marks_token_as_negated(self):
        # Given: A negated field search
        parser = SearchQueryParser()

        # When: Parsing NOT field:value
        result = parser.parse("NOT title:Java")

        # Then: Field token is negated
        assert result.tokens[0].type == "field"
        assert result.tokens[0].negated is True

    def test_complex_boolean_combination(self):
        # Given: A complex query with multiple boolean operators
        parser = SearchQueryParser()

        # When: Parsing complex boolean query
        result = parser.parse("python OR java NOT scala")

        # Then: Correctly parses all operators and negations
        assert result.tokens[0].value == "python"
        assert result.tokens[1].value == "OR"
        assert result.tokens[2].value == "java"
        assert result.tokens[3].value == "scala"
        assert result.tokens[3].negated is True


class TestSearchQueryParserComparisonOperators:
    """Test numeric comparison operators and ranges."""

    def test_parse_numeric_field_with_equality_operator(self):
        # Given: A numeric field with equals operator
        parser = SearchQueryParser()

        # When: Parsing rating:=5
        result = parser.parse("rating:=5")

        # Then: Creates filter with equals comparison
        assert "rating" in result.filters
        assert result.filters["rating"] == {"=": 5.0}

    def test_parse_numeric_field_without_explicit_operator_defaults_to_equals(self):
        # Given: A numeric field without operator
        parser = SearchQueryParser()

        # When: Parsing rating:5
        result = parser.parse("rating:5")

        # Then: Defaults to equals operator
        assert result.filters["rating"] == {"=": 5.0}

    def test_parse_numeric_field_with_greater_than_operator(self):
        # Given: A numeric field with > operator
        parser = SearchQueryParser()

        # When: Parsing rating:>3
        result = parser.parse("rating:>3")

        # Then: Creates filter with > comparison
        assert result.filters["rating"] == {">": 3.0}

    def test_parse_numeric_field_with_greater_equal_operator(self):
        # Given: A numeric field with >= operator
        parser = SearchQueryParser()

        # When: Parsing rating:>=4
        result = parser.parse("rating:>=4")

        # Then: Creates filter with >= comparison
        assert result.filters["rating"] == {">=": 4.0}

    def test_parse_numeric_field_with_less_than_operator(self):
        # Given: A numeric field with < operator
        parser = SearchQueryParser()

        # When: Parsing rating:<3
        result = parser.parse("rating:<3")

        # Then: Creates filter with < comparison
        assert result.filters["rating"] == {"<": 3.0}

    def test_parse_numeric_field_with_less_equal_operator(self):
        # Given: A numeric field with <= operator
        parser = SearchQueryParser()

        # When: Parsing rating:<=4
        result = parser.parse("rating:<=4")

        # Then: Creates filter with <= comparison
        assert result.filters["rating"] == {"<=": 4.0}

    def test_parse_numeric_range_with_dash(self):
        # Given: A range query using dash syntax
        parser = SearchQueryParser()

        # When: Parsing rating:3-5
        result = parser.parse("rating:3-5")

        # Then: Creates filter with both >= and <= bounds
        assert result.filters["rating"] == {">=": 3.0, "<=": 5.0}

    def test_parse_decimal_values_in_numeric_comparisons(self):
        # Given: A numeric comparison with decimal values
        parser = SearchQueryParser()

        # When: Parsing rating:4.5
        result = parser.parse("rating:4.5")

        # Then: Correctly parses decimal value
        assert result.filters["rating"] == {"=": 4.5}

    def test_invalid_numeric_value_returns_empty_filter(self):
        # Given: A numeric field with invalid value
        parser = SearchQueryParser()

        # When: Parsing rating:invalid
        result = parser.parse("rating:invalid")

        # Then: Returns empty filter for that field
        assert result.filters["rating"] == {}


class TestSearchQueryParserBooleanFields:
    """Test boolean field parsing."""

    def test_parse_boolean_field_with_true_value(self):
        # Given: A boolean field with true value
        parser = SearchQueryParser()

        # When: Parsing favorite:true
        result = parser.parse("favorite:true")

        # Then: Converts to boolean True
        assert result.filters["favorite"] is True

    def test_parse_boolean_field_with_yes_value(self):
        # Given: A boolean field with 'yes' value
        parser = SearchQueryParser()

        # When: Parsing favorite:yes
        result = parser.parse("favorite:yes")

        # Then: Converts to boolean True
        assert result.filters["favorite"] is True

    def test_parse_boolean_field_with_one_value(self):
        # Given: A boolean field with '1' value
        parser = SearchQueryParser()

        # When: Parsing favorite:1
        result = parser.parse("favorite:1")

        # Then: Converts to boolean True
        assert result.filters["favorite"] is True

    def test_parse_boolean_field_with_false_value(self):
        # Given: A boolean field with false value
        parser = SearchQueryParser()

        # When: Parsing favorite:false
        result = parser.parse("favorite:false")

        # Then: Converts to boolean False
        assert result.filters["favorite"] is False

    def test_boolean_field_is_case_insensitive(self):
        # Given: Boolean values in various cases
        parser = SearchQueryParser()

        # When: Parsing with different cases
        upper_result = parser.parse("favorite:TRUE")
        mixed_result = parser.parse("favorite:Yes")

        # Then: All are recognized as True
        assert upper_result.filters["favorite"] is True
        assert mixed_result.filters["favorite"] is True


class TestSearchQueryParserExactFilters:
    """Test exact match filter fields."""

    def test_parse_language_field_creates_exact_filter(self):
        # Given: A language field search
        parser = SearchQueryParser()

        # When: Parsing language:en
        result = parser.parse("language:en")

        # Then: Creates exact match filter
        assert result.filters["language"] == "en"

    def test_parse_format_field_creates_exact_filter(self):
        # Given: A format field search
        parser = SearchQueryParser()

        # When: Parsing format:pdf
        result = parser.parse("format:pdf")

        # Then: Creates exact match filter
        assert result.filters["format"] == "pdf"

    def test_parse_series_field_creates_filter(self):
        # Given: A series field search
        parser = SearchQueryParser()

        # When: Parsing series:TAOCP
        result = parser.parse("series:TAOCP")

        # Then: Creates filter for series
        assert result.filters["series"] == "TAOCP"

    def test_parse_publisher_field_creates_filter(self):
        # Given: A publisher field search
        parser = SearchQueryParser()

        # When: Parsing publisher:Manning
        result = parser.parse("publisher:Manning")

        # Then: Creates filter for publisher
        assert result.filters["publisher"] == "Manning"

    def test_parse_status_field_creates_filter(self):
        # Given: A reading status field search
        parser = SearchQueryParser()

        # When: Parsing status:reading
        result = parser.parse("status:reading")

        # Then: Creates filter for status
        assert result.filters["status"] == "reading"


class TestSearchQueryParserSQLGeneration:
    """Test SQL WHERE clause generation from parsed queries."""

    def test_to_sql_conditions_with_empty_query_returns_empty_clause(self):
        # Given: An empty parsed query
        parser = SearchQueryParser()
        parsed = parser.parse("")

        # When: Generating SQL conditions
        where_clause, params = parser.to_sql_conditions(parsed)

        # Then: Returns empty clause and no params
        assert where_clause == ""
        assert params == {}

    def test_to_sql_conditions_for_language_filter(self):
        # Given: A language filter
        parser = SearchQueryParser()
        parsed = parser.parse("language:en")

        # When: Generating SQL conditions
        where_clause, params = parser.to_sql_conditions(parsed)

        # Then: Generates language equality condition
        assert "books.language = :language" in where_clause
        assert params["language"] == "en"

    def test_to_sql_conditions_for_format_filter(self):
        # Given: A format filter
        parser = SearchQueryParser()
        parsed = parser.parse("format:pdf")

        # When: Generating SQL conditions
        where_clause, params = parser.to_sql_conditions(parsed)

        # Then: Generates EXISTS subquery for files table
        assert "EXISTS (SELECT 1 FROM files f" in where_clause
        assert "LOWER(f.format) = :format" in where_clause
        assert params["format"] == "pdf"

    def test_to_sql_conditions_for_series_filter_uses_like(self):
        # Given: A series filter
        parser = SearchQueryParser()
        parsed = parser.parse("series:TAOCP")

        # When: Generating SQL conditions
        where_clause, params = parser.to_sql_conditions(parsed)

        # Then: Generates LIKE condition for partial matching
        assert "books.series LIKE :series" in where_clause
        assert params["series"] == "%TAOCP%"

    def test_to_sql_conditions_for_publisher_filter_uses_like(self):
        # Given: A publisher filter
        parser = SearchQueryParser()
        parsed = parser.parse("publisher:Manning")

        # When: Generating SQL conditions
        where_clause, params = parser.to_sql_conditions(parsed)

        # Then: Generates LIKE condition
        assert "books.publisher LIKE :publisher" in where_clause
        assert params["publisher"] == "%Manning%"

    def test_to_sql_conditions_for_author_filter_uses_exists_subquery(self):
        # Given: An author filter
        parser = SearchQueryParser()
        parsed = parser.parse("author:Knuth")

        # When: Generating SQL conditions
        where_clause, params = parser.to_sql_conditions(parsed)

        # Then: Generates EXISTS subquery for many-to-many join
        assert "EXISTS (SELECT 1 FROM book_authors ba" in where_clause
        assert "JOIN authors a ON ba.author_id = a.id" in where_clause
        assert "a.name LIKE :author_0" in where_clause
        assert params["author_0"] == "%Knuth%"

    def test_to_sql_conditions_for_negated_author_filter(self):
        # Given: A negated author filter
        parser = SearchQueryParser()
        parsed = parser.parse("NOT author:Java")

        # When: Generating SQL conditions
        where_clause, params = parser.to_sql_conditions(parsed)

        # Then: Generates NOT EXISTS subquery
        assert "NOT EXISTS (SELECT 1 FROM book_authors ba" in where_clause
        assert params["author_0"] == "%Java%"

    def test_to_sql_conditions_for_subject_filter_uses_exists_subquery(self):
        # Given: A subject filter
        parser = SearchQueryParser()
        parsed = parser.parse("subject:programming")

        # When: Generating SQL conditions
        where_clause, params = parser.to_sql_conditions(parsed)

        # Then: Generates EXISTS subquery for many-to-many join
        assert "EXISTS (SELECT 1 FROM book_subjects bs" in where_clause
        assert "JOIN subjects s ON bs.subject_id = s.id" in where_clause
        assert "s.name LIKE :subject_0" in where_clause
        assert params["subject_0"] == "%programming%"

    def test_to_sql_conditions_for_negated_subject_filter(self):
        # Given: A negated subject filter
        parser = SearchQueryParser()
        parsed = parser.parse("-tag:java")

        # When: Generating SQL conditions
        where_clause, params = parser.to_sql_conditions(parsed)

        # Then: Generates NOT EXISTS subquery
        assert "NOT EXISTS (SELECT 1 FROM book_subjects bs" in where_clause

    def test_to_sql_conditions_for_rating_equals(self):
        # Given: A rating equals filter
        parser = SearchQueryParser()
        parsed = parser.parse("rating:5")

        # When: Generating SQL conditions
        where_clause, params = parser.to_sql_conditions(parsed)

        # Then: Generates EXISTS subquery for personal_metadata
        assert "EXISTS (SELECT 1 FROM personal_metadata pm" in where_clause
        assert "pm.rating = :rating_eq" in where_clause
        assert params["rating_eq"] == 5.0

    def test_to_sql_conditions_for_rating_greater_than(self):
        # Given: A rating > filter
        parser = SearchQueryParser()
        parsed = parser.parse("rating:>3")

        # When: Generating SQL conditions
        where_clause, params = parser.to_sql_conditions(parsed)

        # Then: Generates correct comparison operator
        assert "pm.rating > :rating_gt" in where_clause
        assert params["rating_gt"] == 3.0

    def test_to_sql_conditions_for_rating_greater_equal(self):
        # Given: A rating >= filter
        parser = SearchQueryParser()
        parsed = parser.parse("rating:>=4")

        # When: Generating SQL conditions
        where_clause, params = parser.to_sql_conditions(parsed)

        # Then: Generates correct comparison operator
        assert "pm.rating >= :rating_gteq" in where_clause
        assert params["rating_gteq"] == 4.0

    def test_to_sql_conditions_for_rating_range(self):
        # Given: A rating range filter
        parser = SearchQueryParser()
        parsed = parser.parse("rating:3-5")

        # When: Generating SQL conditions
        where_clause, params = parser.to_sql_conditions(parsed)

        # Then: Generates both >= and <= conditions
        assert "pm.rating >= :rating_gteq" in where_clause
        assert "pm.rating <= :rating_lteq" in where_clause
        assert params["rating_gteq"] == 3.0
        assert params["rating_lteq"] == 5.0

    def test_to_sql_conditions_for_favorite_filter(self):
        # Given: A favorite filter
        parser = SearchQueryParser()
        parsed = parser.parse("favorite:true")

        # When: Generating SQL conditions
        where_clause, params = parser.to_sql_conditions(parsed)

        # Then: Generates EXISTS subquery for personal_metadata
        assert "EXISTS (SELECT 1 FROM personal_metadata pm" in where_clause
        assert "pm.favorite = :favorite" in where_clause
        assert params["favorite"] is True

    def test_to_sql_conditions_for_status_filter(self):
        # Given: A reading status filter
        parser = SearchQueryParser()
        parsed = parser.parse("status:reading")

        # When: Generating SQL conditions
        where_clause, params = parser.to_sql_conditions(parsed)

        # Then: Generates EXISTS subquery for personal_metadata
        assert "EXISTS (SELECT 1 FROM personal_metadata pm" in where_clause
        assert "pm.reading_status = :status" in where_clause
        assert params["status"] == "reading"

    def test_to_sql_conditions_combines_multiple_filters_with_and(self):
        # Given: Multiple filters in one query
        parser = SearchQueryParser()
        parsed = parser.parse("language:en format:pdf rating:>=4")

        # When: Generating SQL conditions
        where_clause, params = parser.to_sql_conditions(parsed)

        # Then: Combines conditions with AND
        assert " AND " in where_clause
        assert "books.language = :language" in where_clause
        assert "LOWER(f.format) = :format" in where_clause
        assert "pm.rating >= :rating_gteq" in where_clause
        assert len(params) == 3

    def test_to_sql_conditions_uses_parameterized_queries(self):
        # Given: A query with potentially dangerous input (single-quoted to prevent field parsing)
        parser = SearchQueryParser()
        parsed = parser.parse('language:"DROP TABLE books"')

        # When: Generating SQL conditions
        where_clause, params = parser.to_sql_conditions(parsed)

        # Then: Uses parameterized query to prevent SQL injection
        assert ":language" in where_clause
        assert params["language"] == "DROP TABLE books"
        assert "DROP TABLE books" not in where_clause  # Only appears in params, not raw SQL

    def test_to_sql_conditions_for_multiple_authors(self):
        # Given: Multiple author filters
        parser = SearchQueryParser()
        parsed = parser.parse("author:Knuth author:Dijkstra")

        # When: Generating SQL conditions
        where_clause, params = parser.to_sql_conditions(parsed)

        # Then: Generates separate EXISTS clauses with unique param names
        assert "author_0" in params
        assert "author_1" in params
        assert params["author_0"] == "%Knuth%"
        assert params["author_1"] == "%Dijkstra%"

    def test_to_sql_conditions_for_multiple_subjects(self):
        # Given: Multiple subject filters
        parser = SearchQueryParser()
        parsed = parser.parse("tag:python tag:programming")

        # When: Generating SQL conditions
        where_clause, params = parser.to_sql_conditions(parsed)

        # Then: Generates separate EXISTS clauses with unique param names
        assert "subject_0" in params
        assert "subject_1" in params


class TestSearchQueryParserIntegration:
    """Integration tests for complex real-world queries."""

    def test_complex_query_with_field_filters_and_text_search(self):
        # Given: A complex query mixing fields and text search
        parser = SearchQueryParser()

        # When: Parsing complex query
        result = parser.parse('title:Python format:pdf "machine learning" rating:>=4')

        # Then: Correctly separates FTS and filter components
        assert result.fts_query == 'title:Python "machine learning"'
        assert result.filters["format"] == "pdf"
        assert result.filters["rating"] == {">=": 4.0}
        assert result.has_fts_terms()
        assert result.has_filters()

    def test_complex_query_with_boolean_operators_and_negation(self):
        # Given: A complex query with boolean logic
        parser = SearchQueryParser()

        # When: Parsing query with OR and NOT
        result = parser.parse("python OR java NOT scala")

        # Then: Correctly builds FTS query with operators
        assert "python OR java" in result.fts_query
        assert "NOT scala" in result.fts_query

    def test_complex_query_with_multiple_field_types(self):
        # Given: A query using various field types
        parser = SearchQueryParser()

        # When: Parsing multi-field query
        result = parser.parse(
            "author:Knuth series:TAOCP language:en rating:5 favorite:true"
        )

        # Then: Correctly categorizes all filters
        assert "authors" in result.filters
        assert result.filters["series"] == "TAOCP"
        assert result.filters["language"] == "en"
        assert result.filters["rating"] == {"=": 5.0}
        assert result.filters["favorite"] is True

    def test_real_world_query_example_1(self):
        # Given: A realistic user query
        parser = SearchQueryParser()

        # When: Parsing "find Python books in PDF format, rated 4 or higher"
        result = parser.parse("title:Python format:pdf rating:>=4")

        # Then: Produces correct FTS and filters
        assert result.fts_query == "title:Python"
        assert result.filters["format"] == "pdf"
        assert result.filters["rating"][">="] == 4.0

    def test_real_world_query_example_2(self):
        # Given: A realistic search for specific author without Java
        parser = SearchQueryParser()

        # When: Parsing query
        result = parser.parse('author:"Donald Knuth" NOT java')

        # Then: Correctly handles author filter and negated text
        assert "authors" in result.filters
        assert result.filters["authors"][0] == ("Donald Knuth", False)
        assert "NOT java" in result.fts_query

    def test_real_world_query_example_3(self):
        # Given: A search combining tags and text
        parser = SearchQueryParser()

        # When: Parsing tag-based search with OR
        result = parser.parse("tag:programming tag:algorithms rating:4-5")

        # Then: Correctly processes multiple subjects and range
        assert len(result.filters["subjects"]) == 2
        assert result.filters["rating"] == {">=": 4.0, "<=": 5.0}


class TestSearchQueryParserEdgeCases:
    """Test edge cases and error handling."""

    def test_parse_query_with_colon_but_no_value(self):
        # Given: A malformed field query with no value
        parser = SearchQueryParser()

        # When: Parsing field: (no value)
        result = parser.parse("title:")

        # Then: Handles gracefully without errors
        # The regex won't match, so "title:" is treated as text
        assert len(result.tokens) > 0

    def test_parse_query_with_unclosed_quote(self):
        # Given: A query with unclosed quote
        parser = SearchQueryParser()

        # When: Parsing unclosed quote
        result = parser.parse('"machine learning')

        # Then: Handles gracefully - treats as text since quote not closed
        assert len(result.tokens) > 0

    def test_parse_query_with_special_characters(self):
        # Given: A query with special characters
        parser = SearchQueryParser()

        # When: Parsing query with special chars
        result = parser.parse("C++ title:C#")

        # Then: Handles special characters in text
        assert result.tokens[0].value == "C++"

    def test_parse_query_with_multiple_consecutive_operators(self):
        # Given: A query with consecutive operators
        parser = SearchQueryParser()

        # When: Parsing "python OR OR java"
        result = parser.parse("python OR OR java")

        # Then: Handles multiple operators
        assert result.tokens[1].value == "OR"
        assert result.tokens[2].value == "OR"

    def test_parse_query_with_only_operators(self):
        # Given: A query with only operators
        parser = SearchQueryParser()

        # When: Parsing "OR AND NOT"
        result = parser.parse("OR AND NOT")

        # Then: Parses operators without crashing
        assert len(result.tokens) > 0

    def test_parse_field_with_empty_quotes(self):
        # Given: A field with empty quoted value
        parser = SearchQueryParser()

        # When: Parsing title:""
        result = parser.parse('title:""')

        # Then: Creates field token with empty value
        assert result.tokens[0].field == "title"
        assert result.tokens[0].value == ""

    def test_parse_very_long_query(self):
        # Given: A very long query string
        parser = SearchQueryParser()
        long_query = " ".join(["python"] * 100)

        # When: Parsing long query
        result = parser.parse(long_query)

        # Then: Handles without performance issues
        assert len(result.tokens) == 100

    def test_parse_query_with_unicode_characters(self):
        # Given: A query with unicode characters
        parser = SearchQueryParser()

        # When: Parsing unicode query
        result = parser.parse("title:Müller author:Björk")

        # Then: Correctly handles unicode
        assert result.tokens[0].value == "Müller"
        assert result.filters["authors"][0][0] == "Björk"

    def test_parse_unknown_field_name_treated_as_text(self):
        # Given: A query with unknown field name
        parser = SearchQueryParser()

        # When: Parsing unknownfield:value
        result = parser.parse("unknownfield:value")

        # Then: Treats as field token (unknown fields not filtered out in parsing)
        # The Library layer would handle unknown fields
        assert result.tokens[0].type == "field"
        assert result.tokens[0].field == "unknownfield"


class TestConvenienceFunction:
    """Test the convenience parse_search_query function."""

    def test_parse_search_query_function_returns_parsed_query(self):
        # Given: A search query string
        query = "python programming"

        # When: Using convenience function
        result = parse_search_query(query)

        # Then: Returns ParsedQuery instance
        assert isinstance(result, ParsedQuery)
        assert result.fts_query == "python programming"

    def test_parse_search_query_function_handles_complex_query(self):
        # Given: A complex query
        query = 'author:Knuth title:Python rating:>=4 "machine learning"'

        # When: Using convenience function
        result = parse_search_query(query)

        # Then: Correctly parses all components
        assert result.has_fts_terms()
        assert result.has_filters()
        assert len(result.filters) == 2


class TestParsedQueryHelperMethods:
    """Test ParsedQuery helper methods."""

    def test_has_fts_terms_returns_true_when_fts_query_exists(self):
        # Given: A parsed query with FTS terms
        parsed = ParsedQuery(tokens=[], fts_query="python")

        # When: Checking for FTS terms
        result = parsed.has_fts_terms()

        # Then: Returns True
        assert result is True

    def test_has_fts_terms_returns_false_when_no_fts_query(self):
        # Given: A parsed query without FTS terms
        parsed = ParsedQuery(tokens=[], fts_query=None)

        # When: Checking for FTS terms
        result = parsed.has_fts_terms()

        # Then: Returns False
        assert result is False

    def test_has_filters_returns_true_when_filters_exist(self):
        # Given: A parsed query with filters
        parsed = ParsedQuery(tokens=[], filters={"language": "en"})

        # When: Checking for filters
        result = parsed.has_filters()

        # Then: Returns True
        assert result is True

    def test_has_filters_returns_false_when_no_filters(self):
        # Given: A parsed query without filters
        parsed = ParsedQuery(tokens=[], filters={})

        # When: Checking for filters
        result = parsed.has_filters()

        # Then: Returns False
        assert result is False
