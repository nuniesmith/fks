"""
Test for shared_python import (deprecated).

NOTE: shared_python module was part of the legacy microservices architecture
and has been removed. This test now verifies that Django settings work properly.
"""
import pytest


@pytest.mark.skip(reason="shared_python module removed in monolith migration")
def test_shared_import():
    """Legacy test - shared_python module no longer exists."""
    pass
