#!/usr/bin/env python3
"""Fix indentation issues in CLI file."""

import re
from pathlib import Path

cli_file = Path("/home/spinoza/github/repos/ebk/ebk/cli.py")
lines = cli_file.read_text().split('\n')

fixed_lines = []
in_function = False
indent_level = 0

for i, line in enumerate(lines):
    stripped = line.lstrip()
    
    # Track function definitions
    if line.startswith('def '):
        in_function = True
        indent_level = 0
    elif line and not line[0].isspace() and in_function and 'def ' not in line and '@' not in line:
        # This line should probably be indented
        if any(kw in stripped for kw in ['console.print', 'lib =', 'raise typer', 'try:', 'except', 'entry =', 'results =']):
            # Should be indented to 4 spaces
            line = '    ' + stripped
    
    fixed_lines.append(line)

# Write back
cli_file.write_text('\n'.join(fixed_lines))
print("Fixed indentation issues!")