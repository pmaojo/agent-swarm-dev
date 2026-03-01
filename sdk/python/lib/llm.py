import os
import json
import sys
import time
import uuid
import grpc
import requests
import logging
import hashlib
from collections import OrderedDict
from datetime import datetime
from typing import Dict, Any, List, Optional
from litellm import completion
import litellm
# Disable telemetry and callbacks to avoid asyncio/threading conflicts
litellm.telemetry = False
litellm.success_callback = []
litellm.failure_callback = []
litellm.set_verbose = False
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_random_exponential, retry_if_not_exception_type

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("LLMService")

# --- Synapse/Proto Imports ---
SDK_PYTHON_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if SDK_PYTHON_PATH not in sys.path:
    sys.path.insert(0, SDK_PYTHON_PATH)

try:
    from agents.synapse_proto import semantic_engine_pb2, semantic_engine_pb2_grpc
except ImportError:
    logger.warning("⚠️  Warning: Could not import Synapse protobufs. Budgeting disabled.")
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
        # Load environment variables from .env
        load_dotenv(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env")))
        self.mock_mode = os.getenv("MOCK_LLM", "false").lower() == "true"

        self.api_key = os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.model = os.getenv("LLM_MODEL", "gemini/gemini-1.5-flash")
        # Configure Fallbacks (Ordered by preference)
        self.fallback_models = [
            "gemini/gemini-1.5-flash",
            "openrouter/google/gemini-2.0-flash-001"
        ]
        
        # Sense environment
        # fastembed (11435) doesn't provide Ollama completion API - removing incorrect fallback
        if "OLLAMA_API_BASE" in os.environ:
             del os.environ["OLLAMA_API_BASE"]

        if self.mock_mode:
            logger.info("🤖 LLMService initialized in MOCK MODE.")
        else:
            if not self.api_key:
                logger.warning("⚠️  Neither GEMINI_API_KEY nor OPENAI_API_KEY found. Defaulting to MOCK MODE.")
                self.mock_mode = True
            else:
                logger.info(f"🟢 LLMService initialized (Model: {self.model}, Fallbacks: {self.fallback_models})")

        # Synapse Connection
        self.grpc_host = os.getenv("SYNAPSE_GRPC_HOST", "localhost")
        self.grpc_port = int(os.getenv("SYNAPSE_GRPC_PORT", "50051"))
        self.max_daily_budget = float(os.getenv("MAX_DAILY_BUDGET", "10.0")) # Default $10
        self.channel = None
        self.stub = None
        self.namespace = "default"

        # @synapse:rule Implement in-memory LRU cache for LLM completion to reduce redundant LLM API calls and improve latency.
        self._cache = OrderedDict()
        self._cache_max_size = 100

        self.connect_synapse()
        self.ensure_finance_node()

    def connect_synapse(self):
        if not semantic_engine_pb2_grpc:
            return
        try:
            self.channel = grpc.insecure_channel(f"{self.grpc_host}:{self.grpc_port}")
            self.stub = semantic_engine_pb2_grpc.SemanticEngineStub(self.channel)
            print(f"📡 Connected to Synapse at {self.grpc_host}:{self.grpc_port}")
        except Exception as e:
            logger.warning(f"⚠️  LLMService failed to connect to Synapse: {e}")
            self.stub = None

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
            if "CANCELLED" in str(e) or "RST_STREAM" in str(e):
                logger.warning("🔄 gRPC Connection Reset detected in Ingest. Reconnecting...")
                self.connect_synapse()
            logger.error(f"❌ Ingest failed (ignoring for resilience): {e}")

    def _query(self, query: str) -> List[Dict]:
        if not self.stub or not semantic_engine_pb2: return []
        # print(f"DEBUG: Query called: {query}")
        request = semantic_engine_pb2.SparqlRequest(query=query, namespace=self.namespace)
        try:
            response = self.stub.QuerySparql(request)
            return json.loads(response.results_json)
        except Exception as e:
            if "CANCELLED" in str(e) or "RST_STREAM" in str(e):
                logger.warning("🔄 gRPC Connection Reset detected. Reconnecting to Synapse...")
                self.connect_synapse()
            logger.error(f"❌ Query failed: {repr(e)}")
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
            if isinstance(total, str):
                total = total.strip('"')
            return float(total) if total else 0.0
        except (ValueError, TypeError):
            return 0.0

    def send_telegram_alert(self, message: str):
        """Send alert via Telegram API and Hardening Stream."""
        logger.warning(f"🚨 ALERT: {message}")

        # 1. Broadcast to Godot (Hardening Event)
        try:
            requests.post(f"http://localhost:{os.getenv('GATEWAY_PORT', '18789')}/api/v1/events", json={
                "type": "HardeningEvent",
                "message": message,
                "severity": "WARNING",
                "timestamp": datetime.now().isoformat(),
                "details": {"source": "LLMService"}
            }, timeout=2)
        except Exception as e:
            logger.debug(f"Failed to broadcast hardening event: {e}")

        # 2. Telegram API
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("TELEGRAM_CHAT_ID")

        if not token or not chat_id:
            logger.debug("Telegram token/chat_id missing. Skipping Telegram API call.")
            return

        try:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            payload = {"chat_id": chat_id, "text": message}
            requests.post(url, json=payload, timeout=5)
        except Exception as e:
            logger.error(f"❌ Failed to send Telegram alert: {e}")

    def broadcast_thought(self, agent_name: str, thought: str):
        """Broadcast agent thoughts to the Neural Stream via Gateway."""
        from lib.telemetry import report_thought
        report_thought(thought, agent_id=agent_name)

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
                logger.warning("⚠️  80% Budget Warning Triggered!")
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

    def _get_cache_key(self, messages, json_mode, tools, tool_choice) -> str:
        cache_key_data = {
            "messages": messages,
            "json_mode": json_mode,
            "tools": tools,
            "tool_choice": tool_choice,
            "model": self.model,
            "temperature": 0.7
        }
        return hashlib.md5(json.dumps(cache_key_data, sort_keys=True).encode('utf-8')).hexdigest()

    def _check_cache(self, cache_key: str) -> Optional[Any]:
        if cache_key in self._cache:
            result = self._cache.pop(cache_key)
            self._cache[cache_key] = result
            return result
        return None

    def _resolve_model_name(self, m: str) -> str:
        """Helper to standardize model names for LiteLLM."""
        if m.startswith("openrouter/"):
            return m
        
        # Standardize Gemini
        if "gemini" in m.lower():
            res_m = m if "/" in m else f"gemini/{m}"
            if "-latest" in res_m:
                 res_m = res_m.replace("-latest", "")
            
            # Use 3.0, 2.5 or 2.0 if specified or default to 3
            if "flash" in res_m and "-8b" not in res_m:
                 # Prioritize latest versions per user request
                 if "3" in res_m: res_m = "gemini/gemini-3-flash-preview"
                 elif "2.5" in res_m: res_m = "gemini/gemini-2.5-flash"
                 elif "2.0" in res_m: res_m = "gemini/gemini-2.0-flash"
                 else: res_m = "gemini/gemini-3-flash-preview" # Upgrade default to Gemini 3
            return res_m
        return m

    def _prepare_fallbacks(self) -> List[Dict]:
        processed_fallbacks = []
        for m in self.fallback_models:
            res_m = self._resolve_model_name(m)
            fallback_dict = {"model": res_m}
            
            if res_m.startswith("openrouter/"):
                fallback_dict["api_key"] = os.getenv("OPENROUTER_API_KEY")
            
            processed_fallbacks.append(fallback_dict)
        return processed_fallbacks

    @retry(
        wait=wait_random_exponential(min=1, max=60),
        stop=stop_after_attempt(6),
        retry=retry_if_not_exception_type(BudgetExceededException)
    )
    def completion(self, prompt: str, system_prompt: str = "You are a helpful assistant.", json_mode: bool = False, tools: Optional[List[Dict]] = None, tool_choice: Any = None, messages: Optional[List[Dict]] = None) -> Any:
        """
        Generate a completion using the configured LLM, with Budget Enforcement.
        """
        if self.mock_mode:
            logger.info(f"🤖 [MOCK LLM] Prompt: {prompt[:50]}...")
            return '{"status": "success", "mock": true}' if json_mode else "Mock LLM Response: Task Completed."

        self.check_budget()

        if messages is None:
            messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}]

        # LiteLLM uses 'response_format' similar to OpenAI
        response_format = {"type": "json_object"} if json_mode else None
        
        cache_key = self._get_cache_key(messages, json_mode, tools, tool_choice)
        cached_result = self._check_cache(cache_key)
        if cached_result:
            return cached_result

        try:
            target_model = self._resolve_model_name(self.model)
            processed_fallbacks = self._prepare_fallbacks()
            response_format = {"type": "json_object"} if json_mode else None

            # Use synchronous completion to avoid loop issues in threads
            response = litellm.completion(
                model=target_model,
                messages=messages,
                api_key=self.api_key,
                response_format=response_format,
                tools=tools,
                temperature=0.7,
                max_tokens=2000,
                fallbacks=processed_fallbacks
            )

            if response.usage:
                self.log_spend(response.usage.get("prompt_tokens", 0), response.usage.get("completion_tokens", 0))

            result = response.choices[0].message
            if not (tools and result.tool_calls):
                result = result.content

            # Store in cache
            self._cache[cache_key] = result
            if len(self._cache) > self._cache_max_size:
                self._cache.popitem(last=False)

            return result
        except BudgetExceededException:
            raise # Propagate up
        except Exception as e:
            logger.error(f"Error calling LLM via LiteLLM: {e}")
            raise

    def get_structured_completion(self, prompt: str, system_prompt: str) -> Dict[str, Any]:
        """
        Get a JSON-parsed response from the LLM.
        """
        content = self.completion(prompt, system_prompt, json_mode=True)
        try:
            if hasattr(content, 'content'): # Handle tool/message object if returned
                content = content.content

            return json.loads(content)
        except json.JSONDecodeError:
            # Fallback: try to extract JSON from markdown code blocks if present
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
                return json.loads(content)
            raise ValueError(f"Failed to parse JSON from LLM response: {content}")
