#!/bin/bash
set -e

REPO_DIR="apicentric_repo"

echo "🔧 Ensuring apicentric_repo is ready..."

# Try to update/init submodule first if it is tracked
if git submodule status "$REPO_DIR" >/dev/null 2>&1; then
    echo "🔄 Updating submodule..."
    git submodule update --init --recursive "$REPO_DIR"
else
    # Not a submodule or git command failed
    if [ ! -d "$REPO_DIR" ]; then
         echo "⬇️  Cloning apicentric_repo..."
         git clone https://github.com/pmaojo/apicentric.git "$REPO_DIR"
    elif [ -z "$(ls -A "$REPO_DIR")" ]; then
         echo "⚠️  Empty directory found. Cloning..."
         rmdir "$REPO_DIR"
         git clone https://github.com/pmaojo/apicentric.git "$REPO_DIR"
    fi
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
