#!/bin/bash
set -e

REPO_DIR="apicentric_repo"
if [ ! -d "$REPO_DIR" ]; then
    echo "Creating apicentric_repo..."
    git clone https://github.com/pmaojo/apicentric.git "$REPO_DIR"
fi

cd "$REPO_DIR"
echo "Building Apicentric..."
# Check if binary exists to avoid rebuild
if [ -f "target/release/apicentric" ]; then
    echo "✅ Apicentric binary found."
else
    cargo build --release --features mcp
    echo "✅ Apicentric build complete."
fi

# Create symlink
echo "🔗 Linking binary to lib/bin/apicentric..."
mkdir -p ../lib/bin
ln -sf "$(pwd)/target/release/apicentric" "../lib/bin/apicentric"
echo "✅ Symlink created."
