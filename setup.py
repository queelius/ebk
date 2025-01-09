from setuptools import setup, find_packages

setup(
    name="ebk",
    version="0.1.0",
    description="A lightweight tool for managing eBook metadata",
    author="Alex Towell",
    author_email="lex@metafunctor.com",
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "ebooklib=cli:main"
        ]
    },
    install_requires=[
        "streamlit",
        "lxml",
    ],
)
