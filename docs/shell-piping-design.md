# Shell Piping and Text Utilities - Design Document

## Motivation

The ebk shell provides a Unix-like interface for navigating the ebook library through a Virtual File System (VFS). However, without piping and basic text utilities, users cannot compose commands to explore their library effectively.

### Problem

Current limitations:
```bash
# ❌ Cannot paginate large outputs
ebk:/books/42 $ cat text
# (outputs 10,000 lines with no way to page)

# ❌ Cannot count results
ebk:/ $ find author:Knuth
# (displays results but no count)

# ❌ Cannot preview files
ebk:/books/42 $ cat description
# (shows full text, can't see just first 10 lines)

# ❌ Cannot chain operations
ebk:/ $ find subject:python
# (can't pipe to grep to filter further)
```

### Solution

Implement a **minimal but powerful** set of text utilities and piping:

**Text Utilities:**
- `head` - Show first N lines
- `tail` - Show last N lines
- `wc` - Count lines, words, characters
- `sort` - Sort lines alphabetically
- `uniq` - Remove duplicate lines
- `more` - Paginate output

**Piping:**
- `cmd1 | cmd2 | cmd3` - Chain commands via stdout → stdin

**After implementation:**
```bash
# ✅ Paginate large files
ebk:/books/42 $ cat text | more

# ✅ Count results
ebk:/ $ find author:Knuth | wc -l
5 books found

# ✅ Preview files
ebk:/books/42 $ cat description | head -10

# ✅ Chain operations
ebk:/ $ find subject:python | grep -i "machine" | wc -l

# ✅ Complex queries
ebk:/ $ cat text | grep "theorem" | sort | uniq | head -20
```

## Design Principles

### 1. Unix Philosophy
- **Do one thing well** - Each utility has a single, clear purpose
- **Text as universal interface** - Everything is text streams
- **Composability** - Commands chain naturally via pipes

### 2. Bounded Scope
**What we implement:**
- Piping (`|`) for command chaining
- 6 essential text utilities
- String-based stdin/stdout

**What we explicitly DON'T implement:**
- Redirection (`>`, `>>`, `<`) - VFS is read-only, use `!bash` if needed
- Job control (`&`, `fg`, `bg`) - No background jobs needed
- Scripting (variables, loops, functions) - Use Python API instead
- Subshells, command substitution - Too complex
- Binary data handling - Text-only is sufficient

### 3. Simplicity Over Completeness
- Implement core flags only (e.g., `head -n`, not `head -c`)
- String processing, not byte processing
- Synchronous execution, no concurrency
- Clear error messages over POSIX compliance

### 4. Familiar UX
- Match common Unix behavior where possible
- Use standard flag names (`-n`, `-r`, `-l`)
- Sensible defaults (head defaults to 10 lines)

## Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────┐
│                  LibraryShell                       │
│  ┌───────────────────────────────────────────────┐ │
│  │           Command Executor                    │ │
│  │  • Parse command line                         │ │
│  │  • Detect pipes (|)                           │ │
│  │  • Route to pipeline or single execution     │ │
│  └───────────────────────────────────────────────┘ │
│           │                         │               │
│    ┌──────▼──────┐         ┌───────▼────────┐     │
│    │  Pipeline   │         │ Single Command │     │
│    │  Executor   │         │   Executor     │     │
│    └──────┬──────┘         └────────────────┘     │
│           │                                         │
│    ┌──────▼──────────────────────────────┐        │
│    │      Text Utilities Module          │        │
│    │  • head, tail, wc, sort, uniq, more │        │
│    │  • stdin/stdout interface           │        │
│    └─────────────────────────────────────┘        │
└─────────────────────────────────────────────────────┘
```

### Pipeline Execution Flow

```python
Input: "cat text | grep python | head -20"

1. Parse: Split on '|'
   → ["cat text", "grep python", "head -20"]

2. Execute first command:
   cmd: cat text
   stdin: None
   stdout: "Chapter 1\nIntro to Python\n..."

3. Execute second command:
   cmd: grep python
   stdin: "Chapter 1\nIntro to Python\n..."
   stdout: "Intro to Python\nPython is...\n..."

4. Execute third command:
   cmd: head -20
   stdin: "Intro to Python\nPython is...\n..."
   stdout: (first 20 lines)

