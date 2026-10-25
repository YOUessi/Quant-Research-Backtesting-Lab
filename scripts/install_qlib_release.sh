#!/usr/bin/env bash
# One-time pinned source-data setup; never commits or stages market data.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=".venv/bin/python"
TAG="2026-10-25"
BASE="https://github.com/chenditc/investment_data/releases/download/$TAG"
ARCHIVE="data/downloads/qlib_bin_$TAG.tar.gz"
MANIFEST="data/downloads/qlib_bin_$TAG.manifest.json"
TARGET="data/external/qlib_20261025"
[[ -x "$PY" ]] || { echo "First create .venv (Python>=3.10) and install pyqlib" >&2; exit 2; }
mkdir -p data/downloads "$TARGET"
if [[ ! -f "$MANIFEST" ]]; then
  curl -fL --retry 3 --connect-timeout 20 --max-time 120 -o "$MANIFEST.part" "$BASE/qlib_bin.manifest.json"
  mv "$MANIFEST.part" "$MANIFEST"
fi
if [[ ! -f "$ARCHIVE" ]]; then
  curl -fL --retry 3 --connect-timeout 20 --max-time 1800 -o "$ARCHIVE.part" "$BASE/qlib_bin.tar.gz"
  mv "$ARCHIVE.part" "$ARCHIVE"
fi
"$PY" scripts/verify_qlib_bundle.py \
  --archive "$ARCHIVE" --manifest "$MANIFEST" --expected-tag "$TAG" \
  --report "data/downloads/qlib_bundle_verified.json"
if [[ -e "$TARGET/calendars/day.txt" ]]; then
  echo "Qlib data already extracted: $TARGET; not overwriting existing files."
else
  tar -xzf "$ARCHIVE" -C "$TARGET" --strip-components=1
fi
test -f "$TARGET/instruments/csi300.txt"
test -f "$TARGET/calendars/day.txt"
echo "Pinned local Qlib data ready at $TARGET. Raw data remains gitignored."
