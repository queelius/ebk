from setuptools import setup, find_packages
from pathlib import Path

# Read the README file for the long description
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()

setup(
    name="book-memex",
    version="0.5.1",
    description="book-memex - a lightweight tool for managing eBook metadata (renamed from ebk)",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Alex Towell",
    author_email="lex@metafunctor.com",
    url="https://github.com/queelius/ebk",
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "book-memex=book_memex.cli:app",
            "ebk=book_memex._ebk_alias:main",
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
        "jinja2>=3.0.0",
        "xmltodict>=0.13.0"
    ],
    extras_require={
        "mcp": [
            "mcp>=1.0,<2.0",
            "pydantic>=2.0.0",
        ],
        "all": [
            "mcp>=1.0,<2.0",
            "pydantic>=2.0.0",
        ],
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "black>=23.0.0",
            "ruff>=0.1.0",
            "mypy>=1.0.0",
            "pre-commit>=3.0.0",
            "mkdocs>=1.5.0",
            "mkdocs-material>=9.0.0",
            "mkdocstrings[python]>=0.24.0",
            "twine>=4.0.0",
            "build>=0.10.0",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: End Users/Desktop",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Text Processing :: Markup",
    ],
    python_requires='>=3.10',
    include_package_data=True,
    package_data={
        "book_memex": ["exports/templates/**/*"],
    },
)