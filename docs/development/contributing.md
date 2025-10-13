# Contributing

Guide to contributing to ebk.

We welcome contributions! Whether you're fixing bugs, adding features, improving documentation, or reporting issues, your help is appreciated.

## Development Setup

### Prerequisites

- Python 3.10 or higher
- Git
- (Optional) Ollama for LLM features

### Setup Steps

```bash
# Clone the repository
git clone https://github.com/queelius/ebk.git
cd ebk

# Create virtual environment and install dependencies
make setup

# Or manually:
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e ".[dev,all]"
```

## Running Tests

```bash
# Run all tests
make test

# Run with coverage
make test-coverage

# Run specific test file
pytest tests/test_library_api.py -v

# Run unit tests only
pytest -m unit

# Run integration tests only
pytest -m integration
```

## Code Quality

```bash
# Run linters
make lint

# Format code
make format

# Check formatting
make format-check
```

## Making Changes

1. **Create a branch** for your changes:
   ```bash
   git checkout -b feature/my-new-feature
   ```

2. **Make your changes** following the project style:
   - Use type hints
   - Add docstrings to public APIs
   - Follow PEP 8 style guide
   - Keep functions focused and small

3. **Write tests** for new functionality:
   - Add unit tests in `tests/`
   - Aim for >80% code coverage
   - Test edge cases and error handling

4. **Update documentation**:
   - Update `/docs` for user-facing changes
   - Update docstrings for API changes
   - Add examples for new features

5. **Commit your changes**:
   ```bash
   git add .
   git commit -m "Add feature: brief description"
   ```

6. **Push and create PR**:
   ```bash
   git push origin feature/my-new-feature
   ```
   Then create a pull request on GitHub.

## Project Structure

```
ebk/
├── ebk/                    # Main package
│   ├── ai/                # AI/LLM features
│   ├── db/                # Database models
│   ├── services/          # Business logic
│   ├── cli.py            # CLI commands
│   ├── server.py         # Web server
│   └── config.py         # Configuration
├── tests/                 # Test suite
├── docs/                  # Documentation
└── integrations/          # Optional integrations
```

## Code Style Guidelines

- **Type Hints**: Use type hints for all function signatures
- **Docstrings**: Use Google-style docstrings
- **Naming**:
  - `snake_case` for functions and variables
  - `PascalCase` for classes
  - `UPPER_CASE` for constants
- **Line Length**: Maximum 100 characters
- **Imports**: Group standard library, third-party, and local imports

## Adding New Features

### Adding an LLM Provider

1. Create new file in `ebk/ai/llm_providers/`
2. Subclass `BaseLLMProvider`
3. Implement required methods
4. Add tests in `tests/ai/`
5. Update documentation

Example:
```python
from .base import BaseLLMProvider, LLMResponse

class MyProvider(BaseLLMProvider):
    @property
    def name(self) -> str:
        return "my_provider"

    async def complete(self, prompt: str, **kwargs) -> LLMResponse:
        # Implementation
        pass
```

### Adding a CLI Command

1. Add command function in `ebk/cli.py`
2. Use `@app.command()` decorator
3. Add type hints and help text
4. Load config defaults when appropriate
5. Update `docs/user-guide/cli.md`

### Adding Documentation

1. Add markdown files to appropriate `/docs` subdirectory
2. Update `mkdocs.yml` navigation
3. Follow existing documentation style
4. Include code examples
5. Test with `mkdocs serve`

## Reporting Issues

When reporting bugs, please include:

- ebk version (`ebk --version`)
- Python version
- Operating system
- Steps to reproduce
- Expected vs actual behavior
- Error messages and stack traces

## Feature Requests

For feature requests, please describe:

- The use case
- Why existing features don't suffice
- Proposed API or interface
- Any implementation ideas

## Questions?

- Open an issue on [GitHub](https://github.com/queelius/ebk/issues)
- Check existing [documentation](https://queelius.github.io/ebk/)
- Review [architecture documentation](architecture.md)

## License

By contributing, you agree that your contributions will be licensed under the project's MIT License.
