import os
import requests
from datetime import datetime
from typing import Dict, Any, Optional
from lib.contracts import EventType, GatewayEvent

GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:18789")

def report_event(
    event_type: EventType,
    message: str,
    details: Optional[Dict[str, Any]] = None,
    severity: str = "INFO"
):
    """Report an event to the Rust gateway for TUI/Dashboard broadcast."""
    event = GatewayEvent(
        type=event_type,
        message=message,
        details=details or {},
        severity=severity,
        timestamp=datetime.now().isoformat()
    )
    
    try:
        requests.post(
            f"{GATEWAY_URL}/api/v1/events",
            json=event.model_dump(),
            timeout=1
        )
    except Exception:
        # Silently fail if gateway is down
        pass

def report_thought(thought: str, agent_id: str = "agent"):
    """Specifically report an agent's internal reasoning."""
    report_event(
        EventType.AGENT_THOUGHT,
        thought,
        details={"agent_id": agent_id}
    )

def report_tool(tool_name: str, args: Dict[str, Any], agent_id: str = "agent"):
    """Specifically report a tool execution."""
    report_event(
        EventType.TOOL_EXECUTION,
        f"Executing {tool_name}",
        details={"agent_id": agent_id, "tool": tool_name, "args": args},
        severity="DEBUG"
    )
