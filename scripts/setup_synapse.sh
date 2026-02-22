#!/bin/bash
# Setup Synapse for Agent Swarm Dev

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

# Ensure synapse-engine checkout is available (clone + vendor fallback)
if ! bash scripts/ensure_synapse_engine.sh; then
    if [ -x "./synapse" ]; then
        echo "⚠️  synapse-engine is missing or incomplete, but a prebuilt ./synapse binary exists."
        echo "✅ Using existing ./synapse binary and skipping source build."
        exit 0
    fi

    echo "❌ synapse-engine is required and could not be provisioned."
    echo "   You can also use a prebuilt binary in ./synapse (see DOWNLOAD_SYNAPSE.md)."
    exit 1
fi

# Build Synapse Core
echo "🔨 Building synapse-core (light version)..."
cd synapse-engine
# Ensure PROTOC is available here
if [ -z "$PROTOC" ] && [ -f "../protoc/bin/protoc" ]; then
    export PROTOC="$(cd .. && pwd)/protoc/bin/protoc"
fi

cargo build --release --no-default-features -p synapse-core
if [ $? -ne 0 ]; then
    echo "❌ Cargo build failed."
    exit 1
fi
cd ..

# Copy binary to ./synapse
if [ -f "synapse-engine/target/release/synapse" ]; then
    echo "📝 Copying binary to ./synapse..."
    cp synapse-engine/target/release/synapse ./synapse
    chmod +x ./synapse
else
    echo "❌ Build failed: Binary not found at synapse-engine/target/release/synapse"
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
