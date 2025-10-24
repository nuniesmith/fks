#!/usr/bin/env bash
set -euo pipefail

IMAGE="fks_ninja:artifact"
OUT="fks_ninja_package.tgz"

if ! docker image inspect "$IMAGE" > /dev/null 2>&1; then
  echo "[INFO] Building artifact image $IMAGE" >&2
  docker build -t "$IMAGE" .
fi

CID=$(docker create "$IMAGE")
trap 'docker rm -v "$CID" >/dev/null 2>&1 || true' EXIT

docker cp "$CID:/fks_ninja_package.tgz" "$OUT"

echo "[OK] Extracted $OUT"
sha256sum "$OUT"

echo "Contents (top level):"
tar -tzf "$OUT" | head

echo "Next: Extract and copy FKS.dll + bin/Custom into NinjaTrader 8 bin/Custom."
