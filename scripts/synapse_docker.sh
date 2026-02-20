#!/bin/bash
# Synapse Docker Runner for Agent Swarm Dev

IMAGE="pmaojo/synapse-engine:latest"
CONTAINER_NAME="synapse-swarm"
PORT=50051

case "$1" in
  start)
    echo "🚀 Starting Synapse..."
    docker run -d --name $CONTAINER_NAME \
      -p $PORT:$PORT \
      -v synapse-data:/data \
      $IMAGE
    echo "✅ Synapse running on port $PORT"
    ;;
  stop)
    echo "🛑 Stopping Synapse..."
    docker stop $CONTAINER_NAME 2>/dev/null || true
    docker rm $CONTAINER_NAME 2>/dev/null || true
    ;;
  status)
    if docker ps | grep -q $CONTAINER_NAME; then
      echo "✅ Synapse is running on port $PORT"
    else
      echo "❌ Synapse is not running"
    fi
    ;;
  logs)
    docker logs $CONTAINER_NAME
    ;;
  *)
    echo "Usage: $0 {start|stop|status|logs}"
    exit 1
    ;;
esac
