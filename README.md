# ebk

![ebk Logo](https://github.com/queelius/ebk/blob/main/logo.png?raw=true)

**ebk** is a lightweight and versatile tool for managing eBook metadata. It allows users to convert Calibre libraries to JSON, manage and merge multiple libraries, export metadata to Hugo-compatible Markdown files, and interact with your library through a user-friendly Streamlit dashboard.

## Table of Contents

- [ebk](#ebk)
  - [Table of Contents](#table-of-contents)
  - [Features](#features)
  - [Installation](#installation)
  - [Usage](#usage)
    - [Command-Line Interface (CLI)](#command-line-interface-cli)
      - [Convert Calibre Library](#convert-calibre-library)
      - [Export to Hugo](#export-to-hugo)
      - [Launch Streamlit Dashboard](#launch-streamlit-dashboard)
    - [Streamlit Dashboard](#streamlit-dashboard)
  - [Library Management](#library-management)
  - [Merging Libraries](#merging-libraries)
    - [Usage](#usage-1)
  - [Identifying Library Entries](#identifying-library-entries)
  - [Contributing](#contributing)
  - [License](#license)
  - [🛠️ **Known Issues \& TODOs**](#️-known-issues--todos)
  - [📣 **Stay Updated**](#-stay-updated)
  - [🤝 **Support**](#-support)

## Features

- **Convert Calibre Libraries**: Transform your Calibre library into a structured JSON format.
- **Export to Hugo**: Generate Hugo-compatible Markdown files for seamless integration into static sites.
- **Streamlit Dashboard**: Interactive web interface for browsing, filtering, and managing your eBook library.
- **Library Management**: Add, update, delete, and search for books within your JSON library.
- **Merge Libraries**: Combine multiple eBook libraries with support for set operations like union and intersection.
- **Consistent Entry Identification**: Ensures unique and consistent identification of library entries across different libraries.

## Installation

Ensure you have [Python](https://www.python.org/) installed (version 3.7 or higher recommended).

1. **Clone the Repository**

   ```bash
   git clone https://github.com/queelius/ebk.git
   cd ebk
   ```

2. **Install Dependencies**

   It's recommended to use a virtual environment:

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

   Install the required packages:

   ```bash
   pip install -r requirements.txt
   ```

3. **Install ebk Package**

   ```bash
   pip install .
   ```

## Usage

ebk provides both a Command-Line Interface (CLI) and a Streamlit-based web dashboard for interacting with your eBook libraries.

### Command-Line Interface (CLI)

After installation, you can access the CLI using the `ebk` command.

#### Convert Calibre Library

Convert your existing Calibre library into a JSON format.

```bash
ebk convert-calibre /path/to/calibre/library /path/to/output/folder
```

- **Arguments**:
  - `/path/to/calibre/library`: Path to your Calibre library directory.
  - `/path/to/output/folder`: Destination folder where the JSON metadata and copied eBooks will be stored.

#### Export to Hugo

Export your JSON library to Hugo-compatible Markdown files, ready for static site integration.

```bash
ebk export /path/to/metadata.json /path/to/hugo/site
```

- **Arguments**:
  - `/path/to/metadata.json`: Path to your JSON metadata file.
  - `/path/to/hugo/site`: Path to your Hugo site directory.

#### Launch Streamlit Dashboard

Start the interactive Streamlit dashboard to browse and manage your eBook library.

```bash
ebk dash --port 8501
```

- **Options**:
  - `--port`: (Optional) Specify the port for the Streamlit app. Defaults to `8501`.

### Streamlit Dashboard

The Streamlit dashboard provides an intuitive web interface for interacting with your eBook library.

1. **Upload a ZIP Archive**

   Prepare a ZIP archive containing:
   
   - `metadata.json` at the root.
   - All cover images referenced in `metadata.json`.
   - All eBook files referenced in `metadata.json`.

   Use the uploader in the dashboard to upload this ZIP archive.

2. **Advanced Filtering**

   Utilize the sidebar to apply advanced filters based on:
   
   - **Title**: Search by book title.
   - **Authors**: Filter by one or multiple authors.
   - **Subjects**: Filter by subjects or genres.
   - **Language**: Filter by language.
   - **Publication Year**: Select a range of publication years.
   - **Identifiers**: Search by unique identifiers like ISBN.

3. **Browse Books**

   - **Books Tab**: View detailed entries of your eBooks, including cover images, metadata, and download/view links.
   - **Statistics Tab**: Visualize your library with charts showing top authors, subjects, and publication trends.

4. **Download eBooks**

   - **View**: For supported formats like PDF and EPUB, view the eBook directly in the browser.
   - **Download**: Download eBooks in their respective formats.

## Library Management

Manage your eBook library using the `LibraryManager` class, which provides functionalities to:

- **List Books**: Retrieve a list of all books in the library.
- **Search Books**: Search for books by title, author, or tags.
- **Add Book**: Add new books to the library.
- **Delete Book**: Remove books from the library by title.
- **Update Book**: Modify metadata of existing books.

## Merging Libraries

Combine multiple eBook libraries into a single consolidated library with support for set operations:

- **Union**: Combine all unique eBooks from multiple libraries.
- **Intersection**: Retain only eBooks present in all selected libraries.
- **Set-Difference**: Remove eBooks present in one library from another.
- **Tagged Unions**: Merge libraries with tagging for better organization.

### Usage

```bash
ebk merge /path/to/library1 /path/to/library2 /path/to/merged_library
```

- **Arguments**:
  - `/path/to/library1`, `/path/to/library2`: Paths to the source library folders.
  - `/path/to/merged_library`: Destination folder for the merged library.

## Identifying Library Entries

To ensure consistent and unique identification of library entries across different libraries, `ebk` employs the following strategies:

1. **Unique Base Naming**: Each eBook is assigned a base name derived from a slugified combination of the title, first author, and a unique identifier (e.g., UUID or ISBN).

2. **Ebook Identification**: eBooks are identified either by their filename or by a hash of their contents, ensuring that duplicate files are correctly handled during operations like merging.

3. **Set-Theoretic Operations**: When performing set operations (union, intersection, etc.), eBooks are matched based on their unique identifiers to maintain consistency and avoid duplication.

## Contributing

Contributions are welcome! Whether it's fixing bugs, improving documentation, or adding new features, your support is greatly appreciated.

1. **Fork the Repository**

2. **Create a New Branch**

   ```bash
   git checkout -b feature/YourFeature
   ```

3. **Make Your Changes**

4. **Commit Your Changes**

   ```bash
   git commit -m "Add YourFeature"
   ```

5. **Push to the Branch**

   ```bash
   git push origin feature/YourFeature
   ```

6. **Open a Pull Request**

## License

Distributed under the MIT License. See [LICENSE](https://github.com/queelius/ebk/blob/main/LICENSE) for more information.

---

## 🛠️ **Known Issues & TODOs**

1. **Exporter Module (`exporter.py`)**
   - **Current Status**: Basic functionality implemented for exporting JSON metadata to Hugo-compatible Markdown files.
   - **To Do**:
     - **Error Handling**: Replace `os.system` calls with Python's `shutil` for copying files to enhance security and reliability.
     - **Metadata Fields**: Ensure all necessary metadata fields are accurately mapped to Hugo's front matter.
     - **Support for Additional Formats**: Extend support for more eBook formats and metadata nuances.

2. **Merger Module (`merge.py`)**
   - **Current Status**: Implements basic merging of multiple libraries by copying files and consolidating metadata.
   - **To Do**:
     - **Set-Theoretic Operations**: Implement union, intersection, set-difference, and tagged unions to provide flexible merging capabilities.
     - **Conflict Resolution**: Develop strategies to handle conflicts when merging metadata from different sources.
     - **Performance Optimization**: Enhance the module to efficiently handle large libraries.

3. **Consistent Entry Identification**
   - **Current Status**: Utilizes a combination of slugified title, author, and unique identifier for base naming.
   - **To Do**:
     - **Hash-Based Identification**: Incorporate hashing of eBook contents to uniquely identify files, ensuring accurate deduplication.
     - **Multiple eBooks per Entry**: Refine the identification system to handle entries with multiple associated eBook files seamlessly.
     - **Metadata Consistency**: Ensure that all metadata across merged libraries maintains consistency in naming and formatting.

---

## 📣 **Stay Updated**

For the latest updates, feature releases, and more, follow the [GitHub Repository](https://github.com/queelius/ebk).

---

## 🤝 **Support**

If you encounter any issues or have suggestions for improvements, please open an issue on the [GitHub Repository](https://github.com/queelius/ebk/issues).

---

Happy eBook managing! 📚✨