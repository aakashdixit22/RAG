import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    # MongoDB
    MONGODB_URI = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
    MONGODB_DB_NAME = os.environ.get("MONGODB_DB_NAME", "notes_rag_db")

    # Auth
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev-secret-change-me")
    JWT_EXPIRES_HOURS = int(os.environ.get("JWT_EXPIRES_HOURS", "24"))

    # File upload
    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", "uploads")
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_UPLOAD_SIZE_BYTES", str(10 * 1024 * 1024)))
    ALLOWED_EXTENSIONS = {"pdf", "txt"}

    # LLM generation (Gemini)
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
    GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

    # Embeddings (local, sentence-transformers)
    EMBEDDING_MODEL_NAME = os.environ.get("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")

    # RAG pipeline tuning
    CHUNK_SIZE = int(os.environ.get("CHUNK_SIZE", "800"))
    CHUNK_OVERLAP = int(os.environ.get("CHUNK_OVERLAP", "100"))
    TOP_K_CHUNKS = int(os.environ.get("TOP_K_CHUNKS", "3"))
