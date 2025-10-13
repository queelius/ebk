# Changelog

Project changelog and release notes.

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
