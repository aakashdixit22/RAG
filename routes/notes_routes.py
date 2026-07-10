
import datetime
import os

from bson import ObjectId
from bson.errors import InvalidId
from flask import g, jsonify, request
from werkzeug.utils import secure_filename

from app import app
from auth import token_required
from config import Config
from errors import NotFoundError, UnsupportedMediaTypeError, ValidationError
from extensions import get_db
from services.file_extraction import extract_text
from services.rag import build_chunks_with_embeddings, generate_answer, retrieve_relevant_chunks


def _allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in Config.ALLOWED_EXTENSIONS


def _to_object_id(note_id):
    try:
        return ObjectId(note_id)
    except (InvalidId, TypeError):
        raise NotFoundError("Note not found")


def _get_owned_note(note_id, user_id):
    note = get_db().notes.find_one({"_id": _to_object_id(note_id), "user_id": user_id})
    if not note:
        raise NotFoundError("Note not found")
    return note


def _serialize_note(note, include_content=False):
    data = {
        "id": str(note["_id"]),
        "title": note.get("title", ""),
        "file_name": note.get("file_name"),
        "has_file": bool(note.get("file_name")),
        "chunk_count": len(note.get("chunks") or []),
        "created_at": note["created_at"].isoformat(),
        "updated_at": note["updated_at"].isoformat(),
    }
    if include_content:
        data["content"] = note.get("content", "")
        data["extracted_text"] = note.get("extracted_text", "")
    else:
        preview_source = note.get("content") or note.get("extracted_text") or ""
        data["preview"] = preview_source[:200]
    return data


def _process_uploaded_file(file_storage, user_id, note_id):
    filename = secure_filename(file_storage.filename or "")
    if not filename:
        raise ValidationError("Invalid uploaded file name")
    if not _allowed_file(filename):
        raise UnsupportedMediaTypeError("Only .pdf and .txt files are supported")

    file_bytes = file_storage.read()

    extracted_text = extract_text(filename, file_bytes)

    user_dir = os.path.join(Config.UPLOAD_FOLDER, str(user_id))
    os.makedirs(user_dir, exist_ok=True)
    stored_name = f"{note_id}_{filename}"
    file_path = os.path.join(user_dir, stored_name)
    with open(file_path, "wb") as f:
        f.write(file_bytes)

    return {"file_name": filename, "file_path": file_path, "extracted_text": extracted_text}


def _delete_file_if_exists(file_path):
    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
        except OSError:
            pass


def _parse_note_input():
    """Read title/content/file from either a JSON body or a multipart form."""
    if request.content_type and "multipart/form-data" in request.content_type:
        title = request.form.get("title")
        content = request.form.get("content")
        file_storage = request.files.get("file")
    else:
        payload = request.get_json(silent=True) or {}
        title = payload.get("title")
        content = payload.get("content")
        file_storage = None
    return title, content, file_storage


@app.route("/notes", methods=["POST"])
@token_required
def create_note():
    db = get_db()
    user_id = g.current_user["_id"]

    title, content, file_storage = _parse_note_input()
    content = content or ""

    if not title or not title.strip():
        raise ValidationError("'title' is required")

    note_id = ObjectId()
    file_name = file_path = None
    extracted_text = ""
    if file_storage and file_storage.filename:
        file_info = _process_uploaded_file(file_storage, user_id, note_id)
        file_name = file_info["file_name"]
        file_path = file_info["file_path"]
        extracted_text = file_info["extracted_text"]

    full_text = "\n\n".join(t for t in [content, extracted_text] if t)
    chunks = build_chunks_with_embeddings(full_text)

    now = datetime.datetime.now(datetime.timezone.utc)
    note_doc = {
        "_id": note_id,
        "user_id": user_id,
        "title": title.strip(),
        "content": content,
        "extracted_text": extracted_text,
        "file_name": file_name,
        "file_path": file_path,
        "chunks": chunks,
        "created_at": now,
        "updated_at": now,
    }
    db.notes.insert_one(note_doc)
    return jsonify(_serialize_note(note_doc, include_content=True)), 201


@app.route("/notes", methods=["GET"])
@token_required
def list_notes():
    db = get_db()
    user_id = g.current_user["_id"]
    notes = db.notes.find({"user_id": user_id}).sort("created_at", -1)
    return jsonify({"notes": [_serialize_note(n) for n in notes]}), 200


@app.route("/notes/<note_id>", methods=["GET"])
@token_required
def get_note(note_id):
    note = _get_owned_note(note_id, g.current_user["_id"])
    return jsonify(_serialize_note(note, include_content=True)), 200


@app.route("/notes/<note_id>", methods=["PUT"])
@token_required
def update_note(note_id):
    db = get_db()
    user_id = g.current_user["_id"]
    note = _get_owned_note(note_id, user_id)

    title, content, file_storage = _parse_note_input()

    updates = {"updated_at": datetime.datetime.now(datetime.timezone.utc)}
    text_changed = False

    if title is not None:
        if not title.strip():
            raise ValidationError("'title' cannot be empty")
        updates["title"] = title.strip()

    if content is not None:
        updates["content"] = content
        text_changed = True

    if file_storage and file_storage.filename:
        old_file_path = note.get("file_path")
        file_info = _process_uploaded_file(file_storage, user_id, note["_id"])
        updates.update(file_info)
        text_changed = True
        _delete_file_if_exists(old_file_path)

    if text_changed:
        new_content = updates.get("content", note.get("content", ""))
        new_extracted = updates.get("extracted_text", note.get("extracted_text", ""))
        full_text = "\n\n".join(t for t in [new_content, new_extracted] if t)
        updates["chunks"] = build_chunks_with_embeddings(full_text)

    db.notes.update_one({"_id": note["_id"]}, {"$set": updates})
    note.update(updates)
    return jsonify(_serialize_note(note, include_content=True)), 200


@app.route("/notes/<note_id>", methods=["DELETE"])
@token_required
def delete_note(note_id):
    db = get_db()
    note = _get_owned_note(note_id, g.current_user["_id"])
    _delete_file_if_exists(note.get("file_path"))
    db.notes.delete_one({"_id": note["_id"]})
    return "", 204


@app.route("/notes/<note_id>/ask", methods=["POST"])
@token_required
def ask_note(note_id):
    note = _get_owned_note(note_id, g.current_user["_id"])

    payload = request.get_json(silent=True) or {}
    question = (payload.get("question") or "").strip()
    if not question:
        raise ValidationError("'question' is required")

    chunks = note.get("chunks") or []
    if not chunks:
        raise ValidationError("This note has no content yet to ask questions about")

    retrieved = retrieve_relevant_chunks(question, chunks)
    answer = generate_answer(question, retrieved)

    return (
        jsonify(
            {
                "question": question,
                "answer": answer,
                "sources": [
                    {
                        "chunk_index": chunk["chunk_index"],
                        "text": chunk["text"],
                        "similarity": round(score, 4),
                    }
                    for score, chunk in retrieved
                ],
            }
        ),
        200,
    )
