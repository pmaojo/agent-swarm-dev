import os
import json
import sys
import time
import uuid
import grpc
import requests
from datetime import datetime
from typing import Dict, Any, List, Optional
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_random_exponential, retry_if_not_exception_type

# --- Synapse/Proto Imports ---
# Add agents/proto to path if not present, to support imports
current_dir = os.path.dirname(os.path.abspath(__file__))
proto_dir = os.path.join(current_dir, '..', 'agents', 'proto')
if proto_dir not in sys.path:
    sys.path.insert(0, proto_dir)

try:
    import semantic_engine_pb2
    import semantic_engine_pb2_grpc
except ImportError:
    # Fallback for different environments
    try:
        from agents.proto import semantic_engine_pb2, semantic_engine_pb2_grpc
    except ImportError:
        print("⚠️  Warning: Could not import Synapse protobufs. Budgeting disabled.")
        semantic_engine_pb2 = None
        semantic_engine_pb2_grpc = None

# --- Constants ---
# Pricing per 1K tokens (approximate for GPT-4o)
PRICE_INPUT_PER_1K = 0.005
PRICE_OUTPUT_PER_1K = 0.015

SWARM = "http://swarm.os/ontology/"
NIST = "http://nist.gov/caisi/"
RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"

class BudgetExceededException(Exception):
    """Raised when the daily budget is exceeded."""
    pass

