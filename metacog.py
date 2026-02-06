#!/usr/bin/env python3
"""
Metacog - LLM Awareness Engine

Entry point for PyInstaller packaging.
"""

import sys
from pathlib import Path


def get_base_dir() -> Path:
    """Get base directory (works for both dev and frozen exe)"""
    if getattr(sys, 'frozen', False):
        # Running as compiled exe
        return Path(sys.executable).parent
    else:
        # Running as script
        return Path(__file__).parent


def main():
    """Main entry point"""
    base_dir = get_base_dir()

    # Add base dir to path for imports
    sys.path.insert(0, str(base_dir))

    # Set environment for frozen exe
    if getattr(sys, 'frozen', False):
        import os
        # Ensure data directory exists
        data_dir = base_dir / "data"
        data_dir.mkdir(exist_ok=True)

        # Set working directory to exe location
        os.chdir(base_dir)

    # Import and run the app
    from ui.app import main as app_main
    app_main()


if __name__ == "__main__":
    main()
