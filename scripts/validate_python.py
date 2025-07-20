#!/usr/bin/env python
"""Validate Python code by attempting to import all modules."""

import importlib
import sys
from pathlib import Path


def validate_python_files():
    """Try to import all Python modules to catch syntax/import errors."""
    # Add src directory to Python path
    src_path = Path(__file__).parent.parent / "src"
    sys.path.insert(0, str(src_path))
    
    errors = []
    checked = 0
    
    # Find all Python files in src/alpha_brain
    alpha_brain_path = src_path / "alpha_brain"
    for py_file in alpha_brain_path.rglob("*.py"):
        # Skip __pycache__ files
        if "__pycache__" in str(py_file):
            continue
            
        # Convert file path to module name
        relative_path = py_file.relative_to(src_path)
        module_name = str(relative_path.with_suffix("")).replace("/", ".")
        
        # Skip __main__ modules as they execute on import
        if module_name.endswith("__main__"):
            continue
            
        checked += 1
        
        try:
            # Try to import the module
            importlib.import_module(module_name)
            print(f"✓ {module_name}")
        except Exception as e:
            errors.append(f"✗ {module_name}: {e}")
            print(f"✗ {module_name}: {e}")
    
    print(f"\nChecked {checked} modules")
    
    if errors:
        print(f"\n❌ Found {len(errors)} errors:")
        for error in errors:
            print(f"  {error}")
        return 1
    else:
        print("✅ All modules validated successfully!")
        return 0


if __name__ == "__main__":
    sys.exit(validate_python_files())