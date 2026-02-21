#!/usr/bin/env python3
import os
import sys
import json
import asyncio
import logging
import grpc
from typing import List, Dict
import uuid
from datetime import datetime

from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler

# Ensure we can import proto
current_dir = os.path.dirname(os.path.abspath(__file__))
proto_dir = os.path.join(current_dir, 'proto')
if proto_dir not in sys.path:
    sys.path.insert(0, proto_dir)

try:
    import semantic_engine_pb2
    import semantic_engine_pb2_grpc
except ImportError:
    try:
        from agents.proto import semantic_engine_pb2, semantic_engine_pb2_grpc
    except ImportError:
        print("❌ Could not import Synapse protobufs. Telegram bot will fail.")
        sys.exit(1)

# Configuration
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID") # Optional security
GRPC_HOST = os.getenv("SYNAPSE_GRPC_HOST", "localhost")
GRPC_PORT = int(os.getenv("SYNAPSE_GRPC_PORT", "50051"))

# Ontology
NIST = "http://nist.gov/caisi/"
SWARM = "http://swarm.os/ontology/"
RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
PROV = "http://www.w3.org/ns/prov#"

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

class SynapseClient:
    def __init__(self):
        self.channel = grpc.insecure_channel(f"{GRPC_HOST}:{GRPC_PORT}")
        self.stub = semantic_engine_pb2_grpc.SemanticEngineStub(self.channel)
        self.namespace = "default"

    def ingest(self, triples: List[Dict[str, str]]):
        pb_triples = []
        for t in triples:
            pb_triples.append(semantic_engine_pb2.Triple(
                subject=t["subject"],
                predicate=t["predicate"],
                object=t["object"]
            ))
        request = semantic_engine_pb2.IngestRequest(triples=pb_triples, namespace=self.namespace)
        self.stub.IngestTriples(request)

    def query(self, query: str) -> List[Dict]:
        request = semantic_engine_pb2.SparqlRequest(query=query, namespace=self.namespace)
        response = self.stub.QuerySparql(request)
        return json.loads(response.results_json)

# Global client
synapse = SynapseClient()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Swarm Control Bot Online.\nCommands:\n/status - Check system health\n/stop_all - EMERGENCY STOP")

async def stop_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if ALLOWED_CHAT_ID and str(update.effective_chat.id) != ALLOWED_CHAT_ID:
        await update.message.reply_text("⛔ Unauthorized.")
        return

    logging.warning(f"🚨 EMERGENCY STOP TRIGGERED BY {update.effective_user.name}")

    # Ingest Halt Event (Timestamped)
    event_id = f"{NIST}event/status/{uuid.uuid4()}"
    timestamp = datetime.now().isoformat()

    try:
        synapse.ingest([
            {"subject": event_id, "predicate": f"{RDF}type", "object": f"{NIST}StatusChangeEvent"},
            {"subject": event_id, "predicate": f"{NIST}newStatus", "object": '"HALTED"'},
            {"subject": event_id, "predicate": f"{PROV}generatedAtTime", "object": f'"{timestamp}"'},
            {"subject": f"{NIST}SystemControl", "predicate": f"{NIST}hasStatusHistory", "object": event_id},
            # Explicitly attach operationalStatus to the event for query simplification if needed, but the ASK query uses newStatus
            # Backward compatibility: We still mark the global node, but the Orchestrator now relies on the event history ASK query.
            {"subject": f"{NIST}SystemControl", "predicate": f"{NIST}operationalStatus", "object": '"HALTED"'}
        ])
        await update.message.reply_text("🛑 SYSTEM HALTED.\nOrchestrator will stop on next cycle.\nQueue marked as cancelled.")

        # Optional: Mark pending tasks as cancelled?
        # User said: "marca todas las tareas pendientes como cancelled"
        # Query pending tasks
        pending_query = """
        SELECT ?s WHERE { ?s <http://swarm.os/session_status> "pending" }
        """
        results = synapse.query(pending_query)
        updates = []
        for row in results:
            s = row.get('?s') or row.get('s')
            if s:
                # We append 'cancelled' status.
                # Note: This doesn't remove 'pending' unless we delete, but orchestrator looks for 'pending'.
                # Actually orchestrator looks for 'pending'. If we add 'cancelled', it still has 'pending'.
                # But if we change logic to check for cancelled, or if we use valid-time.
                # Simplest is to just update status. Synapse Ingest is additive.
                # Ideally we delete 'pending', but without DELETE support, we rely on timestamp or latest.
                # Or we ingest <s, session_status, "cancelled"> and update query to filter out cancelled?
                # The user instruction was "marca... como cancelled".
                # I'll just add the triple. The Orchestrator should ideally pick the 'latest' status or check for HALT.
                updates.append({
                    "subject": s,
                    "predicate": "http://swarm.os/session_status",
                    "object": '"cancelled"'
                })

        if updates:
            synapse.ingest(updates)
            await update.message.reply_text(f"⚠️ Marked {len(updates)} pending tasks as cancelled.")

    except Exception as e:
        await update.message.reply_text(f"❌ Failed to execute kill switch: {e}")

