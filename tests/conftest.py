import pytest
import os
import json
import time
import requests
from unittest.mock import MagicMock

# Traffic Receipt Path
RECEIPT_FILE = os.path.join(os.getcwd(), "traffic_receipt.json")

def pytest_configure(config):
    """Clear previous receipt on start."""
    if os.path.exists(RECEIPT_FILE):
        try:
            os.remove(RECEIPT_FILE)
        except OSError:
            pass

@pytest.fixture(autouse=True)
def log_requests(monkeypatch):
    """
    Monkeypatch requests.request to log traffic.
    This ensures we capture actual network attempts.
    """
    original_request = requests.request

    def logging_request(method, url, **kwargs):
        # Perform the actual request
        try:
            response = original_request(method, url, **kwargs)
            outcome = "success"
            status = response.status_code
        except Exception as e:
            outcome = "failure"
            status = str(e)
            raise e
        finally:
            # Log the attempt
            entry = {
                "timestamp": time.time(),
                "method": method,
                "url": url,
                "outcome": outcome,
                "status": status
            }
            try:
                # Append to JSON list (inefficient but safe for tests)
                data = []
                if os.path.exists(RECEIPT_FILE):
                    with open(RECEIPT_FILE, "r") as f:
                        try:
                            data = json.load(f)
                        except: pass
                data.append(entry)
                with open(RECEIPT_FILE, "w") as f:
                    json.dump(data, f, indent=2)
            except Exception as e:
                print(f"Failed to write traffic receipt: {e}")

        return response

    monkeypatch.setattr(requests, "request", logging_request)
