#!/usr/bin/env python3
"""
Import Update Script for FKS Refactor

This script updates import statements across the codebase to reflect
the new Django app structure.

Usage:
    python update_imports.py [--dry-run] [--path PATH]
"""

import os
import re
import argparse
from pathlib import Path
from typing import Dict, List, Tuple


# Import mappings: old_pattern -> new_pattern
IMPORT_MAPPINGS = {
    # Exceptions
    r'from shared_python\.exceptions import': 'from core.exceptions import',
    r'import shared_python\.exceptions': 'import core.exceptions',
    
    # Logging
    r'from data\.app_logging import': 'from core.utils.logging import',
    r'from worker\.fks_logging import': 'from core.utils.logging import',
    r'import data\.app_logging': 'import core.utils.logging',
    r'import worker\.fks_logging': 'import core.utils.logging',
    
    # Registry
    r'from assets\.registry import': 'from core.registry import',
    r'import assets\.registry': 'import core.registry',
    
    # Config
    r'from framework\.config import': 'from config_app import',
    r'import framework\.config': 'import config_app',
    r'from src\.config import': 'from config_app.legacy_config import',
    r'import src\.config': 'import config_app.legacy_config',
    
    # Domain -> Trading App
    r'from domain\.trading\.strategies import': 'from trading_app.strategies import',
    r'from domain\.trading\.indicators import': 'from trading_app.indicators import',
    r'from domain\.trading\.backtesting import': 'from trading_app.backtest import',
    r'from domain\.trading\.execution import': 'from trading_app.execution import',
    r'from domain\.trading\.signals import': 'from trading_app.signals import',
    r'from domain\.trading import': 'from trading_app import',
    r'import domain\.trading': 'import trading_app',
    
    # Framework middleware -> API App
    r'from framework\.middleware import': 'from api_app.middleware import',
    r'import framework\.middleware': 'import api_app.middleware',
    
    # Framework cache -> Core
    r'from framework\.cache import': 'from core.cache import',
    r'import framework\.cache': 'import core.cache',
    
    # Framework patterns -> Core
    r'from framework\.patterns import': 'from core.patterns import',
    r'import framework\.patterns': 'import core.patterns',
    
    # Root files -> Trading App
    r'from src\.backtest import': 'from trading_app.backtest.legacy_engine import',
    r'from src\.optimizer import': 'from trading_app.optimizer import',
    r'from src\.signals import': 'from trading_app.signals.legacy_generator import',
    r'import src\.backtest': 'import trading_app.backtest.legacy_engine',
    r'import src\.optimizer': 'import trading_app.optimizer',
    r'import src\.signals': 'import trading_app.signals.legacy_generator',
    
    # Engine -> Trading App
    r'from engine import': 'from trading_app.engine import',
    r'import engine': 'import trading_app.engine',
}


def find_python_files(root_path: Path, exclude_dirs: List[str] = None) -> List[Path]:
    """Find all Python files in the directory tree."""
    if exclude_dirs is None:
        exclude_dirs = ['__pycache__', '.git', 'node_modules', 'venv', 'env', '.venv']
    
    python_files = []
    for dirpath, dirnames, filenames in os.walk(root_path):
        # Remove excluded directories from search
        dirnames[:] = [d for d in dirnames if d not in exclude_dirs]
        
        for filename in filenames:
            if filename.endswith('.py'):
                python_files.append(Path(dirpath) / filename)
    
    return python_files


def update_imports_in_file(file_path: Path, mappings: Dict[str, str], dry_run: bool = False) -> Tuple[int, List[str]]:
    """
    Update import statements in a file.
    
    Returns:
        Tuple of (number of changes, list of changes made)
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return 0, []
    
    original_content = content
    changes = []
    
    for old_pattern, new_pattern in mappings.items():
        # Find all matches
        matches = list(re.finditer(old_pattern, content))
        if matches:
            # Replace all matches
            content = re.sub(old_pattern, new_pattern, content)
            for match in matches:
                changes.append(f"  {match.group(0)} -> {new_pattern}")
    
    if content != original_content:
        if not dry_run:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
            except Exception as e:
                print(f"Error writing {file_path}: {e}")
                return 0, []
        
        return len(changes), changes
    
    return 0, []


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Update imports in FKS project')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be changed without making changes')
    parser.add_argument('--path', type=str, default='src', help='Root path to process (default: src)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show detailed changes')
    args = parser.parse_args()
    
    # Get root path
    root_path = Path(__file__).parent / args.path
    if not root_path.exists():
        print(f"Error: Path {root_path} does not exist")
        return 1
    
    print(f"{'DRY RUN: ' if args.dry_run else ''}Updating imports in {root_path}")
    print(f"Found {len(IMPORT_MAPPINGS)} import mapping rules")
    print()
    
    # Find all Python files
    python_files = find_python_files(root_path)
    print(f"Found {len(python_files)} Python files")
    print()
    
    # Update imports in each file
    total_changes = 0
    files_changed = 0
    
    for file_path in python_files:
        num_changes, changes = update_imports_in_file(file_path, IMPORT_MAPPINGS, args.dry_run)
        
        if num_changes > 0:
            files_changed += 1
            total_changes += num_changes
            rel_path = file_path.relative_to(root_path.parent)
            print(f"{'[DRY RUN] ' if args.dry_run else ''}Updated {rel_path} ({num_changes} changes)")
            
            if args.verbose:
                for change in changes:
                    print(change)
                print()
    
    print()
    print(f"{'Would update' if args.dry_run else 'Updated'} {files_changed} files with {total_changes} total changes")
    
    if args.dry_run:
        print("\nRun without --dry-run to apply changes")
    
    return 0


if __name__ == '__main__':
    exit(main())
