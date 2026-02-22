#!/usr/bin/env python3
import json
import os
import sys

import uvicorn
from dotenv import load_dotenv

# Load .env variables before anything else
load_dotenv(override=True)

# Add project root and SDK Python paths to import path.
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SDK_PYTHON_ROOT = os.path.join(PROJECT_ROOT, "sdk", "python")
SDK_LIB_PATH = os.path.join(SDK_PYTHON_ROOT, "lib")

for path in (SDK_LIB_PATH, SDK_PYTHON_ROOT, PROJECT_ROOT):
    if path not in sys.path:
        sys.path.insert(0, path)


def load_config() -> dict:
    config_path = os.path.join(PROJECT_ROOT, "config", "swarm.json")
    if not os.path.exists(config_path):
        return {}
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"⚠️  Failed to parse config file {config_path}: {e}")
        return {}


if __name__ == "__main__":
    print(f"🔧 Configuring environment from {PROJECT_ROOT}")
    config = load_config()
    gateway_conf = config.get("gateway", {})
    port = gateway_conf.get("port", 18789)

    print(f"🚀 Starting Gateway on port {port}...")

    try:
        from gateway_runtime import app

        uvicorn.run(app, host="0.0.0.0", port=port)
    except ImportError as e:
        print(f"❌ Failed to import gateway runtime: {e}")
        sys.exit(1)
