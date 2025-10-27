"""Interactive REPL shell for library navigation."""

import shlex
import subprocess
import sys
from pathlib import Path
from typing import Optional, List

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.styles import Style
from rich.console import Console
from rich.table import Table

from ebk.library_db import Library
from ebk.vfs import LibraryVFS, DirectoryNode, FileNode, SymlinkNode
from ebk.repl.grep import GrepMatcher
from ebk.repl.find import FindQuery
from ebk.repl.text_utils import (
    TextUtils,
    parse_head_args,
    parse_tail_args,
    parse_wc_args,
    parse_sort_args,
    parse_uniq_args,
)


class Pipeline:
    """Execute a series of piped commands.

    Implements Unix-like piping where stdout of one command
    becomes stdin of the next.
    """

    def __init__(self, command_line: str):
        """Parse pipeline from command line.

        Args:
            command_line: Full command with pipes, e.g., "cat x | grep y"
        """
        self.commands = [cmd.strip() for cmd in command_line.split("|")]

    def execute(self, shell: "LibraryShell") -> Optional[str]:
        """Execute pipeline, passing stdout between commands.

        Args:
            shell: Shell instance for command execution

        Returns:
            Final output as string, or None on error
        """
        output = None

        for i, cmd_str in enumerate(self.commands):
            # Parse command
            try:
                parts = shlex.split(cmd_str)
            except ValueError as e:
                shell.console.print(f"[red]Parse error in pipeline:[/red] {e}")
                return None

            if not parts:
                continue

            cmd_name = parts[0]
            args = parts[1:] if len(parts) > 1 else []

            # Determine if this is the last command (should show output)
            is_last = (i == len(self.commands) - 1)

            # Execute with stdin from previous command
            output = shell.execute_command(cmd_name, args, stdin=output, silent=not is_last)

            if output is None:
                # Command failed, stop pipeline
                return None

        return output


class PathCompleter(Completer):
    """Tab completion for VFS paths."""

    def __init__(self, vfs: LibraryVFS):
        self.vfs = vfs

    def get_completions(self, document, complete_event):
        """Get path completion candidates."""
        text = document.text_before_cursor
        words = text.split()

        # If we're completing a path argument
        if len(words) > 1:
            partial = words[-1]
        else:
            partial = ""

        # Get completions from VFS
        candidates = self.vfs.complete(partial)

        for candidate in candidates:
            yield Completion(candidate, start_position=-len(partial))


