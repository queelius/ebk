from setuptools import setup, find_packages
from pathlib import Path

# Read the README file for the long description
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()

setup(
    name="ebk",
    version="0.3.0",
    description="A lightweight tool for managing eBook metadata",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Alex Towell",
    author_email="lex@metafunctor.com",
    url="https://github.com/queelius/ebk",
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "ebk=ebk.cli:app"
        ],
    },
    install_requires=[
        # Core dependencies only
        "typer>=0.9.0",
        "rich>=13.0.0",
        "lxml>=4.9.0",
        "python-slugify>=8.0.0",
        "pyyaml>=6.0",
        "pypdf>=3.0.0",  # Modern PDF library
        "PyMuPDF>=1.23.0",  # For advanced PDF processing (fitz)
        "ebooklib>=0.18",
        "Pillow>=10.0.0",
        "jmespath>=1.0.0",
        "jinja2>=3.0.0",
        "xmltodict>=0.13.0"
    ],
    extras_require={
        # Optional dependencies for integrations
        "streamlit": [
            "streamlit>=1.28.0",
            "pandas>=2.0.0",
            "altair>=5.0.0"
        ],
        # Metadata extractors
        "metadata": [
            "aiohttp>=3.8.0",  # For API calls
        ],
        "google-books": [
            "aiohttp>=3.8.0",
        ],
        # Network analysis
        "network": [
            # Basic network analysis (no heavy deps)
        ],
        "network-advanced": [
            "networkx>=3.0",
            "matplotlib>=3.5.0",
            "pyvis>=0.3.0",
        ],
        # AI integrations (future)
        "ai": [
            "openai>=1.0.0",
            "anthropic>=0.7.0",
            "transformers>=4.30.0",
        ],
        # Legacy alias for viz -> network
        "viz": [
            "matplotlib>=3.5.0",
            "networkx>=3.0",
            "pyvis>=0.3.0",
            "plotly>=5.0.0",
            "seaborn>=0.12.0"
        ],
        "mcp": [
            "mcp>=0.1.0"
        ],
        "all": [
            # Include all optional dependencies
            "streamlit>=1.28.0",
            "pandas>=2.0.0", 
            "altair>=5.0.0",
            "matplotlib>=3.5.0",
            "networkx>=3.0",
            "pyvis>=0.3.0",
            "plotly>=5.0.0",
            "seaborn>=0.12.0",
            "mcp>=0.1.0"
        ],
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "black>=23.0.0",
            "isort>=5.0.0",
            "flake8>=6.0.0",
            "mypy>=1.0.0",
            "pylint>=2.0.0",
            "pre-commit>=3.0.0",
            "mkdocs>=1.5.0",
            "mkdocs-material>=9.0.0",
            "mkdocstrings[python]>=0.24.0",
            "pymdown-extensions>=10.0",
            "twine>=4.0.0",
            "build>=0.10.0"
        ]
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9", 
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: End Users/Desktop",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Text Processing :: Markup",
    ],
    python_requires='>=3.8',
    include_package_data=True,
    package_data={
        "ebk": ["exports/templates/**/*"],
    },
)