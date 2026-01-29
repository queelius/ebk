"""
Open Library plugin for EBK.

This plugin provides metadata extraction from Open Library API.
Open Library is free and requires no API key.

API Documentation: https://openlibrary.org/developers/api
"""

import asyncio
import aiohttp
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from ebk.plugins.base import MetadataExtractor

logger = logging.getLogger(__name__)


class OpenLibraryExtractor(MetadataExtractor):
    """Extract metadata from Open Library API.

    Open Library is a free, open-source library catalog that provides:
    - Book metadata by ISBN
    - Book search
    - Author information
    - Work/edition data

    No API key required.
    """

    BASE_URL = "https://openlibrary.org"
    COVERS_URL = "https://covers.openlibrary.org"

    def __init__(self):
        super().__init__()
        self.session = None
        self.rate_limit = 100  # requests per minute (be nice to free API)
        self.cache_ttl = 3600  # seconds
        self._request_times = []

    @property
    def name(self) -> str:
        return "open_library"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Extract book metadata from Open Library API (free, no API key required)"

    @property
    def author(self) -> str:
        return "EBK Team"

    @property
    def requires(self) -> List[str]:
        return ["aiohttp"]

    def initialize(self, config: Dict[str, Any] = None) -> None:
        """
        Initialize the plugin with configuration.

        Args:
            config: Configuration dictionary (optional)
        """
        super().initialize(config)

        # Update rate limit if specified
        if 'rate_limit' in self.config:
            self.rate_limit = self.config['rate_limit']

        # Update cache TTL if specified
        if 'cache_ttl' in self.config:
            self.cache_ttl = self.config['cache_ttl']

        logger.info("Initialized Open Library plugin")

    def cleanup(self) -> None:
        """Cleanup resources."""
        if self.session:
            self.session = None

    def validate_config(self) -> bool:
        """
        Validate plugin configuration.

        Returns:
            True if configuration is valid
        """
        # No API key required
        return True

    async def extract(self,
                     file_path: Optional[str] = None,
                     url: Optional[str] = None,
                     isbn: Optional[str] = None,
                     content: Optional[bytes] = None) -> Dict[str, Any]:
        """
        Extract metadata from Open Library API.

        Args:
            file_path: Not used for this extractor
            url: Not used for this extractor
            isbn: ISBN to lookup
            content: Not used for this extractor

        Returns:
            Dictionary with metadata fields
        """
        if not isbn:
            return {}

        # Clean ISBN (remove dashes and spaces)
        clean_isbn = isbn.replace('-', '').replace(' ', '')

        # Rate limiting
        await self._rate_limit_check()

        # Try to get book data
        try:
            data = await self._fetch_book_by_isbn(clean_isbn)

            if not data:
                logger.info(f"No results found for ISBN {isbn}")
                return {}

            metadata = self._parse_book_data(data, clean_isbn)
            metadata['source'] = 'open_library'

            logger.info(f"Successfully extracted metadata for ISBN {isbn}")
            return metadata

        except Exception as e:
            logger.error(f"Failed to extract metadata for ISBN {isbn}: {e}")
            return {}

    async def _rate_limit_check(self) -> None:
        """Check and enforce rate limiting."""
        if not self.rate_limit:
            return

        now = datetime.now().timestamp()

        # Remove timestamps older than 1 minute
        self._request_times = [t for t in self._request_times if now - t < 60]

        # If we've hit the rate limit, wait
        if len(self._request_times) >= self.rate_limit:
            wait_time = 60 - (now - self._request_times[0])
            if wait_time > 0:
                logger.debug(f"Rate limit reached, waiting {wait_time:.1f} seconds")
                await asyncio.sleep(wait_time)

        self._request_times.append(now)

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if not self.session:
            self.session = aiohttp.ClientSession()
        return self.session

    async def _fetch_book_by_isbn(self, isbn: str) -> Optional[Dict[str, Any]]:
        """
        Fetch book data from Open Library by ISBN.

        Uses the ISBN API endpoint which returns edition data.

        Args:
            isbn: ISBN to lookup

        Returns:
            API response data or None
        """
        session = await self._get_session()

        # Open Library ISBN API returns JSON directly
        url = f"{self.BASE_URL}/isbn/{isbn}.json"

        try:
            async with session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 404:
                    logger.debug(f"ISBN {isbn} not found in Open Library")
                    return None
                else:
                    logger.error(f"API request failed with status {response.status}")
                    return None

        except aiohttp.ClientError as e:
            logger.error(f"Network error during API request: {e}")
            return None

    async def _fetch_work_data(self, work_key: str) -> Optional[Dict[str, Any]]:
        """
        Fetch work data (contains description, subjects, etc.).

        Args:
            work_key: Work key (e.g., "/works/OL123W")

        Returns:
            Work data or None
        """
        session = await self._get_session()
        url = f"{self.BASE_URL}{work_key}.json"

        try:
            async with session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                return None
        except aiohttp.ClientError as e:
            logger.error(f"Failed to fetch work data: {e}")
            return None

    async def _fetch_author_data(self, author_key: str) -> Optional[Dict[str, Any]]:
        """
        Fetch author data.

        Args:
            author_key: Author key (e.g., "/authors/OL123A")

        Returns:
            Author data or None
        """
        session = await self._get_session()
        url = f"{self.BASE_URL}{author_key}.json"

        try:
            async with session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                return None
        except aiohttp.ClientError as e:
            logger.error(f"Failed to fetch author data: {e}")
            return None

    def _parse_book_data(self, data: Dict[str, Any], isbn: str) -> Dict[str, Any]:
        """
        Parse edition data from API response.

        Args:
            data: Edition data from API
            isbn: Original ISBN query

        Returns:
            Parsed metadata dictionary
        """
        metadata = {}

        # Basic fields from edition
        if 'title' in data:
            metadata['title'] = data['title']

        if 'subtitle' in data:
            metadata['subtitle'] = data['subtitle']

        if 'publishers' in data:
            publishers = data['publishers']
            if publishers:
                metadata['publisher'] = publishers[0] if isinstance(publishers, list) else publishers

        if 'publish_date' in data:
            metadata['date'] = data['publish_date']
            # Try to extract year
            try:
                date_str = str(data['publish_date'])
                # Common formats: "2020", "March 2020", "2020-03-15"
                import re
                year_match = re.search(r'(\d{4})', date_str)
                if year_match:
                    metadata['year'] = int(year_match.group(1))
            except (ValueError, TypeError):
                pass

        if 'number_of_pages' in data:
            metadata['page_count'] = data['number_of_pages']

        if 'languages' in data:
            # Languages are stored as references like {"key": "/languages/eng"}
            langs = []
            for lang in data['languages']:
                if isinstance(lang, dict) and 'key' in lang:
                    lang_code = lang['key'].split('/')[-1]
                    langs.append(lang_code)
                elif isinstance(lang, str):
                    langs.append(lang)
            if langs:
                metadata['language'] = langs[0]  # Primary language

        # ISBN identifiers
        identifiers = {}
        if 'isbn_10' in data:
            isbn10 = data['isbn_10']
            if isinstance(isbn10, list) and isbn10:
                identifiers['isbn10'] = isbn10[0]
            elif isinstance(isbn10, str):
                identifiers['isbn10'] = isbn10

        if 'isbn_13' in data:
            isbn13 = data['isbn_13']
            if isinstance(isbn13, list) and isbn13:
                identifiers['isbn13'] = isbn13[0]
                identifiers['isbn'] = isbn13[0]
            elif isinstance(isbn13, str):
                identifiers['isbn13'] = isbn13
                identifiers['isbn'] = isbn13

        if identifiers:
            metadata['identifiers'] = identifiers

        # Cover image from covers API
        if 'covers' in data and data['covers']:
            cover_id = data['covers'][0]
            metadata['cover_url'] = f"{self.COVERS_URL}/b/id/{cover_id}-L.jpg"
            metadata['thumbnail_url'] = f"{self.COVERS_URL}/b/id/{cover_id}-M.jpg"
        elif isbn:
            # Fallback to ISBN-based cover URL
            metadata['cover_url'] = f"{self.COVERS_URL}/b/isbn/{isbn}-L.jpg"
            metadata['thumbnail_url'] = f"{self.COVERS_URL}/b/isbn/{isbn}-M.jpg"

        # Authors (stored as references)
        if 'authors' in data:
            authors = []
            for author_ref in data['authors']:
                if isinstance(author_ref, dict) and 'key' in author_ref:
                    # Could fetch full author data here, but for now just use key
                    author_key = author_ref['key']
                    # Open Library author keys are like "/authors/OL123A"
                    authors.append(author_key)
            if authors:
                metadata['author_keys'] = authors

        # Link to Open Library page
        if 'key' in data:
            metadata['source_url'] = f"{self.BASE_URL}{data['key']}"

        return metadata

    async def enrich_with_work_data(self, metadata: Dict[str, Any], work_key: str) -> Dict[str, Any]:
        """
        Enrich metadata with work-level data (description, subjects).

        Args:
            metadata: Existing metadata dict
            work_key: Work key to fetch

        Returns:
            Enriched metadata
        """
        await self._rate_limit_check()
        work_data = await self._fetch_work_data(work_key)

        if not work_data:
            return metadata

        # Description
        if 'description' in work_data:
            desc = work_data['description']
            if isinstance(desc, dict) and 'value' in desc:
                metadata['description'] = desc['value']
            elif isinstance(desc, str):
                metadata['description'] = desc

        # Subjects
        if 'subjects' in work_data:
            metadata['subjects'] = work_data['subjects']

        return metadata

    async def resolve_authors(self, author_keys: List[str]) -> List[str]:
        """
        Resolve author keys to author names.

        Args:
            author_keys: List of author keys

        Returns:
            List of author names
        """
        authors = []
        for key in author_keys:
            await self._rate_limit_check()
            author_data = await self._fetch_author_data(key)
            if author_data and 'name' in author_data:
                authors.append(author_data['name'])
        return authors

    def supported_formats(self) -> List[str]:
        """
        Return list of supported formats.

        This extractor works with ISBNs, not file formats.
        """
        return ['isbn']

    async def search(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Search for books by query.

        Args:
            query: Search query
            max_results: Maximum number of results

        Returns:
            List of metadata dictionaries
        """
        await self._rate_limit_check()

        session = await self._get_session()

        # Open Library search API
        url = f"{self.BASE_URL}/search.json"
        params = {
            'q': query,
            'limit': min(max_results, 100)  # API supports up to 100
        }

        try:
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    logger.error(f"Search failed with status {response.status}")
                    return []

                data = await response.json()

                if data.get('numFound', 0) == 0:
                    return []

                results = []
                for doc in data.get('docs', []):
                    metadata = self._parse_search_result(doc)
                    metadata['source'] = 'open_library'
                    results.append(metadata)

                return results

        except Exception as e:
            logger.error(f"Search failed for query '{query}': {e}")
            return []

    def _parse_search_result(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse a search result document.

        Args:
            doc: Document from search results

        Returns:
            Metadata dictionary
        """
        metadata = {}

        if 'title' in doc:
            metadata['title'] = doc['title']

        if 'author_name' in doc:
            metadata['creators'] = doc['author_name']

        if 'first_publish_year' in doc:
            metadata['year'] = doc['first_publish_year']

        if 'publisher' in doc and doc['publisher']:
            metadata['publisher'] = doc['publisher'][0]

        if 'language' in doc and doc['language']:
            metadata['language'] = doc['language'][0]

        if 'subject' in doc:
            metadata['subjects'] = doc['subject'][:10]  # Limit subjects

        if 'isbn' in doc and doc['isbn']:
            metadata['identifiers'] = {'isbn': doc['isbn'][0]}

        if 'cover_i' in doc:
            cover_id = doc['cover_i']
            metadata['cover_url'] = f"{self.COVERS_URL}/b/id/{cover_id}-L.jpg"
            metadata['thumbnail_url'] = f"{self.COVERS_URL}/b/id/{cover_id}-M.jpg"

        if 'key' in doc:
            metadata['source_url'] = f"{self.BASE_URL}{doc['key']}"

        return metadata


# Synchronous wrapper for compatibility
class OpenLibraryExtractorSync(OpenLibraryExtractor):
    """Synchronous wrapper for Open Library extractor."""

    def extract_sync(self, isbn: str) -> Dict[str, Any]:
        """
        Synchronous extraction method.

        Args:
            isbn: ISBN to lookup

        Returns:
            Metadata dictionary
        """
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.extract(isbn=isbn))
        finally:
            loop.close()

    def search_sync(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Synchronous search method.

        Args:
            query: Search query
            max_results: Maximum results

        Returns:
            List of metadata dictionaries
        """
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.search(query, max_results))
        finally:
            loop.close()
