import streamlit as st
from utils import load_json, save_json, search_metadata, slugify
from pathlib import Path

# Configuration
DATA_FILE = "library.json"

# Load data
@st.cache_data
def load_library(file_path):
    """Load the eBook library JSON file."""
    return load_json(file_path)

@st.cache_data
def save_library_data(data, file_path):
    """Save library data to JSON."""
    save_json(data, file_path)

# Main App
st.title("📚 eBook Library Dashboard")

# Sidebar: File Selector
file_path = st.sidebar.text_input("Library JSON File Path", DATA_FILE)
if not Path(file_path).exists():
    st.sidebar.error(f"File not found: {file_path}")
    st.stop()

# Load the library
library = load_library(file_path)

# Tabs for browsing, searching, and editing
tab1, tab2, tab3 = st.tabs(["Browse Library", "Search Books", "Edit Metadata"])

# Tab 1: Browse Library
with tab1:
    st.header("Browse Library")
    for book in library:
        st.subheader(book["Title"])
        st.text(f"Author: {book['Author']}")
        st.text(f"Tags: {book['Tags']}")
        if "Cover Path" in book and Path(book["Cover Path"]).exists():
            st.image(book["Cover Path"], width=150)
        st.markdown(f"[📖 Open eBook]({book['File Path']})", unsafe_allow_html=True)
        st.write("---")

# Tab 2: Search Books
with tab2:
    st.header("Search Books")
    query = st.text_input("Search Query", "")
    if query:
        results = search_metadata(library, query)
        st.write(f"Found {len(results)} results for '{query}':")
        for book in results:
            st.subheader(book["Title"])
            st.text(f"Author: {book['Author']}")
            st.text(f"Tags: {book['Tags']}")
            if "Cover Path" in book and Path(book["Cover Path"]).exists():
                st.image(book["Cover Path"], width=150)
            st.markdown(f"[📖 Open eBook]({book['File Path']})", unsafe_allow_html=True)
            st.write("---")

# Tab 3: Edit Metadata
with tab3:
    st.header("Edit Metadata")
    selected_book = st.selectbox("Select a Book", [book["Title"] for book in library])
    if selected_book:
        book = next(b for b in library if b["Title"] == selected_book)
        title = st.text_input("Title", book["Title"])
        author = st.text_input("Author", book["Author"])
        tags = st.text_input("Tags", book["Tags"])
        if st.button("Save Changes"):
            book.update({"Title": title, "Author": author, "Tags": tags})
            save_library_data(library, file_path)
            st.success("Book metadata updated!")

# Footer
st.sidebar.write("---")
st.sidebar.write("📘 Developed by Alex Towell")
