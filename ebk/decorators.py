"""Decorators for ebk functionality."""

import functools
import logging
from pathlib import Path
from typing import Callable, Any
import typer
from rich.console import Console

logger = logging.getLogger(__name__)
console = Console()


def handle_library_errors(func: Callable) -> Callable:
    """
    Decorator to handle common library operation errors.
    
    Reduces code duplication by centralizing error handling for:
    - FileNotFoundError: Library doesn't exist
    - PermissionError: No access to files
    - ValueError: Invalid data or arguments
    - General exceptions: Unexpected errors
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        try:
            return func(*args, **kwargs)
        except FileNotFoundError as e:
            console.print(f"[bold red]Error:[/bold red] Library or file not found: {e}")
            raise typer.Exit(code=1)
        except PermissionError as e:
            console.print(f"[bold red]Error:[/bold red] Permission denied: {e}")
            console.print("[yellow]Tip: Check file permissions or run with appropriate privileges[/yellow]")
            raise typer.Exit(code=1)
        except ValueError as e:
            console.print(f"[bold red]Error:[/bold red] Invalid input: {e}")
            raise typer.Exit(code=1)
        except KeyboardInterrupt:
            console.print("\n[yellow]Operation cancelled by user[/yellow]")
            raise typer.Exit(code=130)
        except Exception as e:
            logger.error(f"Unexpected error in {func.__name__}: {e}", exc_info=True)
            console.print(f"[bold red]Unexpected error:[/bold red] {e}")
            console.print("[dim]See log file for details[/dim]")
            raise typer.Exit(code=1)
    
    return wrapper


def validate_path(path_type: str = "directory") -> Callable:
    """
    Decorator to validate and sanitize file paths for security.
    
    Args:
        path_type: Either "directory" or "file"
    
    Prevents:
        - Path traversal attacks
        - Access to system directories
        - Symbolic link attacks
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # Find path arguments (usually first positional arg)
            if args:
                path = Path(args[0]).resolve()
                
                # Security checks
                try:
                    # Ensure path is within current directory or explicitly allowed
                    cwd = Path.cwd()
                    home = Path.home()
                    
                    # Check if path is trying to escape to system directories
                    if path.parts[0] in ('/', '\\') and not (
                        path.is_relative_to(cwd) or 
                        path.is_relative_to(home)
                    ):
                        raise ValueError(f"Access to system path not allowed: {path}")
                    
                    # Check for suspicious patterns
                    suspicious_patterns = ['../', '...', '~/', '/etc/', '/usr/', '/bin/', '/sys/']
                    path_str = str(path)
                    for pattern in suspicious_patterns:
                        if pattern in path_str and not path.is_relative_to(home):
                            raise ValueError(f"Suspicious path pattern detected: {pattern}")
                    
                    # Validate based on type
                    if path_type == "directory":
                        if path.exists() and not path.is_dir():
                            raise ValueError(f"Path exists but is not a directory: {path}")
                    elif path_type == "file":
                        if path.exists() and not path.is_file():
                            raise ValueError(f"Path exists but is not a file: {path}")
                    
                    # Replace the path with the resolved, safe version
                    args = (str(path),) + args[1:]
                    
                except ValueError as e:
                    console.print(f"[bold red]Security Error:[/bold red] {e}")
                    raise typer.Exit(code=1)
            
            return func(*args, **kwargs)
        
        return wrapper
    return decorator


def require_confirmation(message: str = "Are you sure you want to continue?") -> Callable:
    """
    Decorator to require user confirmation for destructive operations.
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # Check if --yes flag was passed (common pattern)
            if kwargs.get('yes', False):
                return func(*args, **kwargs)
            
            # Ask for confirmation
            console.print(f"[yellow]⚠️  {message}[/yellow]")
            response = typer.confirm("Continue?")
            
            if not response:
                console.print("[red]Operation cancelled[/red]")
                raise typer.Exit(code=0)
            
            return func(*args, **kwargs)
        
        return wrapper
    return decorator