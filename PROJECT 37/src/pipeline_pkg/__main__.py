"""
Main entry point for the pipeline package.

This module allows the package to be run with `python -m pipeline_pkg`.
"""

from .cli import app

if __name__ == "__main__":
    app()
