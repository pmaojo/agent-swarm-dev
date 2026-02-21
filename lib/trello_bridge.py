import os
import requests
import time
import json
import logging
from typing import List, Dict, Optional, Callable

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("TrelloBridge")

class TrelloBridge:
    def __init__(self, api_key: str = None, token: str = None, board_id: str = None):
        self.api_key = api_key or os.getenv("TRELLO_API_KEY")
        self.token = token or os.getenv("TRELLO_TOKEN")
        self.board_id = board_id or os.getenv("TRELLO_BOARD_ID")
        self.base_url = "https://api.trello.com/1"
        self.poll_interval = 10  # Seconds
        self.lists_cache = {}  # Map list_name -> list_id
        self.callbacks = {}    # Map list_name -> callback(card_data)

        # Track processed cards to prevent re-triggering for the same state
        # Set of tuples: (card_id, list_name)
        # We need to clear this if the card moves, but for simplicity,
        # we can just track what we've processed in the current list.
        # If a card moves back to a list, we should process it again? Yes.
        # But if it stays in a list (e.g., waiting for approval), we shouldn't.
        self.processed_states = set()

        if not all([self.api_key, self.token, self.board_id]):
            logger.warning("⚠️ Trello credentials missing. Bridge will run in Mock Mode.")
            self.mock_mode = True
        else:
            self.mock_mode = False
            self.refresh_lists()

    def _request(self, method: str, endpoint: str, params: Dict = None, data: Dict = None) -> Optional[Dict]:
        if self.mock_mode:
            logger.info(f"[MOCK] {method} {endpoint} params={params} data={data}")
            return {}

        url = f"{self.base_url}{endpoint}"
        query_params = {
            'key': self.api_key,
            'token': self.token
        }
        if params:
            query_params.update(params)

        try:
            response = requests.request(method, url, params=query_params, json=data)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Trello API Error: {e}")
            if response is not None:
                logger.error(f"Response: {response.text}")
            return None

    def refresh_lists(self):
        """Fetch all lists on the board and cache their IDs."""
        data = self._request("GET", f"/boards/{self.board_id}/lists")
        if data:
            self.lists_cache = {lst['name']: lst['id'] for lst in data}
            logger.info(f"✅ Trello Lists Loaded: {list(self.lists_cache.keys())}")

    def get_list_id(self, list_name: str) -> Optional[str]:
        return self.lists_cache.get(list_name)

    def get_cards_in_list(self, list_name: str) -> List[Dict]:
        """Get all cards in a specific list."""
        list_id = self.get_list_id(list_name)
        if not list_id:
            logger.warning(f"List '{list_name}' not found.")
            return []

        return self._request("GET", f"/lists/{list_id}/cards") or []

    def move_card(self, card_id: str, target_list_name: str):
        """Move a card to a different list."""
        target_list_id = self.get_list_id(target_list_name)
        if not target_list_id:
            logger.error(f"Cannot move card. Target list '{target_list_name}' not found.")
            return

        logger.info(f"🚚 Moving card {card_id} to '{target_list_name}'...")
        self._request("PUT", f"/cards/{card_id}", params={'idList': target_list_id})

        # Clear processing state for this card in the OLD list (implicitly handled by the set logic)
        # But we should also mark it as processed in the NEW list if we moved it ourselves?
        # No, usually we want the NEXT agent to pick it up.
        # So we leave it unprocessed for the next list callback.

    def update_card_desc(self, card_id: str, desc: str):
        """Update a card's description."""
        logger.info(f"📝 Updating description for {card_id}...")
        self._request("PUT", f"/cards/{card_id}", params={'desc': desc})

    def add_comment(self, card_id: str, text: str):
        """Add a comment to a card."""
        logger.info(f"💬 Commenting on {card_id}: {text[:50]}...")
        self._request("POST", f"/cards/{card_id}/actions/comments", params={'text': text})

    def has_label(self, card_id: str, label_name: str) -> bool:
        """Check if a card has a specific label (case-insensitive)."""
        card_data = self._request("GET", f"/cards/{card_id}")
        if not card_data: return False

        labels = card_data.get('labels', [])
        for label in labels:
            if label.get('name', '').lower() == label_name.lower():
                return True
        return False

    def register_callback(self, list_name: str, callback: Callable[[Dict], None]):
        """Register a function to be called when a card is found in a list."""
        self.callbacks[list_name] = callback

    def sync_loop_step(self):
        """
        Executes a single polling step. Non-blocking.
        """
        if self.mock_mode:
            logger.info("[MOCK] Polling Trello... (Mocking card detection)")
            # Simulate finding a card in INBOX only once
            if "INBOX" in self.callbacks and ('mock_card_1', 'INBOX') not in self.processed_states:
                 fake_card = {'id': 'mock_card_1', 'name': 'Test Feature', 'desc': 'Build a login page', 'idList': 'mock_list_id'}
                 logger.info(f"[MOCK] Found card in INBOX: {fake_card['name']}")
                 self.callbacks["INBOX"](fake_card)
                 self.processed_states.add(('mock_card_1', 'INBOX'))
            return

        # Real Polling
        # self.refresh_lists() # Optimization: Don't refresh on every tick.

        for list_name, callback in self.callbacks.items():
            cards = self.get_cards_in_list(list_name)
            for card in cards:
                card_id = card['id']
                state_key = (card_id, list_name)

                if state_key in self.processed_states:
                    continue # Skip already processed in this state

                logger.info(f"🔎 Found NEW card '{card['name']}' in '{list_name}'")
                try:
                    callback(card)
                    self.processed_states.add(state_key)
                except Exception as e:
                    logger.error(f"❌ Callback failed for card {card_id}: {e}")

    def sync_loop(self):
        """
        Main blocking polling loop.
        """
        logger.info("🔄 Starting Trello Sync Loop...")
        while True:
            self.sync_loop_step()
            time.sleep(self.poll_interval)

if __name__ == "__main__":
    # Test stub
    bridge = TrelloBridge()
    bridge.sync_loop()