class LLMService:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.model = os.getenv("LLM_MODEL", "gpt-4o")
        self.client = OpenAI(api_key=self.api_key)

        # Synapse Connection
        self.grpc_host = os.getenv("SYNAPSE_GRPC_HOST", "localhost")
        self.grpc_port = int(os.getenv("SYNAPSE_GRPC_PORT", "50051"))
        self.max_daily_budget = float(os.getenv("MAX_DAILY_BUDGET", "10.0")) # Default $10
        self.channel = None
        self.stub = None
        self.namespace = "default"

        self.connect_synapse()
        self.ensure_finance_node()

    def connect_synapse(self):
        if not semantic_engine_pb2_grpc:
            return
        try:
            self.channel = grpc.insecure_channel(f"{self.grpc_host}:{self.grpc_port}")
            self.stub = semantic_engine_pb2_grpc.SemanticEngineStub(self.channel)
        except Exception as e:
            print(f"⚠️  LLMService failed to connect to Synapse: {e}")

    def ensure_finance_node(self):
        """Ensure the finance node exists with the max budget."""
        if not self.stub: return

        triples = [
            {"subject": f"{SWARM}Finance", "predicate": f"{RDF}type", "object": f"{SWARM}FinancialRecord"},
            {"subject": f"{SWARM}Finance", "predicate": f"{SWARM}maxBudget", "object": f'"{self.max_daily_budget}"'}
        ]
        self._ingest(triples)

    def _ingest(self, triples: List[Dict[str, str]]):
        if not self.stub or not semantic_engine_pb2: return
        pb_triples = []
        for t in triples:
            pb_triples.append(semantic_engine_pb2.Triple(
                subject=t["subject"],
                predicate=t["predicate"],
                object=t["object"]
            ))
        request = semantic_engine_pb2.IngestRequest(triples=pb_triples, namespace=self.namespace)
        try:
            self.stub.IngestTriples(request)
        except Exception as e:
            print(f"❌ Ingest failed: {e}")

    def _query(self, query: str) -> List[Dict]:
        if not self.stub or not semantic_engine_pb2: return []
        # print(f"DEBUG: Query called: {query}")
        request = semantic_engine_pb2.SparqlRequest(query=query, namespace=self.namespace)
        try:
            response = self.stub.QuerySparql(request)
            return json.loads(response.results_json)
        except Exception as e:
            print(f"❌ Query failed: {repr(e)}")
            # import traceback
            # traceback.print_exc()
            return []

    def get_daily_spend(self) -> float:
        """Calculate total spend for today using Append-Only Log."""
        today = datetime.now().strftime("%Y-%m-%d")
        query = f"""
        PREFIX swarm: <{SWARM}>
        SELECT (SUM(?amount) as ?total)
        WHERE {{
            ?event a swarm:SpendEvent .
            ?event swarm:date "{today}" .
            ?event swarm:amount ?amount .
        }}
        """
        results = self._query(query)
        if not results: return 0.0

        total = results[0].get("?total") or results[0].get("total")
        try:
            return float(total) if total else 0.0
        except:
            return 0.0

    def send_telegram_alert(self, message: str):
        """Send alert via Telegram API."""
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("TELEGRAM_CHAT_ID")

        if not token or not chat_id:
            print(f"⚠️ Telegram Alert skipped (Missing Token/ChatID): {message}")
            return

        try:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            payload = {"chat_id": chat_id, "text": message}
            requests.post(url, json=payload, timeout=5)
        except Exception as e:
            print(f"❌ Failed to send Telegram alert: {e}")

    def check_budget_warning(self, current_spend: float):
        """Check if 80% threshold exceeded and alert."""
        if not self.stub: return

        threshold = self.max_daily_budget * 0.8
        if current_spend >= threshold:
            today = datetime.now().strftime("%Y-%m-%d")

            # Check if alert already sent today
            query = f"""
            PREFIX swarm: <{SWARM}>
            SELECT ?event
            WHERE {{
                ?event a swarm:BudgetWarning .
                ?event swarm:date "{today}" .
            }}
            LIMIT 1
            """
            results = self._query(query)

            if not results:
                print("⚠️  80% Budget Warning Triggered!")
                msg = f"⚠️ Budget Warning: 80% of daily limit reached (${current_spend:.2f} / ${self.max_daily_budget:.2f})"
                self.send_telegram_alert(msg)

                # Log warning event
                warning_id = f"{SWARM}event/warning/{uuid.uuid4()}"
                self._ingest([
                    {"subject": warning_id, "predicate": f"{RDF}type", "object": f"{SWARM}BudgetWarning"},
                    {"subject": warning_id, "predicate": f"{SWARM}date", "object": f'"{today}"'},
                    {"subject": warning_id, "predicate": f"{SWARM}triggerAmount", "object": f'"{current_spend:.2f}"'}
                ])

    def check_budget(self):
        """Check if daily spend exceeds budget."""
        if not self.stub: return # Fail open if Synapse down? Or fail closed? Using fail open for now.

        current_spend = self.get_daily_spend()

        # Check Warning First
        self.check_budget_warning(current_spend)

        if current_spend >= self.max_daily_budget:
            raise BudgetExceededException(
                f"Daily budget exceeded! Spent: ${current_spend:.4f}, Limit: ${self.max_daily_budget:.2f}"
            )

    def log_spend(self, prompt_tokens: int, completion_tokens: int):
        """Log the cost of a call."""
        if not self.stub: return

        cost = (prompt_tokens / 1000 * PRICE_INPUT_PER_1K) + \
               (completion_tokens / 1000 * PRICE_OUTPUT_PER_1K)

        today = datetime.now().strftime("%Y-%m-%d")
        event_id = f"{SWARM}event/spend/{uuid.uuid4()}"

        triples = [
            {"subject": event_id, "predicate": f"{RDF}type", "object": f"{SWARM}SpendEvent"},
            {"subject": event_id, "predicate": f"{SWARM}date", "object": f'"{today}"'},
            {"subject": event_id, "predicate": f"{SWARM}amount", "object": f'"{cost:.6f}"'}, # High precision
            {"subject": f"{SWARM}Finance", "predicate": f"{SWARM}dailySpent", "object": f'"{self.get_daily_spend() + cost:.6f}"'} # Cache (approx)
        ]
        self._ingest(triples)
        # print(f"💰 Cost logged: ${cost:.6f}")

    @retry(
        wait=wait_random_exponential(min=1, max=60),
        stop=stop_after_attempt(6),
        retry=retry_if_not_exception_type(BudgetExceededException)
    )
    def completion(self, prompt: str, system_prompt: str = "You are a helpful assistant.", json_mode: bool = False) -> str:
        """
        Generate a completion using the configured LLM, with Budget Enforcement.
        """
        self.check_budget()

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]

        response_format = {"type": "json_object"} if json_mode else None

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                response_format=response_format,
                temperature=0.7
            )

            # Track Usage
            usage = response.usage
            if usage:
                self.log_spend(usage.prompt_tokens, usage.completion_tokens)

            return response.choices[0].message.content
        except BudgetExceededException:
            raise # Propagate up
        except Exception as e:
            print(f"Error calling LLM: {e}")
            raise

    def get_structured_completion(self, prompt: str, system_prompt: str) -> Dict[str, Any]:
        """
        Get a JSON-parsed response from the LLM.
        """
        content = self.completion(prompt, system_prompt, json_mode=True)
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # Fallback: try to extract JSON from markdown code blocks if present
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
                return json.loads(content)
            raise ValueError(f"Failed to parse JSON from LLM response: {content}")
