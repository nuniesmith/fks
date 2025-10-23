"""Test to verify cleanup of small and empty Python files.

This test validates that the cleanup performed in issue [P3.5] was successful:
- Empty package directories were removed
- Stub files were enhanced with proper documentation
- All imports still work correctly
"""

import os
import sys
from pathlib import Path

import pytest


class TestCleanupVerification:
    """Verify small file cleanup was successful."""

    def test_removed_empty_directories(self):
        """Verify empty package directories were removed."""
        src_path = Path("src")
        
        # These directories should NOT exist anymore
        removed_dirs = [
            src_path / "trading" / "execution",
            src_path / "infrastructure" / "messaging",
        ]
        
        for dir_path in removed_dirs:
            assert not dir_path.exists(), f"Directory {dir_path} should have been removed"

    def test_removed_modules_not_importable(self):
        """Verify removed modules cannot be imported."""
        # These imports should fail
        with pytest.raises(ModuleNotFoundError):
            import trading.execution  # noqa: F401
        
        with pytest.raises(ModuleNotFoundError):
            import infrastructure.messaging  # noqa: F401

    def test_core_imports_still_work(self):
        """Verify core module imports still work after cleanup."""
        try:
            import trading
            import api
            import authentication
            import core
            import web
            import infrastructure
            import framework
            
            # If we get here, all imports succeeded
            assert True
        except ImportError as e:
            pytest.fail(f"Import failed after cleanup: {e}")

    def test_enhanced_files_have_content(self):
        """Verify enhanced files now have meaningful content."""
        src_path = Path("src")
        
        enhanced_files = [
            src_path / "__init__.py",
            src_path / "api" / "admin.py",
            src_path / "api" / "models.py",
            src_path / "web" / "models.py",
        ]
        
        for file_path in enhanced_files:
            assert file_path.exists(), f"File {file_path} should exist"
            
            # Read content
            content = file_path.read_text()
            
            # Check for meaningful content
            assert len(content) > 100, f"File {file_path} should have more than 100 bytes"
            assert '"""' in content, f"File {file_path} should have docstrings"
            
            # Check for specific enhancements
            if file_path.name == "__init__.py" and str(file_path) == "src/__init__.py":
                assert "__version__" in content
                assert "FKS Trading Platform" in content
            elif file_path.name == "admin.py":
                assert "legacy" in content.lower() or "migration" in content.lower()
            elif file_path.name == "models.py":
                assert "migration" in content.lower() or "models" in content.lower()

    def test_small_file_count_reduced(self):
        """Verify the count of small Python files was reduced."""
        src_path = Path("src")
        
        # Count files under 100 bytes
        small_files = [
            f for f in src_path.rglob("*.py")
            if f.is_file() and f.stat().st_size < 100
        ]
        
        count = len(small_files)
        
        # Should have reduced from 24 to 18 (or less)
        assert count <= 18, f"Expected ≤18 small files, found {count}"
        
        # Validate remaining small files are legitimate
        for file_path in small_files:
            content = file_path.read_text()
            
            # All remaining small files should have either:
            # 1. A docstring, or
            # 2. A comment explaining their purpose
            has_docstring = '"""' in content or "'''" in content
            has_comment = "#" in content
            has_all_export = "__all__" in content
            
            assert has_docstring or has_comment or has_all_export, (
                f"File {file_path} ({file_path.stat().st_size} bytes) lacks documentation"
            )

    def test_migration_init_files_preserved(self):
        """Verify Django migration __init__.py files were preserved."""
        migration_inits = [
            Path("src/api/migrations/__init__.py"),
            Path("src/config/migrations/__init__.py"),
            Path("src/core/migrations/__init__.py"),
            Path("src/trading/migrations/__init__.py"),
            Path("src/web/migrations/__init__.py"),
        ]
        
        for init_file in migration_inits:
            assert init_file.exists(), f"Migration init {init_file} should be preserved"
            
            # These are small by design (Django requirement)
            assert init_file.stat().st_size < 100

    def test_package_init_files_have_docstrings(self):
        """Verify package __init__.py files have docstrings or __all__."""
        package_inits = [
            Path("src/trading/__init__.py"),
            Path("src/api/__init__.py"),
            Path("src/web/__init__.py"),
            Path("src/infrastructure/__init__.py"),
            Path("src/framework/exceptions/__init__.py"),
        ]
        
        for init_file in package_inits:
            assert init_file.exists(), f"Package init {init_file} should exist"
            
            content = init_file.read_text()
            
            # Should have either docstring or __all__
            has_docstring = '"""' in content
            has_all_export = "__all__" in content
            
            assert has_docstring or has_all_export, (
                f"Package init {init_file} should have docstring or __all__"
            )


class TestNoRegressions:
    """Verify cleanup didn't break existing functionality."""

    def test_django_apps_discoverable(self):
        """Verify Django apps are still discoverable."""
        django_apps = [
            "api",
            "authentication",
            "core",
            "trading",
            "web",
        ]
        
        for app in django_apps:
            app_path = Path("src") / app
            assert app_path.exists(), f"Django app {app} should exist"
            assert (app_path / "__init__.py").exists(), f"Django app {app} should have __init__.py"

    def test_no_broken_relative_imports(self):
        """Verify relative imports in core modules still work."""
        try:
            # Test a few key modules that might use relative imports
            from trading.tasks import sync_market_data  # noqa: F401
            from trading.backtest.engine import run_backtest  # noqa: F401
            
            # If we get here, imports succeeded
            assert True
        except ImportError as e:
            pytest.fail(f"Relative import broke after cleanup: {e}")