class LibraryShell:
    """Interactive shell for navigating the library VFS.

    Provides a Linux-like shell interface with commands:
    - cd, pwd, ls: Navigate the virtual filesystem
    - cat: Read file content
    - grep: Search file content
    - find: Query metadata with filters
    - open: Open files in system viewer
    - !<bash>: Execute bash commands
    - !ebk <cmd>: Pass through to ebk CLI
    - help, ?, man: Context-sensitive help
    - exit, quit: Exit the shell
    """

    def __init__(self, library_path: Path):
        """Initialize the REPL shell.

        Args:
            library_path: Path to the library
        """
        self.library = Library.open(library_path)
        self.vfs = LibraryVFS(self.library)
        self.console = Console()
        self.running = True
        self.grep_matcher = GrepMatcher(self.vfs)
        self.find_query = FindQuery(self.library)

        # Setup prompt toolkit
        history_file = library_path / ".ebk_history"
        self.session = PromptSession(
            history=FileHistory(str(history_file)),
            completer=PathCompleter(self.vfs),
            style=Style.from_dict(
                {
                    "prompt": "ansicyan bold",
                }
            ),
        )

        # Command registry
        self.commands = {
            "cd": self.cmd_cd,
            "pwd": self.cmd_pwd,
            "ls": self.cmd_ls,
            "cat": self.cmd_cat,
            "grep": self.cmd_grep,
            "find": self.cmd_find,
            "head": self.cmd_head,
            "tail": self.cmd_tail,
            "wc": self.cmd_wc,
            "sort": self.cmd_sort,
            "uniq": self.cmd_uniq,
            "more": self.cmd_more,
            "ln": self.cmd_ln,
            "mv": self.cmd_mv,
            "rm": self.cmd_rm,
            "mkdir": self.cmd_mkdir,
            "echo": self.cmd_echo,
            "tag": self.cmd_tag,
            "untag": self.cmd_untag,
            "help": self.cmd_help,
            "?": self.cmd_help,
            "man": self.cmd_help,
            "exit": self.cmd_exit,
            "quit": self.cmd_quit,
        }

    def get_prompt(self) -> str:
        """Generate prompt showing current path.

        Returns:
            Prompt string like "ebk:/books/42 $ "
        """
        path = self.vfs.pwd()
        if path == "/":
            path = "/"
        return f"ebk:{path} $ "

    def run(self):
        """Run the shell main loop."""
        self.console.print(
            "[bold cyan]ebk shell[/bold cyan] - Interactive library navigation", style="bold"
        )
        self.console.print(f"Library: {self.library.library_path}")
        self.console.print("Type 'help' for available commands, 'exit' to quit.\n")

        while self.running:
            try:
                # Get user input
                line = self.session.prompt(self.get_prompt())
                line = line.strip()

                if not line:
                    continue

                # Parse and execute command
                self.execute(line)

            except KeyboardInterrupt:
                self.console.print("\nUse 'exit' or 'quit' to exit the shell.")
                continue
            except EOFError:
                break
            except Exception as e:
                from rich.markup import escape
                self.console.print(f"[red]Error:[/red] {escape(str(e))}", style="bold")

        self.cleanup()

    def execute(self, line: str):
        """Parse and execute a command line.

        Args:
            line: Command line to execute
        """
        # Handle bash commands (!<bash>)
        if line.startswith("!"):
            self.execute_bash(line[1:])
            return

        # Check for output redirection (>)
        if ">" in line and "|" not in line:
            # Split on > for redirection
            parts = line.split(">", 1)
            if len(parts) == 2:
                cmd_part = parts[0].strip()
                file_path = parts[1].strip()

                # Execute command and capture output
                try:
                    cmd_parts = shlex.split(cmd_part)
                    if not cmd_parts:
                        return

                    cmd = cmd_parts[0]
                    args = cmd_parts[1:]

                    if cmd in self.commands:
                        # Execute with silent=True to capture output
                        output = self.commands[cmd](args, stdin=None, silent=True)

                        # Write output to VFS file
                        if output is not None:
                            self.write_to_vfs_file(file_path, output)
                        return
                    else:
                        self.console.print(f"[red]Unknown command:[/red] {cmd}")
                        return
                except ValueError as e:
                    self.console.print(f"[red]Parse error:[/red] {e}")
                    return

        # Check for pipes
        if "|" in line:
            pipeline = Pipeline(line)
            pipeline.execute(self)
            # Note: Last command in pipeline already printed output (silent=False)
            # so we don't print it again here
            return

        # Parse command and arguments
        try:
            parts = shlex.split(line)
        except ValueError as e:
            self.console.print(f"[red]Parse error:[/red] {e}")
            return

        if not parts:
            return

        cmd = parts[0]
        args = parts[1:]

        # Find and execute command
        if cmd in self.commands:
            self.commands[cmd](args)
        else:
            self.console.print(
                f"[red]Unknown command:[/red] {cmd}. Type 'help' for available commands."
            )

    def execute_command(
        self, cmd_name: str, args: List[str], stdin: Optional[str] = None, silent: bool = False
    ) -> Optional[str]:
        """Execute a command with optional stdin (for piping).

        Args:
            cmd_name: Command name
            args: Command arguments
            stdin: Optional input from previous command in pipeline
            silent: If True, suppress console output (for intermediate pipeline commands)

        Returns:
            Command output as string, or None on error
        """
        if cmd_name not in self.commands:
            self.console.print(f"[red]Unknown command:[/red] {cmd_name}")
            return None

        # Call command with stdin and silent parameters
        return self.commands[cmd_name](args, stdin=stdin, silent=silent)

    def resolve_vfs_path_to_real(self, vfs_path: str) -> Optional[str]:
        """Resolve a VFS path to a real filesystem path.

        Args:
            vfs_path: VFS path (e.g., /books/42/files/book.pdf)

        Returns:
            Real filesystem path or None if not a physical file
        """
        from ebk.vfs.nodes.files import PhysicalFileNode

        # Handle relative paths
        if not vfs_path.startswith('/'):
            current = self.vfs.pwd()
            if current == '/':
                vfs_path = '/' + vfs_path
            else:
                vfs_path = current + '/' + vfs_path

        # Get the node
        node = self.vfs.get_node(vfs_path)
        if node is None:
            return None

        # Check if it's a physical file
        if isinstance(node, PhysicalFileNode):
            # Return the real filesystem path
            file_path = self.library.library_path / node.db_file.path
            return str(file_path)

        return None

    def execute_bash(self, command: str):
        """Execute a bash command.

        VFS paths in the command are automatically resolved to real filesystem paths.

        Args:
            command: Bash command to execute
        """
        # Check for ebk passthrough (!ebk <cmd>)
        if command.startswith("ebk "):
            self.execute_ebk_passthrough(command[4:])
            return

        # Try to resolve VFS paths to real filesystem paths
        # Parse the command to find potential VFS paths
        try:
            parts = shlex.split(command)
            resolved_parts = []

            for i, part in enumerate(parts):
                # Skip the command itself (first part)
                if i == 0:
                    resolved_parts.append(part)
                    continue

                # Try to resolve as VFS path
                real_path = self.resolve_vfs_path_to_real(part)
                if real_path:
                    # Quote the path to handle spaces
                    resolved_parts.append(shlex.quote(real_path))
                else:
                    # Keep original
                    resolved_parts.append(shlex.quote(part))

            # Reconstruct command with resolved paths
            resolved_command = ' '.join(resolved_parts)

        except ValueError:
            # If parsing fails, use original command
            resolved_command = command

        # Execute bash command
        try:
            result = subprocess.run(
                resolved_command, shell=True, capture_output=True, text=True, cwd=str(self.library.library_path)
            )

            if result.stdout:
                self.console.print(result.stdout, end="")
            if result.stderr:
                self.console.print(f"[yellow]{result.stderr}[/yellow]", end="")

            if result.returncode != 0:
                self.console.print(
                    f"[red]Command exited with code {result.returncode}[/red]"
                )

        except Exception as e:
            self.console.print(f"[red]Error executing bash command:[/red] {e}")

    def execute_ebk_passthrough(self, command: str):
        """Execute an ebk CLI command.

        Args:
            command: ebk command (without 'ebk' prefix)
        """
        try:
            # Execute ebk CLI command
            cmd = f"ebk {command}"
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True
            )

            if result.stdout:
                self.console.print(result.stdout, end="")
            if result.stderr:
                self.console.print(f"[yellow]{result.stderr}[/yellow]", end="")

            if result.returncode != 0:
                self.console.print(
                    f"[red]Command exited with code {result.returncode}[/red]"
                )

        except Exception as e:
            self.console.print(f"[red]Error executing ebk command:[/red] {e}")

    # Command implementations

    def cmd_cd(self, args: List[str], stdin: Optional[str] = None, silent: bool = False) -> Optional[str]:
        """Change directory.

        Usage: cd <path>
        """
        if not args:
            # cd with no args goes to root
            path = "/"
        else:
            path = args[0]

        if self.vfs.cd(path):
            # Success - optionally show new location
            return None
        else:
            self.console.print(f"[red]cd: {path}: No such directory[/red]")
            return None

    def cmd_pwd(self, args: List[str], stdin: Optional[str] = None, silent: bool = False) -> Optional[str]:
        """Print working directory.

        Usage: pwd
        """
        path = self.vfs.pwd()
        if not silent:
            self.console.print(path)
        return path

    def cmd_ls(self, args: List[str], stdin: Optional[str] = None, silent: bool = False) -> Optional[str]:
        """List directory contents.

        Usage: ls [path]
        """
        path = args[0] if args else "."

        try:
            nodes = self.vfs.ls(path)
            if not nodes:
                # Either empty directory or error
                node = self.vfs.get_node(path)
                if node is None:
                    if not silent:
                        self.console.print(f"[red]ls: {path}: No such file or directory[/red]")
                    return None
                # Otherwise it's just empty
                return None

            # Create formatted table
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Type", style="cyan")
            table.add_column("Name", style="white")
            table.add_column("Info", style="dim")

            # Collect output for piping
            output_lines = []

            for node in nodes:
                try:
                    # Determine type icon
                    if isinstance(node, DirectoryNode):
                        type_icon = "📁"
                        type_char = "d"
                    elif isinstance(node, SymlinkNode):
                        type_icon = "🔗"
                        type_char = "l"
                    else:
                        type_icon = "📄"
                        type_char = "f"

                    # Get node info
                    info = node.get_info()
                    info_str = self._format_node_info(info)

                    # Apply color to name if present
                    name_str = node.name
                    if "color" in info and info["color"]:
                        try:
                            # Validate that the color is a valid hex code
                            color = info["color"]
                            if color.startswith('#') and len(color) in [4, 7]:
                                name_str = f"[{color}]{node.name}[/]"
                        except Exception:
                            # If color formatting fails, just use plain name
                            pass

                    if not silent:
                        table.add_row(type_icon, name_str, info_str)

                    # Add to output for piping
                    output_lines.append(f"{type_char}\t{node.name}\t{info_str}")
                except Exception as e:
                    # Skip nodes that error, but log the issue
                    if not silent:
                        self.console.print(f"[yellow]Warning: Error reading node {node.name}: {e}[/yellow]")
                    continue

            if not silent:
                self.console.print(table)
            return "\n".join(output_lines) if output_lines else None
        except Exception as e:
            if not silent:
                self.console.print(f"[red]Error: {e}[/red]")
            return None

    def _format_node_info(self, info: dict) -> str:
        """Format node info for display.

        Args:
            info: Node info dict

        Returns:
            Formatted info string
        """
        # Extract key info based on node type
        parts = []

        # File preview (for metadata files)
        if "preview" in info and info["preview"]:
            parts.append(info["preview"])

        if "title" in info:
            parts.append(info["title"])
        if "author" in info:
            parts.append(f"by {info['author']}")
        if "subject" in info:
            parts.append(info["subject"])
        if "book_count" in info:
            parts.append(f"{info['book_count']} books")
        if "score" in info:
            parts.append(f"similarity: {info['score']:.2f}")
        if "size" in info and info["size"] is not None:
            size_mb = info["size"] / (1024 * 1024)
            parts.append(f"{size_mb:.2f} MB")
        if "format" in info:
            parts.append(info["format"].upper())
        if "total_size" in info and info["total_size"] is not None and info["total_size"] > 0:
            size_mb = info["total_size"] / (1024 * 1024)
            parts.append(f"{size_mb:.2f} MB total")
        if "file_count" in info:
            parts.append(f"{info['file_count']} files")
        # Note: color is now applied to the name directly in cmd_ls, not shown here

        return " | ".join(parts) if parts else ""

    def cmd_cat(self, args: List[str], stdin: Optional[str] = None, silent: bool = False) -> Optional[str]:
        """Read file content.

        Usage: cat <file>
        """
        # If stdin provided, just pass it through (for pipeline chaining)
        if stdin:
            if not silent:
                self.console.print(stdin)
            return stdin

        if not args:
            if not silent:
                self.console.print("[red]cat: missing file argument[/red]")
            return None

        path = args[0]
        try:
            content = self.vfs.cat(path)
            if not silent:
                self.console.print(content)
            return content
        except Exception as e:
            if not silent:
                self.console.print(f"[red]cat: {e}[/red]")
            return None

    def cmd_grep(self, args: List[str], stdin: Optional[str] = None, silent: bool = False) -> Optional[str]:
        """Search file content (Unix-like).

        Usage: grep [options] <pattern> [files...]
        Options:
            -r: Recursive search
            -i: Case insensitive
            -n: Show line numbers
        """
        if not args:
            if not silent:
                self.console.print("[red]grep: missing pattern[/red]")
                self.console.print("Usage: grep [options] <pattern> [files...]")
            return None

        # Parse flags
        recursive = False
        ignore_case = False
        line_numbers = False
        pattern = None
        paths = []

        i = 0
        while i < len(args):
            arg = args[i]

            if arg.startswith("-"):
                # Parse flags
                for flag in arg[1:]:
                    if flag == "r":
                        recursive = True
                    elif flag == "i":
                        ignore_case = True
                    elif flag == "n":
                        line_numbers = True
                    else:
                        if not silent:
                            self.console.print(f"[red]grep: unknown option: -{flag}[/red]")
                        return None
            else:
                # First non-flag arg is pattern
                if pattern is None:
                    pattern = arg
                else:
                    # Rest are paths
                    paths.append(arg)

            i += 1

        if pattern is None:
            if not silent:
                self.console.print("[red]grep: missing pattern[/red]")
            return None

        # If stdin provided, grep on stdin content
        if stdin:
            import re
            flags = re.IGNORECASE if ignore_case else 0
            regex = re.compile(pattern, flags)

            matched_lines = []
            for line_num, line in enumerate(stdin.split("\n"), 1):
                if regex.search(line):
                    if line_numbers:
                        matched_lines.append(f"{line_num}:{line}")
                    else:
                        matched_lines.append(line)

            output = "\n".join(matched_lines)
            if output and not silent:
                self.console.print(output)
            return output if output else None

        # Default to current directory if no paths specified
        if not paths:
            paths = ["."]

        # Perform grep on VFS
        try:
            results = self.grep_matcher.grep(
                pattern, paths, recursive, ignore_case, line_numbers
            )

            if not results:
                # No matches found
                return None

            # Display and collect results
            output_lines = []
            for file_path, line_num, line_content in results:
                if line_numbers and line_num > 0:
                    line_str = f"{file_path}:{line_num}:{line_content}"
                    if not silent:
                        self.console.print(f"[cyan]{file_path}[/cyan]:[yellow]{line_num}[/yellow]:{line_content}")
                else:
                    line_str = f"{file_path}:{line_content}"
                    if not silent:
                        self.console.print(f"[cyan]{file_path}[/cyan]:{line_content}")
                output_lines.append(line_str)

            return "\n".join(output_lines) if output_lines else None

        except ValueError as e:
            if not silent:
                self.console.print(f"[red]grep: {e}[/red]")
            return None
        except Exception as e:
            self.console.print(f"[red]grep error: {e}[/red]")
            return None

    def cmd_find(self, args: List[str], stdin: Optional[str] = None, silent: bool = False) -> Optional[str]:
        """Find books with metadata filters.

        Usage: find [filters...]
        Filters: field:value (e.g., author:Knuth, subject:python)

        Fields:
            title:TEXT       - Search by title (partial match)
            author:TEXT      - Search by author (partial match)
            subject:TEXT     - Search by subject/tag (partial match)
            text:TEXT        - Full-text search (title, description, extracted text)
            language:CODE    - Filter by language (exact, e.g., en, fr)
            year:YYYY        - Filter by publication year
            publisher:TEXT   - Search by publisher (partial match)
            format:EXT       - Filter by file format (pdf, epub, mobi)
            limit:N          - Limit results (default: 50)

        Examples:
            find author:Knuth
            find subject:python year:2020
            find language:en format:pdf
            find text:"machine learning" limit:10
            find text:algorithm year:1975
        """
        # stdin is ignored for find (it searches metadata, not text content)

        if not args:
            if not silent:
                self.console.print("[yellow]Usage:[/yellow] find field:value [field:value ...]")
                self.console.print("\n[yellow]Examples:[/yellow]")
                self.console.print("  find author:Knuth")
                self.console.print("  find subject:python year:2020")
                self.console.print("  find language:en format:pdf")
                self.console.print("\n[dim]Type 'help find' for more information.[/dim]")
            return None

        try:
            # Parse filters
            filters = self.find_query.parse_filters(args)

            # Execute find
            books = self.find_query.find(filters)

            if not books:
                if not silent:
                    self.console.print("[yellow]No books found matching filters.[/yellow]")
                return None

            # Display results
            if not silent:
                self.console.print(f"\n[cyan]Found {len(books)} book(s):[/cyan]\n")

            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("ID", style="cyan", width=6)
            table.add_column("Title", style="white")
            table.add_column("Authors", style="green")
            table.add_column("Year", style="yellow", width=6)
            table.add_column("Language", style="dim", width=8)

            # Collect output lines for piping
            output_lines = []

            for book in books:
                book_id = str(book.id)
                title = book.title or "(No title)"
                authors = ", ".join(a.name for a in book.authors) if book.authors else "(No author)"
                # Extract year from publication_date if available
                year = ""
                if book.publication_date:
                    # publication_date can be year, YYYY-MM, or YYYY-MM-DD
                    year = book.publication_date.split("-")[0] if "-" in book.publication_date else book.publication_date
                language = book.language or ""

                if not silent:
                    table.add_row(book_id, title, authors, year, language)

                # Create plain text output for piping
                output_lines.append(f"{book_id}\t{title}\t{authors}\t{year}\t{language}")

            if not silent:
                self.console.print(table)

                # Show usage hint
                self.console.print(
                    f"\n[dim]Tip: Use 'cd /books/<id>' to navigate to a book[/dim]"
                )

            return "\n".join(output_lines) if output_lines else None

        except ValueError as e:
            if not silent:
                self.console.print(f"[red]find: {e}[/red]")
            return None
        except Exception as e:
            if not silent:
                self.console.print(f"[red]find error: {e}[/red]")
            return None

    def cmd_mkdir(self, args: List[str], stdin: Optional[str] = None, silent: bool = False) -> Optional[str]:
        """Create a new tag (directory).

        Usage: mkdir <tag-path>

        Examples:
            mkdir /tags/Work/                    - Create "Work" tag
            mkdir /tags/Work/Project-2024/       - Create "Work/Project-2024" tag
            mkdir /tags/Reading/Fiction/Sci-Fi/  - Create nested tag hierarchy

        Note: Parent tags are created automatically if they don't exist.
        Only works in /tags/ directory.
        """
        from ebk.services.tag_service import TagService

        if len(args) < 1:
            if not silent:
                self.console.print("[red]Usage:[/red] mkdir <tag-path>")
            return None

        target_path = args[0]

        # Only allow creating tags in /tags/
        if not target_path.startswith('/tags/'):
            if not silent:
                self.console.print(f"[red]Can only create tags in /tags/ (e.g., mkdir /tags/NewTag/)[/red]")
            return None

        # Extract tag path from /tags/Work/Project -> Work/Project
        tag_path = target_path.replace('/tags/', '').strip('/')
        if not tag_path:
            if not silent:
                self.console.print(f"[red]Invalid tag path[/red]")
            return None

        # Create the tag
        tag_service = TagService(self.library.session)
        try:
            tag = tag_service.get_or_create_tag(tag_path)
            if not silent:
                self.console.print(f"[green]✓ Created tag '{tag.path}'[/green]")
                if tag.depth > 0:
                    self.console.print(f"  Full path: {tag.path}")
                    self.console.print(f"  Depth: {tag.depth}")
        except Exception as e:
            if not silent:
                self.console.print(f"[red]Error creating tag:[/red] {e}")
            return None

        return None

    def cmd_echo(self, args: List[str], stdin: Optional[str] = None, silent: bool = False) -> Optional[str]:
        """Echo text to stdout or redirect to file.

        Usage: echo <text>
               echo <text> > <file>

        Examples:
            echo "Hello World"                          - Print to console
            echo "My description" > /tags/Work/description  - Write to file

        Note: Redirection (>) is handled by the execute() method.
        """
        # Join all arguments with spaces
        text = " ".join(args)

        if not silent:
            self.console.print(text)

        # Return the text for potential redirection
        return text

    def write_to_vfs_file(self, path: str, content: str) -> None:
        """Write content to a VFS file.

        Args:
            path: VFS path to file
            content: Content to write
        """
        from ebk.vfs.base import FileNode

        # Resolve the path
        node = self.vfs.get_node(path)

        if node is None:
            self.console.print(f"[red]File not found:[/red] {path}")
            return

        if not isinstance(node, FileNode):
            self.console.print(f"[red]Not a file:[/red] {path}")
            return

        # Check if writable
        if not node.is_writable():
            self.console.print(f"[red]File is read-only:[/red] {path}")
            return

        # Write content
        try:
            node.write_content(content)
            self.console.print(f"[green]✓ Wrote to {path}[/green]")
        except Exception as e:
            self.console.print(f"[red]Error writing to file:[/red] {e}")

    def cmd_tag(self, args: List[str], stdin: Optional[str] = None, silent: bool = False) -> Optional[str]:
        """Tag a book (context-aware shorthand for ln).

        Usage: tag <tag-path> [book-id]

        If book-id is omitted, uses current directory (must be in /books/ID/).
        Tag paths can be relative to /tags/ (no need to prefix with /tags/).

        Examples:
            tag Work                    # From /books/42/: tag current book with Work
            tag Work/Project-2024       # Tag with nested tag
            tag Reading 1555            # Tag book 1555 with Reading (from anywhere)
            tag Fiction/Sci-Fi 1555     # Tag book 1555 with Fiction/Sci-Fi
        """
        from ebk.db.models import Book

        if len(args) < 1:
            if not silent:
                self.console.print("[red]Usage:[/red] tag <tag-path> [book-id]")
            return None

        tag_path = args[0]
        book_id = None

        # If book ID provided, use it
        if len(args) >= 2:
            try:
                book_id = int(args[1])
            except ValueError:
                if not silent:
                    self.console.print(f"[red]Invalid book ID:[/red] {args[1]}")
                return None
        else:
            # Try to infer from current directory
            pwd = self.vfs.pwd()
            if pwd.startswith('/books/'):
                parts = pwd.strip('/').split('/')
                if len(parts) >= 2:
                    try:
                        book_id = int(parts[1])
                    except ValueError:
                        pass

            if book_id is None:
                if not silent:
                    self.console.print("[red]Error:[/red] Not in a book directory and no book ID provided")
                    self.console.print("[yellow]Usage:[/yellow] tag <tag-path> [book-id]")
                return None

        # Normalize tag path (remove /tags/ prefix if present)
        if tag_path.startswith('/tags/'):
            tag_path = tag_path.replace('/tags/', '').strip('/')
        tag_path = tag_path.strip('/')

        # Build full VFS paths for ln command
        source = f"/books/{book_id}"
        dest = f"/tags/{tag_path}/"

        # Delegate to ln command
        return self.cmd_ln([source, dest], stdin, silent)

    def cmd_untag(self, args: List[str], stdin: Optional[str] = None, silent: bool = False) -> Optional[str]:
        """Remove a tag from a book (context-aware shorthand for rm).

        Usage: untag <tag-path> [book-id]

        If book-id is omitted, uses current directory (must be in /books/ID/).
        Tag paths can be relative to /tags/ (no need to prefix with /tags/).

        Examples:
            untag Work                  # From /books/42/: remove Work tag from current book
            untag Work/Project-2024     # Remove nested tag
            untag Reading 1555          # Remove Reading tag from book 1555 (from anywhere)
            untag Fiction/Sci-Fi 1555   # Remove Fiction/Sci-Fi from book 1555
        """
        from ebk.db.models import Book

        if len(args) < 1:
            if not silent:
                self.console.print("[red]Usage:[/red] untag <tag-path> [book-id]")
            return None

        tag_path = args[0]
        book_id = None

        # If book ID provided, use it
        if len(args) >= 2:
            try:
                book_id = int(args[1])
            except ValueError:
                if not silent:
                    self.console.print(f"[red]Invalid book ID:[/red] {args[1]}")
                return None
        else:
            # Try to infer from current directory
            pwd = self.vfs.pwd()
            if pwd.startswith('/books/'):
                parts = pwd.strip('/').split('/')
                if len(parts) >= 2:
                    try:
                        book_id = int(parts[1])
                    except ValueError:
                        pass

            if book_id is None:
                if not silent:
                    self.console.print("[red]Error:[/red] Not in a book directory and no book ID provided")
                    self.console.print("[yellow]Usage:[/yellow] untag <tag-path> [book-id]")
                return None

        # Normalize tag path (remove /tags/ prefix if present)
        if tag_path.startswith('/tags/'):
            tag_path = tag_path.replace('/tags/', '').strip('/')
        tag_path = tag_path.strip('/')

        # Build full VFS path for rm command
        target = f"/tags/{tag_path}/{book_id}"

        # Delegate to rm command
        return self.cmd_rm([target], stdin, silent)

    def cmd_help(self, args: List[str], stdin: Optional[str] = None, silent: bool = False) -> Optional[str]:
        """Show help information.

        Usage: help [command]
        """
        if args:
            # Show help for specific command
            cmd = args[0]
            if cmd in self.commands:
                func = self.commands[cmd]
                self.console.print(f"[bold]{cmd}[/bold]")
                self.console.print(func.__doc__ or "No documentation available.")
            else:
                self.console.print(f"[red]Unknown command:[/red] {cmd}")
        else:
            # Show general help
            self.console.print("[bold cyan]Available Commands:[/bold cyan]\n")

            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Command", style="cyan")
            table.add_column("Description", style="white")

            table.add_row("cd <path>", "Change directory")
            table.add_row("pwd", "Print working directory")
            table.add_row("ls [path]", "List directory contents")
            table.add_row("cat <file>", "Read file content")
            table.add_row("grep <pattern>", "Search file content (Unix-like)")
            table.add_row("find <filters>", "Find books with metadata filters")
            table.add_row("head [-n N]", "Show first N lines")
            table.add_row("tail [-n N]", "Show last N lines")
            table.add_row("wc [-lwc]", "Count lines, words, characters")
            table.add_row("sort [-r]", "Sort lines")
            table.add_row("uniq [-c]", "Remove duplicate lines")
            table.add_row("more", "Paginate output")
            table.add_row("ln <src> <dest>", "Link book to tag (ln /books/42 /tags/Work/)")
            table.add_row("mv <src> <dest>", "Move book between tags")
            table.add_row("rm [-r] <path>", "Remove tag from book, delete tag, or DELETE book")
            table.add_row("mkdir <path>", "Create new tag (mkdir /tags/Work/)")
            table.add_row("echo <text>", "Echo text (supports > redirection)")
            table.add_row("tag <tag-path> [id]", "Tag a book (context-aware)")
            table.add_row("untag <tag-path> [id]", "Remove tag from book (context-aware)")
            table.add_row("!<cmd> <file>", "Execute system command (auto-resolves VFS paths)")
            table.add_row("!ebk <cmd>", "Pass through to ebk CLI")
            table.add_row("help [cmd]", "Show help")
            table.add_row("exit, quit", "Exit the shell")

            self.console.print(table)

            self.console.print("\n[bold cyan]Piping:[/bold cyan]")
            self.console.print("  Commands can be chained with | (pipe)")
            self.console.print("  Example: cat text | grep python | head -20")
            self.console.print("  Example: find author:Knuth | wc -l")

            self.console.print("\n[bold cyan]Output Redirection:[/bold cyan]")
            self.console.print("  Use > to redirect output to VFS files")
            self.console.print("  Example: echo \"My notes\" > /tags/Work/description")
            self.console.print("  Example: echo \"#FF5733\" > /tags/Work/color")

            self.console.print("\n[bold cyan]System Commands:[/bold cyan]")
            self.console.print("  Use ! prefix to run system commands")
            self.console.print("  VFS paths are auto-resolved to real filesystem paths")
            self.console.print("  Example: !xdg-open book.pdf    - Opens file in default viewer")
            self.console.print("  Example: !evince book.pdf      - Opens with specific program")
            self.console.print("  Example: !ls -lh               - Run any shell command")

            self.console.print("\n[bold cyan]VFS Structure:[/bold cyan]")
            self.console.print("  /books/       - All books")
            self.console.print("  /books/42/    - Book with ID 42")
            self.console.print("    ├── title, authors, subjects, description")
            self.console.print("    ├── text    - Extracted full text")
            self.console.print("    ├── files/  - Physical files (PDF, EPUB, etc.)")
            self.console.print("    ├── similar/ - Similar books")
            self.console.print("    └── tags/   - Tags for this book (symlinks)")
            self.console.print("  /authors/     - Browse by author")
            self.console.print("  /subjects/    - Browse by subject")
            self.console.print("  /tags/        - Browse by user-defined hierarchical tags")

        return None

    def cmd_head(self, args: List[str], stdin: Optional[str] = None, silent: bool = False) -> Optional[str]:
        """Show first N lines of file or stdin.

        Usage: head [-n NUM] [file]
        """
        try:
            lines, filename = parse_head_args(args)

            # Get content
            if stdin:
                content = stdin
            elif filename:
                content = self.vfs.cat(filename)
            else:
                if not silent:
                    self.console.print("[yellow]Usage: head [-n NUM] [file][/yellow]")
                return None

            # Process
            output = TextUtils.head(content, lines)
            if not silent:
                self.console.print(output)
            return output

        except ValueError as e:
            if not silent:
                self.console.print(f"[red]{e}[/red]")
            return None

    def cmd_tail(self, args: List[str], stdin: Optional[str] = None, silent: bool = False) -> Optional[str]:
        """Show last N lines of file or stdin.

        Usage: tail [-n NUM] [file]
        """
        try:
            lines, filename = parse_tail_args(args)

            # Get content
            if stdin:
                content = stdin
            elif filename:
                content = self.vfs.cat(filename)
            else:
                if not silent:
                    self.console.print("[yellow]Usage: tail [-n NUM] [file][/yellow]")
                return None

            # Process
            output = TextUtils.tail(content, lines)
            if not silent:
                self.console.print(output)
            return output

        except ValueError as e:
            if not silent:
                self.console.print(f"[red]{e}[/red]")
            return None

    def cmd_wc(self, args: List[str], stdin: Optional[str] = None, silent: bool = False) -> Optional[str]:
        """Count lines, words, and characters.

        Usage: wc [-l|-w|-c] [file]
        """
        try:
            lines_only, words_only, chars_only, filename = parse_wc_args(args)

            # Get content
            if stdin:
                content = stdin
            elif filename:
                content = self.vfs.cat(filename)
            else:
                if not silent:
                    self.console.print("[yellow]Usage: wc [-l|-w|-c] [file][/yellow]")
                return None

            # Process
            output = TextUtils.wc(content, lines_only, words_only, chars_only)
            if not silent:
                self.console.print(output)
            return output

        except ValueError as e:
            if not silent:
                self.console.print(f"[red]{e}[/red]")
            return None

    def cmd_sort(self, args: List[str], stdin: Optional[str] = None, silent: bool = False) -> Optional[str]:
        """Sort lines alphabetically.

        Usage: sort [-r] [file]
        """
        try:
            reverse, filename = parse_sort_args(args)

            # Get content
            if stdin:
                content = stdin
            elif filename:
                content = self.vfs.cat(filename)
            else:
                if not silent:
                    self.console.print("[yellow]Usage: sort [-r] [file][/yellow]")
                return None

            # Process
            output = TextUtils.sort_lines(content, reverse)
            if not silent:
                self.console.print(output)
            return output

        except ValueError as e:
            if not silent:
                self.console.print(f"[red]{e}[/red]")
            return None

    def cmd_uniq(self, args: List[str], stdin: Optional[str] = None, silent: bool = False) -> Optional[str]:
        """Remove duplicate adjacent lines.

        Usage: uniq [-c] [file]
        """
        try:
            count, filename = parse_uniq_args(args)

            # Get content
            if stdin:
                content = stdin
            elif filename:
                content = self.vfs.cat(filename)
            else:
                if not silent:
                    self.console.print("[yellow]Usage: uniq [-c] [file][/yellow]")
                return None

            # Process
            output = TextUtils.uniq(content, count)
            if not silent:
                self.console.print(output)
            return output

        except ValueError as e:
            if not silent:
                self.console.print(f"[red]{e}[/red]")
            return None

    def cmd_more(self, args: List[str], stdin: Optional[str] = None, silent: bool = False) -> Optional[str]:
        """Paginate output.

        Usage: more [file]
        """
        # Get content
        if stdin:
            content = stdin
        elif args:
            content = self.vfs.cat(args[0])
        else:
            if not silent:
                self.console.print("[yellow]Usage: more [file][/yellow]")
            return None

        # Use Rich's pager (only if not silent)
        if not silent:
            with self.console.pager():
                self.console.print(content)

        return content

    def cmd_exit(self, args: List[str], stdin: Optional[str] = None, silent: bool = False) -> Optional[str]:
        """Exit the shell.

        Usage: exit
        """
        self.running = False
        self.console.print("[cyan]Goodbye![/cyan]")
        return None

    def cmd_quit(self, args: List[str], stdin: Optional[str] = None, silent: bool = False) -> Optional[str]:
        """Quit the shell.

        Usage: quit
        """
        return self.cmd_exit(args, stdin)

    def cmd_ln(self, args: List[str], stdin: Optional[str] = None, silent: bool = False) -> Optional[str]:
        """Link (add tag to book).

        Usage: ln <source> <dest>

        Examples:
            ln /books/42 /tags/Work/          - Add "Work" tag to book 42
            ln /books/42 /tags/Work/Project/  - Add "Work/Project" tag to book 42
            ln /tags/Work/42 /tags/Archive/   - Add "Archive" tag (resolves symlink)
            ln /subjects/computers/42 /tags/Reading/  - Tag book from subject

        Note: Creates a link/relationship between a book and a tag without
        removing any existing tags. Books are canonical entities at /books/ID/,
        tags are views/links to books. Source can be a direct book path or
        a symlink (which will be automatically resolved to the book ID).
        """
        from ebk.services.tag_service import TagService
        from ebk.db.models import Book

        if len(args) < 2:
            if not silent:
                self.console.print("[red]Usage:[/red] ln <source> <dest>")
            return None

        source_path = args[0]
        dest_path = args[1]

        # Resolve source to book
        source_node = self.vfs.get_node(source_path)
        if source_node is None:
            if not silent:
                self.console.print(f"[red]Source not found:[/red] {source_path}")
            return None

        # Extract book ID from source
        # Handle:
        # 1. Direct book paths: /books/42
        # 2. Symlinks in tags: /tags/Work/42 (VFS resolves to BookNode)
        # 3. Symlinks in subjects: /subjects/computers/42
        # 4. Symlinks in authors: /authors/knuth-donald/42
        book_id = None

        from ebk.vfs.base import SymlinkNode
        from ebk.vfs.nodes.books import BookNode

        # If source is a BookNode (VFS auto-resolves symlinks), extract book ID
        if hasattr(source_node, 'book') and hasattr(source_node.book, 'id'):
            book_id = source_node.book.id
        # If source is a symlink, extract book ID from target path
        elif isinstance(source_node, SymlinkNode):
            # Target path is like "/books/42"
            target_parts = source_node.target_path.strip('/').split('/')
            if target_parts[0] == 'books' and len(target_parts) >= 2:
                try:
                    book_id = int(target_parts[1])
                except ValueError:
                    pass
        else:
            # Try to extract from original path
            path_parts = source_path.strip('/').split('/')
            if path_parts[0] == 'books' and len(path_parts) >= 2:
                try:
                    book_id = int(path_parts[1])
                except ValueError:
                    pass

        if book_id is None:
            if not silent:
                self.console.print(f"[red]Source must be a book or book symlink (e.g., /books/42 or /tags/Work/42)[/red]")
            return None

        # Get book from database
        book = self.library.session.query(Book).filter_by(id=book_id).first()
        if not book:
            if not silent:
                self.console.print(f"[red]Book {book_id} not found[/red]")
            return None

        # Resolve destination to tag path
        if not dest_path.startswith('/tags/'):
            if not silent:
                self.console.print(f"[red]Destination must be a tag path (e.g., /tags/Work/)[/red]")
            return None

        # Extract tag path from destination
        tag_path = dest_path.replace('/tags/', '').strip('/')
        if not tag_path:
            if not silent:
                self.console.print(f"[red]Invalid tag path[/red]")
            return None

        # Add tag to book
        tag_service = TagService(self.library.session)
        try:
            tag = tag_service.add_tag_to_book(book, tag_path)
            if not silent:
                self.console.print(f"[green]✓ Added tag '{tag.path}' to book {book.id}[/green]")
                if book.title:
                    self.console.print(f"  Book: {book.title}")
        except Exception as e:
            if not silent:
                self.console.print(f"[red]Error adding tag:[/red] {e}")
            return None

        return None

    def cmd_mv(self, args: List[str], stdin: Optional[str] = None, silent: bool = False) -> Optional[str]:
        """Move (change tag on book).

        Usage: mv <source> <dest>

        Examples:
            mv /tags/Work/42 /tags/Archive/  - Move book 42 from Work to Archive

        Note: This removes the source tag and adds the destination tag.
        Use 'cp' to add a tag without removing the old one.
        """
        from ebk.services.tag_service import TagService
        from ebk.db.models import Book

        if len(args) < 2:
            if not silent:
                self.console.print("[red]Usage:[/red] mv <source> <dest>")
            return None

        source_path = args[0]
        dest_path = args[1]

        # Both source and dest should be tag paths for mv
        if not source_path.startswith('/tags/'):
            if not silent:
                self.console.print(f"[red]Source must be a tag path (e.g., /tags/Work/42)[/red]")
            return None

        if not dest_path.startswith('/tags/'):
            if not silent:
                self.console.print(f"[red]Destination must be a tag path (e.g., /tags/Archive/)[/red]")
            return None

        # Extract source tag path and book ID
        source_parts = source_path.replace('/tags/', '').strip('/').split('/')
        if len(source_parts) < 2:
            if not silent:
                self.console.print(f"[red]Source must include tag and book ID (e.g., /tags/Work/42)[/red]")
            return None

        # Last part is book ID
        try:
            book_id = int(source_parts[-1])
        except ValueError:
            if not silent:
                self.console.print(f"[red]Invalid book ID in source path[/red]")
            return None

        # Everything except last part is the source tag path
        source_tag_path = '/'.join(source_parts[:-1])

        # Get book from database
        book = self.library.session.query(Book).filter_by(id=book_id).first()
        if not book:
            if not silent:
                self.console.print(f"[red]Book {book_id} not found[/red]")
            return None

        # Extract destination tag path
        dest_tag_path = dest_path.replace('/tags/', '').strip('/')
        if not dest_tag_path:
            if not silent:
                self.console.print(f"[red]Invalid destination tag path[/red]")
            return None

        # Remove source tag and add destination tag
        tag_service = TagService(self.library.session)
        try:
            # Remove old tag
            removed = tag_service.remove_tag_from_book(book, source_tag_path)
            if not removed:
                if not silent:
                    self.console.print(f"[yellow]Warning: Book didn't have tag '{source_tag_path}'[/yellow]")

            # Add new tag
            tag = tag_service.add_tag_to_book(book, dest_tag_path)

            if not silent:
                self.console.print(f"[green]✓ Moved book {book.id} from '{source_tag_path}' to '{tag.path}'[/green]")
                if book.title:
                    self.console.print(f"  Book: {book.title}")
        except Exception as e:
            if not silent:
                self.console.print(f"[red]Error moving tag:[/red] {e}")
            return None

        return None

    def _rm_book(self, target_path: str, silent: bool = False) -> Optional[str]:
        """Delete a book from the library - SCARY operation!

        Args:
            target_path: Path like /books/42/
            silent: If True, suppress output

        Returns:
            None
        """
        from ebk.db.models import Book

        # Extract book ID from path
        path_parts = target_path.strip('/').split('/')
        if path_parts[0] != 'books' or len(path_parts) < 2:
            if not silent:
                self.console.print(f"[red]Invalid book path:[/red] {target_path}")
                self.console.print("[yellow]Expected format:[/yellow] /books/ID/")
            return None

        try:
            book_id = int(path_parts[1])
        except ValueError:
            if not silent:
                self.console.print(f"[red]Invalid book ID:[/red] {path_parts[1]}")
            return None

        # Get book from database
        book = self.library.session.query(Book).filter_by(id=book_id).first()
        if not book:
            if not silent:
                self.console.print(f"[red]Book {book_id} not found[/red]")
            return None

        # SCARY CONFIRMATION
        if not silent:
            self.console.print("[bold red]⚠️  WARNING: DELETE BOOK ⚠️[/bold red]")
            self.console.print(f"\n[red]You are about to PERMANENTLY DELETE this book:[/red]")
            self.console.print(f"  ID: {book.id}")
            if book.title:
                self.console.print(f"  Title: {book.title}")
            if book.authors:
                self.console.print(f"  Authors: {', '.join([a.name for a in book.authors])}")

            # Count files
            file_count = len(book.files) if hasattr(book, 'files') else 0
            if file_count > 0:
                self.console.print(f"  Files: {file_count} file(s) will be deleted")

            self.console.print("\n[bold red]This operation CANNOT be undone![/bold red]")
            self.console.print("[yellow]Type 'DELETE' (all caps) to confirm, or anything else to cancel:[/yellow]")

            # Get confirmation from user
            confirmation = self.session.prompt("Confirm deletion: ")

            if confirmation != "DELETE":
                self.console.print("[green]✓ Cancelled - book was NOT deleted[/green]")
                return None

        # Delete the book
        try:
            # Delete associated files from filesystem
            for file in book.files:
                file_path = self.library.library_path / file.path
                if file_path.exists():
                    file_path.unlink()

            # Delete from database (SQLAlchemy will handle cascading deletes)
            self.library.session.delete(book)
            self.library.session.commit()

            if not silent:
                self.console.print(f"[bold red]✓ Book {book_id} has been DELETED[/bold red]")
        except Exception as e:
            self.library.session.rollback()
            if not silent:
                self.console.print(f"[red]Error deleting book:[/red] {e}")
            return None

        return None

    def cmd_rm(self, args: List[str], stdin: Optional[str] = None, silent: bool = False) -> Optional[str]:
        """Remove (remove tag from book, delete tag, or DELETE book).

        Usage: rm <path>

        Examples:
            rm /tags/Work/42      - Remove "Work" tag from book 42
            rm /tags/Work/        - Delete "Work" tag (requires -r flag if has children)
            rm /books/42/         - DELETE book (requires typing 'DELETE' to confirm)

        Options:
            -r    Recursively delete tag and all children
        """
        from ebk.services.tag_service import TagService
        from ebk.db.models import Book

        if len(args) < 1:
            if not silent:
                self.console.print("[red]Usage:[/red] rm [-r] <path>")
            return None

        # Parse flags
        recursive = False
        paths = []
        for arg in args:
            if arg == '-r':
                recursive = True
            else:
                paths.append(arg)

        if not paths:
            if not silent:
                self.console.print("[red]Usage:[/red] rm [-r] <path>")
            return None

        target_path = paths[0]

        # Handle /books/ID/ deletion - SCARY!
        if target_path.startswith('/books/'):
            return self._rm_book(target_path, silent)

        if not target_path.startswith('/tags/'):
            if not silent:
                self.console.print(f"[red]Path must be /books/ID/ or /tags/... (e.g., /tags/Work/42 or /tags/Work/)[/red]")
            return None

        # Extract tag path components
        path_parts = target_path.replace('/tags/', '').strip('/').split('/')

        # Check if last part is a book ID
        try:
            book_id = int(path_parts[-1])
            # This is a book within a tag - remove tag from book
            tag_path = '/'.join(path_parts[:-1])

            # Get book from database
            book = self.library.session.query(Book).filter_by(id=book_id).first()
            if not book:
                if not silent:
                    self.console.print(f"[red]Book {book_id} not found[/red]")
                return None

            # Remove tag from book
            tag_service = TagService(self.library.session)
            try:
                removed = tag_service.remove_tag_from_book(book, tag_path)
                if removed:
                    if not silent:
                        self.console.print(f"[green]✓ Removed tag '{tag_path}' from book {book.id}[/green]")
                        if book.title:
                            self.console.print(f"  Book: {book.title}")
                else:
                    if not silent:
                        self.console.print(f"[yellow]Book {book.id} didn't have tag '{tag_path}'[/yellow]")
            except Exception as e:
                if not silent:
                    self.console.print(f"[red]Error removing tag:[/red] {e}")
                return None

        except ValueError:
            # This is a tag directory - delete the tag itself
            tag_path = '/'.join(path_parts)

            tag_service = TagService(self.library.session)
            try:
                deleted = tag_service.delete_tag(tag_path, delete_children=recursive)
                if deleted:
                    if not silent:
                        self.console.print(f"[green]✓ Deleted tag '{tag_path}'[/green]")
                else:
                    if not silent:
                        self.console.print(f"[yellow]Tag '{tag_path}' not found[/yellow]")
            except ValueError as e:
                if not silent:
                    self.console.print(f"[red]Error:[/red] {e}")
                    self.console.print(f"[yellow]Hint:[/yellow] Use 'rm -r {target_path}' to delete tag and its children")
                return None
            except Exception as e:
                if not silent:
                    self.console.print(f"[red]Error deleting tag:[/red] {e}")
                return None

        return None

    def cleanup(self):
        """Clean up resources."""
        self.library.close()
