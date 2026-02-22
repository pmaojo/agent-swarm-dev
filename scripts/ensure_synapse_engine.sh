#!/bin/bash
# Ensure synapse-engine sources are available locally.
# Strategy:
# 1) Reuse existing checkout.
# 2) Clone from public repo.
# 3) Fallback to vendored copy if clone fails.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

SYNAPSE_DIR="${SYNAPSE_ENGINE_DIR:-$PROJECT_DIR/synapse-engine}"
VENDOR_DIR="${SYNAPSE_ENGINE_VENDOR_DIR:-$PROJECT_DIR/vendor/synapse-engine}"
REPO_URL="${SYNAPSE_ENGINE_REPO_URL:-https://github.com/pmaojo/synapse-engine.git}"

has_synapse_checkout() {
    [ -d "$1" ] && [ -f "$1/Cargo.toml" ]
}

sync_to_vendor() {
    local src_dir="$1"
    local dst_dir="$2"

    mkdir -p "$(dirname "$dst_dir")"
    rm -rf "$dst_dir"
    cp -R "$src_dir" "$dst_dir"
    rm -rf "$dst_dir/.git"
}

restore_from_vendor() {
    local src_dir="$1"
    local dst_dir="$2"

    rm -rf "$dst_dir"
    cp -R "$src_dir" "$dst_dir"
}

if has_synapse_checkout "$SYNAPSE_DIR"; then
    echo "✅ synapse-engine checkout found at $SYNAPSE_DIR"
    echo "🔄 Updating vendor fallback at $VENDOR_DIR"
    sync_to_vendor "$SYNAPSE_DIR" "$VENDOR_DIR"
    exit 0
fi

echo "⬇️  synapse-engine missing. Cloning from $REPO_URL..."
rm -rf "$SYNAPSE_DIR"
if git clone --depth 1 "$REPO_URL" "$SYNAPSE_DIR"; then
    if has_synapse_checkout "$SYNAPSE_DIR"; then
        echo "✅ Clone completed. Updating vendor fallback at $VENDOR_DIR"
        sync_to_vendor "$SYNAPSE_DIR" "$VENDOR_DIR"
        exit 0
    fi
    echo "⚠️  Clone succeeded but checkout is incomplete (missing Cargo.toml)."
fi

echo "⚠️  Clone failed or incomplete. Trying vendored fallback..."
if has_synapse_checkout "$VENDOR_DIR"; then
    restore_from_vendor "$VENDOR_DIR" "$SYNAPSE_DIR"
    echo "✅ Restored synapse-engine from vendor fallback."
    exit 0
fi

echo "❌ Unable to provision synapse-engine."
echo "   Tried clone: $REPO_URL"
echo "   Missing vendor fallback at: $VENDOR_DIR"
exit 1
