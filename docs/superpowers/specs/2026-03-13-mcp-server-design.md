# MCP Server + AI Layer Removal — Design Spec

**Date:** 2026-03-13
**Status:** Approved
**Branch:** TBD (from `fix/security-docs-simplification`)

## Summary

Replace ebk's bespoke LLM orchestration layer (`ebk/ai/`, ~3,300 LOC) with an MCP server that exposes the library as tools for Claude Code or any MCP client. The AI story moves from "ebk orchestrates LLMs" to "ebk is a tool that AI clients use." Simultaneously fix remaining code review items (#8, #9, #10, #12).

## Motivation

The current AI layer has problems:

- **61% dead code** — 5 of 7 modules (knowledge graph, semantic search, text extractor, question generator, reading companion) are fully implemented but never imported
- **0% test coverage** across the entire `ebk/ai/` directory
- **Single integration point** — only the `ebk enrich` CLI command uses it
- **Redundant with Claude Code** — Claude Code is a better orchestrator than a hardcoded enrichment pipeline

An MCP server is a better architecture because:

- **Claude Code becomes the intelligence** — no need to maintain prompt templates, JSON parsing, provider abstractions
- **Flexible** — any query or mutation that Claude Code can reason about, not limited to pre-built enrichment operations
- **Standard protocol** — any MCP client works, not just Claude Code
- **Testable** — 3 tools with clear contracts vs. 7 untested AI modules

## MCP Server Design

### Module Structure

```
ebk/mcp/
├── __init__.py
├── server.py          # MCP server setup, tool registration, CLI entry point
├── tools.py           # Tool implementations (get_schema, execute_sql, update_books)
└── sql_executor.py    # Read-only SQL execution (reuses Views DSL authorizer pattern)
```

### Entry Point

```bash
ebk mcp-serve [library_path]
```

- Uses config default library path if omitted (same as other ebk commands)
- Stdio transport (standard for Claude Code MCP servers)
- Opens Library, creates session, registers tools
- Clean shutdown closes Library

### Tool: `get_schema`

**Parameters:** None

**Returns:** JSON object describing:
- Tables with columns (name, type, nullable, primary key)
- Relationships (e.g., `books → authors` via `book_authors` junction)
- Enum-like constraints (e.g., `reading_status ∈ {unread, reading, read, abandoned}`)

**Purpose:** Gives the MCP client everything it needs to write correct SQL and understand what fields `update_books` accepts. Derived from SQLAlchemy model introspection — no manual maintenance needed when the schema changes.

**Junction table columns:** Association tables with semantic columns (e.g., `book_authors.role`, `book_authors.position`, `book_subjects.relevance_score`) are included in the schema output. These columns are not visible through SQLAlchemy relationship introspection alone, so the implementation must also enumerate association table columns explicitly.

### Tool: `execute_sql`

**Parameters:**
```json
{
  "sql": "SELECT b.title, a.name FROM books b JOIN book_authors ba ON ... WHERE ...",
  "params": ["optional", "bind", "params"]
}
```

**Returns:**
```json
{
  "columns": ["title", "name"],
  "rows": [["The Art of...", "Knuth"], ...],
  "row_count": 42
}
```

**Security:** 3-layer defense (reused from Views DSL):
1. Prefix check — must start with `SELECT` (case-insensitive, ignoring whitespace)
2. Read-only SQLite connection (`?mode=ro`)
3. `sqlite3.set_authorizer()` callback — whitelist `SQLITE_SELECT`, `SQLITE_READ`, `SQLITE_FUNCTION`

**Limits:** Row limit of 1000 (configurable). When the limit is hit, returns the first 1000 rows with `"truncated": true` in the response so the client knows the result is incomplete.

**Parameterized queries:** Positional binding via `?` placeholders. The `params` list provides values in order.

**Error handling:** SQL errors (syntax, authorizer denial, etc.) return `{"error": "message"}` with the SQLite error message for debuggability.

### Tool: `update_books`

**Parameters:**
```json
{
  "updates": {
    "42": {
      "title": "New Title",
      "rating": 4.5,
      "add_tags": ["Programming/Python", "Reference"],
      "remove_authors": ["Wrong Author"]
    },
    "43": {
      "reading_status": "read",
      "add_subjects": ["Machine Learning"]
    }
  }
}
```

**Scalar fields** (direct assignment):
- `title`, `subtitle`, `language`, `publisher`, `publication_date`, `description`
- `series`, `series_index`, `page_count`
- `rating` (0-5), `favorite` (bool), `reading_status` (enum), `reading_progress` (0-100)

**Collection operations** (prefix-based):
- `add_tags` / `remove_tags` — hierarchical tag paths
- `add_authors` / `remove_authors` — author names
- `add_subjects` / `remove_subjects` — subject names

**Special operations:**
- `merge_into: target_book_id` — merge this book into the target (combines files, metadata), then delete this book. **Mutually exclusive** with all other fields — if `merge_into` is present alongside other updates, return a validation error.

**PersonalMetadata fields:** `rating`, `favorite`, `reading_status`, and `reading_progress` live on the `PersonalMetadata` model, not `Book`. The implementation transparently creates or updates the associated `PersonalMetadata` record.

**Allowed fields:** Derived from the ORM model, not a hardcoded whitelist. Any column on `Book` or `PersonalMetadata` is a valid scalar target. The `get_schema` tool documents the complete set.

**Returns:**
```json
{
  "updated": [42, 43],
  "errors": {}
}
```

**Validation:** Rejects unknown fields. Type-checks values. Returns per-book errors without aborting the batch.

