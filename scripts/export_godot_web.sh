#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VISUALIZER_PATH="${ROOT_DIR}/visualizer"
OUTPUT_DIR="${ROOT_DIR}/commander-dashboard/public/godot"
OUTPUT_HTML="${OUTPUT_DIR}/index.html"

mkdir -p "${OUTPUT_DIR}"

(
  cd "${VISUALIZER_PATH}"
  godot --headless --path . --export-release "Web" "${OUTPUT_HTML}"
)

required_artifacts=("index.js" "index.wasm" "index.pck")
for artifact in "${required_artifacts[@]}"; do
  if [[ ! -f "${OUTPUT_DIR}/${artifact}" ]]; then
    echo "Missing required artifact: ${OUTPUT_DIR}/${artifact}" >&2
    exit 1
  fi
done

echo "Godot Web export completed: ${OUTPUT_DIR}"
