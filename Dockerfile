# WISP monitoring assistant - the app only (RAG pipeline, SQLite/Chroma stores, Gradio UI).
# The LLM is NOT in here: it stays external (local Ollama on the host, or a hosted API),
# configured through .env / environment variables. See docker-compose.yml.
FROM python:3.11-slim

WORKDIR /app

# build-essential: fallback in case chromadb's native deps need to compile on this platform.
RUN apt-get update && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# CPU-only torch first: this container only runs CPU embedding inference (the LLM is
# external), so the default CUDA-enabled wheel would pull ~5GB of unused nvidia-* libs.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt

# Bake the embedding model into the image at build time (needs internet during build
# only), so the container never needs internet access at runtime. Must match the
# "bge-small" entry in wisp_rag.py's MODELS table.
RUN python -c "from sentence_transformers import SentenceTransformer; \
SentenceTransformer('BAAI/bge-small-en-v1.5')"
ENV HF_HUB_OFFLINE=1

COPY . .

ENV WISP_HOST=0.0.0.0 \
    WISP_PORT=7860
EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s \
    CMD curl -f http://localhost:7860/ || exit 1

CMD ["python", "wisp_assistant.py", "ui"]
