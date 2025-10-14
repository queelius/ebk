"""
Advanced search query parser for ebk.

Supports field-specific searches, boolean logic, and comparison operators.

Examples:
    title:Python rating:>=4 format:pdf
    author:"Donald Knuth" series:TAOCP
    tag:programming favorite:true NOT java
    "machine learning" OR "deep learning"
"""

import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class SearchToken:
    """Represents a single search token."""
    type: str  # 'field', 'text', 'operator', 'phrase'
    value: str
    field: Optional[str] = None
    operator: Optional[str] = None  # For comparisons: '=', '>', '>=', '<', '<=', '-' (range)
    negated: bool = False


@dataclass
class ParsedQuery:
    """Parsed search query with structured tokens."""
    tokens: List[SearchToken] = field(default_factory=list)
    fts_query: Optional[str] = None  # Combined FTS query for title/description/text
    filters: Dict[str, Any] = field(default_factory=dict)  # Exact filters (language, format, etc.)

    def has_fts_terms(self) -> bool:
        """Check if query has full-text search terms."""
        return bool(self.fts_query)

    def has_filters(self) -> bool:
        """Check if query has filter conditions."""
        return bool(self.filters)


class SearchQueryParser:
    """
    Parser for advanced search queries with field specifiers and boolean logic.

    Syntax:
        - Field searches: field:value (e.g., title:Python, author:Knuth)
        - Phrases: "quoted text" (e.g., "machine learning")
        - Boolean: AND (implicit), OR (explicit), NOT/-prefix (negation)
        - Comparisons: rating:>=4, rating:3-5
        - Multiple fields: title:python format:pdf (implicit AND)

    Field mappings:
        - title: Book title
        - author: Author names
        - tag/subject: Subjects/tags
        - description: Book description
        - series: Series name
        - publisher: Publisher name
        - language: Language code (exact match)
        - format: File format (exact match)
        - rating: Personal rating (numeric comparison)
        - favorite: Favorite status (boolean)
        - status: Reading status (exact match)
    """

    # Field aliases
    FIELD_ALIASES = {
        'tag': 'subject',
        'tags': 'subject',
        'subjects': 'subject',
        'lang': 'language',
        'fmt': 'format',
        'type': 'format',
    }

    # Fields that support FTS (full-text search)
    FTS_FIELDS = {'title', 'description', 'text', 'author', 'subject'}

    # Fields that are exact filters (not FTS)
    FILTER_FIELDS = {'language', 'format', 'series', 'publisher', 'rating', 'favorite', 'status'}

    # Numeric fields that support comparison operators
    NUMERIC_FIELDS = {'rating'}

    # Boolean fields
    BOOLEAN_FIELDS = {'favorite'}

    def __init__(self):
        # Regex patterns
        self.field_pattern = re.compile(r'(\w+):(>=|<=|>|<|=)?("[^"]+"|[\S]+)')
        self.phrase_pattern = re.compile(r'"([^"]+)"')
        self.operator_pattern = re.compile(r'\b(AND|OR|NOT)\b', re.IGNORECASE)

    def parse(self, query: str) -> ParsedQuery:
        """
        Parse search query into structured format.

        Args:
            query: Search query string

        Returns:
            ParsedQuery with tokens, FTS query, and filters
        """
        if not query or not query.strip():
            return ParsedQuery()

        query = query.strip()
        tokens = []
        remaining_text = []
        pos = 0

        # Track OR groups for FTS
        or_groups = []
        current_or_group = []

        while pos < len(query):
            # Skip whitespace
            if query[pos].isspace():
                pos += 1
                continue

            # Check for NOT operator or -prefix
            negated = False
            if query[pos:pos+4].upper() == 'NOT ' or query[pos] == '-':
                negated = True
                if query[pos] == '-':
                    pos += 1
                else:
                    pos += 4
                while pos < len(query) and query[pos].isspace():
                    pos += 1

            # Check for OR operator
            if query[pos:pos+3].upper() == 'OR ':
                tokens.append(SearchToken(type='operator', value='OR'))
                pos += 3
                continue

            # Check for AND operator (usually implicit, but can be explicit)
            if query[pos:pos+4].upper() == 'AND ':
                tokens.append(SearchToken(type='operator', value='AND'))
                pos += 4
                continue

            # Try to match field:value
            field_match = self.field_pattern.match(query, pos)
            if field_match:
                field_name = field_match.group(1).lower()
                operator = field_match.group(2) or '='
                value = field_match.group(3).strip('"')

                # Apply field aliases
                field_name = self.FIELD_ALIASES.get(field_name, field_name)

                tokens.append(SearchToken(
                    type='field',
                    field=field_name,
                    value=value,
                    operator=operator,
                    negated=negated
                ))
                pos = field_match.end()
                continue

            # Try to match quoted phrase
            phrase_match = self.phrase_pattern.match(query, pos)
            if phrase_match:
                phrase = phrase_match.group(1)
                tokens.append(SearchToken(
                    type='phrase',
                    value=phrase,
                    negated=negated
                ))
                pos = phrase_match.end()
                continue

            # Match single word
            end_pos = pos
            while end_pos < len(query) and not query[end_pos].isspace():
                end_pos += 1

            if end_pos > pos:
                word = query[pos:end_pos]
                tokens.append(SearchToken(
                    type='text',
                    value=word,
                    negated=negated
                ))
                pos = end_pos
                continue

            pos += 1

        # Build ParsedQuery from tokens
        parsed = ParsedQuery(tokens=tokens)
        self._build_fts_and_filters(parsed)

        return parsed

    def _build_fts_and_filters(self, parsed: ParsedQuery):
        """
        Build FTS query and filters from parsed tokens.

        Modifies parsed query in place.
        """
        fts_parts = []  # Parts for FTS5 query
        filters = {}

        i = 0
        while i < len(parsed.tokens):
            token = parsed.tokens[i]

            if token.type == 'operator':
                # Add OR operator to FTS query
                if token.value == 'OR' and fts_parts:
                    fts_parts.append('OR')
                i += 1
                continue

            if token.type == 'field':
                field = token.field
                value = token.value
                operator = token.operator

                # Handle FTS fields
                if field in self.FTS_FIELDS:
                    # Build FTS query with field prefix
                    if field == 'subject':
                        # Subjects are handled separately (join table)
                        if 'subjects' not in filters:
                            filters['subjects'] = []
                        filters['subjects'].append((value, token.negated))
                    elif field == 'author':
                        # Authors are not in FTS table, handle via SQL join
                        if 'authors' not in filters:
                            filters['authors'] = []
                        filters['authors'].append((value, token.negated))
                    else:
                        # title, description, text - these ARE in FTS table
                        # Map 'text' to 'extracted_text' column name
                        fts_column = 'extracted_text' if field == 'text' else field

                        # Build FTS5 column-specific query
                        fts_term = f"{fts_column}:{value}"
                        if token.negated:
                            fts_term = f"NOT {fts_term}"
                        fts_parts.append(fts_term)

                # Handle exact filter fields
                elif field in self.FILTER_FIELDS:
                    if field in self.NUMERIC_FIELDS:
                        # Parse numeric comparison
                        filters[field] = self._parse_numeric_filter(value, operator)
                    elif field in self.BOOLEAN_FIELDS:
                        # Parse boolean
                        filters[field] = value.lower() in ('true', 'yes', '1')
                    else:
                        # Exact match
                        filters[field] = value

            elif token.type in ('text', 'phrase'):
                # Add to FTS query
                value = token.value
                if ' ' in value or token.type == 'phrase':
                    # Quoted phrase for FTS5
                    value = f'"{value}"'
                if token.negated:
                    value = f"NOT {value}"
                fts_parts.append(value)

            i += 1

        # Build final FTS query
        if fts_parts:
            parsed.fts_query = ' '.join(fts_parts)

        parsed.filters = filters

    def _parse_numeric_filter(self, value: str, operator: str) -> Dict[str, Any]:
        """
        Parse numeric filter with comparison operator.

        Examples:
            rating:5 -> {'=': 5}
            rating:>=4 -> {'>=': 4}
            rating:3-5 -> {'>=': 3, '<=': 5}
        """
        # Check for range (e.g., 3-5)
        if '-' in value and operator == '=':
            parts = value.split('-')
            if len(parts) == 2:
                try:
                    min_val = float(parts[0].strip())
                    max_val = float(parts[1].strip())
                    return {'>=': min_val, '<=': max_val}
                except ValueError:
                    pass

        # Single value with operator
        try:
            num_val = float(value)
            return {operator: num_val}
        except ValueError:
            return {}

    def to_sql_conditions(self, parsed: ParsedQuery) -> Tuple[str, Dict[str, Any]]:
        """
        Convert parsed query to SQL WHERE conditions.

        Returns:
            Tuple of (where_clause, params_dict)

        This is used by Library.search() to build the final SQL query.
        """
        conditions = []
        params = {}

        # Handle filters
        for field, value in parsed.filters.items():
            if field == 'subjects':
                # Handle subject filtering (many-to-many)
                for i, (subject, negated) in enumerate(value):
                    param_name = f'subject_{i}'
                    if negated:
                        conditions.append(
                            f"NOT EXISTS (SELECT 1 FROM book_subjects bs "
                            f"JOIN subjects s ON bs.subject_id = s.id "
                            f"WHERE bs.book_id = books.id AND s.name LIKE :{param_name})"
                        )
                    else:
                        conditions.append(
                            f"EXISTS (SELECT 1 FROM book_subjects bs "
                            f"JOIN subjects s ON bs.subject_id = s.id "
                            f"WHERE bs.book_id = books.id AND s.name LIKE :{param_name})"
                        )
                    params[param_name] = f"%{subject}%"

            elif field == 'authors':
                # Handle author filtering (many-to-many)
                for i, (author, negated) in enumerate(value):
                    param_name = f'author_{i}'
                    if negated:
                        conditions.append(
                            f"NOT EXISTS (SELECT 1 FROM book_authors ba "
                            f"JOIN authors a ON ba.author_id = a.id "
                            f"WHERE ba.book_id = books.id AND a.name LIKE :{param_name})"
                        )
                    else:
                        conditions.append(
                            f"EXISTS (SELECT 1 FROM book_authors ba "
                            f"JOIN authors a ON ba.author_id = a.id "
                            f"WHERE ba.book_id = books.id AND a.name LIKE :{param_name})"
                        )
                    params[param_name] = f"%{author}%"

            elif field == 'rating':
                # Numeric comparison via personal_metadata
                for op, val in value.items():
                    param_name = f'rating_{op.replace("<", "lt").replace(">", "gt").replace("=", "eq")}'
                    conditions.append(
                        f"EXISTS (SELECT 1 FROM personal_metadata pm "
                        f"WHERE pm.book_id = books.id AND pm.rating {op} :{param_name})"
                    )
                    params[param_name] = val

            elif field == 'favorite':
                # Boolean via personal_metadata
                conditions.append(
                    f"EXISTS (SELECT 1 FROM personal_metadata pm "
                    f"WHERE pm.book_id = books.id AND pm.favorite = :favorite)"
                )
                params['favorite'] = value

            elif field == 'status':
                # Reading status via personal_metadata
                conditions.append(
                    f"EXISTS (SELECT 1 FROM personal_metadata pm "
                    f"WHERE pm.book_id = books.id AND pm.reading_status = :status)"
                )
                params['status'] = value

            elif field == 'format':
                # File format
                conditions.append(
                    f"EXISTS (SELECT 1 FROM files f "
                    f"WHERE f.book_id = books.id AND LOWER(f.format) = :format)"
                )
                params['format'] = value.lower()

            elif field == 'language':
                conditions.append("books.language = :language")
                params['language'] = value

            elif field == 'series':
                conditions.append("books.series LIKE :series")
                params['series'] = f"%{value}%"

            elif field == 'publisher':
                conditions.append("books.publisher LIKE :publisher")
                params['publisher'] = f"%{value}%"

        where_clause = ' AND '.join(conditions) if conditions else ''
        return where_clause, params


# Convenience function for parsing queries
def parse_search_query(query: str) -> ParsedQuery:
    """Parse a search query string."""
    parser = SearchQueryParser()
    return parser.parse(query)
