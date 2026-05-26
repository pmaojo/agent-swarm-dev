"""
synapse_connect — connects every agent to the Synapse gRPC server.

Reads SYNAPSE_GRPC_HOST / SYNAPSE_GRPC_PORT from the environment.
If the server is not reachable the call raises so the agent fails loudly
instead of silently degrading to an in-process stub.
"""

import logging
import os

import grpc

logger = logging.getLogger("SynapseConnect")

_DEFAULT_TIMEOUT = float(os.getenv("SYNAPSE_CONNECT_TIMEOUT", "5.0"))


def connect_synapse(host: str | None = None, port: int | str | None = None,
                    timeout: float = _DEFAULT_TIMEOUT):
    """
    Connect to the Synapse gRPC server and return a SemanticEngineStub.

    Raises RuntimeError if the server is not reachable within *timeout* seconds
    so callers fail fast and visibly rather than silently falling back.
    """
    host = host or os.getenv("SYNAPSE_GRPC_HOST", "localhost")
    port = port or os.getenv("SYNAPSE_GRPC_PORT", "50051")

    try:
        from agents.synapse_proto import semantic_engine_pb2_grpc
    except ImportError:
        from synapse_proto import semantic_engine_pb2_grpc  # type: ignore

    addr = f"{host}:{port}"
    channel = grpc.insecure_channel(addr)
    try:
        grpc.channel_ready_future(channel).result(timeout=timeout)
        stub = semantic_engine_pb2_grpc.SemanticEngineStub(channel)
        logger.info("✅ Connected to Synapse gRPC at %s", addr)
        return stub
    except grpc.FutureTimeoutError:
        channel.close()
        raise RuntimeError(
            f"Synapse gRPC not reachable at {addr} — is the server running? "
            f"Start it with: cd vendor/synapse-engine && ./start_synapse.sh"
        )
    except Exception as e:
        channel.close()
        raise RuntimeError(f"Synapse gRPC error at {addr}: {e}") from e
