#!/bin/bash
# Setup Synapse for Agent Swarm Dev

echo "📦 Setting up Synapse..."

# Create data directory locally to avoid permission issues
mkdir -p synapse-data

# Check for protoc
if ! command -v protoc &> /dev/null; then
    echo "⚠️  protoc not found. Installing locally..."
    mkdir -p protoc
    # Check if we already have it
    if [ ! -f "protoc/bin/protoc" ]; then
        echo "⬇️  Downloading protoc..."
        # Use a stable version suitable for most environments
        curl -L -o protoc.zip https://github.com/protocolbuffers/protobuf/releases/download/v25.1/protoc-25.1-linux-x86_64.zip
        unzip -o protoc.zip -d protoc > /dev/null
        rm protoc.zip
        chmod +x protoc/bin/protoc
    fi
    # Add to PATH and set PROTOC env var
    export PATH="$(pwd)/protoc/bin:$PATH"
    export PROTOC="$(pwd)/protoc/bin/protoc"
    echo "✅ protoc installed at $(pwd)/protoc/bin/protoc"
else
    echo "✅ protoc found at $(which protoc)"
fi

# Initialize submodule
if [ -d "synapse-engine" ]; then
    echo "🔄 Updating synapse-engine submodule..."
    git submodule update --init --recursive
else
    echo "⚠️  synapse-engine directory not found. Please run: git submodule add https://github.com/pmaojo/synapse-engine synapse-engine"
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

# Check GLIBC version
echo "🔍 Checking GLIBC version..."
ldd --version | head -1

echo ""
echo "✅ Setup complete!"
echo ""
echo "To run Synapse:"
echo "  GRAPH_STORAGE_PATH=./synapse-data ./scripts/start_synapse.sh"
