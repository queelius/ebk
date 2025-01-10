import json
import os
import streamlit as st
from io import BytesIO
from PIL import Image
import zipfile
import pandas as pd
import altair as alt
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_metadata(metadata_content: BytesIO) -> list:
    """
    Loads metadata from the uploaded JSON file.
    Returns a list of dictionaries.
    """
    try:
        data = json.load(metadata_content)
        logger.debug("Metadata loaded successfully.")
        return data
    except json.JSONDecodeError as e:
        st.error(f"JSON decoding error: {e}")
        logger.error(f"JSONDecodeError: {e}")
        return []
    except Exception as e:
        st.error(f"Unexpected error loading metadata.json: {e}")
        logger.error(f"Unexpected error: {e}")
        return []

def extract_zip(zip_bytes: BytesIO) -> dict:
    """
    Extracts a ZIP file in-memory and returns a dictionary of its contents.
    Keys are file names, and values are BytesIO objects containing the file data.
    """
    extracted_files = {}
    try:
        with zipfile.ZipFile(zip_bytes) as z:
            for file_info in z.infolist():
                if not file_info.is_dir():
                    with z.open(file_info) as f:
                        normalized_path = os.path.normpath(file_info.filename)
                        # Prevent files from being extracted outside the current directory
                        if os.path.commonprefix([normalized_path, os.path.basename(normalized_path)]) != "":
                            extracted_files[normalized_path] = BytesIO(f.read())
                            logger.debug(f"Extracted: {normalized_path}")
        logger.debug("ZIP archive extracted successfully.")
        return extracted_files
    except zipfile.BadZipFile:
        st.error("The uploaded file is not a valid ZIP archive.")
        logger.error("BadZipFile encountered.")
        return {}
    except Exception as e:
        st.error(f"Error extracting ZIP file: {e}")
        logger.error(f"Exception during ZIP extraction: {e}")
        return {}

def display_books_tab(filtered_df: pd.DataFrame, cover_images: dict, ebook_files: dict):
    """
    Displays the Books tab with book entries and download links.
    """
    st.subheader("📚 Book Entries")
    if not filtered_df.empty:
        for idx, row in filtered_df.iterrows():
            with st.expander(f"**{row.get('title', 'No Title')}**"):
                # Layout: Cover Image & Downloads | Metadata
                cols = st.columns([1.5, 3])

                # Left Column: Cover Image and Download Links
                with cols[0]:
                    # Cover Image
                    cover_path = row.get("cover_path", "")
                    cover_filename = os.path.basename(cover_path)
                    cover_data = cover_images.get(cover_filename)
                    if cover_data:
                        try:
                            image = Image.open(cover_data)
                            st.image(image, use_container_width=True, caption="🖼️ Cover")
                            logger.debug(f"Displayed cover image: {cover_filename}")
                        except Exception as e:
                            st.error(f"🖼️ Error loading image: {e}")
                            logger.error(f"Error loading image {cover_filename}: {e}")
                    else:
                        st.info("🖼️ No cover image available.")
                        logger.debug(f"No cover image available for {cover_filename}.")

                # Right Column: Metadata Details
                with cols[1]:
                    metadata_details = {
                        "📖 **Title**": row.get("title", "N/A"),
                        "👤 **Author(s)**": ", ".join(row.get("creators", ["N/A"])),
                        "📚 **Subjects**": ", ".join(row.get("subjects", ["N/A"])),
                        "📝 **Description**": row.get("description", "N/A"),
                        "🌐 **Language**": row.get("language", "N/A"),
                        "📅 **Publication Date**": row.get("date", "N/A") if pd.notna(row.get("date", None)) else "N/A",
                        "🔑 **Identifiers**": ", ".join([f"{k}: {v}" for k, v in row.get("identifiers", {}).items()])
                    }

                    for key, value in metadata_details.items():
                        st.markdown(f"{key}: {value}")

                    # Ebook Download Links
                    ebook_paths = row.get("file_paths", [])
                    if ebook_paths:
                        st.markdown("### 📥 Download Ebook(s)")
                        for ebook_path in ebook_paths:
                            ebook_filename = os.path.basename(ebook_path)
                            ebook_data = ebook_files.get(ebook_filename)
                            if ebook_data:
                                # Determine MIME type based on file extension
                                _, ext = os.path.splitext(ebook_filename.lower())
                                mime_types = {
                                    '.pdf': 'application/pdf',
                                    '.epub': 'application/epub+zip',
                                    '.mobi': 'application/x-mobipocket-ebook',
                                    '.azw3': 'application/vnd.amazon.ebook',
                                    '.txt': 'text/plain'
                                }
                                mime_type = mime_types.get(ext, 'application/octet-stream')

                                st.download_button(
                                    label=f"💾 {ebook_filename}",
                                    data=ebook_data.getvalue(),
                                    file_name=ebook_filename,
                                    mime=mime_type
                                )
                                logger.debug(f"Provided download button for {ebook_filename}.")
                            else:
                                st.warning(f"Ebook file '{ebook_filename}' not found in the uploaded ZIP.")
                                logger.warning(f"Ebook file '{ebook_filename}' not found in the uploaded ZIP.")
                    else:
                        st.info("📄 No ebook files available for download.")
                        logger.debug("No ebook files available for download.")

    else:
        st.info("📚 No books match the current filter criteria.")
        logger.debug("No books match the current filter criteria.")

