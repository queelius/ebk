#!/usr/bin/env python3
"""
Quick script to analyze test coverage without running tests.
This gives us an overview of what needs testing.
"""

import os
from pathlib import Path
import ast
import importlib.util


def get_module_functions_and_classes(filepath):
    """Extract all functions and classes from a Python file."""
    with open(filepath, 'r') as f:
        try:
            tree = ast.parse(f.read())
        except SyntaxError:
            return [], []
    
    functions = []
    classes = []
    
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            functions.append(node.name)
        elif isinstance(node, ast.ClassDef):
            classes.append(node.name)
    
    return functions, classes


def analyze_test_coverage():
    """Analyze which modules and functions might need more tests."""
    
    ebk_path = Path("ebk")
    tests_path = Path("tests")
    
    # Get all Python files in ebk package
    ebk_files = list(ebk_path.rglob("*.py"))
    test_files = list(tests_path.glob("test_*.py"))
    
    print("📊 Test Coverage Analysis\n")
    print("=" * 60)
    
    # Modules with no test files
    tested_modules = set()
    for test_file in test_files:
        # Extract what module is being tested from test filename
        module_name = test_file.stem.replace("test_", "")
        tested_modules.add(module_name)
    
    print("\n🔍 Modules that might need test files:")
    print("-" * 40)
    
    untested_modules = []
    for ebk_file in ebk_files:
        if ebk_file.name == "__init__.py":
            continue
        
        module_name = ebk_file.stem
        if module_name not in tested_modules and not any(t in tested_modules for t in [module_name, module_name.replace("_", "")]):
            untested_modules.append(ebk_file)
            try:
                print(f"  ❌ {ebk_file.relative_to(Path.cwd())}")
            except ValueError:
                print(f"  ❌ {ebk_file}")
    
    # Analyze what's tested in test_library_api.py
    print("\n✅ What's tested in test_library_api.py:")
    print("-" * 40)
    
    test_content = (tests_path / "test_library_api.py").read_text()
    tested_methods = set()
    
    # Simple pattern matching for tested methods
    import re
    for match in re.finditer(r'def test_(\w+)', test_content):
        tested_methods.add(match.group(1))
    
    print(f"  Found {len(tested_methods)} test methods")
    
    # Check library.py coverage
    library_file = ebk_path / "library.py"
    if library_file.exists():
        functions, classes = get_module_functions_and_classes(library_file)
        
        print("\n📁 library.py analysis:")
        print(f"  Total classes: {len(classes)}")
        print(f"  Total methods/functions: {len(functions)}")
        
        # New methods we added
        new_methods = [
            "find_similar",
            "recommend",
            "analyze_reading_patterns",
            "export_to_symlink_dag",
            "export_graph"
        ]
        
        print("\n🆕 New methods that need testing:")
        for method in new_methods:
            if method in functions:
                # Check if we have a test for it
                has_test = any(method in test_name for test_name in tested_methods)
                status = "✅" if has_test else "❌"
                print(f"  {status} {method}")
    
    # Check symlink_dag.py
    symlink_file = ebk_path / "exports" / "symlink_dag.py"
    if symlink_file.exists():
        functions, classes = get_module_functions_and_classes(symlink_file)
        print(f"\n📁 exports/symlink_dag.py:")
        print(f"  Classes: {classes}")
        print(f"  Needs test file: test_symlink_dag.py")
    
    # Summary
    print("\n📋 Summary:")
    print("-" * 40)
    print(f"  Total ebk modules: {len(ebk_files)}")
    print(f"  Test files: {len(test_files)}")
    print(f"  Untested modules: {len(untested_modules)}")
    
    print("\n💡 Recommendations:")
    print("  1. Run: make test-coverage")
    print("  2. Focus on testing new features (find_similar, recommend, etc.)")
    print("  3. Add test files for untested modules")
    print("  4. Aim for >80% coverage")


if __name__ == "__main__":
    analyze_test_coverage()