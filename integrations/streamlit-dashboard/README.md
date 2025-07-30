# ebk Streamlit Dashboard

A web-based interface for browsing and managing ebk libraries.

## Overview

This Streamlit dashboard provides an interactive way to explore your ebook library with features like:
- Visual library browsing with cover images
- Advanced filtering and search
- Library statistics and visualizations
- Direct ebook downloads
- JMESPath queries for power users

## Installation

### Option 1: Standalone Installation

```bash
# Clone just the dashboard
git clone https://github.com/queelius/ebk.git
cd ebk/integrations/streamlit-dashboard

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Option 2: With ebk Installation

```bash
# Install ebk with streamlit extras
pip install ebk[streamlit]
```

## Usage

### Running the Dashboard

```bash
# Standalone
streamlit run app.py

# With custom port
streamlit run app.py --server.port 8080

# If installed with ebk
ebk-dashboard  # Future feature
```

### Using the Dashboard

1. **Upload Library**: 
   - Export your ebk library to ZIP: `ebk export zip /path/to/library library.zip`
   - Upload the ZIP file through the dashboard interface

2. **Browse and Filter**:
   - Use the sidebar filters for language, year, subjects
   - Search by title, author, or any text field
   - Sort by various criteria

3. **Advanced Search**:
   - Switch to "Advanced Search" tab
   - Use JMESPath queries like: `[?language=='en' && publication_year > `2020`]`

4. **Download Books**:
   - Click on any book to see details
   - Use the download button to get the ebook file

## Configuration

### Environment Variables

```bash
# Port configuration
export STREAMLIT_SERVER_PORT=8501

# Theme
export STREAMLIT_THEME_BASE="light"
export STREAMLIT_THEME_PRIMARY_COLOR="#FF6B6B"
```

### Config File

Create `.streamlit/config.toml`:

```toml
[server]
port = 8501
headless = true
enableCORS = false

[theme]
primaryColor = "#FF6B6B"
backgroundColor = "#FFFFFF"
secondaryBackgroundColor = "#F0F2F6"
textColor = "#262730"
font = "sans serif"
```

## Deployment

### Local Deployment

```bash
# Basic
streamlit run app.py

# Production-like
streamlit run app.py \
  --server.port 80 \
  --server.headless true \
  --browser.gatherUsageStats false
```

### Docker Deployment

```dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

### Cloud Deployment

#### Streamlit Cloud
1. Push to GitHub
2. Connect to [share.streamlit.io](https://share.streamlit.io)
3. Deploy directly from repository

#### Heroku
Create `Procfile`:
```
web: streamlit run app.py --server.port=$PORT
```

#### AWS/GCP/Azure
Use containerized deployment with the Docker image above.

## API Integration

The dashboard can also connect to an ebk API server (future feature):

```python
# In app.py configuration
API_ENDPOINT = os.getenv("EBK_API_URL", "http://localhost:5000")
```

## Development

### Project Structure
```
streamlit-dashboard/
├── app.py              # Main Streamlit application
├── display.py          # Display components and layouts
├── filters.py          # Filtering and search logic
├── utils.py           # Utility functions
├── requirements.txt   # Python dependencies
├── README.md         # This file
└── .streamlit/       # Streamlit configuration
    └── config.toml
```

### Adding Features

1. **New Filters**: Edit `filters.py` to add new filtering options
2. **Visualizations**: Add to `display.py` for new chart types
3. **Export Formats**: Extend `utils.py` for additional export options

### Testing

```bash
# Run tests
pytest tests/

# With coverage
pytest --cov=. tests/
```

## Troubleshooting

### Common Issues

1. **Large Libraries**: For libraries > 1000 books, consider:
   - Enabling pagination
   - Using server-side filtering
   - Implementing lazy loading

2. **Memory Usage**: Streamlit caches data by default. Clear cache with:
   - Press 'C' in the app
   - Or restart the server

3. **File Upload Limits**: Default is 200MB. Increase with:
   ```toml
   [server]
   maxUploadSize = 500
   ```

## Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature/new-feature`
3. Commit changes: `git commit -am 'Add new feature'`
4. Push branch: `git push origin feature/new-feature`
5. Submit Pull Request

## License

Same as ebk - MIT License