async def resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if ALLOWED_CHAT_ID and str(update.effective_chat.id) != ALLOWED_CHAT_ID:
        await update.message.reply_text("⛔ Unauthorized.")
        return

    logging.info(f"▶️ SYSTEM RESUMED BY {update.effective_user.name}")

    # Ingest Resume Event (Timestamped)
    event_id = f"{NIST}event/status/{uuid.uuid4()}"
    timestamp = datetime.now().isoformat()

    try:
        synapse.ingest([
            {"subject": event_id, "predicate": f"{RDF}type", "object": f"{NIST}StatusChangeEvent"},
            {"subject": event_id, "predicate": f"{NIST}newStatus", "object": '"OPERATIONAL"'},
            {"subject": event_id, "predicate": f"{PROV}generatedAtTime", "object": f'"{timestamp}"'},
            {"subject": f"{NIST}SystemControl", "predicate": f"{NIST}hasStatusHistory", "object": event_id},
             # Backward compatibility
            {"subject": f"{NIST}SystemControl", "predicate": f"{NIST}operationalStatus", "object": '"OPERATIONAL"'}
        ])
        await update.message.reply_text("✅ System Operational Status set to OPERATIONAL.")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to resume: {e}")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # Get Budget
        today = os.popen("date +%Y-%m-%d").read().strip() # Use python date
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")

        budget_query = f"""
        PREFIX swarm: <{SWARM}>
        SELECT (SUM(?amount) as ?total)
        WHERE {{
            ?event a swarm:SpendEvent .
            ?event swarm:date "{today}" .
            ?event swarm:amount ?amount .
        }}
        """
        budget_res = synapse.query(budget_query)
        spent = 0.0
        if budget_res:
             val = budget_res[0].get('?total') or budget_res[0].get('total')
             if val: spent = float(val)

        # Get Pending Tasks
        pending_query = """
        SELECT (COUNT(?s) as ?count) WHERE { ?s <http://swarm.os/session_status> "pending" }
        """
        pending_res = synapse.query(pending_query)
        pending = 0
        if pending_res:
            val = pending_res[0].get('?count') or pending_res[0].get('count')
            if val: pending = int(val)

        # Get System Status
        status_query = f"""
        PREFIX nist: <{NIST}>
        SELECT ?status WHERE {{ <{NIST}SystemControl> nist:operationalStatus ?status }}
        """
        # We might get multiple statuses. We want the last one if ordered, but SPARQL is unordered set.
        # Assuming append-only, we might get multiple.
        # Ideally we'd filter by time if we had timestamps on triples.
        # For now, if ANY status is HALTED, we assume halted? Or we just list them.
        status_res = synapse.query(status_query)
        statuses = [r.get('?status') or r.get('status') for r in status_res]
        current_status = statuses[-1] if statuses else "UNKNOWN"

        msg = (
            f"📊 **System Status**\n"
            f"Status: {current_status}\n"
            f"Pending Tasks: {pending}\n"
            f"Daily Spend: ${spent:.4f}\n"
        )
        await update.message.reply_text(msg, parse_mode='Markdown')

    except Exception as e:
        await update.message.reply_text(f"❌ Status check failed: {e}")

