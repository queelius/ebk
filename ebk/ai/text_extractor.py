"""
Extract text and structured content from various ebook formats.
"""

import re
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import fitz  # PyMuPDF
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)


class ChapterExtractor:
    """Extract chapters and structured content from books."""

    def extract(self, file_path: Path) -> List[Dict[str, Any]]:
        """Extract chapters from a book file."""
        file_path = Path(file_path)
        suffix = file_path.suffix.lower()

        if suffix == '.pdf':
            return self._extract_pdf_chapters(file_path)
        elif suffix == '.epub':
            return self._extract_epub_chapters(file_path)
        else:
            logger.warning(f"Unsupported format: {suffix}")
            return []

    def _extract_pdf_chapters(self, file_path: Path) -> List[Dict[str, Any]]:
        """Extract chapters from a PDF file."""
        chapters = []

        try:
            pdf = fitz.open(str(file_path))
            toc = pdf.get_toc()  # Table of contents

            if toc:
                # Use TOC if available
                for i, (level, title, page_num) in enumerate(toc):
                    if level == 1:  # Main chapters
                        # Get chapter content
                        start_page = page_num - 1
                        end_page = toc[i + 1][2] - 1 if i + 1 < len(toc) else len(pdf)

                        text = ""
                        for page_idx in range(start_page, min(end_page, len(pdf))):
                            page = pdf[page_idx]
                            text += page.get_text()

                        chapters.append({
                            'title': title,
                            'level': level,
                            'page_start': start_page + 1,
                            'page_end': end_page,
                            'content': text.strip()
                        })
            else:
                # Fallback: Try to detect chapters by patterns
                chapters = self._detect_pdf_chapters_by_pattern(pdf)

            pdf.close()

        except Exception as e:
            logger.error(f"Error extracting PDF chapters: {e}")

        return chapters

    def _detect_pdf_chapters_by_pattern(self, pdf) -> List[Dict[str, Any]]:
        """Detect chapters in PDF by common patterns."""
        chapters = []
        chapter_pattern = re.compile(
            r'^(Chapter|CHAPTER|Ch\.|CH\.?)\s+(\d+|[IVX]+)[\s:\-]*(.*)$',
            re.MULTILINE
        )

        current_chapter = None
        chapter_text = []

        for page_num in range(len(pdf)):
            page = pdf[page_num]
            text = page.get_text()

            # Look for chapter headings
            matches = chapter_pattern.finditer(text)
            for match in matches:
                if current_chapter:
                    # Save previous chapter
                    current_chapter['content'] = '\n'.join(chapter_text).strip()
                    current_chapter['page_end'] = page_num
                    chapters.append(current_chapter)
                    chapter_text = []

                # Start new chapter
                current_chapter = {
                    'title': match.group(3).strip() or f"Chapter {match.group(2)}",
                    'level': 1,
                    'page_start': page_num + 1,
                    'page_end': None,
                    'content': ''
                }

            if current_chapter:
                chapter_text.append(text)

        # Save last chapter
        if current_chapter:
            current_chapter['content'] = '\n'.join(chapter_text).strip()
            current_chapter['page_end'] = len(pdf)
            chapters.append(current_chapter)

        return chapters

    def _extract_epub_chapters(self, file_path: Path) -> List[Dict[str, Any]]:
        """Extract chapters from an EPUB file."""
        chapters = []

        try:
            book = epub.read_epub(str(file_path))

            # Get table of contents
            toc = book.toc

            # Extract text from each chapter
            for item in book.get_items():
                if item.get_type() == ebooklib.ITEM_DOCUMENT:
                    soup = BeautifulSoup(item.content, 'html.parser')

                    # Try to find chapter title
                    title = None
                    for heading in ['h1', 'h2', 'h3']:
                        heading_elem = soup.find(heading)
                        if heading_elem:
                            title = heading_elem.get_text().strip()
                            break

                    if not title:
                        title = item.get_name()

                    # Extract text content
                    text = soup.get_text(separator='\n').strip()

                    if text:
                        chapters.append({
                            'title': title,
                            'level': 1,
                            'page_start': None,  # EPUB doesn't have pages
                            'page_end': None,
                            'content': text
                        })

        except Exception as e:
            logger.error(f"Error extracting EPUB chapters: {e}")

        return chapters


