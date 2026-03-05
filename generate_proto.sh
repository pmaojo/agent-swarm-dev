#!/bin/bash
python -m grpc_tools.protoc -I vendor/synapse-engine/crates/semantic-engine/proto --python_out=sdk/python/agents/synapse_proto --grpc_python_out=sdk/python/agents/synapse_proto vendor/synapse-engine/crates/semantic-engine/proto/semantic_engine.proto
python -m grpc_tools.protoc -I vendor/synapse-engine/crates/semantic-engine/proto --python_out=vendor/synapse-engine/scripts/generated --grpc_python_out=vendor/synapse-engine/scripts/generated vendor/synapse-engine/crates/semantic-engine/proto/semantic_engine.proto
python -m grpc_tools.protoc -I vendor/synapse-engine/crates/semantic-engine/proto --python_out=synapse-engine/scripts/generated --grpc_python_out=synapse-engine/scripts/generated vendor/synapse-engine/crates/semantic-engine/proto/semantic_engine.proto
