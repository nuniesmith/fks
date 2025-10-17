# Code Quality Fixes - Round 2

## Summary

Fixed remaining Ruff linting errors related to deprecated type annotations and code formatting.

## Issues Fixed

### 1. **UP006: Use Built-in Generic Types (PEP 585)**
**Problem**: Using deprecated `typing.List` and `typing.Dict` instead of built-in `list` and `dict` for type annotations (Python 3.9+ feature).

**Locations**:
- `src/api/middleware/__init__.py` (multiple occurrences)

**Solution**: Replaced all occurrences with modern built-in generic types:
- `List[str]` → `list[str]`
- `Dict[str, Any]` → `dict[str, Any]`

**Examples**:
```python
# Before:
from typing import Any, Dict, List, Union

def setup_middleware(app: FastAPI) -> Dict[str, Any]:
    ...

def get_origins(self) -> List[str]:
    ...

# After:
from typing import Any, Union

def setup_middleware(app: FastAPI) -> dict[str, Any]:
    ...

def get_origins(self) -> list[str]:
    ...
```

### 2. **UP035: Remove Deprecated typing Imports**
**Problem**: `typing.List` and `typing.Dict` are deprecated in Python 3.9+.

**Solution**: Removed `List` and `Dict` from imports in `src/api/middleware/__init__.py`.

```python
# Before:
from typing import Any, Dict, List, Union

# After:
from typing import Any, Union
```

### 3. **W292: Missing Newline at End of File**
**Problem**: `src/__init__.py` was missing a newline at the end of the file.

**Solution**: Added newline at the end of file.

### 4. **I001: Unsorted Import Block**
**Problem**: Imports in `src/__init__.py` were not sorted alphabetically.

**Solution**: Sorted imports alphabetically:
```python
# Before:
from config import *  # noqa: F403
from database import *  # noqa: F403
from cache import *  # noqa: F403
from data import *  # noqa: F403
from backtest import *  # noqa: F403
from signals import *  # noqa: F403
from utils import *  # noqa: F403

# After:
from backtest import *  # noqa: F403
from cache import *  # noqa: F403
from config import *  # noqa: F403
from data import *  # noqa: F403
from database import *  # noqa: F403
from signals import *  # noqa: F403
from utils import *  # noqa: F403
```

## Files Modified

### 1. `src/api/middleware/__init__.py`
**Changes**:
- Removed `List` and `Dict` from typing imports
- Updated all type annotations to use built-in generics:
  - Function parameters: `cors_origins: list[str]`, `cors_allow_methods: list[str]`, etc.
  - Return types: `-> dict[str, Any]`, `-> list[str]`
- Updated 13 function signatures and type annotations

### 2. `src/__init__.py`
**Changes**:
- Sorted imports alphabetically
- Added newline at end of file

## Python Version Compatibility

These changes utilize **PEP 585** (Type Hinting Generics In Standard Collections), introduced in Python 3.9.

Since the project targets Python 3.13, using built-in generic types is the recommended approach:
- ✅ More concise
- ✅ No need to import from `typing` module
- ✅ Better performance
- ✅ Modern Python best practices

## Verification

All Ruff errors should now be resolved:
- ✅ UP006: Use `list` instead of `List` - FIXED
- ✅ UP035: `typing.List` is deprecated - FIXED
- ✅ UP035: `typing.Dict` is deprecated - FIXED
- ✅ W292: No newline at end of file - FIXED
- ✅ I001: Import block unsorted - FIXED

## Testing

The changes are purely cosmetic (type annotation modernization) and do not affect runtime behavior. However, they:
1. Make the code more maintainable
2. Follow modern Python best practices
3. Improve IDE type checking and auto-completion
4. Ensure compatibility with Python 3.9+ type system

## Next Steps

1. ✅ Code should pass Ruff checks
2. ✅ Type hints are modernized for Python 3.9+
3. ✅ Imports are properly sorted
4. ✅ Code formatting follows standards

## Discord Notification Issue

The workflow also shows a Discord notification issue:
```
embed field value must be shorter than 1024, got 1122
```

This is a Discord API limitation where embed field values must be ≤1024 characters. The commit message is too long (1122 characters). This can be addressed by either:
1. Truncating commit messages in Discord notifications
2. Using a shorter commit message format
3. Splitting into multiple fields

This is a separate issue from code quality and doesn't affect the build.
