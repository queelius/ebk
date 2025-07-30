# ebk Visualization Integration

Network visualization tools for exploring relationships in ebook libraries.

## Overview

This integration provides interactive network visualizations of ebook libraries, revealing hidden connections and patterns through graph-based representations.

## Visualization Types

### 1. Co-authorship Networks
- **Nodes**: Books or Authors (configurable)
- **Edges**: Shared authorship
- **Use cases**: 
  - Discover collaborative patterns
  - Identify prolific co-authors
  - Track research groups or writing partnerships

### 2. Subject/Tag Networks
- **Nodes**: Books
- **Edges**: Shared subjects/tags (weighted by overlap)
- **Use cases**:
  - Explore thematic clusters
  - Find related books across different authors
  - Identify interdisciplinary works

### 3. Citation Networks (if metadata available)
- **Nodes**: Books/Papers
- **Edges**: Citation relationships
- **Use cases**:
  - Trace intellectual lineages
  - Identify influential works
  - Discover foundational texts

### 4. Language Networks
- **Nodes**: Books
- **Edges**: Books available in multiple languages
- **Use cases**:
  - Explore translation patterns
  - Identify polyglot collections
  - Find language learning resources

### 5. Temporal Networks
- **Nodes**: Books
- **Edges**: Published within same time period
- **Use cases**:
  - Analyze publishing trends
  - Historical context visualization
  - Track genre evolution

## Technical Implementation

### Graph Construction
```python
# Example: Building a co-authorship network
import networkx as nx
from ebk.utils import load_library

def build_coauthor_network(lib_dir):
    G = nx.Graph()
    library = load_library(lib_dir)
    
    for entry in library:
        if 'creators' in entry and len(entry['creators']) > 1:
            # Add edges between all co-authors
            for i, author1 in enumerate(entry['creators']):
                for author2 in entry['creators'][i+1:]:
                    if G.has_edge(author1, author2):
                        G[author1][author2]['weight'] += 1
                    else:
                        G.add_edge(author1, author2, weight=1)
    
    return G
```

### Visualization Options

#### 1. Static Visualizations
- **NetworkX + Matplotlib**: Basic layouts (spring, circular, hierarchical)
- **Graphviz**: Professional graph layouts via pygraphviz
- **Export formats**: PNG, SVG, PDF

#### 2. Interactive Visualizations
- **Pyvis**: Interactive HTML networks
- **Plotly**: Zoomable, clickable network graphs
- **D3.js integration**: Custom web-based visualizations

#### 3. Advanced Platforms
- **Gephi export**: For professional network analysis
- **Cytoscape format**: For biological sciences backgrounds
- **GraphML/GEXF**: Standard formats for graph tools

## Proposed Features

### Core Functionality
- Multiple layout algorithms (force-directed, hierarchical, radial)
- Node sizing by metrics (degree, betweenness, pagerank)
- Edge thickness by relationship strength
- Color coding by attributes (genre, language, year)
- Clustering detection and highlighting

### Filtering & Interaction
- Filter by publication year range
- Search and highlight specific nodes
- Zoom and pan controls
- Click nodes for book details
- Export subgraphs

### Analytics
- Network statistics dashboard
- Community detection
- Central books/authors identification
- Path finding between books
- Recommendation based on network proximity

## Usage Examples

```bash
# Generate a co-authorship network
ebk-viz coauthor /path/to/library --output network.html

# Create a subject similarity network
ebk-viz subjects /path/to/library --min-similarity 0.3

# Build a temporal network for a specific decade
ebk-viz temporal /path/to/library --start-year 2010 --end-year 2020

# Export for Gephi analysis
ebk-viz export /path/to/library --format gephi --type coauthor
```

## Configuration

```yaml
# viz-config.yaml
visualization:
  default_layout: "force_atlas_2"
  node_size:
    metric: "degree"  # degree, betweenness, pagerank
    min_size: 10
    max_size: 50
  edge_display:
    min_weight: 1
    curved: true
  colors:
    by_attribute: "language"  # genre, year, language
    palette: "viridis"
```

## Dependencies

```
networkx>=3.0
pyvis>=0.3.0
plotly>=5.0.0
pandas>=2.0.0
matplotlib>=3.5.0
pygraphviz  # optional, for better layouts
```

## Integration with ebk

The visualization tools would integrate seamlessly with ebk's existing infrastructure:

1. Use `ebk.utils.load_library()` to access metadata
2. Leverage existing search/filter capabilities
3. Export visualizations alongside other formats
4. Include in Streamlit dashboard as interactive tab

## Future Enhancements

- **AI-powered layout**: Use embeddings to position similar books
- **3D visualizations**: For very large libraries
- **VR/AR support**: Immersive library exploration
- **Real-time updates**: Live visualization as library changes
- **Collaborative features**: Share and annotate networks

## Contributing

We welcome contributions! Areas of interest:
- New visualization types
- Performance optimizations for large libraries
- Mobile-responsive designs
- Accessibility improvements
- Novel interaction paradigms