# Changelog

Project changelog and release notes.

## v0.4.3 (2025-01-03)

### New Features

- **Book Merge**: Combine duplicate book entries into one
  - `ebk book merge <primary_id> <secondary_ids>` - Merge multiple books
  - Preserves all metadata, files, covers, tags, and annotations
  - `--dry-run` to preview changes, `--delete-duplicates` to remove duplicate files

- **Bulk Edit**: Edit multiple books at once
  - `ebk book bulk-edit --ids 1,2,3 --language en --add-tag Work`
  - Select books via `--ids`, `--search`, or `--view`
  - Edit language, publisher, series, tags, subjects, rating, status, favorite

- **Goodreads Export**: Export library for Goodreads import
  - `ebk export goodreads ~/library ~/goodreads.csv`
  - Includes ratings, reading status, bookshelves (tags)
  - Import at goodreads.com/review/import

- **Calibre Export**: Export library for Calibre import
  - `ebk export calibre ~/library ~/calibre.csv`
  - Includes author_sort, identifiers, series info

### Documentation

- Complete documentation overhaul
- Removed intermediate/internal docs (phase summaries, design docs)
- Updated index.md with current features and motivation
- Rewrote quickstart guide with current CLI commands
- Comprehensive import/export guide with all formats
- Updated Python API documentation

### Improvements

- Views now support `--view` flag in all export commands
- OPDS export supports file and cover copying

## v0.3.1 (2025-01-14)

### New Features
- 🔍 **Advanced Search**: Field-specific queries with boolean logic
  - Field searches: `title:`, `author:`, `tag:`, `description:`, `text:`
  - Filter fields: `language:`, `format:`, `rating:`, `favorite:`, `status:`
  - Boolean operators: `AND` (implicit), `OR`, `NOT`/`-prefix`
  - Rating comparisons: `rating:>=4`, `rating:3-5`
  - Phrase searches: `"exact phrase"`
- 📄 **HTML Export Pagination**: 50 books per page with navigation controls
  - URL state tracking for bookmarkable pages
  - Page numbers in URL query parameters
  - Previous/Next buttons with page number links
- 📋 **Cover Copying**: `--copy` flag now copies both files AND covers

### Improvements
- Search parser with FTS5 column-specific queries (`title:term`)
- Author and subject filtering via SQL JOINs (not in FTS table)
- HTML export with URL-based state management (filters, search, page)
- Fixed `ExtractedText.content` attribute name (was incorrectly using `full_text`)
- Added missing `Library.add_subject()` method for metadata enrichment

### Bug Fixes
- Fixed `ebk enrich` command attribute error with extracted text
- Fixed HTML export `--copy` not copying cover images
- Fixed field searches not working (FTS5 column prefixes)

### Documentation
- Comprehensive search guide with all syntax and examples
- Updated README with advanced search features
- Import/export guide with pagination documentation
- Clear notes about HTML export limitations (client-side filtering only)

## v0.3.0 (2025-01-XX)

### New Features
- ✨ Configuration system at `~/.config/ebk/config.json`
- 🤖 LLM provider abstraction with Ollama support (local and remote)
- 🏷️ AI-powered metadata enrichment (tags, categories, descriptions, difficulty assessment)
- 🌐 Enhanced web server with config defaults and auto-open browser
- 📚 Complete documentation overhaul with mkdocs

### Configuration System
- Centralized configuration management with `ebk config` command
- Four configuration sections: `llm`, `server`, `cli`, `library`
- Support for default library path
- Server host, port, and auto-open browser settings
- CLI defaults for verbosity and color output

### LLM Integration
- Abstract `BaseLLMProvider` interface in `ebk/ai/llm_providers/`
- `OllamaProvider` with local and remote support
- `MetadataEnrichmentService` for intelligent metadata generation
- `ebk enrich` command with selective enrichment options
- Support for multiple models and temperature control

### Server Updates
- `ebk serve` now uses config defaults for library path, host, and port
- Optional library path argument (uses config if not specified)
- Auto-open browser feature
- REST API improvements

### Documentation
- New user guides: Configuration, LLM Features, Web Server, CLI Reference
- Updated README with quickstart and modern examples
- Deployed to GitHub Pages

### Breaking Changes
- `ebk serve` library path is now optional (uses config default)
- Some CLI options renamed for consistency (e.g., `--llm-*` prefix)

## Earlier Versions

See [GitHub Releases](https://github.com/queelius/ebk/releases) for information about earlier versions.