5. Display final output to console
```

### Command Interface

All commands must support dual-mode execution:

```python
def cmd_grep(self, args: List[str], stdin: Optional[str] = None) -> str:
    """Execute grep with optional stdin.

    Args:
        args: Command arguments (e.g., ["-i", "pattern", "file"])
        stdin: Optional input from previous command in pipeline

    Returns:
        Command output as string
    """
    if stdin:
        # Process stdin (pipeline mode)
        return self._grep_string(pattern, stdin, flags)
    else:
        # Process VFS files (standalone mode)
        return self._grep_files(pattern, paths, flags)
```

## Text Utilities Specification

### 1. head - Show first N lines

**Syntax:**
```bash
head [-n NUM] [file]
```

**Flags:**
- `-n NUM` - Show first NUM lines (default: 10)

**Examples:**
```bash
head -n 5 title        # First 5 lines of title file
cat text | head        # First 10 lines of piped input
cat text | head -n 100 # First 100 lines
```

**Implementation:**
- Split on `\n`
- Return first N lines
- ~30 lines of code

### 2. tail - Show last N lines

**Syntax:**
```bash
tail [-n NUM] [file]
```

**Flags:**
- `-n NUM` - Show last NUM lines (default: 10)

**Examples:**
```bash
tail -n 20 description  # Last 20 lines
cat text | tail         # Last 10 lines of piped input
```

**Implementation:**
- Split on `\n`
- Return last N lines
- ~30 lines of code

### 3. wc - Count lines, words, characters

**Syntax:**
```bash
wc [-l|-w|-c] [file]
```

**Flags:**
- `-l` - Count lines only
- `-w` - Count words only
- `-c` - Count characters only
- (no flag) - Show all three

**Examples:**
```bash
wc text                    # Lines, words, chars
wc -l text                # Line count only
find author:Knuth | wc -l # Count search results
```

**Output format:**
```
  123  4567  89012  filename  # lines words chars
```

**Implementation:**
- Count `\n`, split on whitespace, len()
- ~40 lines of code

### 4. sort - Sort lines alphabetically

**Syntax:**
```bash
sort [-r] [file]
```

**Flags:**
- `-r` - Reverse sort (Z to A)

**Examples:**
```bash
cat authors | sort        # Alphabetical
cat authors | sort -r     # Reverse alphabetical
```

**Implementation:**
- `sorted(lines)` or `sorted(lines, reverse=True)`
- ~20 lines of code

### 5. uniq - Remove duplicate adjacent lines

**Syntax:**
```bash
uniq [-c] [file]
```

**Flags:**
- `-c` - Prefix lines with occurrence count

**Examples:**
```bash
cat subjects | sort | uniq       # Unique subjects
cat subjects | sort | uniq -c    # Count each subject
```

**Output with `-c`:**
```
   3 Python
   5 Machine Learning
   1 Algorithms
```

**Implementation:**
- Compare adjacent lines
- With `-c`: count occurrences
- ~30 lines of code

### 6. more - Paginate output

**Syntax:**
```bash
more [file]
```

**Behavior:**
- Display one page at a time
- Use Rich's `Pager` for consistent UX
- Space to advance, q to quit

**Examples:**
```bash
cat text | more
more description
```

**Implementation:**
- Use `console.pager()` from Rich
- ~40 lines of code

## Pipeline Implementation

### Pipeline Parser

```python
class Pipeline:
    """Execute a series of piped commands."""

    def __init__(self, command_line: str):
        """Parse pipeline from command line.

        Args:
            command_line: Full command with pipes, e.g., "cat x | grep y"
        """
        self.commands = [cmd.strip() for cmd in command_line.split('|')]

    def execute(self, shell: 'LibraryShell') -> str:
        """Execute pipeline, passing stdout between commands.

        Args:
            shell: Shell instance for command execution

        Returns:
            Final output as string
        """
        output = None

        for cmd_str in self.commands:
            # Parse command
            parts = shlex.split(cmd_str)
            cmd_name = parts[0]
            args = parts[1:] if len(parts) > 1 else []

            # Execute with stdin from previous command
            output = shell.execute_command(cmd_name, args, stdin=output)

            if output is None:
                # Command failed
                return None

        return output
```

### Command Execution Updates

Modify `LibraryShell.execute()`:

```python
def execute(self, line: str):
    """Execute command line with optional piping."""

    # Check for pipes
    if '|' in line:
        pipeline = Pipeline(line)
        output = pipeline.execute(self)
        if output:
            self.console.print(output)
    else:
        # Existing single command execution
        self._execute_single(line)
