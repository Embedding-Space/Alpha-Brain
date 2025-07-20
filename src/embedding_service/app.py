"""FastAPI embedding service."""

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
from transformers import pipeline

# Model names
SEMANTIC_MODEL = "sentence-transformers/all-mpnet-base-v2"
EMOTIONAL_MODEL = "j-hartmann/emotion-english-roberta-large"

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

    # Load emotional model (7D emotion classifier)
    print(f"Loading emotional model: {EMOTIONAL_MODEL}")
    emotional_model = pipeline(
        "text-classification",
        model=EMOTIONAL_MODEL,
        return_all_scores=True,
        device=-1,  # CPU
    )
    print("Emotional model loaded")

    # Test models and warm them up
    test_text = "test"
    print("Warming up models with test inference...")
    warmup_start = time.time()
    semantic_dim = len(semantic_model.encode(test_text))
    # For emotion model, test it differently
    emotional_model(test_text)[0]  # Warm up the model
    emotional_dim = 7  # Always 7 emotions
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
        semantic_dim=semantic_model.get_sentence_embedding_dimension()
        if semantic_model
        else None,
        emotional_dim=7 if emotional_model else None,  # Always 7 emotions
    )


def extract_emotion_vector(emotion_results):
    """Extract 7D emotion vector from classifier results."""
    # Order: anger, disgust, fear, joy, neutral, sadness, surprise
    emotion_order = [
        "anger",
        "disgust",
        "fear",
        "joy",
        "neutral",
        "sadness",
        "surprise",
    ]
    return [
        next(r["score"] for r in emotion_results if r["label"] == emotion)
        for emotion in emotion_order
    ]


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
        # Truncate text for emotion model (max 512 tokens)
        # Take first ~2000 chars to stay under token limit
        truncated_text = (
            request.text[:2000] if len(request.text) > 2000 else request.text
        )

        # Get emotion classification results
        emotion_results = emotional_model(truncated_text)[0]
        # Extract 7D vector
        emotional_emb = extract_emotion_vector(emotion_results)
        response.emotional = emotional_emb

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
        # Process each text through emotion classifier
        emotional_embs = []
        for text in texts:
            # Truncate text for emotion model (max 512 tokens)
            truncated_text = text[:2000] if len(text) > 2000 else text
            emotion_results = emotional_model(truncated_text)[0]
            emotion_vector = extract_emotion_vector(emotion_results)
            emotional_embs.append(emotion_vector)
        result["emotional"] = emotional_embs

    return result


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=8001, reload=True)
