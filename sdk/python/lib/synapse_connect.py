"""
synapse_connect — single helper used by every agent to obtain a Synapse stub.

Priority:
  1. gRPC server at SYNAPSE_GRPC_HOST:SYNAPSE_GRPC_PORT (or the supplied host/port)
  2. LocalSynapseStub (rdflib, no server required)

Usage:
    from lib.synapse_connect import connect_synapse
    self.stub = connect_synapse(self.grpc_host, self.grpc_port)
"""

import logging
import os

import grpc

logger = logging.getLogger("SynapseConnect")


def connect_synapse(host: str | None = None, port: int | str | None = None, timeout: float = 2.0):
    """
    Try to connect to the Synapse gRPC server.  If the server is not
    reachable within *timeout* seconds, return a LocalSynapseStub instead.

    Returns an object that implements IngestTriples / QuerySparql / HybridSearch
    with the same call signature as SemanticEngineStub.
    """
    host = host or os.getenv("SYNAPSE_GRPC_HOST", "localhost")
    port = port or os.getenv("SYNAPSE_GRPC_PORT", "50051")

    try:
        # Import stubs lazily to keep import order flexible
        from agents.synapse_proto import (
            semantic_engine_pb2_grpc,
        )
    except ImportError:
        try:
            from synapse_proto import semantic_engine_pb2_grpc  # type: ignore
        except ImportError:
            logger.warning("Cannot import synapse_proto — using LocalSynapseStub")
            return _local_stub()

    addr = f"{host}:{port}"
    channel = grpc.insecure_channel(addr)
    try:
        grpc.channel_ready_future(channel).result(timeout=timeout)
        stub = semantic_engine_pb2_grpc.SemanticEngineStub(channel)
        logger.info("✅ Connected to Synapse gRPC at %s", addr)
        return stub
    except grpc.FutureTimeoutError:
        logger.warning("⚠️  Synapse gRPC not reachable at %s — using LocalSynapseStub", addr)
        channel.close()
        return _local_stub()
    except Exception as e:
        logger.warning("⚠️  Synapse gRPC error (%s) — using LocalSynapseStub", e)
        channel.close()
        return _local_stub()


def _local_stub():
    from lib.local_synapse import LocalSynapseStub  # type: ignore
    return LocalSynapseStub()
