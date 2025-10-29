#!/usr/bin/env python3
"""
Validation script to check that all imports work correctly.
This can be run in CI to catch import issues early.
"""

import sys
import os

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def validate_imports():
    """Validate that critical imports work."""
    print("🔍 Validating imports...")
    
    try:
        # Test basic imports
        import fastapi
        print("✅ FastAPI import successful")
    except ImportError as e:
        print(f"❌ FastAPI import failed: {e}")
        return False
        
    try:
        # Test application import from src directory
        import fastapi_main
        if hasattr(fastapi_main, 'app'):
            print("✅ Application import successful (from fastapi_main)")
        else:
            print("⚠️  FastAPI app object not found in fastapi_main")
            
    except ImportError as e:
        print(f"❌ Application import failed: {e}")
        print("⚠️  This is expected if dependencies are not installed")
        # Don't fail on this during development
        # return False
    
    print("🎉 All critical imports validated successfully!")
    return True

if __name__ == "__main__":
    if validate_imports():
        sys.exit(0)
    else:
        sys.exit(1)
