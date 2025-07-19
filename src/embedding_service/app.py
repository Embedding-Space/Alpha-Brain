"""FastAPI embedding service."""

import time
from contextlib import asynccontextmanager

import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

# Model names
SEMANTIC_MODEL = "sentence-transformers/all-mpnet-base-v2"
EMOTIONAL_MODEL = "ng3owb/sentiment-embedding-model"

# Global model instances
semantic_model = None
emotional_model = None


class EmbedRequest(BaseModel):
    """Request for embedding generation."""
    text: str
    model_type: str = "both"  # "semantic", "emotional", or "both"


class EmbedResponse(BaseModel):
    """Response with embeddings."""
    semantic: list[float] | None = None
    emotional: list[float] | None = None
    
    
class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    models_loaded: bool
    semantic_dim: int | None = None
    emotional_dim: int | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load models on startup."""
    global semantic_model, emotional_model
    
    print("Loading embedding models...")
    start_time = time.time()
    
    # Load semantic model
    print(f"Loading semantic model: {SEMANTIC_MODEL}")
    semantic_model = SentenceTransformer(SEMANTIC_MODEL, device="cpu")
    print("Semantic model loaded")
    
    # Load emotional model
    print(f"Loading emotional model: {EMOTIONAL_MODEL}")
    emotional_model = SentenceTransformer(EMOTIONAL_MODEL, device="cpu")
    print("Emotional model loaded")
    
    # Test models and warm them up
    test_text = "test"
    print("Warming up models with test inference...")
    warmup_start = time.time()
    semantic_dim = len(semantic_model.encode(test_text))
    emotional_dim = len(emotional_model.encode(test_text))
    warmup_time = time.time() - warmup_start
    
    load_time = time.time() - start_time
    print(f"Models loaded in {load_time:.2f} seconds")
    print(f"Warmup inference took {warmup_time:.2f} seconds")
    print(f"Semantic dimensions: {semantic_dim}")
    print(f"Emotional dimensions: {emotional_dim}")
    
    yield
    
    # Cleanup (if needed)
    print("Shutting down embedding service")


# Create FastAPI app
app = FastAPI(
    title="Alpha Brain Embedding Service",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy" if semantic_model and emotional_model else "loading",
        models_loaded=semantic_model is not None and emotional_model is not None,
        semantic_dim=semantic_model.get_sentence_embedding_dimension() if semantic_model else None,
        emotional_dim=emotional_model.get_sentence_embedding_dimension() if emotional_model else None,
    )


@app.post("/embed", response_model=EmbedResponse)
async def embed(request: EmbedRequest):
    """Generate embeddings for text."""
    if not semantic_model or not emotional_model:
        raise HTTPException(status_code=503, detail="Models not loaded yet")
    
    response = EmbedResponse()
    
    if request.model_type in ["semantic", "both"]:
        semantic_emb = semantic_model.encode(request.text)
        response.semantic = semantic_emb.tolist()
    
    if request.model_type in ["emotional", "both"]:
        emotional_emb = emotional_model.encode(request.text)
        response.emotional = emotional_emb.tolist()
    
    return response


@app.post("/embed_batch")
async def embed_batch(texts: list[str], model_type: str = "both"):
    """Generate embeddings for multiple texts."""
    if not semantic_model or not emotional_model:
        raise HTTPException(status_code=503, detail="Models not loaded yet")
    
    result = {}
    
    if model_type in ["semantic", "both"]:
        semantic_embs = semantic_model.encode(texts)
        result["semantic"] = semantic_embs.tolist()
    
    if model_type in ["emotional", "both"]:
        emotional_embs = emotional_model.encode(texts)
        result["emotional"] = emotional_embs.tolist()
    
    return result


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8001, reload=True)