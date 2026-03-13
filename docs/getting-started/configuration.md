# Configuration Guide

ebk uses a centralized configuration system that stores all settings in a single JSON file. This guide covers how to set up and manage your ebk configuration.

## Configuration File Location

The configuration file is stored at:

```
~/.config/ebk/config.json
```

On Windows:
```
%USERPROFILE%\.config\ebk\config.json
```

For backward compatibility, ebk also supports the legacy `~/.ebkrc` file, but the new JSON format is recommended.

## Configuration Structure

The configuration file is organized into three main sections:

### Server Configuration

Settings for the web server interface:

```json
{
  "server": {
    "host": "0.0.0.0",
    "port": 8000,
    "auto_open_browser": false,
    "page_size": 50
  }
}
```

- **host**: Server bind address (`0.0.0.0` = all interfaces, `127.0.0.1` = localhost only)
- **port**: Server port
- **auto_open_browser**: Automatically open browser when starting server
- **page_size**: Default number of books per page

### CLI Configuration

Default CLI behavior settings:

```json
{
  "cli": {
    "verbose": false,
    "color": true,
    "page_size": 50
  }
}
```

- **verbose**: Enable verbose logging by default
- **color**: Enable colored output (uses Rich)
- **page_size**: Default page size for list commands

### Library Configuration

Library-related preferences:

```json
{
  "library": {
    "default_path": null
  }
}
```

- **default_path**: Default library path (can be used with commands that accept an optional path)

## Managing Configuration

### Initialize Configuration

Create a configuration file with default values:

```bash
ebk config init
```

This creates `~/.config/ebk/config.json` if it doesn't exist.

### View Configuration

View the entire configuration:

```bash
ebk config show
```

View a specific section:

```bash
ebk config show --section server
```

### Edit Configuration

Edit the configuration file in your default editor:

```bash
ebk config edit
```

This opens the JSON file in the editor specified by your `EDITOR` environment variable.

### Set Configuration Values

Set individual configuration values:

```bash
# Set server options
ebk config set server.port 8080
ebk config set server.auto_open_browser true

# Set CLI defaults
ebk config set cli.verbose true
ebk config set cli.page_size 100

# Set library defaults
ebk config set library.default_path ~/my-ebooks
```

### Get Configuration Values

Retrieve specific configuration values:

```bash
ebk config get server.port
ebk config get library.default_path
```

## Common Configuration Scenarios

### Web Server for Local Access Only

For security, bind the web server to localhost only:

```bash
ebk config set server.host 127.0.0.1
ebk config set server.port 8000
```

### Web Server for Network Access

To allow access from other devices on your network:

```bash
ebk config set server.host 0.0.0.0
ebk config set server.port 8000
```

Then access from other devices at `http://your-ip:8000`

### Development Mode

For development with verbose output:

```bash
ebk config set cli.verbose true
ebk config set cli.color true
```

## CLI Overrides

All configuration settings can be overridden via CLI arguments:

```bash
# Override server settings
ebk serve ~/library --host 127.0.0.1 --port 9000

# Enable verbose mode for single command
ebk --verbose import book.pdf ~/library
```

CLI arguments always take precedence over configuration file values.

## Environment Variables

Some settings can also be controlled via environment variables:

```bash
# Editor for config edit
export EDITOR=vim
```

## Configuration Best Practices

1. **Set default library path**: If you primarily work with one library, set it as default:
   ```bash
   ebk config set library.default_path ~/my-ebooks
   ```

2. **Enable auto-open for convenience**: If you frequently use the web interface:
   ```bash
   ebk config set server.auto_open_browser true
   ```

3. **Adjust page size for your screen**: Larger screens can show more items:
   ```bash
   ebk config set cli.page_size 100
   ebk config set server.page_size 100
   ```

## Troubleshooting

### Configuration file not found

If commands don't use your configuration:

```bash
# Check if config exists
ls -la ~/.config/ebk/config.json

# Create if missing
ebk config init
```

### Invalid JSON

If you manually edited the config and broke it:

```bash
# Backup and recreate
mv ~/.config/ebk/config.json ~/.config/ebk/config.json.bak
ebk config init
```

### Server won't start

If the web server fails to start:

```bash
# Check if port is in use
lsof -i :8000

# Try different port
ebk serve ~/library --port 8080

# Or update config
ebk config set server.port 8080
```

## Next Steps

- [Quick Start Guide](quickstart.md) - Start using ebk
- [Web Server Guide](../user-guide/server.md) - Use the web interface
- [MCP Server](../integrations/mcp.md) - AI assistant integration
- [CLI Reference](../user-guide/cli.md) - Complete command reference