class TextExtractor:
    """Extract and process text from ebooks for knowledge extraction."""

    def __init__(self):
        self.chapter_extractor = ChapterExtractor()

    def extract_full_text(self, file_path: Path) -> str:
        """Extract complete text from a book."""
        file_path = Path(file_path)
        suffix = file_path.suffix.lower()

        if suffix == '.pdf':
            return self._extract_pdf_text(file_path)
        elif suffix == '.epub':
            return self._extract_epub_text(file_path)
        elif suffix in ['.txt', '.md']:
            return file_path.read_text(encoding='utf-8')
        else:
            logger.warning(f"Unsupported format: {suffix}")
            return ""

    def extract_key_passages(self, file_path: Path,
                           keywords: List[str] = None,
                           context_size: int = 200) -> List[Dict[str, Any]]:
        """
        Extract passages containing specific keywords or important concepts.
        """
        chapters = self.chapter_extractor.extract(file_path)
        passages = []

        for chapter in chapters:
            content = chapter.get('content', '')
            if not content:
                continue

            # Split into sentences
            sentences = self._split_into_sentences(content)

            for i, sentence in enumerate(sentences):
                # Check if sentence contains keywords or is important
                if self._is_important_passage(sentence, keywords):
                    # Get context
                    start = max(0, i - 2)
                    end = min(len(sentences), i + 3)
                    context = ' '.join(sentences[start:end])

                    passages.append({
                        'chapter': chapter['title'],
                        'page': chapter.get('page_start'),
                        'sentence': sentence,
                        'context': context,
                        'importance_score': self._calculate_importance(sentence, keywords)
                    })

        # Sort by importance
        passages.sort(key=lambda x: x['importance_score'], reverse=True)
        return passages

    def extract_quotes(self, file_path: Path) -> List[Dict[str, str]]:
        """Extract quoted text from a book."""
        text = self.extract_full_text(file_path)
        quotes = []

        # Pattern for quotes
        quote_patterns = [
            r'"([^"]+)"',  # Double quotes
            r"'([^']+)'",  # Single quotes
            r'"([^"]+)"',  # Smart quotes
            r'«([^»]+)»'   # French quotes
        ]

        for pattern in quote_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                if len(match) > 30 and len(match) < 500:  # Reasonable quote length
                    quotes.append({
                        'text': match,
                        'length': len(match)
                    })

        # Remove duplicates
        seen = set()
        unique_quotes = []
        for quote in quotes:
            if quote['text'] not in seen:
                seen.add(quote['text'])
                unique_quotes.append(quote)

        return unique_quotes

    def extract_definitions(self, file_path: Path) -> List[Dict[str, str]]:
        """Extract definitions and explanations from text."""
        text = self.extract_full_text(file_path)
        definitions = []

        # Patterns that indicate definitions
        definition_patterns = [
            r'(\w+) is defined as ([^.]+)',
            r'(\w+) means ([^.]+)',
            r'(\w+): ([^.]+)',
            r'define (\w+) as ([^.]+)',
            r'(\w+) refers to ([^.]+)',
        ]

        for pattern in definition_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for term, definition in matches:
                if len(definition) > 20:  # Meaningful definition
                    definitions.append({
                        'term': term.strip(),
                        'definition': definition.strip()
                    })

        return definitions

    def extract_summaries(self, file_path: Path,
                         summary_length: int = 500) -> List[Dict[str, str]]:
        """
        Extract or generate chapter summaries.
        Looks for explicit summaries or creates them from beginning/end of chapters.
        """
        chapters = self.chapter_extractor.extract(file_path)
        summaries = []

        for chapter in chapters:
            content = chapter.get('content', '')
            if not content:
                continue

            # Look for explicit summary sections
            summary_text = self._find_summary_section(content)

            if not summary_text:
                # Create summary from first and last paragraphs
                paragraphs = content.split('\n\n')
                if len(paragraphs) > 3:
                    summary_text = paragraphs[0][:summary_length // 2] + "..." + \
                                 paragraphs[-1][:summary_length // 2]
                else:
                    summary_text = content[:summary_length]

            summaries.append({
                'chapter': chapter['title'],
                'summary': summary_text.strip(),
                'page': chapter.get('page_start')
            })

        return summaries

    def _extract_pdf_text(self, file_path: Path) -> str:
        """Extract text from PDF."""
        text = ""
        try:
            pdf = fitz.open(str(file_path))
            for page in pdf:
                text += page.get_text()
            pdf.close()
        except Exception as e:
            logger.error(f"Error extracting PDF text: {e}")
        return text

    def _extract_epub_text(self, file_path: Path) -> str:
        """Extract text from EPUB."""
        text = ""
        try:
            book = epub.read_epub(str(file_path))
            for item in book.get_items():
                if item.get_type() == ebooklib.ITEM_DOCUMENT:
                    soup = BeautifulSoup(item.content, 'html.parser')
                    text += soup.get_text(separator='\n')
        except Exception as e:
            logger.error(f"Error extracting EPUB text: {e}")
        return text

    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences."""
        # Simple sentence splitter - can be improved with NLTK
        sentences = re.split(r'[.!?]\s+', text)
        return [s.strip() for s in sentences if s.strip()]

    def _is_important_passage(self, sentence: str, keywords: List[str] = None) -> bool:
        """Determine if a passage is important."""
        if not keywords:
            # Default important indicators
            keywords = ['therefore', 'thus', 'consequently', 'important',
                       'key', 'critical', 'essential', 'fundamental']

        sentence_lower = sentence.lower()
        return any(kw.lower() in sentence_lower for kw in keywords)

    def _calculate_importance(self, sentence: str, keywords: List[str] = None) -> float:
        """Calculate importance score for a sentence."""
        score = 0.0

        # Length factor
        if 50 < len(sentence) < 300:
            score += 0.2

        # Keyword presence
        if keywords:
            sentence_lower = sentence.lower()
            for kw in keywords:
                if kw.lower() in sentence_lower:
                    score += 0.3

        # Importance indicators
        importance_indicators = ['important', 'key', 'critical', 'essential',
                                'fundamental', 'significant', 'crucial']
        for indicator in importance_indicators:
            if indicator in sentence.lower():
                score += 0.2

        # Conclusion indicators
        if any(word in sentence.lower() for word in ['therefore', 'thus', 'consequently', 'in conclusion']):
            score += 0.3

        return min(score, 1.0)

    def _find_summary_section(self, text: str) -> Optional[str]:
        """Find explicit summary section in text."""
        summary_patterns = [
            r'Summary[:\s]+([^\\n]+(?:\\n[^\\n]+)*)',
            r'In summary[,:\s]+([^.]+\.)',
            r'To summarize[,:\s]+([^.]+\.)',
            r'Key points[:\s]+([^\\n]+(?:\\n[^\\n]+)*)'
        ]

        for pattern in summary_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)

        return None