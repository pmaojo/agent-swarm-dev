#!/bin/bash
# Setup Synapse for Agent Swarm Dev

set -e

echo "📦 Setting up Synapse..."

# Create data directory locally to avoid permission issues
mkdir -p synapse-data

# Check for protoc
if ! command -v protoc &> /dev/null; then
    echo "❌ protoc not found. Please install it first (e.g. 'brew install protobuf' on macOS or 'apt install protobuf-compiler' on Ubuntu)."
    exit 1
else
    echo "✅ protoc found at $(which protoc)"
fi

SYNAPSE_ENGINE_DIR="synapse-engine"
SYNAPSE_MANIFEST_PATH=""
SYNAPSE_TARGET_BINARY=""

# Validate synapse-engine checkout
if [ -d "$SYNAPSE_ENGINE_DIR" ]; then
    if [ -f "$SYNAPSE_ENGINE_DIR/Cargo.toml" ]; then
        SYNAPSE_MANIFEST_PATH="$SYNAPSE_ENGINE_DIR/Cargo.toml"
    else
        # Fallback for layout changes: find the first Cargo.toml under synapse-engine
        SYNAPSE_MANIFEST_PATH="$(find "$SYNAPSE_ENGINE_DIR" -maxdepth 3 -name Cargo.toml | head -n 1)"
    fi

    if [ -n "$SYNAPSE_MANIFEST_PATH" ]; then
        manifest_dir="$(dirname "$SYNAPSE_MANIFEST_PATH")"
        SYNAPSE_TARGET_BINARY="$manifest_dir/target/release/synapse"
        echo "🔄 Found synapse-engine checkout (manifest: $SYNAPSE_MANIFEST_PATH). Skipping submodule update to preserve local patches..."
        # git submodule update --init --recursive
    fi
fi

if [ -z "$SYNAPSE_MANIFEST_PATH" ]; then
    if [ -f "./synapse" ]; then
        if [ ! -x "./synapse" ]; then
            echo "⚠️  ./synapse exists but is not executable. Running 'chmod +x ./synapse'..."
            chmod +x ./synapse
        fi
        echo "⚠️  synapse-engine is missing or incomplete, but a prebuilt ./synapse binary exists."
        echo "✅ Using existing ./synapse binary and skipping source build."
        exit 0
    fi

    echo "❌ synapse-engine is missing or incomplete (no Cargo.toml found under $SYNAPSE_ENGINE_DIR)."
    echo "   This usually means checkout failed or repository contents are incomplete in this environment."
    echo "   Use one of the following options:"
    echo "   1) Restore synapse-engine source contents"
    echo "   2) Download a prebuilt binary into ./synapse (see DOWNLOAD_SYNAPSE.md)"
    exit 1
fi

# Build Synapse Core
echo "🔨 Building synapse-core (light version)..."
# Ensure PROTOC is available here
if [ -z "$PROTOC" ] && [ -f "./protoc/bin/protoc" ]; then
    export PROTOC="$(pwd)/protoc/bin/protoc"
fi

cargo build --manifest-path "$SYNAPSE_MANIFEST_PATH" --release --no-default-features -p synapse-core

# Copy binary to ./synapse
if [ -f "$SYNAPSE_TARGET_BINARY" ]; then
    echo "📝 Copying binary to ./synapse..."
    cp "$SYNAPSE_TARGET_BINARY" ./synapse
    chmod +x ./synapse
else
    echo "❌ Build failed: Binary not found at $SYNAPSE_TARGET_BINARY"
    exit 1
fi

# Check GLIBC version (Linux) or System info (Mac)
echo "🔍 Checking System info..."
if command -v ldd &> /dev/null; then
    ldd --version | head -1
elif command -v sw_vers &> /dev/null; then
    sw_vers | head -2
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "To run Synapse:"
echo "  GRAPH_STORAGE_PATH=./synapse-data ./scripts/start_synapse.sh"
