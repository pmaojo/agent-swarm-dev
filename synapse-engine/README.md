# synapse-engine placeholder

This repository no longer tracks `synapse-engine` as a git submodule because
some environments fail to fetch the pinned submodule commit.

To build from source, clone `https://github.com/pmaojo/synapse-engine.git`
into this directory and then run:

```bash
source scripts/start_all.sh
```

If source checkout is unavailable, provide a prebuilt executable at `./synapse`
(see `DOWNLOAD_SYNAPSE.md`).