def display_statistics_tab(filtered_df: pd.DataFrame):
    """
    Displays the Statistics tab with various visualizations.
    """
    st.subheader("📊 Statistics")

    if not filtered_df.empty:
        # Visualization: Books per Author (Top 10)
        st.markdown("### 📈 Top 10 Authors by Number of Books")
        author_counts = pd.Series([creator for creators in filtered_df['creators'] for creator in creators]).value_counts().nlargest(10).reset_index()
        author_counts.columns = ['Author', 'Number of Books']
        
        chart = alt.Chart(author_counts).mark_bar().encode(
            x=alt.X('Number of Books:Q', title='Number of Books'),
            y=alt.Y('Author:N', sort='-x', title='Author'),
            tooltip=['Author', 'Number of Books']
        ).properties(
            width=600,
            height=400
        )
        
        st.altair_chart(chart, use_container_width=True)
        logger.debug("Displayed Top 10 Authors chart.")

        # Visualization: Books per Subject (Top 10)
        st.markdown("### 📊 Top 10 Subjects by Number of Books")
        subject_counts = pd.Series([subject for subjects in filtered_df['subjects'] for subject in subjects]).value_counts().nlargest(10).reset_index()
        subject_counts.columns = ['Subject', 'Number of Books']
        
        subject_chart = alt.Chart(subject_counts).mark_bar().encode(
            x=alt.X('Number of Books:Q', title='Number of Books'),
            y=alt.Y('Subject:N', sort='-x', title='Subject'),
            tooltip=['Subject', 'Number of Books']
        ).properties(
            width=600,
            height=400
        )
        
        st.altair_chart(subject_chart, use_container_width=True)
        logger.debug("Displayed Top 10 Subjects chart.")

        # Visualization: Books Published Over Time
        st.markdown("### 📈 Books Published Over Time")
        if 'date' in filtered_df.columns and pd.api.types.is_numeric_dtype(filtered_df['date']):
            publication_years = filtered_df['date'].dropna().astype(int)
            if not publication_years.empty:
                year_counts = publication_years.value_counts().sort_index().reset_index()
                year_counts.columns = ['Year', 'Number of Books']
                
                time_chart = alt.Chart(year_counts).mark_line(point=True).encode(
                    x=alt.X('Year:O', title='Year'),
                    y=alt.Y('Number of Books:Q', title='Number of Books'),
                    tooltip=['Year', 'Number of Books']
                ).properties(
                    width=800,
                    height=400
                )
                
                st.altair_chart(time_chart, use_container_width=True)
                logger.debug("Displayed Books Published Over Time chart.")
            else:
                st.info("📅 No publication date data available.")
                logger.warning("Publication year data is empty after filtering.")
        else:
            st.info("📅 Publication date data is not available or not in a numeric format.")
            logger.warning("Publication date data is not available or not numeric.")
    else:
        st.info("📊 No statistics to display as no books match the current filter criteria.")
        logger.debug("No statistics to display due to empty filtered DataFrame.")

