# Download Synapse Binary

Download the light build from GitHub Actions:

```bash
# Download latest artifact
curl -sL "https://github.com/pmaojo/synapse-engine/releases/latest/download/synapse-light" -o synapse
chmod +x synapse
```

Or build from source:

```bash
git clone https://github.com/pmaojo/synapse-engine.git
cd synapse-engine
cargo build --release --no-default-features -p synapse-core
cp target/release/synapse ../agent-swarm-dev/
```

## Source provisioning fallback (clone + vendor)

The startup flow now uses `scripts/ensure_synapse_engine.sh` to:

1. Reuse an existing `synapse-engine/` checkout.
2. Clone `https://github.com/pmaojo/synapse-engine.git` when missing.
3. Keep a vendored fallback at `vendor/synapse-engine` after a successful clone.
4. Restore from the vendored fallback if future clone attempts fail.

You can run it manually:

```bash
bash scripts/ensure_synapse_engine.sh
```
