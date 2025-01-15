import streamlit as st
import pandas as pd
import os
import logging
from utils import load_metadata, extract_zip
from filters import sanitize_dataframe, create_filters
from display import display_books_tab, display_statistics_tab

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

#def display_footer():
#    st.markdown("---")
#    st.write("Developed with ❤️ using Streamlit.")

def display_dashboard(metadata_list: list, cover_images: dict, ebook_files: dict):
    """
    Displays the main dashboard with advanced filtering and a compact UI layout using tabs.
    """
    # Convert metadata list to DataFrame
    df = pd.DataFrame(metadata_list)
    logger.debug("Converted metadata list to DataFrame.")

    # Sanitize DataFrame
    df = sanitize_dataframe(df)
    logger.debug("Sanitized DataFrame.")

    # Apply Filters
    filtered_df = create_filters(df)
    logger.debug("Applied filters to DataFrame.")

    # Create Tabs
    tabs = st.tabs(["📚 Books", "📊 Statistics"])

    with tabs[0]:
        # Display Books
        display_books_tab(filtered_df, cover_images, ebook_files)

    with tabs[1]:
        # Display Statistics
        display_statistics_tab(filtered_df)

    # Display Footer
    # display_footer()

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
    1. **Prepare a ZIP Archive** of an ebk library using the following process:
       - Go to the directory containing the desired ebk library (should have 'metadata.json` and associated files).
       - Compress the directory into a ZIP archive.
            - The `ebk` CLI tool can also autoatically output a ZIP archive,
              e.g., `ebk import calibre <calibre-library> --output.zip`.
    2. **Upload the ZIP Archive** using the uploader below.
    3. **Use the Sidebar** to apply filters and search your library.
    4. **Interact** with the dashboard to view details and download ebooks.
    """)

    # File uploader for ZIP archive
    st.subheader("📁 Upload ZIP Archive")
    zip_file = st.file_uploader(
        label="Upload a ZIP file containing `metadata.json`, cover images, and ebook files",
        type=["zip"],
        key="zip_upload"
    )

    MAX_ZIP_SIZE = 8 * 1024 * 1024 * 1024  # 1 GB

    if zip_file:
        if zip_file.size > MAX_ZIP_SIZE:
            st.error(f"❌ Uploaded ZIP file is {zip_file.size / 1024 / 1024 / 1024:.2f} GB, which exceeds the size limit of 1 GB.")
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
