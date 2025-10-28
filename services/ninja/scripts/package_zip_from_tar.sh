#!/usr/bin/env bash
set -euo pipefail

TAR=${1:-fks_ninja_package.tgz}
VERSION=${FKS_VERSION:-1.0.0}
ZIP="FKS_TradingSystem_v${VERSION}.zip"
WORKDIR=$(mktemp -d)
cleanup() { rm -rf "$WORKDIR"; }
trap cleanup EXIT

if [ ! -f "$TAR" ]; then
  echo "[ERROR] Tarball '$TAR' not found. Run scripts/extract_ninja_package.sh first." >&2
  exit 1
fi

echo "[INFO] Using tarball: $TAR"
tar -xzf "$TAR" -C "$WORKDIR"

# Expected structure: bin/Release/... we packaged as bin/*. We want NT8 import style zip with root containing DLL and bin/Custom tree.
ROOT="$WORKDIR/root"
mkdir -p "$ROOT"

# Copy DLL to root and construct bin/Custom tree (Indicators/Strategies under Custom)
if [ -f "$WORKDIR/bin/FKS.dll" ]; then
  cp "$WORKDIR/bin/FKS.dll" "$ROOT/"
else
  echo "[WARN] FKS.dll not found in bin/." >&2
fi

mkdir -p "$ROOT/bin/Custom/Indicators" "$ROOT/bin/Custom/Strategies" "$ROOT/bin/Custom/AddOns"

# Move raw indicator/strategy sources into expected Custom layout
if [ -d "$WORKDIR/bin/Indicators" ]; then
  cp -R "$WORKDIR/bin/Indicators/." "$ROOT/bin/Custom/Indicators/"
fi
if [ -d "$WORKDIR/bin/Strategies" ]; then
  cp -R "$WORKDIR/bin/Strategies/." "$ROOT/bin/Custom/Strategies/"
fi

# Include AdditionalReferences if present
if [ -f "$WORKDIR/bin/AdditionalReferences.txt" ]; then
  cp "$WORKDIR/bin/AdditionalReferences.txt" "$ROOT/"
fi

pushd "$ROOT" >/dev/null
zip -r "$ZIP" . >/dev/null
popd >/dev/null

mv "$ROOT/$ZIP" .
echo "[OK] Created NinjaTrader import ZIP: $ZIP"
unzip -l "$ZIP" | head

echo "Import via NinjaTrader: Tools -> Import -> NinjaScript Add-On -> select $ZIP"
