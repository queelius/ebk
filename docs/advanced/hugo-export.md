# Hugo Export with Jinja Templates

The ebk Hugo export now supports flexible organization and templating through Jinja2.

## Basic Usage

```bash
# Legacy export (flat structure)
ebk export hugo /path/to/library /path/to/hugo-site

# New Jinja-based export with organization options
ebk export hugo /path/to/library /path/to/hugo-site --jinja --organize-by year
```

## Organization Options

With the `--jinja` flag, you can organize your library in different ways:

### Flat (default)
All books in one directory:
```
content/library/
├── _index.md
├── book-1-abc12345.md
├── book-2-def67890.md
└── ...
```

### By Year
```bash
ebk export hugo /path/to/library /path/to/hugo-site --jinja --organize-by year
```
```
content/library/
├── _index.md
├── 2023/
│   ├── _index.md
│   └── book-1-abc12345.md
├── 2024/
│   ├── _index.md
│   └── book-2-def67890.md
└── unknown-year/
    └── ...
```

### By Language
```bash
ebk export hugo /path/to/library /path/to/hugo-site --jinja --organize-by language
```
```
content/library/
├── _index.md
├── en/
│   ├── _index.md
│   └── books...
├── es/
│   ├── _index.md
│   └── books...
└── ...
```

### By Subject
```bash
ebk export hugo /path/to/library /path/to/hugo-site --jinja --organize-by subject
```
Books appear in multiple subject directories if they have multiple subjects:
```
content/library/
├── _index.md
├── fiction/
│   ├── _index.md
│   └── books...
├── science/
│   ├── _index.md
│   └── books...
└── ...
```

### By Creator
```bash
ebk export hugo /path/to/library /path/to/hugo-site --jinja --organize-by creator
```
Books appear under each of their creators:
```
content/library/
├── _index.md
├── jane-doe/
│   ├── _index.md
│   └── books...
├── john-smith/
│   ├── _index.md
│   └── books...
└── ...
```

## Custom Templates

You can provide your own Jinja2 templates:

```bash
ebk export hugo /path/to/library /path/to/hugo-site --jinja \
    --template-dir /path/to/custom/templates
```

Your template directory should follow this structure:
```
templates/
└── hugo/
    ├── book.md      # Individual book page
    ├── index.md     # Category index pages
    └── library.md   # Main library index
```

### Template Variables

#### book.md
- `book`: Dictionary with all metadata fields
- `ebook_urls`: List of download URLs
- `cover_url`: Cover image URL

#### index.md
- `title`: Section title
- `organize_by`: Organization method
- `group_key`: Current group identifier
- `books`: List of books in this section
- `book_count`: Number of books

#### library.md
- `title`: Library title
- `books`: All books in the library
- `stats`: Library statistics dictionary

## Hugo Configuration

To fully utilize the exported library, configure your Hugo site:

### 1. Add Library Section
In `config.toml`:
```toml
[[menu.main]]
  name = "Library"
  url = "/library/"
  weight = 10
```

### 2. Create Custom Layouts
Create `layouts/library/single.html` for book pages:
```html
{{ define "main" }}
<article class="book-page">
  <h1>{{ .Title }}</h1>
  
  {{ with .Params.cover_image }}
    <img src="{{ . }}" alt="Book cover" class="book-cover">
  {{ end }}
  
  <div class="book-meta">
    {{ with .Params.creators_display }}
      <p>By {{ delimit . ", " }}</p>
    {{ end }}
    
    {{ with .Params.description }}
      <div class="description">{{ . | markdownify }}</div>
    {{ end }}
  </div>
  
  {{ with .Params.ebook_files }}
    <div class="downloads">
      <h3>Download</h3>
      {{ range . }}
        <a href="{{ . }}" class="download-btn">Download</a>
      {{ end }}
    </div>
  {{ end }}
</article>
{{ end }}
```

### 3. Style Your Library
Add CSS for the book grid and cards:
```css
.book-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 2rem;
}

.book-card {
  border: 1px solid #ddd;
  padding: 1rem;
  transition: transform 0.2s;
}

.book-card:hover {
  transform: translateY(-5px);
}
```

## Advanced Features

### Filtering and Search
The exported structure supports Hugo's built-in taxonomy system. You can filter by:
- Tags (from subjects)
- Authors (from creators)
- Years
- Languages

### Multiple Views
Since books can appear in multiple categories (e.g., by subject AND by author), users can browse your library from different perspectives.

### Static but Dynamic
While Hugo generates static files, the organization allows for client-side filtering and search using JavaScript if desired.

## Example Workflow

1. Import your Calibre library:
   ```bash
   ebk import-calibre ~/Calibre ~/my-ebk-library
   ```

2. Export to Hugo with year organization:
   ```bash
   ebk export hugo ~/my-ebk-library ~/my-hugo-site --jinja --organize-by year
   ```

3. Build and serve your Hugo site:
   ```bash
   cd ~/my-hugo-site
   hugo serve
   ```

4. Visit `http://localhost:1313/library/` to browse your collection!

## Tips

- Use `--organize-by subject` for topic-based browsing
- Use `--organize-by creator` for author-centric libraries
- Combine with Hugo's search functionality for full-text search
- The unique_id in URLs ensures no conflicts even with duplicate titles
- Consider using Hugo's image processing for cover thumbnails