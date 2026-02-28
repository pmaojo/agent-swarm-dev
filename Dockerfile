# Stage 1: Build Frontend (React)
FROM node:20-slim AS frontend-builder
WORKDIR /app
COPY commander-dashboard ./commander-dashboard
WORKDIR /app/commander-dashboard
# Use cached npm install if possible but copy entire dir for now
RUN npm install
RUN npm run build

# Stage 2: Runtime (Python)
FROM python:3.11-slim
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
  curl \
  git \
  && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY sdk/python/lib ./sdk/python/lib
COPY sdk/python/agents ./sdk/python/agents
COPY sdk/python/data ./sdk/python/data
COPY scripts ./scripts
COPY scenarios ./scenarios
COPY swarm_schema.yaml .
# Ensure we have the latest generated Python files from grpc based on the container's version limit
COPY synapse-engine/crates/semantic-engine/proto/semantic_engine.proto ./
RUN python -m grpc_tools.protoc -I. \
  --python_out=./sdk/python/agents/synapse_proto \
  --grpc_python_out=./sdk/python/agents/synapse_proto \
  semantic_engine.proto \
  && mkdir -p commander-dashboard/dist

# Copy built frontend from Stage 1
COPY --from=frontend-builder /app/commander-dashboard/dist ./commander-dashboard/dist

# Environment variables
ENV PORT=18789
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/sdk/python/lib:/app/sdk/python:/app/sdk/python/agents/synapse_proto

# Expose port
EXPOSE 18789

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl --fail http://127.0.0.1:18789/status || exit 1

# Start the unified Rust gateway
CMD ["/app/swarmd/target/release/swarmd"]