def display_dashboard(metadata_list: list, cover_images: dict, ebook_files: dict):
    """
    Displays the main dashboard with advanced filtering and a compact UI layout using tabs.
    """
    # Convert metadata list to DataFrame for easier filtering
    df = pd.DataFrame(metadata_list)
    logger.debug("Converted metadata list to DataFrame.")

    # List of columns that should contain lists
    list_columns = ['creators', 'subjects', 'file_paths']

    def ensure_list(column):
        """
        Ensures that each entry in the column is a list. If not, replaces it with an empty list.
        """
        return column.apply(lambda x: x if isinstance(x, list) else [])

    # Apply the ensure_list function to relevant columns
    for col in list_columns:
        if col in df.columns:
            df[col] = ensure_list(df[col])
            logger.debug(f"Processed list column: {col}")
        else:
            # If the column doesn't exist, create it with empty lists
            df[col] = [[] for _ in range(len(df))]
            logger.debug(f"Created empty list column: {col}")

    # Handle 'identifiers' column separately
    if 'identifiers' in df.columns:
        df['identifiers'] = df['identifiers'].apply(lambda x: x if isinstance(x, dict) else {})
        logger.debug("Sanitized 'identifiers' column to ensure all entries are dictionaries.")
    else:
        df['identifiers'] = [{} for _ in range(len(df))]
        logger.debug("Created empty 'identifiers' column.")

    # Sanitize the 'language' column: replace NaN with empty strings and ensure all entries are strings
    if 'language' in df.columns:
        df['language'] = df['language'].apply(lambda x: x if isinstance(x, str) else '').fillna('').astype(str)
        logger.debug("Sanitized 'language' column.")
    else:
        df['language'] = ['' for _ in range(len(df))]
        logger.debug("Created empty 'language' column.")

    # Sanitize the 'cover_path' column: replace NaN or non-string with empty strings
    if 'cover_path' in df.columns:
        df['cover_path'] = df['cover_path'].apply(lambda x: x if isinstance(x, str) else '').fillna('').astype(str)
        logger.debug("Sanitized 'cover_path' column.")
    else:
        df['cover_path'] = ['' for _ in range(len(df))]
        logger.debug("Created empty 'cover_path' column.")

    # Sanitize other string fields: 'title', 'description'
    string_fields = ['title', 'description']
    for field in string_fields:
        if field in df.columns:
            df[field] = df[field].apply(lambda x: x if isinstance(x, str) else '').fillna('').astype(str)
            logger.debug(f"Sanitized '{field}' column.")
        else:
            df[field] = ['' for _ in range(len(df))]
            logger.debug(f"Created empty '{field}' column.")

    # Sanitize 'date' column: ensure it's numeric, else set to None
    if 'date' in df.columns:
        df['date'] = pd.to_numeric(df['date'], errors='coerce')
        logger.debug("Sanitized 'date' column to ensure all entries are numeric.")
    else:
        df['date'] = [None for _ in range(len(df))]
        logger.debug("Created empty 'date' column.")

    # Sidebar for Advanced Filters
    st.sidebar.header("🔍 Advanced Filters")

    # Title Search
    title_search = st.sidebar.text_input("🔎 Search by Title")

    # Author Filter (Multi-select)
    all_creators = sorted(set(creator for creators in df['creators'] for creator in creators))
    selected_authors = st.sidebar.multiselect("👤 Filter by Author(s)", all_creators, default=[])

    # Subjects Filter (Multi-select)
    all_subjects = sorted(set(subject for subjects in df['subjects'] for subject in subjects))
    selected_subjects = st.sidebar.multiselect("📚 Filter by Subject(s)", all_subjects, default=[])

    # Language Filter (Multi-select)
    all_languages = sorted(set(lang for lang in df['language'] if lang))
    selected_languages = st.sidebar.multiselect("🌐 Filter by Language(s)", all_languages, default=[])

    # Publication Date Filter (Range Slider)
    selected_years = None
    if 'date' in df.columns and pd.api.types.is_numeric_dtype(df['date']):
        min_year = df['date'].min()
        max_year = df['date'].max()
        if pd.notna(min_year) and pd.notna(max_year):
            min_year = int(min_year)
            max_year = int(max_year)
            selected_years = st.sidebar.slider("📅 Publication Year Range", min_year, max_year, (min_year, max_year))
            logger.debug(f"Publication year range: {selected_years}")
        else:
            st.sidebar.info("📅 No valid publication year data available.")
            logger.warning("Publication year data is not available or entirely NaN.")
    else:
        st.sidebar.info("📅 Publication date data is not available or not in a numeric format.")
        logger.warning("Publication date data is not available or not numeric.")

    # Identifier Search
    identifier_search = st.sidebar.text_input("🔑 Search by Identifier (e.g., ISBN)")

    # Apply Filters
    filtered_df = df.copy()

    if title_search:
        filtered_df = filtered_df[filtered_df['title'].str.contains(title_search, case=False, na=False)]
        logger.debug(f"Applied title search filter: '{title_search}'")

    if selected_authors:
        filtered_df = filtered_df[filtered_df['creators'].apply(lambda x: any(creator in selected_authors for creator in x))]
        logger.debug(f"Applied author filter: {selected_authors}")

    if selected_subjects:
        filtered_df = filtered_df[filtered_df['subjects'].apply(lambda x: any(subject in selected_subjects for subject in x))]
        logger.debug(f"Applied subject filter: {selected_subjects}")

    if selected_languages:
        filtered_df = filtered_df[filtered_df['language'].isin(selected_languages)]
        logger.debug(f"Applied language filter: {selected_languages}")

    if selected_years:
        filtered_df = filtered_df[(filtered_df['date'] >= selected_years[0]) & (filtered_df['date'] <= selected_years[1])]
        logger.debug(f"Applied publication year range filter: {selected_years}")

    if identifier_search:
        # Assuming identifiers are stored as dictionaries
        filtered_df = filtered_df[filtered_df['identifiers'].apply(
            lambda ids: any(identifier_search.lower() in str(v).lower() for k, v in ids.items())
        )]
        logger.debug(f"Applied identifier search filter: '{identifier_search}'")

    # Create Tabs
    tabs = st.tabs(["📚 Books", "📊 Statistics"])

    with tabs[0]:
        # Display Books
        display_books_tab(filtered_df, cover_images, ebook_files)

    with tabs[1]:
        # Display Statistics
        display_statistics_tab(filtered_df)

    # Optional: Add Footer or Additional Information
    st.markdown("---")
    st.write("Developed with ❤️ using Streamlit.")

