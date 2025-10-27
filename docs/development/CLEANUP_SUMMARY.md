# Project Root Cleanup Summary

This document summarizes the cleanup performed on the project root directory on 2025-10-27.

## Changes Made

### 1. Documentation Organization
**Moved to `/docs/development/`:**
- AI_FEATURES.md
- CODE_REVIEW.md
- DESIGN_PLAN.md
- PLUGIN_ARCHITECTURE.md
- PYTHONIC_API.md
- ROADMAP.md
- TESTS_QUICK_REFERENCE.md
- TEST_DESIGN_SUMMARY.md

**Kept in root:**
- README.md (project readme)
- CLAUDE.md (Claude Code instructions)

### 2. Utility Scripts Organization
**Moved to `/scripts/`:**
- apply_decorators.py
- check_coverage.py
- fix_all_indentation.py
- fix_cli_indents.py

### 3. Requirements Files Cleanup
**Kept:**
- requirements-core.txt (clean dependency list with version specifiers)

**Archived to `/archive/`:**
- requirements.txt (frozen pip output with unrelated dependencies)
- requirements2.txt (frozen pip output with unrelated dependencies)

### 4. Legacy Code Archived
**Moved to `/archive/`:**
- legacy/ (old code: merge.py, personal.py, utils.py, imports/)
- test_fluent_api/ (old test directory)
- test.png (test file, actually JSON data)

### 5. .gitignore Updates
**Added:**
- site/ (MkDocs build output)
- archive/ (archived files)

**Already present:**
- htmlcov/ (coverage HTML reports)
- build/, dist/, *.egg-info/ (build artifacts)

## Current Root Directory Structure

```
ebk/
├── README.md                # Project documentation
├── CLAUDE.md               # Claude Code instructions
├── LICENSE                 # License file
├── Makefile                # Build automation
├── pyproject.toml          # Modern Python packaging
├── setup.py                # Python packaging (legacy)
├── mkdocs.yml              # Documentation configuration
├── requirements-core.txt   # Core dependencies
├── environment.yml         # Conda environment
├── archive/                # Archived legacy files (gitignored)
├── docs/                   # MkDocs documentation
├── ebk/                    # Main package
├── examples/               # Example code
├── integrations/           # Optional integrations
├── scripts/                # Utility scripts
└── tests/                  # Test suite
```

## Rationale

The cleanup follows Python project best practices:
- Documentation goes in /docs
- Utility scripts go in /scripts
- Tests stay in /tests
- Build artifacts are gitignored
- Only essential files remain in root
- Legacy/archived code goes in /archive (gitignored)

## What Was NOT Changed

- All source code (ebk/ package)
- All tests (tests/ directory)
- Build configuration (pyproject.toml, setup.py, Makefile)
- Existing docs structure (docs/ subdirectories)
- Examples and integrations directories
