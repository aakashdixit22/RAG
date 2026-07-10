import re

import numpy as np

from config import Config
from errors import APIError
from extensions import get_embedding_model, get_gemini_model


def chunk_text(text, chunk_size=None, overlap=None):
   
    chunk_size = chunk_size or Config.CHUNK_SIZE
    overlap = overlap or Config.CHUNK_OVERLAP

    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []

    chunks = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + chunk_size, n)
        if end < n:
            last_space = text.rfind(" ", start, end)
            if last_space > start:
                end = last_space
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= n:
            break
        start = max(end - overlap, start + 1)
    return chunks


def embed_texts(texts):
    """Embed a batch of chunk strings. Returns a list of float lists (JSON/BSON-safe)."""
    if not texts:
        return []
    model = get_embedding_model()
    embeddings = model.encode(texts, convert_to_numpy=True)
    return embeddings.tolist()


def embed_query(text):
    """Embed a single question string. Returns a 1-D numpy array."""
    model = get_embedding_model()
    return model.encode([text], convert_to_numpy=True)[0]


def cosine_similarity(vec_a, vec_b):
    a = np.asarray(vec_a, dtype=np.float32)
    b = np.asarray(vec_b, dtype=np.float32)
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def build_chunks_with_embeddings(text):
    """Chunk `text` and embed each chunk. Returns Mongo-storable dicts."""
    chunks = chunk_text(text)
    if not chunks:
        return []
    embeddings = embed_texts(chunks)
    return [
        {"chunk_index": i, "text": chunk, "embedding": embedding}
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings))
    ]


def retrieve_relevant_chunks(question, chunks, top_k=None):
    """Embed the question and rank stored chunks by cosine similarity.

    Returns a list of (score, chunk) tuples, highest similarity first.
    """
    top_k = top_k or Config.TOP_K_CHUNKS
    if not chunks:
        return []

    query_embedding = embed_query(question)
    scored = [(cosine_similarity(query_embedding, c["embedding"]), c) for c in chunks]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return scored[:top_k]


_PROMPT_TEMPLATE = """You are answering a question about a specific note, using ONLY the context excerpts below. \
Do not use outside knowledge. If the context does not contain enough information to answer, say so explicitly \
instead of guessing.

Context excerpts:
{context}

Question: {question}

Answer:"""


def generate_answer(question, retrieved_chunks):
    """Call the LLM with only the retrieved chunks (never the full document) as context."""
    context = (
        "\n\n---\n\n".join(chunk["text"] for _, chunk in retrieved_chunks)
        if retrieved_chunks
        else "(no relevant context found)"
    )
    prompt = _PROMPT_TEMPLATE.format(context=context, question=question)

    try:
        model = get_gemini_model()
        response = model.generate_content(prompt)
        answer = (getattr(response, "text", None) or "").strip()
    except Exception as exc:
        raise APIError(f"Failed to generate an answer from the LLM: {exc}", 502)

    if not answer:
        answer = "The model did not return an answer for this question."
    return answer
