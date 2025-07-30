# Installation

## Requirements

- Python 3.10 or higher
- pip package manager

## Basic Installation

Install the core ebk package:

```bash
pip install ebk
```

## Installation with Optional Features

### Web Dashboard
```bash
pip install ebk[streamlit]
```

### Visualization Tools
```bash
pip install ebk[viz]
```

### All Features
```bash
pip install ebk[all]
```

### Development Installation
```bash
pip install ebk[dev]
```

## Installing from Source

1. Clone the repository:
```bash
git clone https://github.com/queelius/ebk.git
cd ebk
```

2. Create a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install in development mode:
```bash
pip install -e ".[dev]"
```

## Using the Makefile

The project includes a Makefile for common development tasks:

```bash
# Set up complete development environment
make setup

# Run tests
make test

# Check code coverage
make test-coverage

# Format code
make format

# Run linting
make lint
```

## Verifying Installation

Check that ebk is installed correctly:

```bash
ebk --version
ebk --help
```

## Next Steps

- Follow the [Quick Start Guide](quickstart.md) to create your first library
- Read about [Configuration](configuration.md) options
- Explore the [CLI Reference](../user-guide/cli.md)