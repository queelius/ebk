# ebk Roadmap & TODOs

## Overview
This document outlines the development roadmap and pending tasks for the ebk project. Items are organized by priority and category.

See also: [Contributing Guide](contributing.md)

## ✅ Recently Completed
- [x] Plugin system architecture with abstract base classes
- [x] Plugin registry with automatic discovery
- [x] Hook system for event-based plugin interaction  
- [x] Migration from setup.py to pyproject.toml (PEP 517/518/621)
- [x] Unified HTTP LLM provider for OpenAI-compatible APIs
- [x] Proper separation of core plugins vs integrations
- [x] 100% test passing rate achieved
- [x] Network/graph analysis integration
- [x] Google Books metadata extractor

## 🚀 High Priority

### Core Improvements
- [x] **Exporter Module Enhancement** - Replace `os.system` calls with `shutil` for better security and reliability ✅
- [ ] **Performance Optimization** - Implement lazy loading for large libraries
- [ ] **Async Support** - Add async methods for I/O-heavy operations (metadata extraction, API calls)
- [ ] **Caching Layer** - Implement metadata caching for faster repeated operations

### Plugin System
- [ ] **Plugin Documentation** - Create comprehensive plugin development guide
- [ ] **Plugin Examples** - Add example plugins demonstrating each base class
- [ ] **Plugin Testing Framework** - Standardized testing utilities for plugin developers
- [ ] **Plugin Marketplace** - Consider creating a registry/marketplace for community plugins

### API Enhancements  
- [ ] **GraphQL API** - Add GraphQL endpoint for flexible queries
- [ ] **REST API** - Create REST API server for remote library access
- [ ] **Webhook Support** - Allow plugins to register webhooks for events

## 📋 Medium Priority

### Integrations
- [ ] **Goodreads Integration** - Import reading lists and ratings
- [ ] **LibraryThing Integration** - Sync with LibraryThing collections
- [ ] **OPDS Server** - Implement OPDS catalog server for e-reader apps
- [ ] **Kindle Integration** - Import highlights and notes from Kindle
- [ ] **Zotero Integration** - Sync with Zotero research libraries

### Export Formats
- [ ] **LaTeX/BibTeX Export** - Academic bibliography export
- [ ] **CSV/Excel Export** - Spreadsheet-compatible formats
- [ ] **MARC21 Export** - Library standard format
- [ ] **RIS Export** - Reference manager format
- [ ] **Static Site Generators** - Support for Jekyll, Gatsby, Next.js

### Search & Discovery
- [ ] **Full-Text Search** - Index and search book contents (with plugin)
- [ ] **Semantic Search** - Vector embeddings for similarity search
- [ ] **Faceted Search** - Advanced filtering with facets
- [ ] **Search History** - Track and replay searches
- [ ] **Saved Searches** - Store complex queries for reuse

## 🔮 Low Priority / Future Considerations

### Advanced Features
- [ ] **OCR Support** - Extract text from scanned PDFs
- [ ] **Translation Plugin** - Auto-translate metadata
- [ ] **Reading Progress Tracking** - Track reading status and progress
- [ ] **Annotation System** - Store and manage book annotations
- [ ] **Recommendation Engine** - ML-based book recommendations
- [ ] **Duplicate Detection** - Advanced fuzzy matching for duplicates

### UI/UX Improvements
- [ ] **Desktop App** - Native desktop application (Electron/Tauri)
- [ ] **Mobile App** - iOS/Android companion apps
- [ ] **Browser Extension** - Quick-add books from web pages
- [ ] **Terminal UI** - Rich TUI for library browsing
- [ ] **Voice Interface** - Alexa/Google Assistant integration

### Infrastructure
- [ ] **Docker Image** - Official Docker container
- [ ] **Kubernetes Helm Chart** - For cloud deployments
- [ ] **Backup/Restore Plugin** - Automated backup strategies
- [ ] **Multi-User Support** - User accounts and permissions
- [ ] **Federation** - Connect multiple ebk instances

## 🐛 Known Issues

### Current Bugs
- [ ] PDF cover extraction fails for some encrypted PDFs
- [ ] Unicode handling issues in some Windows environments
- [ ] Memory usage high for libraries with 10k+ entries

### Technical Debt
- [ ] Refactor merge.py to use more efficient algorithms
- [ ] Standardize error handling across all modules
- [ ] Improve test coverage for edge cases
- [ ] Update deprecated dependencies (PyPDF2 → pypdf)

## 📝 Documentation Needs

- [ ] Plugin development tutorial
- [ ] API reference documentation
- [ ] Video tutorials for common workflows
- [ ] Troubleshooting guide
- [ ] Performance tuning guide
- [ ] Migration guides from other tools

## 🤝 Community

- [ ] Contribution guidelines (contributing.md)
- [ ] Code of conduct (CODE_OF_CONDUCT.md)
- [ ] Issue templates for GitHub
- [ ] Pull request templates
- [ ] Community forum or Discord server

## Version Planning

### v1.1.0 (Next Minor Release)
- Exporter shutil migration
- Plugin documentation
- Performance optimizations
- Bug fixes

### v1.2.0 
- REST API
- OPDS server
- Full-text search plugin

### v2.0.0 (Next Major Release)
- Breaking API changes for async support
- Multi-user support
- Federation capabilities
- Desktop/mobile apps

---

## Contributing

We welcome contributions! Please see our [Contributing Guide](contributing.md) (coming soon) for details on how to get started.

## Feedback

Have ideas or suggestions? Please open an issue on our [GitHub repository](https://github.com/queelius/ebk/issues) or contact us at lex@metafunctor.com.

---

Last updated: 2025-08-24