# Web Server

ebk includes a FastAPI-based web server that provides a modern web interface for browsing and managing your ebook library.

## Quick Start

### Basic Usage

Start the server with default settings:

```bash
ebk serve ~/my-library
```

The server will start at `http://localhost:8000` (or the configured host/port).

### Custom Host and Port

```bash
# Listen on specific port
ebk serve ~/library --port 8080

# Localhost only (more secure)
ebk serve ~/library --host 127.0.0.1 --port 8000

# Listen on all interfaces (network access)
ebk serve ~/library --host 0.0.0.0 --port 8000
```

### Auto-Open Browser

```bash
# Open browser automatically
ebk serve ~/library --auto-open

# Or configure as default
ebk config set server.auto_open_browser true
ebk serve ~/library
```

## Configuration

Configure server defaults in `~/.config/ebk/config.json`:

```bash
# Set default port
ebk config set server.port 8080

# Set default host
ebk config set server.host 0.0.0.0

# Enable auto-open
ebk config set server.auto_open_browser true

# Set page size
ebk config set server.page_size 50
```

View current configuration:

```bash
ebk config show --section server
```

## Web Interface Features

### Book Browsing

The web interface provides:

- **Grid view** with book covers
- **List view** with detailed information
- **Pagination** for large libraries
- **Sorting** by title, author, date, rating
- **Filtering** by author, language, format, rating, tags

### Navigation

Use URL parameters for direct navigation:

```
# Pagination
http://localhost:8000/?page=2

# Filtering
http://localhost:8000/?author=Knuth
http://localhost:8000/?language=en
http://localhost:8000/?format=pdf

# Sorting
http://localhost:8000/?sort_by=title
http://localhost:8000/?sort_by=date&sort_order=desc

# Combine filters
http://localhost:8000/?author=Knuth&language=en&sort_by=title
```

### Search

Full-text search across title, author, and description:

```
http://localhost:8000/search?q=python+programming
```

### Book Details

Click on any book to view:

- Complete metadata
- All available formats
- Cover image
- Description
- Authors and subjects
- Reading status and rating
- Personal tags and notes

### File Access

Click on format badges to:

- **Open files** directly in browser (PDF)
- **Download files** (EPUB, MOBI, etc.)
- **View cover** in full size

## REST API

The server provides a REST API for programmatic access.

### Endpoints

#### List Books

```bash
# Get all books (paginated)
curl http://localhost:8000/api/books

# With filters
curl "http://localhost:8000/api/books?author=Knuth&language=en"

# With pagination
curl "http://localhost:8000/api/books?page=2&limit=50"
```

Response:

```json
{
  "books": [
    {
      "id": 1,
      "title": "The Art of Computer Programming, Vol. 1",
      "authors": ["Donald E. Knuth"],
      "language": "en",
      "publisher": "Addison-Wesley",
      "publication_date": "1997-07-23",
      "subjects": ["Computer Science", "Algorithms"],
      "files": [
        {"format": "pdf", "size": 15728640, "path": "..."}
      ],
      "rating": 5.0,
      "favorite": true,
      "reading_status": "read",
      "tags": ["must-read", "reference"]
    }
  ],
  "total": 150,
  "page": 1,
  "limit": 50
}
```

#### Get Book Details

```bash
# Get specific book
curl http://localhost:8000/api/books/42
```

Response:

```json
{
  "id": 42,
  "title": "Introduction to Algorithms",
  "subtitle": "Third Edition",
  "authors": ["Cormen", "Leiserson", "Rivest", "Stein"],
  "language": "en",
  "publisher": "MIT Press",
  "publication_date": "2009-07-31",
  "series": null,
  "series_index": null,
  "description": "Comprehensive algorithms textbook...",
  "subjects": ["Algorithms", "Computer Science", "Data Structures"],
  "files": [
    {"format": "pdf", "size": 20971520, "path": "files/ab/abc123.pdf"},
    {"format": "epub", "size": 10485760, "path": "files/cd/cde456.epub"}
  ],
  "rating": 5.0,
  "favorite": true,
  "reading_status": "reading",
  "tags": ["textbook", "algorithms", "must-read"],
  "cover_path": "covers/ab/abc123.jpg"
}
```

#### Search Books

```bash
# Full-text search
curl "http://localhost:8000/api/search?q=machine+learning"
```

#### Update Book

```bash
# Update book metadata
curl -X PATCH http://localhost:8000/api/books/42 \
  -H "Content-Type: application/json" \
  -d '{
    "rating": 5,
    "favorite": true,
    "reading_status": "read",
    "tags": ["must-read", "reference"]
  }'
```

#### Upload Book

```bash
# Import new book
curl -X POST http://localhost:8000/api/books \
  -F "file=@book.pdf" \
  -F "title=My Book" \
  -F "authors=Author Name"
```

#### Get Statistics

```bash
# Library statistics
curl http://localhost:8000/api/stats
```

Response:

```json
{
  "total_books": 250,
  "total_authors": 180,
  "total_subjects": 45,
  "total_files": 320,
  "total_size_mb": 15360.5,
  "languages": ["en", "de", "fr"],
  "formats": ["pdf", "epub", "mobi"]
}
```

