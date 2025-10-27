#!/usr/bin/env python3
"""Fix all indentation issues in CLI file comprehensively."""

from pathlib import Path

cli_file = Path("/home/spinoza/github/repos/ebk/ebk/cli.py")
lines = cli_file.read_text().split('\n')

fixed_lines = []
in_function = False
expected_indent = 0
in_try_block = False
in_except_block = False

for i, line in enumerate(lines):
    stripped = line.lstrip()
    current_indent = len(line) - len(stripped)
    
    # Track function definitions
    if line.strip().startswith('def '):
        in_function = True
        expected_indent = current_indent + 4
        fixed_lines.append(line)
        continue
    
    # Track decorators and class definitions
    if line.strip().startswith('@') or line.strip().startswith('class '):
        in_function = False
        fixed_lines.append(line)
        continue
    
    # Empty lines
    if not line.strip():
        fixed_lines.append(line)
        continue
    
    # Handle try/except blocks
    if stripped.startswith('try:'):
        in_try_block = True
        in_except_block = False
        if in_function and current_indent < expected_indent:
            line = ' ' * expected_indent + stripped
        fixed_lines.append(line)
        continue
        
    if stripped.startswith('except ') or stripped == 'except:':
        in_try_block = False
        in_except_block = True
        if in_function and current_indent < expected_indent:
            line = ' ' * expected_indent + stripped
        fixed_lines.append(line)
        continue
    
    if stripped.startswith('finally:'):
        in_try_block = False
        in_except_block = False
        if in_function and current_indent < expected_indent:
            line = ' ' * expected_indent + stripped
        fixed_lines.append(line)
        continue
    
    # Fix unindented lines that should be indented
    if in_function and current_indent < expected_indent:
        # These should be at the function body level
        if any(kw in stripped for kw in [
            'lib = Library.open',
            'console.print(',
            'raise typer.Exit',
            'entry = ',
            'results = ',
            'data = ',
            'table = ',
            'stats = ',
            'if ', 'elif ', 'else:',
            'for ', 'while ',
            'with ',
            'return ',
            'pass', 'continue', 'break'
        ]):
            line = ' ' * expected_indent + stripped
        # These need extra indent (inside if/for/with blocks)
        elif any(kw in stripped for kw in [
            'dest_path = ',
            'dest_str = ',
            'task = ',
            'logger.'
        ]):
            # Check if we're inside a block
            if i > 0 and ('if ' in lines[i-1] or 'for ' in lines[i-1] or 'with ' in lines[i-1] or 'elif ' in lines[i-1]):
                line = ' ' * (expected_indent + 4) + stripped
            else:
                line = ' ' * expected_indent + stripped
    
    # Fix over-indented lines
    if stripped.startswith('raise typer.Exit') and current_indent > expected_indent + 8:
        line = ' ' * (expected_indent + 4) + stripped
    
    fixed_lines.append(line)

# Write back
cli_file.write_text('\n'.join(fixed_lines))
print("Fixed all indentation issues comprehensively!")