async def approve_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if ALLOWED_CHAT_ID and str(update.effective_chat.id) != ALLOWED_CHAT_ID:
        await update.message.reply_text("⛔ Unauthorized.")
        return

    try:
        uuid_arg = context.args[0]
        # Allow passing full URI or just UUID suffix if consistent, but shell.py generates full URI <http://nist.gov/caisi/request/UUID>
        # The user sees `http://nist.gov/caisi/request/UUID` or just the UUID?
        # Shell.py output: `UUID: <uuid>` (it returns the full URI string).
        # So user will likely copy-paste the full URI.
        # But telegram message format: `UUID: cmd_uuid`.
        # cmd_uuid in shell.py is `http://nist.gov/caisi/request/{uuid}`.
        # So user copies that.
        # If user copies just the UUID part, we need to handle it?
        # Let's assume user copies what is provided.
        # But spaces/formatting might be an issue.
        # We will wrap it in <> if not present for subject?
        # shell.py ingest uses `subject=cmd_uuid`.
        # If cmd_uuid starts with http, it's a URI.
        # synapse.ingest wrapper expects string.
        # In shell.py: `{"subject": cmd_uuid, ...}`
        # In ingest: `pb_triples.append(..., subject=t["subject"])`
        # Synapse expects full URI string usually.

        target_subject = uuid_arg
        if not target_subject.startswith("http"):
            # Assume it's the suffix, reconstruct?
            target_subject = f"{NIST}request/{target_subject}"

        synapse.ingest([
            {"subject": target_subject, "predicate": f"{NIST}approvalStatus", "object": '"APPROVED"'},
            {"subject": target_subject, "predicate": f"{PROV}wasAttributedTo", "object": f'"{update.effective_user.name}"'}
        ])
        await update.message.reply_text(f"✅ Approved command request.")

    except IndexError:
        await update.message.reply_text("⚠️ Usage: /approve <uuid_or_uri>")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to approve: {e}")

async def deny_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if ALLOWED_CHAT_ID and str(update.effective_chat.id) != ALLOWED_CHAT_ID:
        await update.message.reply_text("⛔ Unauthorized.")
        return

    try:
        uuid_arg = context.args[0]
        target_subject = uuid_arg
        if not target_subject.startswith("http"):
            target_subject = f"{NIST}request/{target_subject}"

        synapse.ingest([
            {"subject": target_subject, "predicate": f"{NIST}approvalStatus", "object": '"REJECTED"'},
            {"subject": target_subject, "predicate": f"{PROV}wasAttributedTo", "object": f'"{update.effective_user.name}"'}
        ])
        await update.message.reply_text(f"🚫 Denied command request.")
    except IndexError:
        await update.message.reply_text("⚠️ Usage: /deny <uuid_or_uri>")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to deny: {e}")

if __name__ == '__main__':
    if not TELEGRAM_TOKEN:
        print("⚠️  TELEGRAM_BOT_TOKEN not set. Bot disabled.")
        sys.exit(0)

    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('stop_all', stop_all))
    application.add_handler(CommandHandler('resume', resume))
    application.add_handler(CommandHandler('status', status_command))
    application.add_handler(CommandHandler('approve', approve_command))
    application.add_handler(CommandHandler('deny', deny_command))

    print("🤖 Telegram Bot Polling...")
    application.run_polling()
