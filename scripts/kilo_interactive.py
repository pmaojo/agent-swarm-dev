#!/usr/bin/env python3
"""
Kilo Interactive Mode (CLI).
Command Center for Synapse Agent Swarm.
"""
import sys
import os
import readline
import shlex
import time
import json
from typing import Dict, Any

# Adjust paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lib'))

from agents.coder import CoderAgent
from agents.reviewer import ReviewerAgent
from agents.tools.browser import BrowserTool
from agents.tools.knowledge import KnowledgeHarvester
from agents.tools.scenarios import ScenarioLoader
from agents.tools.context import ContextParser
from llm import LLMService

class KiloShell:
    def __init__(self):
        self.context = {"history": []}
        self.browser = BrowserTool()
        self.harvester = KnowledgeHarvester()
        self.scenario_loader = ScenarioLoader()
        self.context_parser = ContextParser()
        self.llm = LLMService() # Direct LLM access for /ask

        # Agents are instantiated per task or reused?
        # Reusing might keep state, but they are designed to be stateless mostly.
        # But CoderAgent holds connection.
        self.coder = CoderAgent()
        self.reviewer = ReviewerAgent()

    def print_help(self):
        print("""
🤖 Kilo Interactive Mode - Commands:
  /ask <query>        - Chat with LLM (aware of context).
  /code <task>        - Run CoderAgent to implement a task.
  /review             - Run ReviewerAgent on last modified files.
  /browser <query>    - Search documentation using BrowserTool.
  /harvest <path>     - Scan path for @synapse tags and ingest.
  /scenario <name>    - Load a Synapse scenario (ontology).
  /context            - Show current context/history.
  /clear              - Clear context.
  /help               - Show this help.
  /quit               - Exit.
""")

    def handle_ask(self, query):
        print("🤔 Thinking...")
        # Expand context with parser
        expanded_query = self.context_parser.expand_context(query)

        try:
            response = self.llm.completion(expanded_query)
            print(f"\n🤖 {response}\n")
        except Exception as e:
            print(f"❌ Error: {e}")

    def handle_code(self, task):
        print(f"🚀 [Coder] Starting task: {task}")
        result = self.coder.run(task, self.context)

        # Update context
        self.context["history"].append({
            "agent": "Coder",
            "outcome": result.get("status"),
            "result": result.get("result", {})
        })

        if result.get("status") == "success":
            print(f"✅ Task Completed.")
            print(f"📄 Modified Files: {result.get('result', {}).get('saved_files', [])}")
            print(f"📝 Summary: {result.get('result', {}).get('result', '')}")
        else:
            print(f"❌ Task Failed: {result.get('error')}")

    def handle_review(self):
        print(f"🧐 [Reviewer] Starting review...")
        result = self.reviewer.run("Review recent changes", self.context)

        if result.get("status") == "success":
            print(f"✅ Review Passed.")
        else:
            print(f"❌ Review Failed/Issues Found:")
            for issue in result.get("issues", []):
                print(f"  - {issue}")

        # Show detailed feedback
        print(json.dumps(result.get("review", {}), indent=2))

    def handle_browser(self, query):
        results = self.browser.search_documentation(query)
        for i, res in enumerate(results):
            print(f"{i+1}. {res['title']}")
            print(f"   {res['url']}")
            print(f"   {res['snippet'][:150]}...\n")

    def handle_harvest(self, path):
        self.harvester.scan_and_ingest(path)

    def handle_scenario(self, name):
        self.scenario_loader.load_scenario(name)

    def start(self):
        print("\nWelcome to Kilo Interactive Mode (Synapse Swarm). Type /help for commands.\n")
        while True:
            try:
                user_input = input("kilo> ").strip()
                if not user_input: continue

                if user_input.startswith("/"):
                    parts = user_input.split(" ", 1)
                    cmd = parts[0]
                    arg = parts[1] if len(parts) > 1 else ""

                    if cmd == "/quit":
                        break
                    elif cmd == "/help":
                        self.print_help()
                    elif cmd == "/ask":
                        self.handle_ask(arg)
                    elif cmd == "/code":
                        self.handle_code(arg)
                    elif cmd == "/review":
                        self.handle_review()
                    elif cmd == "/browser":
                        self.handle_browser(arg)
                    elif cmd == "/harvest":
                        self.handle_harvest(arg)
                    elif cmd == "/scenario":
                        self.handle_scenario(arg)
                    elif cmd == "/context":
                        print(json.dumps(self.context, indent=2))
                    elif cmd == "/clear":
                        self.context = {"history": []}
                        print("Context cleared.")
                    else:
                        print(f"Unknown command: {cmd}")
                else:
                    # Default to /ask if no command? or just warn
                    print("Please use a command (start with /). Try /help or /ask <query>.")

            except KeyboardInterrupt:
                print("\nType /quit to exit.")
            except Exception as e:
                print(f"❌ Error: {e}")

        # Cleanup
        self.coder.close()
        self.reviewer.close()
        self.browser.close()
        self.harvester.close()
        self.scenario_loader.close()
        self.context_parser.close()

if __name__ == "__main__":
    shell = KiloShell()
    shell.start()