```

Update command methods to accept `stdin`:

```python
def execute_command(self, cmd_name: str, args: List[str],
                   stdin: Optional[str] = None) -> Optional[str]:
    """Execute a command with optional stdin.

    Args:
        cmd_name: Command name
        args: Command arguments
        stdin: Optional input from previous command

    Returns:
        Command output as string, or None on error
    """
    if cmd_name in self.commands:
        return self.commands[cmd_name](args, stdin=stdin)
    else:
        self.console.print(f"[red]Unknown command: {cmd_name}[/red]")
        return None
```

## Usage Examples

### Basic Piping

```bash
# Paginate long output
ebk:/books/42 $ cat text | more

# Preview file
ebk:/books/42 $ cat description | head -10

# Count lines
ebk:/books/42 $ cat text | wc -l
1247 lines

# Find and count
ebk:/ $ find author:Knuth | wc -l
5 books
```

### Complex Workflows

```bash
# Most common words in a book
ebk:/books/42 $ cat text | tr ' ' '\n' | sort | uniq -c | sort -rn | head -20

# Find books with "algorithm" in title
ebk:/ $ find title:algorithm | head -5

# Unique subjects, sorted
ebk:/ $ find subject:* | sort | uniq

# Count authors with > 5 books
ebk:/ $ find author:* | uniq | wc -l

# Preview search results
ebk:/ $ grep -r "machine learning" /books | head -50 | more
```

### VFS Navigation + Piping

```bash
# Count files in current book
ebk:/books/42 $ ls files | wc -l

# Show similar books
ebk:/books/42 $ ls similar | head -5

# Sorted author list
ebk:/authors $ ls | sort
```

## Error Handling

### Pipeline Errors

- If any command in pipeline fails, **stop execution**
- Show error from failing command
- Don't execute remaining commands

```bash
ebk:/ $ cat nonexistent | grep foo
cat: nonexistent: No such file or directory
# (grep never executes)
```

### Command Errors

- Invalid flags: Show usage
- Missing arguments: Show usage
- File not found: Show error, return None
- Stdin required but not provided: Show error

## Testing Strategy

### Unit Tests

Each utility gets comprehensive tests:

```python
def test_head_basic():
    """Test head with default 10 lines."""

def test_head_custom_lines():
    """Test head with -n flag."""

def test_head_stdin():
    """Test head reading from stdin."""

def test_head_empty_input():
    """Test head with empty input."""
```

### Integration Tests

Test piping combinations:

```python
def test_pipeline_cat_grep():
    """Test cat | grep."""

def test_pipeline_find_wc():
    """Test find | wc -l."""

def test_pipeline_sort_uniq():
    """Test sort | uniq."""

def test_pipeline_three_commands():
    """Test cat | grep | head."""
```

### Edge Cases

- Empty stdin
- Very long lines (>10k chars)
- Unicode handling
- Commands with no output
- Invalid command in pipeline

## Performance Considerations

### String Processing

- Python strings are efficient for text processing
- No need for streaming (library files are manageable size)
- Max file size: ~10MB (typical ebook text)

### Pipeline Buffering

- Buffer entire output between commands
- No streaming needed (text files are small)
- Trade memory for simplicity

### Optimization Opportunities

If needed later:
- Lazy evaluation with generators
- Streaming for very large files
- Parallel pipeline execution (probably overkill)

## Future Extensions (Out of Scope)

These are explicitly **NOT** being implemented:

- **Advanced sorting** (`sort -n`, `-k`, `-t`) - Diminishing returns
- **Advanced grep** (`-A`, `-B`, `-C` context) - Already complex enough
- **Redirection** (`>`, `>>`, `<`) - VFS is read-only
- **Tee command** - Not needed for read-only exploration
- **Xargs** - Interesting but adds complexity
- **Awk/sed** - Way too complex, use Python instead
- **Cut/paste** - Niche use cases
- **Regex in other commands** - Keep grep for that

## Summary

This design provides:

✅ **Familiar UX** - Unix users feel at home
✅ **Composability** - Commands chain naturally
✅ **Power** - Complex queries possible
✅ **Simplicity** - ~500 lines total code
✅ **Maintainability** - Clear boundaries, well-tested
✅ **Focused** - Enhanced library browsing, not general shell

The scope is deliberately limited to avoid:

❌ Scope creep (no scripting, job control, etc.)
❌ Complexity explosion (no subshells, variables, etc.)
❌ Maintenance burden (simple code, simple tests)

**Result:** A shell that feels professional and powerful while remaining focused on its core purpose - exploring ebook libraries.
