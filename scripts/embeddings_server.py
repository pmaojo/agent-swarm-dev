#!/usr/bin/env python3
"""
FastEmbed HTTP Server for Synapse
Serve embeddings via HTTP API (compatible with Ollama format)
"""

from fastembed import TextEmbedding
from flask import Flask, request, jsonify
import argparse
import signal
import sys

app = Flask(__name__)
model = None

def signal_handler(sig, frame):
    print('\n🛑 Shutting down...')
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

@app.route("/api/embeddings", methods=["POST"])
def embeddings():
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No JSON data"}), 400
            
        prompt = data.get("prompt", "")
        if not prompt:
            return jsonify({"error": "No prompt provided"}), 400
        
        # Generate embedding - convert numpy array to list
        result = list(model.embed([prompt]))
        embedding = result[0].tolist()  # numpy.ndarray.tolist()
        
        return jsonify({
            "embedding": embedding
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

def main():
    global model
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="BAAI/bge-small-en-v1.5", help="FastEmbed model")
    parser.add_argument("--port", type=int, default=11434, help="Port")
    args = parser.parse_args()
    
    print(f"📥 Loading model: {args.model}")
    model = TextEmbedding(args.model)
    print(f"✅ Server ready on port {args.port}")
    
    app.run(host="0.0.0.0", port=args.port, debug=False)

if __name__ == "__main__":
    main()
