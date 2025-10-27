# AI-Powered Features in ebk

## 🧠 Your Library Becomes Your Second Brain

ebk now includes groundbreaking AI features that transform your ebook collection from static files into a living knowledge system. These features work together to amplify your learning and make every book you own exponentially more valuable.

## Features Overview

### 1. Knowledge Graph Construction
Build a interconnected web of concepts across all your books, enabling you to see how ideas connect and evolve.

### 2. Semantic Search
Find information using natural language queries that understand meaning, not just keywords.

### 3. Learning Path Generation
Create personalized reading sequences that bridge from your current knowledge to your learning goals.

### 4. Intelligent Q&A
Ask questions about your library and get answers synthesized from multiple sources.

### 5. Reading Sessions & Active Recall
Track your reading with comprehension testing and spaced repetition for better retention.

## Installation

```bash
# Install with AI features
pip install ebk[ai]

# Or install all features including AI
pip install ebk[all]
```

## Quick Start

### Step 1: Build Your Knowledge Graph

First, analyze your library to extract concepts and build the knowledge graph:

```bash
# Build knowledge graph for your entire library
ebk build-knowledge /path/to/your/library

# Or build for specific books
ebk build-knowledge /path/to/library --book book_id_1 --book book_id_2
```

This will:
- Extract key concepts and definitions from each book
- Identify relationships between ideas
- Calculate importance scores using PageRank
- Create a searchable knowledge network

### Step 2: Index for Semantic Search

Enable intelligent content discovery:

```bash
# Create semantic search index
ebk index-semantic /path/to/library

# Customize chunk size for better granularity
ebk index-semantic /path/to/library --chunk-size 300
```

### Step 3: Start Asking Questions

Now you can query your library intelligently:

```bash
# Ask about specific topics
ebk ask /path/to/library "What do my books say about habit formation?"

# Find connections between concepts
ebk ask /path/to/library "How does stoicism relate to modern psychology?"

# Get key principles
ebk ask /path/to/library "What are the main principles of machine learning?"
```

### Step 4: Generate Learning Paths

Create personalized reading sequences:

```bash
# Bridge from basic to advanced topics
ebk learning-path /path/to/library "linear algebra" "quantum computing"

# Navigate between disciplines
ebk learning-path /path/to/library "psychology" "neuroscience"

# Learn progressively
ebk learning-path /path/to/library "basic programming" "distributed systems"
```

## Advanced Usage

### Knowledge Graph Exploration

The knowledge graph stores data in `.knowledge_graph/` within your library:

```python
from ebk.ai import KnowledgeGraph

# Load existing graph
kg = KnowledgeGraph("/path/to/library")

# Find concept paths
path = kg.find_concept_path("habit", "neuroplasticity")
print(f"Learning path: {' -> '.join(path)}")

# Get related concepts
related = kg.find_related_concepts("machine learning", max_distance=2)
for concept, relevance in related[:5]:
    print(f"{concept}: {relevance:.2f}")

# Get most important concepts
key_concepts = kg.get_key_concepts(top_n=10)
for concept in key_concepts:
    print(f"{concept.name}: {concept.importance_score:.3f}")
```

### Semantic Search API

```python
from ebk.ai import SemanticSearch

search = SemanticSearch("/path/to/library")

# Search across library
results = search.search_library(
    "strategies for overcoming procrastination",
    top_k=5
)

for result in results:
    print(f"Book: {result['book_id']}")
    print(f"Relevance: {result['similarity']:.2f}")
    print(f"Text: {result['text'][:200]}...")

# Find similar books
similar = search.find_similar_books("book_id_123", top_k=3)
for book_id, similarity in similar:
    print(f"{book_id}: {similarity:.2f}")
```

### Reading Sessions with Active Recall

```python
from ebk.ai import ReadingCompanion, QuestionGenerator

companion = ReadingCompanion("/path/to/library")

# Start a reading session
session = companion.start_session("book_id_123", chapter="Chapter 3")

# Track progress
companion.add_highlight(session.session_id, "Important quote here...")
companion.add_note(session.session_id, "This relates to previous chapter")

# Generate questions for active recall
qgen = QuestionGenerator()
questions = qgen.generate_from_highlights(session.highlights)

for q in questions:
    print(f"Q: {q.question_text}")
    print(f"A: {q.answer}\n")

# End session
companion.end_session(session.session_id)

# Check reading stats
stats = companion.get_reading_stats()
print(f"Total reading time: {stats['total_time']}")
print(f"Current streak: {companion.get_reading_streak()} days")
```

## How It Works

### Knowledge Graph Architecture

The knowledge graph uses NetworkX to create a directed graph where:
- **Nodes** represent concepts, ideas, and definitions
- **Edges** represent relationships (supports, contradicts, extends, exemplifies)
- **Weights** indicate relationship strength
- **PageRank** determines concept importance

### Semantic Search Technology

Two-tier approach for maximum compatibility:
1. **Primary**: Sentence-transformers for state-of-the-art embeddings
2. **Fallback**: TF-IDF vectorization for systems without GPU

### Text Extraction Pipeline

Intelligent extraction from multiple formats:
- **PDF**: Chapter detection via TOC or pattern matching
- **EPUB**: HTML parsing with BeautifulSoup
- **Smart chunking**: Overlapping segments for context preservation

## Privacy & Performance

### Local-First Design
- All processing happens on your machine
- No data sent to external servers
- Your knowledge graph stays private

### Performance Optimization
- Incremental indexing (only process new books)
- Cached embeddings for fast retrieval
- Efficient vector similarity search

### Storage Requirements
- Knowledge graph: ~1MB per 100 books
- Semantic index: ~10MB per 100 books
- Reading sessions: <1MB

## Roadmap

### Coming Soon
- [ ] LLM integration for deeper analysis (Ollama support)
- [ ] Export to Obsidian/Roam/Notion
- [ ] Collaborative knowledge graphs
- [ ] Reading group features
- [ ] Mobile companion app

### Future Vision
- Distributed knowledge protocol (P2P sharing)
- AR reading assistance
- Voice-based Q&A
- Automatic podcast/video transcript integration

## Examples & Use Cases

### Academic Research
```bash
# Build comprehensive literature review
ebk ask /library "recent advances in transformer architectures"

# Find citation networks
ebk learning-path /library "attention mechanism" "multimodal transformers"
```

### Self-Learning
```bash
# Design curriculum
ebk learning-path /library "beginner python" "machine learning engineer"

# Test comprehension
ebk quiz /library --book python_basics --type conceptual
```

### Book Clubs
```bash
# Find discussion topics
ebk ask /library "controversial themes in 1984"

# Compare perspectives
ebk ask /library "how different authors approach dystopia"
```

## Troubleshooting

### Issue: Knowledge graph building is slow
**Solution**: Process specific books first:
```bash
ebk build-knowledge /library --book important_book_id
```

### Issue: Semantic search not finding relevant content
**Solution**: Rebuild index with smaller chunks:
```bash
ebk index-semantic /library --chunk-size 200 --force
```

### Issue: Out of memory during indexing
**Solution**: Use batch processing:
```bash
# Process books in smaller batches
ebk index-semantic /library --book book1 --book book2
```

## Contributing

We welcome contributions! Areas we're especially interested in:
- Additional language support for extraction
- Better concept relationship detection
- Integration with more ebook formats
- Visualization improvements

## License

The AI features are part of ebk's MIT licensed codebase.

---

*Transform your library into a learning accelerator with ebk's AI features!*