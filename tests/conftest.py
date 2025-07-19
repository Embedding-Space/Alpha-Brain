"""Shared test fixtures and configuration."""

import sys
from pathlib import Path

# Add src to path for all tests
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
