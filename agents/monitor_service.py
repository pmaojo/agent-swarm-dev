#!/usr/bin/env python3
import os
import sys
import json
import logging
import grpc
from dotenv import load_dotenv

load_dotenv(override=True)
from typing import List, Dict
import uuid
from datetime import datetime

from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

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
        print("❌ Could not import Synapse protobufs. Monitor service will fail.")
        sys.exit(1)

# Configuration
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID") # Optional security
GRPC_HOST = os.getenv("SYNAPSE_GRPC_HOST", "localhost")
GRPC_PORT = int(os.getenv("SYNAPSE_GRPC_PORT", "50051"))
MAX_DAILY_BUDGET = float(os.getenv("MAX_DAILY_BUDGET", "10.0"))

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
    await update.message.reply_text("🤖 Monitor Service Online.\nCommands:\n/status - Check system health\n/stop_all - EMERGENCY STOP")

async def stop_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if ALLOWED_CHAT_ID and str(update.effective_chat.id) != ALLOWED_CHAT_ID:
        await update.message.reply_text("⛔ Unauthorized.")
        return

    logging.warning(f"🚨 EMERGENCY STOP TRIGGERED BY {update.effective_user.name}")
    await perform_emergency_halt(context)
    await update.message.reply_text("🛑 SYSTEM HALTED BY USER COMMAND.")

async def perform_emergency_halt(context: ContextTypes.DEFAULT_TYPE):
    # Ingest Halt Event (Timestamped)
    event_id = f"{NIST}event/status/{uuid.uuid4()}"
    timestamp = datetime.now().isoformat()

    try:
        synapse.ingest([
            {"subject": event_id, "predicate": f"{RDF}type", "object": f"{NIST}StatusChangeEvent"},
            {"subject": event_id, "predicate": f"{NIST}newStatus", "object": '"HALTED"'},
            {"subject": event_id, "predicate": f"{PROV}generatedAtTime", "object": f'"{timestamp}"'},
            {"subject": f"{NIST}SystemControl", "predicate": f"{NIST}hasStatusHistory", "object": event_id},
            {"subject": f"{NIST}SystemControl", "predicate": f"{NIST}operationalStatus", "object": '"HALTED"'}
        ])
    except Exception as e:
        logging.error(f"❌ Failed to execute kill switch: {e}")

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
            {"subject": f"{NIST}SystemControl", "predicate": f"{NIST}operationalStatus", "object": '"OPERATIONAL"'}
        ])
        await update.message.reply_text("✅ System Operational Status set to OPERATIONAL.")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to resume: {e}")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # Get Budget
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

        # Get System Status
        status_query = f"""
        PREFIX nist: <{NIST}>
        SELECT ?status WHERE {{ <{NIST}SystemControl> nist:operationalStatus ?status }}
        """
        status_res = synapse.query(status_query)
        statuses = [r.get('?status') or r.get('status') for r in status_res]
        current_status = statuses[-1] if statuses else "UNKNOWN"

        msg = (
            f"📊 **System Status**\n"
            f"Status: {current_status}\n"
            f"Daily Spend: ${spent:.4f} / ${MAX_DAILY_BUDGET:.2f}\n"
        )
        await update.message.reply_text(msg, parse_mode='Markdown')

    except Exception as e:
        await update.message.reply_text(f"❌ Status check failed: {e}")

async def help_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "👋 ¡Hola! Soy el Bot Monitor del Enjambre.\n"
        "Solo respondo a comandos específicos. Prueba:\n"
        "/status - Ver estado del sistema y presupuesto\n"
        "/stop_all - Parada de emergencia\n"
        "/resume - Reanudar sistema"
    )
    await update.message.reply_text(msg)

async def monitor_loop(context: ContextTypes.DEFAULT_TYPE):
    """Background task to monitor budget and errors."""
    try:
        # 1. Budget Check
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

        threshold = MAX_DAILY_BUDGET * 0.8
        if spent >= threshold:
            # Check if already halted today due to budget?
            # Or just check operational status
            status_query = f"""
            PREFIX nist: <{NIST}>
            SELECT ?status WHERE {{ <{NIST}SystemControl> nist:operationalStatus ?status }}
            """
            status_res = synapse.query(status_query)
            statuses = [r.get('?status') or r.get('status') for r in status_res]
            current_status = statuses[-1] if statuses else "UNKNOWN"

            if current_status != "HALTED":
                logging.warning(f"🚨 BUDGET ALERT: ${spent:.2f} >= 80% of ${MAX_DAILY_BUDGET:.2f}. INITIATING HALT.")
                await perform_emergency_halt(context)
                if ALLOWED_CHAT_ID:
                    await context.bot.send_message(chat_id=ALLOWED_CHAT_ID, text=f"🚨 **EMERGENCY HALT TRIGGERED**\nReason: Budget Exceeded 80% Threshold (${spent:.2f} / ${MAX_DAILY_BUDGET:.2f})")

        # 2. Error Check (Reviewer Rejections)
        # We look for ExecutionRecords with resultState "on_failure" associated with Reviewer
        # For the current session? Or generally recent ones?
        # Let's count failures in the last hour? Or just consolidated count?
        # The requirement: "If ReviewerAgent rejects a PR more than 3 times".
        # This implies "for a single task".
        # We can query: SELECT ?task (COUNT(?exec) as ?failures) WHERE ... GROUP BY ?task HAVING (?failures > 3)

        error_query = f"""
        PREFIX swarm: <{SWARM}>
        PREFIX nist: <{NIST}>
        PREFIX prov: <{PROV}>

        SELECT ?task (COUNT(?exec) as ?failures)
        WHERE {{
            ?exec a swarm:ExecutionRecord .
            ?exec nist:resultState "on_failure" .
            ?exec prov:wasAssociatedWith <{SWARM}agent/Reviewer> .
            ?exec swarm:relatedTask ?task .
            FILTER NOT EXISTS {{ ?task swarm:hasAlert "true" }}
        }}
        GROUP BY ?task
        HAVING (COUNT(?exec) > 3)
        """
        error_res = synapse.query(error_query)

        for row in error_res:
            task_uri = row.get('?task') or row.get('task')
            failures = row.get('?failures') or row.get('failures')

            if task_uri:
                logging.warning(f"⚠️ TACTICAL BLOCK: Task {task_uri} rejected {failures} times.")
                if ALLOWED_CHAT_ID:
                    await context.bot.send_message(chat_id=ALLOWED_CHAT_ID, text=f"⚠️ **TACTICAL BLOCK DETECTED**\nTask: {task_uri}\nReviewer Rejections: {failures}\nRequesting Intervention.")

                # Mark as alerted to avoid spam
                synapse.ingest([{
                    "subject": task_uri,
                    "predicate": f"{SWARM}hasAlert",
                    "object": '"true"'
                }])

    except Exception as e:
        logging.error(f"Error in monitor loop: {e}")

if __name__ == '__main__':
    if not TELEGRAM_TOKEN:
        print("⚠️  TELEGRAM_BOT_TOKEN not set. Monitor Service disabled.")
        sys.exit(0)

    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('stop_all', stop_all))
    application.add_handler(CommandHandler('resume', resume))
    application.add_handler(CommandHandler('status', status_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, help_message))

    # Add Monitor Job (runs every 60s)
    if application.job_queue:
        application.job_queue.run_repeating(monitor_loop, interval=60, first=10)
        print("✅ Monitor Loop Scheduled.")
    else:
        print("❌ JobQueue not available.")

    print("🤖 Monitor Service Polling...")
    application.run_polling()
