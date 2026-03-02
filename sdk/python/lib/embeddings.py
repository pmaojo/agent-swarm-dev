import os
import json
import torch
import torch.nn as nn
from fastembed import TextEmbedding

class FractalProjectionHead(nn.Module):
    """
    Lightweight MLP (~2.5M params) to project fastembed (bge-small) embeddings
    into a fractal space aligned with Synapse Ontology.
    """
    def __init__(self, input_dim=384, hidden_dim=2048, output_dim=384):
        super(FractalProjectionHead, self).__init__()
        self.fc1 = nn.Linear(input_dim, hidden_dim)
        self.relu = nn.ReLU()
        self.fc2 = nn.Linear(hidden_dim, output_dim)

    def forward(self, x):
        x = self.fc1(x)
        x = self.relu(x)
        x = self.fc2(x)
        # Normalize to unit vector for cosine similarity compatibility
        return torch.nn.functional.normalize(x, p=2, dim=1)

class FastEmbedFractal:
    def __init__(self, model_name="BAAI/bge-small-en-v1.5", model_path=None):
        self.embedding_model = TextEmbedding(model_name=model_name)
        self.projection_head = FractalProjectionHead()
        if model_path and os.path.exists(model_path):
            self.projection_head.load_state_dict(torch.load(model_path))
        self.projection_head.eval()

    def embed(self, texts):
        # fastembed returns a generator of numpy arrays
        base_embeddings = list(self.embedding_model.embed(texts))
        if not base_embeddings:
            return []

        import numpy as np
        base_tensor = torch.tensor(np.array(base_embeddings), dtype=torch.float32)

        with torch.no_grad():
            fractal_embeddings = self.projection_head(base_tensor)

        return fractal_embeddings.numpy().tolist()

if __name__ == "__main__":
    # Test
    embedder = FastEmbedFractal()
    vectors = embedder.embed(["Hello world", "This is a test of fractal routing"])
    print(f"Generated {len(vectors)} vectors of dimension {len(vectors[0])}")