## Deletion Plan

### Remove entirely (~3,300 LOC)

| File | LOC | Reason |
|------|-----|--------|
| `ebk/ai/__init__.py` | 22 | Package root |
| `ebk/ai/metadata_enrichment.py` | 394 | Replaced by MCP + Claude Code |
| `ebk/ai/knowledge_graph.py` | 449 | Dead code (never imported) |
| `ebk/ai/semantic_search.py` | 432 | Dead code (never imported) |
| `ebk/ai/text_extractor.py` | 392 | Dead code (never imported) |
| `ebk/ai/question_generator.py` | 327 | Dead code (never imported) |
| `ebk/ai/reading_companion.py` | 223 | Dead code (never imported) |
| `ebk/ai/llm_providers/__init__.py` | 26 | Package root |
| `ebk/ai/llm_providers/base.py` | 299 | No longer needed |
| `ebk/ai/llm_providers/ollama.py` | 294 | No longer needed |
| `ebk/ai/llm_providers/anthropic.py` | 209 | No longer needed |
| `ebk/ai/llm_providers/gemini.py` | 245 | No longer needed |

### Remove `integrations/` LLM and old MCP code

| Path | Reason |
|------|--------|
| `integrations/mcp/ebk_mcp_server.py` | Old MCP server that wraps CLI via subprocess — replaced by new `ebk/mcp/` |
| `integrations/llm/` | Parallel LLM integration layer (Pydantic-based), unused by core package |
| `integrations/PLUGINS.md`, `integrations/README.md` | References to removed LLM functionality — update or remove |
| `docs/integrations/mcp.md` | Points to old MCP server — replace with new MCP docs |

### Remove from CLI (`cli.py`)

- `enrich` command (~160 lines)
- Related LLM provider imports
- `config` command LLM options (`--llm-provider`, `--llm-model`, `--llm-host`, `--llm-port`, `--llm-api-key`, `--llm-temperature`) and associated logic (~40 lines)

### Remove from config (`config.py`)

- `LLMConfig` dataclass and its section in the config file
- LLM parameters from `update_config()` function

### Remove from DB models

- `EnrichmentHistory` model (`db/models.py`) — built specifically for the AI enrichment pipeline. No longer needed since MCP clients manage their own enrichment workflow. Remove the model but do NOT add a migration to drop the table (existing databases keep it harmlessly).

### Remove from docs

- `docs/user-guide/llm-features.md` — delete entirely
- References to LLM/enrichment in: architecture, configuration, index, changelog
- `mkdocs.yml` — remove `integrations/mcp.md` nav entry, add new MCP docs

### Keep

- `ebk/services/text_extraction.py` — services-layer PDF/EPUB text extraction, used by import pipeline. Separate from the AI stub.

### Update

- `pyproject.toml` — remove AI-related optional dependencies, add `mcp` dependency
- `setup.py` — same treatment (legacy packaging file, may still be referenced)
- `CLAUDE.md` — remove references to AI features, `ebk enrich`, add MCP info
- Docs — new MCP documentation, updated architecture/config docs

### Update existing tests

- `tests/test_core_modules.py` — remove `TestLLMConfig` class and any assertions on `cfg.llm`

## Code Review Fixes (Bundled)

### #8: Export service test coverage

Add tests for:
- `export_goodreads_csv()` — verify column headers, field mapping, multi-author handling
- `export_calibre_csv()` — verify Calibre-specific format, tag serialization

### #9: DSL comparison logic refactor

Replace repeated operator dispatch (~75 lines) with an operator map:

```python
import operator as op

_COMPARISON_OPS = {
    'gte': op.ge, 'gt': op.gt,
    'lte': op.le, 'lt': op.lt,
    'eq': op.eq, 'ne': op.ne,
}
```

`_apply_comparison()` resolves the SQLAlchemy column per field, then applies `op_func(column, value)` once.

### #10: Compose transform override bug

**Bug:** Compose transform extracts bare `Book` objects from `TransformedBook` wrappers via `{tb.book for tb in result}`, discarding any previously applied overrides.

**Fix:** Refactor `_evaluate_transform()` to accept and return `List[TransformedBook]` instead of `Set[Book]`. Each subsequent transform in the compose chain receives the previous transform's output with overrides intact. This changes the signature of `_evaluate_transform` and its callers — a non-trivial but contained refactor within `dsl.py`.

### #12: Search parser edge cases

Add tests for:
- Nested parentheses: `"(python OR java) AND (advanced OR beginner)"`
- Colons in field values: `"title:C++:The Book"`
- Escaped/unbalanced quotes

## Dependencies

**Add:**
- `mcp>=1.0,<2.0` — MCP server protocol library (pin to major version to avoid breaking API changes)

**Remove (optional deps):**
- AI-specific optional dependencies no longer needed (check both `pyproject.toml` and `setup.py`)

## Testing Strategy

- **MCP tools:** Unit tests for each tool with a temporary library fixture
- **`execute_sql`:** Test authorizer blocks writes, parameterized queries work, row limits enforced
- **`update_books`:** Test scalar updates, collection add/remove, merge, validation errors, batch semantics
- **`get_schema`:** Test schema reflects actual model (prevents drift)
- **Integration:** End-to-end test: create library → add books → query via SQL → update via tool → verify

## Non-Goals

- Authentication/authorization on the MCP server (stdio transport implies local trust)
- Streaming/SSE transport (stdio is sufficient for Claude Code)
- Preserving backward compatibility with `ebk enrich` (clean removal)
