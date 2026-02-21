#!/usr/bin/env python3
import os
import sys
import json
import uvicorn

# Add project root to path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, PROJECT_ROOT)
def load_config():
    config_path = os.path.join(PROJECT_ROOT, 'config', 'swarm.json')
    if not os.path.exists(config_path):
        return {}
    with open(config_path, 'r') as f:
        return json.load(f)

if __name__ == "__main__":
    print(f"🔧 Configuring environment from {PROJECT_ROOT}")
    config = load_config()
    gateway_conf = config.get('gateway', {})
    port = gateway_conf.get('port', 18789)

    print(f"🚀 Starting Gateway on port {port}...")

    # Import app after setting path
    try:
        from lib.gateway_runtime import app
        uvicorn.run(app, host="0.0.0.0", port=port)
    except ImportError as e:
        print(f"❌ Failed to import gateway runtime: {e}")
        sys.exit(1)
