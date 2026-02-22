import os
import sys
import uuid
import grpc
import subprocess
import json
from typing import List, Dict, Optional

# --- Synapse/Proto Imports ---
SDK_PYTHON_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if SDK_PYTHON_PATH not in sys.path:
    sys.path.insert(0, SDK_PYTHON_PATH)

try:
    from agents.synapse_proto import semantic_engine_pb2, semantic_engine_pb2_grpc
except ImportError:
    semantic_engine_pb2 = None
    semantic_engine_pb2_grpc = None

SWARM = "http://swarm.os/ontology/"
NIST = "http://nist.gov/caisi/"
RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
PROV = "http://www.w3.org/ns/prov#"

class GitService:
    def __init__(self, repo_path: str = "."):
        self.repo_path = os.path.abspath(repo_path)
        self.grpc_host = os.getenv("SYNAPSE_GRPC_HOST", "localhost")
        self.grpc_port = int(os.getenv("SYNAPSE_GRPC_PORT", "50051"))
        self.channel = None
        self.stub = None
        self.connect_synapse()

    def connect_synapse(self):
        if not semantic_engine_pb2_grpc:
            return
        try:
            self.channel = grpc.insecure_channel(f"{self.grpc_host}:{self.grpc_port}")
            self.stub = semantic_engine_pb2_grpc.SemanticEngineStub(self.channel)
        except Exception as e:
            print(f"⚠️  GitService failed to connect to Synapse: {e}")

    def _ingest(self, triples: List[Dict[str, str]], namespace: str = "default"):
        if not self.stub or not semantic_engine_pb2: return
        pb_triples = []
        for t in triples:
            pb_triples.append(semantic_engine_pb2.Triple(
                subject=t["subject"],
                predicate=t["predicate"],
                object=t["object"]
            ))
        request = semantic_engine_pb2.IngestRequest(triples=pb_triples, namespace=namespace)
        try:
            self.stub.IngestTriples(request)
        except Exception as e:
            print(f"❌ GitService Ingest failed: {e}")

    def _run_git(self, args: List[str]) -> str:
        """Run a git command in the repo."""
        try:
            result = subprocess.run(
                ["git"] + args,
                cwd=self.repo_path,
                check=True,
                capture_output=True,
                text=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            print(f"❌ Git Command Failed: {e} | Stderr: {e.stderr}")
            raise Exception(f"Git command failed: {' '.join(args)}")

    def get_current_branch(self) -> str:
        return self._run_git(["rev-parse", "--abbrev-ref", "HEAD"])

    def create_branch(self, task_id: str, agent_name: str, base_branch: str = "main") -> str:
        """
        Creates a sovereign branch for the task and ingests traceability triples.
        """
        # Sanitize task_id for branch name
        safe_task_id = "".join([c if c.isalnum() else "-" for c in task_id]).strip("-")
        branch_name = f"feature/{safe_task_id}"

        print(f"🌿 Creating Sovereign Branch: {branch_name} for Agent: {agent_name}")

        # Checkout base and create new branch
        try:
            # Check if branch exists
            self._run_git(["rev-parse", "--verify", branch_name])
            self._run_git(["checkout", branch_name])
            print(f"   Context switched to existing branch: {branch_name}")
        except:
            # Create new
            try:
                self._run_git(["checkout", base_branch])
                self._run_git(["pull"]) # Ensure base is up to date
            except:
                pass # Might fail in offline/test env
            self._run_git(["checkout", "-b", branch_name])

        # Ingest Semantic Traceability
        branch_uri = f"{SWARM}branch/{branch_name}"
        task_uri = f"{SWARM}task/{task_id}"
        agent_uri = f"{SWARM}agent/{agent_name}"

        triples = [
            {"subject": branch_uri, "predicate": f"{RDF}type", "object": f"{SWARM}GitBranch"},
            {"subject": branch_uri, "predicate": f"{SWARM}name", "object": f'"{branch_name}"'},
            {"subject": branch_uri, "predicate": f"{SWARM}originatesFrom", "object": task_uri},
            {"subject": branch_uri, "predicate": f"{PROV}wasAttributedTo", "object": agent_uri},
            {"subject": branch_uri, "predicate": f"{SWARM}status", "object": '"ACTIVE"'}
        ]
        self._ingest(triples)
        print(f"🔗 Traceability Ingested: <{branch_name}> originatesFrom <{task_id}>")

        return branch_name

    def commit_changes(self, message: str, agent_name: str):
        """
        Stages all changes and commits them.
        """
        self._run_git(["add", "."])
        # Check if there are changes
        status = self._run_git(["status", "--porcelain"])
        if not status:
            print("⚠️ No changes to commit.")
            return

        self._run_git(["commit", "-m", message])
        commit_hash = self._run_git(["rev-parse", "HEAD"])

        branch_name = self.get_current_branch()
        branch_uri = f"{SWARM}branch/{branch_name}"
        commit_uri = f"{SWARM}commit/{commit_hash}"
        agent_uri = f"{SWARM}agent/{agent_name}"

        triples = [
            {"subject": commit_uri, "predicate": f"{RDF}type", "object": f"{SWARM}GitCommit"},
            {"subject": commit_uri, "predicate": f"{SWARM}message", "object": f'"{message}"'},
            {"subject": commit_uri, "predicate": f"{SWARM}partOf", "object": branch_uri},
            {"subject": commit_uri, "predicate": f"{PROV}wasAssociatedWith", "object": agent_uri}
        ]
        self._ingest(triples)
        print(f"💾 Committed: {commit_hash[:7]} by {agent_name}")

    def create_pr(self, title: str, body: str, agent_name: str) -> str:
        """
        Creates a PR using 'gh' CLI if available, otherwise mocks it.
        Updates Synapse with traceability.
        """
        branch_name = self.get_current_branch()
        print(f"🚀 Pushing branch {branch_name}...")

        has_remote = False
        try:
            remotes = self._run_git(["remote"])
            if remotes:
                self._run_git(["push", "-u", "origin", branch_name])
                has_remote = True
            else:
                print("⚠️ No remote found, skipping push (local simulation).")
        except Exception as e:
             print(f"⚠️ Push failed (likely permissions or mock env): {e}")

        pr_uri = None

        # Try using GH CLI if remote exists and push succeeded
        if has_remote:
            try:
                # Check for gh cli
                subprocess.run(["gh", "--version"], check=True, capture_output=True)

                print(f"gh CLI found. Creating real PR: {title}")
                cmd = ["gh", "pr", "create", "--title", title, "--body", body, "--head", branch_name, "--base", "main"]
                result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.repo_path)

                if result.returncode == 0:
                    # Parse PR URL from stdout (usually the last line)
                    # Output: https://github.com/org/repo/pull/123
                    pr_url = result.stdout.strip().split('\n')[-1]
                    if pr_url.startswith("http"):
                        pr_uri = pr_url
                        print(f"✅ PR Created: {pr_uri}")
                else:
                    print(f"⚠️ gh pr create failed: {result.stderr}")
            except FileNotFoundError:
                print("ℹ️ gh CLI not installed. Skipping real PR creation.")
            except Exception as e:
                print(f"⚠️ Failed to invoke gh CLI: {e}")

        if not pr_uri:
             # Fallback to simulated PR URI
             pr_id = str(uuid.uuid4())[:8]
             pr_uri = f"{SWARM}pr/{pr_id}"
             print(f"📋 [Simulation] Created PR: {title} (URI: {pr_uri})")

        # Ingest PR Status
        triples = [
            {"subject": pr_uri, "predicate": f"{RDF}type", "object": f"{SWARM}PullRequest"},
            {"subject": pr_uri, "predicate": f"{SWARM}title", "object": f'"{title}"'},
            {"subject": pr_uri, "predicate": f"{SWARM}sourceBranch", "object": f"{SWARM}branch/{branch_name}"},
            {"subject": pr_uri, "predicate": f"{SWARM}status", "object": '"PENDING_NEURO_REVIEW"'},
        ]
        self._ingest(triples)
        return pr_uri

    def get_diff(self, branch_name: str, base_branch: str = "main") -> str:
        """Get the diff between branches."""
        try:
            return self._run_git(["diff", base_branch + "..." + branch_name])
        except:
            return ""

if __name__ == "__main__":
    # Test
    git = GitService()
    print("Current Branch:", git.get_current_branch())