### API Authentication

Currently the API is open (no authentication). For production use, consider:

1. **Reverse proxy** with authentication (nginx, Apache)
2. **VPN** for secure access
3. **Firewall rules** to restrict access

Future versions will support API keys and OAuth.

## Network Access

### Local Access Only

For security, bind to localhost:

```bash
ebk serve ~/library --host 127.0.0.1
```

Access from same machine only: `http://localhost:8000`

### LAN Access

To access from other devices on your network:

```bash
ebk serve ~/library --host 0.0.0.0 --port 8000
```

Find your IP address:

```bash
# Linux/Mac
ifconfig | grep inet

# Windows
ipconfig
```

Access from other devices: `http://your-ip:8000`

### Public Access (Not Recommended)

For internet access, use a reverse proxy with authentication:

```nginx
# nginx configuration
server {
    listen 80;
    server_name books.example.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;

        # Basic authentication
        auth_basic "eBook Library";
        auth_basic_user_file /etc/nginx/.htpasswd;
    }
}
```

## Production Deployment

### Using systemd (Linux)

Create service file: `/etc/systemd/system/ebk-server.service`

```ini
[Unit]
Description=ebk Web Server
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/home/your-username
ExecStart=/home/your-username/.local/bin/ebk serve /home/your-username/library --host 0.0.0.0 --port 8000
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable ebk-server
sudo systemctl start ebk-server
sudo systemctl status ebk-server
```

### Using Docker

Create `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install ebk
RUN pip install ebk

# Expose port
EXPOSE 8000

# Mount library as volume
VOLUME ["/library"]

# Start server
CMD ["ebk", "serve", "/library", "--host", "0.0.0.0", "--port", "8000"]
```

Build and run:

```bash
# Build image
docker build -t ebk-server .

# Run container
docker run -d \
  -p 8000:8000 \
  -v ~/my-library:/library \
  --name ebk \
  ebk-server

# View logs
docker logs -f ebk
```

### Using docker-compose

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  ebk:
    image: ebk-server
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ~/my-library:/library:ro
    restart: unless-stopped
    environment:
      - EBK_HOST=0.0.0.0
      - EBK_PORT=8000
```

Start:

```bash
docker-compose up -d
```

## Security Considerations

### File System Access

The web server requires:

- **Read access** to library files
- **Write access** for uploads and metadata updates
- **Execute access** for opening files

Set appropriate permissions:

```bash
# Set library ownership
chown -R your-username:your-username ~/library

# Set secure permissions
chmod -R 755 ~/library/files
chmod 644 ~/library/library.db
```

### Network Security

1. **Firewall**: Only allow access from trusted networks
   ```bash
   # Allow from local network only
   sudo ufw allow from 192.168.1.0/24 to any port 8000
   ```

2. **HTTPS**: Use reverse proxy with SSL/TLS for production

3. **Authentication**: Implement via reverse proxy or VPN

### File Uploads

If allowing uploads:

1. **Validate file types** (only ebooks)
2. **Limit file size** (prevent DoS)
3. **Scan for malware** if accepting external files
4. **Use dedicated upload directory** with restricted permissions

## Troubleshooting

### Port Already in Use

If port 8000 is already used:

```bash
# Check what's using the port
lsof -i :8000

# Use different port
ebk serve ~/library --port 8080
```

### Permission Denied

If server can't read library:

```bash
# Check permissions
ls -la ~/library

# Fix permissions
chmod -R 755 ~/library
```

### Can't Access from Network

If other devices can't connect:

1. **Check firewall**:
   ```bash
   sudo ufw status
   sudo ufw allow 8000
   ```

2. **Verify host binding**:
   ```bash
   # Must be 0.0.0.0 for network access
   ebk serve ~/library --host 0.0.0.0
   ```

3. **Check network**:
   ```bash
   # Test from other device
   ping your-ip
   telnet your-ip 8000
   ```

### Slow Performance

If web interface is slow:

1. **Check database size**:
   ```bash
   du -h ~/library/library.db
   ```

2. **Optimize database**:
   ```bash
   sqlite3 ~/library/library.db "VACUUM;"
   ```

3. **Reduce page size**:
   ```bash
   ebk config set server.page_size 20
   ```

4. **Generate thumbnails** for faster loading:
   ```bash
   ebk generate-thumbnails ~/library
   ```

## Advanced Configuration

### Custom Static Files

Serve additional static files:

```python
from fastapi.staticfiles import StaticFiles
from ebk.server import app

# Mount custom static directory
app.mount("/static", StaticFiles(directory="/path/to/static"), name="static")
```

### Custom Templates

Override default templates:

```python
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="/path/to/templates")
```

### CORS Configuration

Enable CORS for API access from web apps:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## Next Steps

- [Configuration Guide](../getting-started/configuration.md) - Configure server defaults
- [CLI Reference](cli.md) - All server options
- [Python API](api.md) - Programmatic server control
- [REST API Documentation](api.md#rest-api) - Complete API reference
