#!/bin/bash
# Validate all FKS protobuf files

set -euo pipefail

echo "Checking for protoc compiler..."
if ! command -v protoc &> /dev/null; then
    echo "❌ protoc not found. Install with:"
    echo "  Ubuntu/Debian: sudo apt install protobuf-compiler"
    echo "  macOS: brew install protobuf"
    exit 1
fi

echo "✅ protoc found: $(protoc --version)"
echo ""

# All current proto files
PROTO_FILES=(
    "fks/common/v1/common.proto"
    "fks/janus/v1/janus.proto"
    "fks/forward/v1/forward.proto"
    "fks/execution/v1/execution.proto"
    "fks/data/v1/data.proto"
    "fks/cns/v1/cns.proto"
    "fks/signals/v1/signals.proto"
    "fks/paper_trading/v1/paper_trading.proto"
    "fks/neuromorphic/distributed/v1/distributed.proto"
    "fks/feedback/v1/feedback.proto"
    "fks/rc/v1/rc.proto"
)

PASS=0
FAIL=0
FAILED_FILES=()

for proto in "${PROTO_FILES[@]}"; do
    echo "Validating ${proto}..."
    if protoc --proto_path=proto --descriptor_set_out=/dev/null "proto/${proto}" 2>&1; then
        echo "  ✅ Valid"
        ((PASS++))
    else
        echo "  ❌ Failed"
        ((FAIL++))
        FAILED_FILES+=("${proto}")
    fi
done

echo ""
echo "Checking for 'optional' keyword in field definitions (should not be present)..."
OPTIONAL_FOUND=0
for proto in "${PROTO_FILES[@]}"; do
    if grep -qE "^\s*optional\s" "proto/${proto}" 2>/dev/null; then
        echo "  ❌ Found 'optional' keyword in ${proto}"
        OPTIONAL_FOUND=1
    fi
done

if [ "${OPTIONAL_FOUND}" -eq 0 ]; then
    echo "  ✅ No 'optional' keyword in field definitions (good for compatibility)"
fi

echo ""
echo "Summary:"
echo "  Total proto files: ${#PROTO_FILES[@]}"
echo "  Passed: ${PASS}"
echo "  Failed: ${FAIL}"

if [ "${FAIL}" -gt 0 ]; then
    echo ""
    echo "Failed files:"
    for f in "${FAILED_FILES[@]}"; do
        echo "  - ${f}"
    done
    exit 1
fi

if [ "${OPTIONAL_FOUND}" -ne 0 ]; then
    echo ""
    echo "❌ 'optional' keyword compatibility issues detected"
    exit 1
fi

echo ""
echo "All checks passed! ✅"
