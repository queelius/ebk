# ebk Integrations

This directory contains integration examples and servers for external tools to interact with ebk.

## Streamlit Dashboard

The `streamlit-dashboard/` directory contains a web-based interface for browsing and managing ebk libraries.

### Features

- Interactive library browsing with cover images
- Advanced filtering and search capabilities
- Library statistics and visualizations
- Direct ebook downloads
- Can be deployed standalone or integrated with ebk

### Usage

See the [Streamlit Dashboard README](streamlit-dashboard/README.md) for installation and deployment options.

## MCP (Model Context Protocol) Integration

The `mcp/` directory contains an MCP server implementation that allows AI assistants like Claude to interact with ebk libraries through a standardized protocol.

### Features

The MCP server exposes the following tools:
- Import libraries from various sources (Calibre, ebooks, ZIP)
- Export libraries to different formats (ZIP, Hugo)
- Search libraries using regex or JMESPath
- List and browse library contents
- Add/update/remove entries
- Merge multiple libraries
- Get library statistics

### Usage

See the [MCP README](mcp/README.md) for setup and usage instructions.

## Visualization Integration

The `viz/` directory contains documentation and examples for creating network visualizations of ebook libraries.

### Features

- Co-authorship networks
- Subject/tag similarity graphs
- Temporal publication networks
- Interactive and static visualization options
- Multiple export formats (HTML, Gephi, GraphML)

### Usage

See the [Visualization README](viz/README.md) for detailed documentation and examples.

## Adding New Integrations

To add a new integration:

1. Create a new directory under `integrations/`
2. Include a README explaining the integration
3. Provide installation and usage instructions
4. Consider submitting a PR to share with the community