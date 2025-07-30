# ebk MCP Server

This is an MCP (Model Context Protocol) server that enables AI assistants to interact with ebk libraries.

## Installation

1. Ensure ebk is installed:
   ```bash
   pip install /path/to/ebk
   ```

2. Install the MCP server dependencies:
   ```bash
   pip install mcp
   ```

## Configuration

Add the ebk MCP server to your MCP configuration file (e.g., for Claude Desktop):

```json
{
  "mcpServers": {
    "ebk": {
      "command": "python",
      "args": ["-m", "ebk_mcp_server"],
      "env": {}
    }
  }
}
```

## Available Tools

The MCP server exposes the following ebk functionality:

### Library Management
- `import_calibre` - Import a Calibre library
- `import_ebooks` - Import a directory of ebooks
- `import_zip` - Import an ebk library from ZIP
- `export_zip` - Export library to ZIP format
- `export_hugo` - Export library for Hugo static site

### Search and Browse
- `list` - List all entries in a library
- `search` - Search using regex patterns
- `search_jmespath` - Search using JMESPath queries
- `stats` - Get library statistics

### Entry Management
- `add` - Add new entries to library
- `update_index` - Update entry by index
- `update_id` - Update entry by unique ID
- `remove` - Remove entries matching regex
- `remove_index` - Remove entry by index
- `remove_id` - Remove entry by unique ID

### Library Operations
- `merge` - Merge multiple libraries (union, intersect, diff, symdiff)

## Usage Examples

Once configured, AI assistants can use natural language to interact with your ebook libraries:

- "Import my Calibre library at /home/user/Calibre"
- "Search for all Python books in my library"
- "Export my ebook library to a ZIP file"
- "Show statistics about my ebook collection"
- "Merge my work and personal libraries"

## Development

The MCP server implementation can be found in `ebk_mcp_server.py`.