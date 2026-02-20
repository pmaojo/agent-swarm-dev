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
