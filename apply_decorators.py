#!/usr/bin/env python3
"""Script to apply handle_library_errors decorator to CLI commands."""

import re
from pathlib import Path

cli_file = Path("/home/spinoza/github/repos/ebk/ebk/cli.py")
content = cli_file.read_text()

# Commands that need the decorator
commands_to_update = [
    "add", "remove", "remove_index", "remove_id", 
    "update_index", "update_id", "search", "export_dag", 
    "export_multi", "rate", "comment", "mark", 
    "personal_stats", "recommend", "similar", "list_indices", "ls"
]

# Add decorator to commands that don't have it
for cmd in commands_to_update:
    # Pattern to find the command definition
    pattern = rf"(@app\.command\(\))\n(def {cmd}\()"
    
    # Check if decorator already exists
    if f"@handle_library_errors\ndef {cmd}(" not in content:
        # Add the decorator
        replacement = r"\1\n@handle_library_errors\n\2"
        content = re.sub(pattern, replacement, content)
        print(f"Added decorator to {cmd}")

# Now remove the try/except blocks for FileNotFoundError
# This is more complex as we need to maintain proper indentation

# Pattern to match the try/except blocks with FileNotFoundError
error_pattern = r'''    try:
        lib = Library\.open\(lib_dir\)(.+?)    except FileNotFoundError:
        console\.print\(f"\[bold red\]Error:\[/bold red\] The library directory '{lib_dir}' does not exist\."\)
        raise typer\.Exit\(code=1\)
    except Exception as e:
        logger\.error\(.+?\)
        console\.print\(.+?\)
        raise typer\.Exit\(code=1\)'''

# Simplified replacement - just the body without try/except
def replace_error_blocks(match):
    body = match.group(1)
    # Remove one level of indentation from the body
    lines = body.split('\n')
    unindented = []
    for line in lines:
        if line.startswith('        '):
            unindented.append(line[4:])  # Remove 4 spaces
        else:
            unindented.append(line)
    return '    lib = Library.open(lib_dir)' + '\n'.join(unindented)

content = re.sub(error_pattern, replace_error_blocks, content, flags=re.DOTALL)

# Write back the modified content
cli_file.write_text(content)
print("Applied decorators and removed duplicate error handling!")