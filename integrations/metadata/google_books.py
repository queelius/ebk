"""
Google Books plugin for EBK.

This plugin provides metadata extraction from Google Books API.
"""

import os
import asyncio
import aiohttp
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from ebk.plugins.base import MetadataExtractor

logger = logging.getLogger(__name__)


class GoogleBooksExtractor(MetadataExtractor):
    """Extract metadata from Google Books API."""
    
    def __init__(self):
        super().__init__()
        self.api_key = None
        self.base_url = "https://www.googleapis.com/books/v1/volumes"
        self.session = None
        self.rate_limit = 100  # requests per minute
        self.cache_ttl = 3600  # seconds
        self._request_times = []
        
    @property
    def name(self) -> str:
        return "google_books"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def description(self) -> str:
        return "Extract book metadata from Google Books API"
    
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
            config: Configuration dictionary with optional 'api_key'
        """
        super().initialize(config)
        
        # Get API key from config or environment
        self.api_key = self.config.get('api_key') or os.environ.get('GOOGLE_BOOKS_API_KEY')
        
        # Update rate limit if specified
        if 'rate_limit' in self.config:
            self.rate_limit = self.config['rate_limit']
        
        # Update cache TTL if specified
        if 'cache_ttl' in self.config:
            self.cache_ttl = self.config['cache_ttl']
        
        logger.info(f"Initialized Google Books plugin (API key: {'present' if self.api_key else 'absent'})")
    
    def cleanup(self) -> None:
        """Cleanup resources."""
        if self.session:
            # Note: In real async code, this should be awaited
            # For now, we'll just set it to None
            self.session = None
    
    def validate_config(self) -> bool:
        """
        Validate plugin configuration.
        
        Returns:
            True if configuration is valid
        """
        # API key is optional (works without it but with limitations)
        return True
    
    async def extract(self, 
                     file_path: Optional[str] = None,
                     url: Optional[str] = None,
                     isbn: Optional[str] = None,
                     content: Optional[bytes] = None) -> Dict[str, Any]:
        """
        Extract metadata from Google Books API.
        
        Args:
            file_path: Not used for this extractor
            url: Not used for this extractor
            isbn: ISBN to lookup
            content: Not used for this extractor
            
        Returns:
            Dictionary with metadata fields
        """
        if not isbn:
            # Try to extract ISBN from other parameters if possible
            if file_path:
                # Could implement ISBN extraction from file metadata
                pass
            return {}
        
        # Clean ISBN (remove dashes and spaces)
        clean_isbn = isbn.replace('-', '').replace(' ', '')
        
        # Rate limiting
        await self._rate_limit_check()
        
        # Make API request
        try:
            data = await self._fetch_book_data(clean_isbn)
            
            if not data or data.get('totalItems', 0) == 0:
                logger.info(f"No results found for ISBN {isbn}")
                return {}
            
            # Parse the first result
            item = data['items'][0]['volumeInfo']
            
            metadata = self._parse_volume_info(item)
            metadata['source'] = 'google_books'
            metadata['source_url'] = data['items'][0].get('selfLink')
            
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
    
    async def _fetch_book_data(self, isbn: str) -> Optional[Dict[str, Any]]:
        """
        Fetch book data from Google Books API.
        
        Args:
            isbn: ISBN to lookup
            
        Returns:
            API response data or None
        """
        # Create session if needed
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        # Build query parameters
        params = {'q': f'isbn:{isbn}'}
        if self.api_key:
            params['key'] = self.api_key
        
        try:
            async with self.session.get(self.base_url, params=params) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"API request failed with status {response.status}")
                    return None
                    
        except aiohttp.ClientError as e:
            logger.error(f"Network error during API request: {e}")
            return None
    
    def _parse_volume_info(self, volume_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse volume info from API response.
        
        Args:
            volume_info: Volume info from API
            
        Returns:
            Parsed metadata dictionary
        """
        metadata = {}
        
        # Basic fields
        if 'title' in volume_info:
            metadata['title'] = volume_info['title']
        
        if 'subtitle' in volume_info:
            metadata['subtitle'] = volume_info['subtitle']
        
        if 'authors' in volume_info:
            metadata['creators'] = volume_info['authors']
        
        if 'publisher' in volume_info:
            metadata['publisher'] = volume_info['publisher']
        
        if 'publishedDate' in volume_info:
            metadata['date'] = volume_info['publishedDate']
            # Try to extract year
            try:
                date_str = volume_info['publishedDate']
                if len(date_str) >= 4:
                    metadata['year'] = int(date_str[:4])
            except (ValueError, TypeError):
                pass
        
        if 'description' in volume_info:
            metadata['description'] = volume_info['description']
        
        if 'categories' in volume_info:
            metadata['subjects'] = volume_info['categories']
        
        if 'language' in volume_info:
            metadata['language'] = volume_info['language']
        
        if 'pageCount' in volume_info:
            metadata['page_count'] = volume_info['pageCount']
        
        # Industry identifiers (ISBN, etc.)
        if 'industryIdentifiers' in volume_info:
            identifiers = {}
            for identifier in volume_info['industryIdentifiers']:
                id_type = identifier.get('type', '').lower()
                id_value = identifier.get('identifier')
                
                if id_type == 'isbn_10':
                    identifiers['isbn10'] = id_value
                elif id_type == 'isbn_13':
                    identifiers['isbn13'] = id_value
                    identifiers['isbn'] = id_value  # Use ISBN-13 as default
                else:
                    identifiers[id_type] = id_value
            
            if identifiers:
                metadata['identifiers'] = identifiers
        
        # Image links
        if 'imageLinks' in volume_info:
            image_links = volume_info['imageLinks']
            
            # Prefer larger images
            if 'extraLarge' in image_links:
                metadata['cover_url'] = image_links['extraLarge']
            elif 'large' in image_links:
                metadata['cover_url'] = image_links['large']
            elif 'medium' in image_links:
                metadata['cover_url'] = image_links['medium']
            elif 'small' in image_links:
                metadata['cover_url'] = image_links['small']
            elif 'thumbnail' in image_links:
                metadata['cover_url'] = image_links['thumbnail']
            
            # Always include thumbnail if available
            if 'thumbnail' in image_links:
                metadata['thumbnail_url'] = image_links['thumbnail']
        
        # Additional fields
        if 'averageRating' in volume_info:
            metadata['rating'] = volume_info['averageRating']
        
        if 'ratingsCount' in volume_info:
            metadata['ratings_count'] = volume_info['ratingsCount']
        
        if 'maturityRating' in volume_info:
            metadata['maturity_rating'] = volume_info['maturityRating']
        
        if 'previewLink' in volume_info:
            metadata['preview_url'] = volume_info['previewLink']
        
        if 'infoLink' in volume_info:
            metadata['info_url'] = volume_info['infoLink']
        
        return metadata
    
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
        # Rate limiting
        await self._rate_limit_check()
        
        # Create session if needed
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        # Build query parameters
        params = {
            'q': query,
            'maxResults': min(max_results, 40)  # API limit is 40
        }
        if self.api_key:
            params['key'] = self.api_key
        
        try:
            async with self.session.get(self.base_url, params=params) as response:
                if response.status != 200:
                    logger.error(f"Search failed with status {response.status}")
                    return []
                
                data = await response.json()
                
                if data.get('totalItems', 0) == 0:
                    return []
                
                results = []
                for item in data.get('items', []):
                    volume_info = item.get('volumeInfo', {})
                    metadata = self._parse_volume_info(volume_info)
                    metadata['source'] = 'google_books'
                    metadata['source_url'] = item.get('selfLink')
                    results.append(metadata)
                
                return results
                
        except Exception as e:
            logger.error(f"Search failed for query '{query}': {e}")
            return []


# Optional: Synchronous wrapper for compatibility
class GoogleBooksExtractorSync(GoogleBooksExtractor):
    """Synchronous wrapper for Google Books extractor."""
    
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