#!/usr/bin/env python3
"""
Trello Bridge Integration Script
Runs the Product Manager, Architect, and Orchestrator agents in a unified loop
connected to the Trello Board.
"""
import os
import sys
import time
import logging

# Add path to lib and agents
SDK_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'sdk', 'python'))
sys.path.insert(0, SDK_ROOT)
sys.path.insert(0, os.path.join(SDK_ROOT, 'agents'))
sys.path.insert(0, os.path.join(SDK_ROOT, 'lib'))
sys.path.insert(0, os.path.join(SDK_ROOT, 'agents', 'synapse_proto'))

from trello_bridge import TrelloBridge
from product_manager import ProductManagerAgent
from architect import ArchitectAgent
from orchestrator import OrchestratorAgent
from lib.code_graph_indexer import CodeGraphIndexer

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("SwarmController")

def main():
    logger.info("🤖 Starting Swarm Trello Controller...")

    # 0. Initialize CodeGraph (Index Repository)
    logger.info("🔍 Initializing CodeGraph Indexing...")
    try:
        indexer = CodeGraphIndexer()
        indexer.index_repository()
    except Exception as e:
        logger.error(f"❌ CodeGraph Indexing failed: {e}")

    # Initialize Bridge (Shared Instance? Or let each agent have one?)
    # Agents currently instantiate their own bridge.
    # For efficiency, we should probably share one, but given the structure,
    # letting them have their own is fine for now, though it means multiple polls if we run them separately.
    # HOWEVER, we want a SINGLE loop.

    # We will instantiate the agents and manually register their callbacks to a SINGLE bridge instance.
    bridge = TrelloBridge()

    pm_agent = ProductManagerAgent()
    architect_agent = ArchitectAgent()
    orchestrator_agent = OrchestratorAgent()

    # Override bridge instances to share the same one (optimization)
    pm_agent.bridge = bridge
    architect_agent.bridge = bridge
    orchestrator_agent.bridge = bridge

    # Register Callbacks
    logger.info("🔗 Registering Agent Callbacks...")
    bridge.register_callback("INBOX", pm_agent.process_card)
    bridge.register_callback("REQUIREMENTS", architect_agent.process_card)
    bridge.register_callback("TODO", orchestrator_agent.process_trello_todo)

    logger.info("✅ All Agents Registered. Entering Main Loop.")

    try:
        while True:
            # 1. Trello Sync (Triggers Callbacks)
            bridge.sync_loop_step()

            # 2. Synapse/Orchestrator Autonomous Checks
            # The Orchestrator has its own loop logic in `autonomous_loop`,
            # but we are effectively replacing it with this unified loop.
            # We need to run the Synapse check part of Orchestrator.
            # Orchestrator doesn't expose a 'step' method for Synapse, but `check_operational_status` is there.
            # Real autonomous tasks from Synapse (not Trello) are handled in `autonomous_loop`.
            # If we want to support both, we should extract the logic.
            # For now, let's just assume Trello is the driver.

            status = orchestrator_agent.check_operational_status()
            if status == "HALTED":
                logger.warning("🛑 System Halted via Synapse Event.")
                time.sleep(10)
                continue

            time.sleep(5) # Poll interval

    except KeyboardInterrupt:
        logger.info("🛑 Shutting down Swarm Controller...")
    except Exception as e:
        logger.error(f"❌ Fatal Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
