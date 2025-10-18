#!/usr/bin/env python
"""
Validate test files for syntax and structure without executing them.
This script checks that tests are properly formatted and importable.
"""
import ast
import sys
from pathlib import Path


def validate_test_file(filepath):
    """Validate a single test file."""
    print(f"Validating: {filepath}")
    
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        
        # Parse the file to check syntax
        tree = ast.parse(content, filename=str(filepath))
        
        # Count test functions and classes
        test_funcs = 0
        test_classes = 0
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                if node.name.startswith('test_'):
                    test_funcs += 1
            elif isinstance(node, ast.ClassDef):
                if node.name.startswith('Test'):
                    test_classes += 1
        
        print(f"  ✓ Valid Python syntax")
        print(f"  ✓ {test_classes} test classes")
        print(f"  ✓ {test_funcs} test functions")
        return True
        
    except SyntaxError as e:
        print(f"  ✗ Syntax error: {e}")
        return False
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False


def main():
    """Validate all new test files."""
    test_root = Path(__file__).parent
    
    # Test files to validate
    test_files = [
        test_root / 'unit' / 'test_rag' / 'test_document_processor.py',
        test_root / 'unit' / 'test_rag' / 'test_embeddings_mocked.py',
        test_root / 'unit' / 'test_rag' / 'test_intelligence_mocked.py',
        test_root / 'integration' / 'test_celery' / 'test_tasks.py',
        test_root / 'performance' / 'test_rag_performance.py',
        test_root / 'performance' / 'test_trading_performance.py',
    ]
    
    print("=" * 60)
    print("TEST FILE VALIDATION")
    print("=" * 60)
    print()
    
    results = []
    for test_file in test_files:
        if test_file.exists():
            valid = validate_test_file(test_file)
            results.append((test_file.name, valid))
        else:
            print(f"Warning: {test_file} not found")
            results.append((test_file.name, False))
        print()
    
    # Summary
    print("=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    passed = sum(1 for _, valid in results if valid)
    total = len(results)
    
    for filename, valid in results:
        status = "✓ PASS" if valid else "✗ FAIL"
        print(f"{status} - {filename}")
    
    print()
    print(f"Total: {passed}/{total} files passed validation")
    print("=" * 60)
    
    return 0 if passed == total else 1


if __name__ == '__main__':
    sys.exit(main())
