from setuptools import setup, find_packages
from pathlib import Path

# Read the README file for the long description
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()

setup(
    name="ebk",
    version="0.2.0",
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
            #"ebk=ebk.cli:main"
        ]
    },
    install_requires=[
        "streamlit",
        "lxml",
        "pandas",
        "slugify",
        "pyyaml",
        "pathlib",
        "PyPDF2",
        "ebooklib",
        "altair",
        "Pillow"
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.10',
    include_package_data=True,  # Include non-Python files specified in MANIFEST.in
    package_data={
        "ebk.streamlit": ["*"],  # Include all files in the streamlit subpackage
    },
)