def main():
    st.set_page_config(page_title="Calibre Metadata Dashboard", layout="wide")
    st.title("📚 Calibre Metadata Dashboard")
    st.write("""
    Upload a **ZIP archive** containing your `metadata.json`, all associated cover images, and ebook files.
    The app will automatically process and display your library with advanced search and filtering options.
    """)

    # Sidebar for Instructions
    st.sidebar.header("📝 Instructions")
    st.sidebar.write("""
    1. **Prepare a ZIP Archive** containing:
       - `metadata.json` at the root.
       - All cover images referenced in `metadata.json`.
       - All ebook files referenced in `metadata.json`.
    2. **Upload the ZIP Archive** using the uploader below.
    3. **Use the Sidebar** to apply advanced filters and search your library.
    4. **Interact** with the dashboard to view details and download ebooks.
    """)

    # File uploader for ZIP archive
    st.subheader("📁 Upload ZIP Archive")
    zip_file = st.file_uploader(
        label="Upload a ZIP file containing `metadata.json`, cover images, and ebook files",
        type=["zip"],
        key="zip_upload"
    )

    # File size limit (e.g., 200 MB)
    MAX_ZIP_SIZE = 200 * 1024 * 1024  # 200 MB

    if zip_file:
        if zip_file.size > MAX_ZIP_SIZE:
            st.error("❌ Uploaded ZIP file is too large. Please upload a ZIP file smaller than 200 MB.")
            logger.error("Uploaded ZIP file exceeds the size limit.")
            st.stop()

        with st.spinner("🔄 Extracting and processing ZIP archive..."):
            extracted_files = extract_zip(zip_file)
        if not extracted_files:
            logger.error("No files extracted from the ZIP archive.")
            st.stop()  # Stop if extraction failed

        # Locate metadata.json (case-insensitive search)
        metadata_key = next((k for k in extracted_files if os.path.basename(k).lower() == "metadata.json"), None)
        if not metadata_key:
            st.error("❌ `metadata.json` not found in the uploaded ZIP archive.")
            logger.error("`metadata.json` not found in the uploaded ZIP archive.")
            st.stop()

        metadata_content = extracted_files[metadata_key]
        metadata_list = load_metadata(metadata_content)
        if not metadata_list:
            logger.error("Failed to load metadata from `metadata.json`.")
            st.stop()

        # Collect cover images and ebook files
        cover_images = {}
        ebook_files = {}
        for filename, file_bytes in extracted_files.items():
            lower_filename = filename.lower()
            basename = os.path.basename(filename)
            if lower_filename.endswith(('.jpg', '.jpeg', '.png')):
                cover_images[basename] = file_bytes
                logger.debug(f"Added cover image: {basename}")
            elif lower_filename.endswith(('.pdf', '.epub', '.mobi', '.azw3', '.txt')):
                ebook_files[basename] = file_bytes
                logger.debug(f"Added ebook file: {basename}")
            else:
                # Ignore other file types or handle as needed
                logger.debug(f"Ignored unsupported file type: {basename}")
                pass

        # Inform user about unmatched cover images
        expected_covers = {os.path.basename(md.get("cover_path", "")) for md in metadata_list if md.get("cover_path")}
        uploaded_covers = set(cover_images.keys())
        missing_covers = expected_covers - uploaded_covers
        if missing_covers:
            st.warning(f"⚠️ The following cover images are referenced in `metadata.json` but were not uploaded: {', '.join(missing_covers)}")
            logger.warning(f"Missing cover images: {missing_covers}")

        # Inform user about unmatched ebook files
        expected_ebooks = {os.path.basename(path) for md in metadata_list for path in md.get("file_paths", [])}
        uploaded_ebooks = set(ebook_files.keys())
        missing_ebooks = expected_ebooks - uploaded_ebooks
        if missing_ebooks:
            st.warning(f"⚠️ The following ebook files are referenced in `metadata.json` but were not uploaded: {', '.join(missing_ebooks)}")
            logger.warning(f"Missing ebook files: {missing_ebooks}")

        # Display the dashboard with metadata and cover images
        display_dashboard(metadata_list, cover_images, ebook_files)
    else:
        st.info("📥 Please upload a ZIP archive to get started.")
        logger.debug("No ZIP archive uploaded yet.")

if __name__ == "__main__":
    main()
