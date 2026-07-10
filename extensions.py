
from pymongo import MongoClient

from config import Config

_mongo_client = None
_db = None
_embedding_model = None
_gemini_configured = False


def get_db():
    global _mongo_client, _db
    if _db is None:
        _mongo_client = MongoClient(Config.MONGODB_URI)
        _db = _mongo_client[Config.MONGODB_DB_NAME]
        _db.users.create_index("email", unique=True)
        _db.notes.create_index("user_id")
    return _db


def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        # Imported here, not at module load time, so the (slow) torch/ML import
        # only happens once an embedding is actually requested.
        from sentence_transformers import SentenceTransformer

        _embedding_model = SentenceTransformer(Config.EMBEDDING_MODEL_NAME)
    return _embedding_model


def get_gemini_model():
    global _gemini_configured
    import google.generativeai as genai

    if not Config.GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Add it to your .env file (see .env.example)."
        )
    if not _gemini_configured:
        genai.configure(api_key=Config.GEMINI_API_KEY)
        _gemini_configured = True
    return genai.GenerativeModel(Config.GEMINI_MODEL)
