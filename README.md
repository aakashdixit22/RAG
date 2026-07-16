# Smart Notes RAG API

A Flask REST API for a note-taking app: JWT auth, notes CRUD, PDF/TXT upload with
text extraction, and a question-answering endpoint
Retrieval-Augmented Generation pipeline (chunking → embedding → cosine-similarity
retrieval → grounded generation)

## Tech stack

| Concern | Choice |
|---|---|
| Framework | Flask |
| Database | MongoDB (via `pymongo`) |
| Auth | JWT (`PyJWT`), passwords hashed with `bcrypt` |
| File parsing | `pypdf` for PDF, native decode for `.txt` |
| Embeddings | `sentence-transformers` (`all-MiniLM-L6-v2`), local, no API key |
| Generation | Google Gemini (`google-generativeai`) |
| Retrieval | In-memory cosine similarity (`numpy`) — no vector DB |

## Setup

1. **Python 3.10+** recommended.

   ```bash
   python -m venv venv
   source venv/bin/activate   # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Configure environment variables.**

   ```bash
   cp .env.example .env
   ```

   Fill in:
   - `MONGODB_URI` — a MongoDB Atlas connection string (or any reachable Mongo instance).
   - `GEMINI_API_KEY` — get one free at https://aistudio.google.com/apikey.
   - `JWT_SECRET_KEY` — any long random string.

   Everything else has a sensible default (see `.env.example`).

3. **Run the server.**

   ```bash
   python run.py
   ```

   (Not `python app.py` — `app.py` only *defines* the Flask app; `run.py` is the
   entrypoint that actually starts it. See the comment in `app.py` for why they're
   split — running `app.py` directly silently creates a second, unserved copy of
   the app that all the routes below `/health` end up registered on instead.)

   The API listens on `http://localhost:5000` by default. `GET /health` returns
   `{"status": "ok"}` once it's up.

# Testing the API in Postman — Step by Step

Walkthrough for the core flow: register/login, upload a file, then ask the AI a question grounded in that file.

## 0. Start the server

```
python run.py
```

Runs on `http://127.0.0.1:5000`. If a request that should work returns `404 Not Found`, check whether an old `python run.py` process is still running in the background and holding the port — kill it before starting a fresh one, otherwise your requests may randomly hit the stale process.

## 1. Register (first time) or Login (returning)

### Register — new account

```
POST http://127.0.0.1:5000/auth/register
Headers: Content-Type: application/json

Body (raw JSON):
{
  "email": "test@example.com",
  "password": "CorrectHorseBattery1"
}
```

Response `201`:
```json
{ "user": { "id": "...", "email": "test@example.com" }, "token": "eyJ..." }
```

Error cases: `400` if the email is invalid or the password is under 8 characters; `409` if that email is already registered — use Login instead in that case.

### Login — existing account

```
POST http://127.0.0.1:5000/auth/login
Headers: Content-Type: application/json

Body (raw JSON):
{
  "email": "test@example.com",
  "password": "CorrectHorseBattery1"
}
```

Response `200`:
```json
{ "user": { "id": "...", "email": "test@example.com" }, "token": "eyJ..." }
```

Error case: `401` on wrong email/password.

Either way, copy the `token` value — **without the surrounding quotes**.

## 2. Upload a file (create a note)

```
POST http://127.0.0.1:5000/notes
```

**Headers tab:**
| Key | Value |
|---|---|
| `Authorization` | `Bearer <paste token here, no quotes>` |

Don't set `Content-Type` manually — Postman adds the multipart boundary itself.

**Body tab → select `form-data`**, add two rows:

| Key | Type | Value |
|---|---|---|
| `title` | Text | any title you want, e.g. `My Resume` |
| `file` | File | click into Value, select a `.pdf` or `.txt` |

Common mistakes to avoid here:
- Each row has a Text/File type toggle hidden on the right of the Key column (visible on hover) — make sure `title`'s row is **Text** and `file`'s row is **File**. If you pick a file for the `title` row, the title text never gets sent and you'll get `400 'title' is required`.
- The file row's **Key must literally be `file`** (not `title`, not anything else) — the backend looks for `request.files.get("file")`. If the key is wrong, the note is created but with `"has_file": false` and `"chunk_count": 0` (file silently ignored).
- Make sure the row's checkbox (left side) is ticked, or Postman won't send that field at all.

Response `201` when done correctly:
```json
{
  "id": "6a50a03e9041401ecb69a103",
  "title": "My Resume",
  "file_name": "sample.txt",
  "has_file": true,
  "chunk_count": 1,
  "extracted_text": "...",
  ...
}
```

Copy the `id` — that's your `note_id` for the next step.

## 3. Ask a question grounded in the uploaded file

```
POST http://127.0.0.1:5000/notes/<note_id>/ask
Headers: Content-Type: application/json
         Authorization: Bearer <same token as step 2>

Body (raw JSON):
{
  "question": "What are the main causes of global warming?"
}
```

Response `200`:
```json
{
  "question": "What are the main causes of global warming?",
  "answer": "...",
  "sources": [
    { "chunk_index": 0, "text": "...", "similarity": 0.81 }
  ]
}
```

## 4. List all your notes

```
GET http://127.0.0.1:5000/notes
Headers: Authorization: Bearer <same token as step 2>
```

No body needed — in Postman just set the method dropdown to `GET`, paste the URL, and add the header.

Response `200` — newest first, each entry is a summary (a 200-char `preview` instead of full `content`/`extracted_text`):
```json
{
  "notes": [
    { "id": "6a50a03e9041401ecb69a103", "title": "My Resume", "file_name": "sample.txt", "has_file": true, "chunk_count": 1, "preview": "...", "created_at": "...", "updated_at": "..." }
  ]
}
```

## 5. Retrieve a single note

```
GET http://127.0.0.1:5000/notes/<note_id>
Headers: Authorization: Bearer <same token as step 2>
```

Response `200` — full detail this time, including `content` and `extracted_text` (not just the preview from step 4).

Error case: `404 "Note not found"` if the `note_id` doesn't exist, is malformed, or belongs to a different user — ownership is never revealed, it looks identical to a missing note.

## 6. Delete a note

```
DELETE http://127.0.0.1:5000/notes/<note_id>
Headers: Authorization: Bearer <same token as step 2>
```

Response `204 No Content` on success (also deletes the note's uploaded file from disk, if any). Same `404` error case as step 5 applies, and deleting an already-deleted note 404s too — it's not idempotent-200.

## Trade-off

- **Storage vs. retrieval speed**: embeddings are stored as a plain field in MongoDB instead of a dedicated vector DB — zero extra infrastructure to set up, but retrieval means fetching *every* chunk's embedding for a note and comparing it against the query one by one in Python (no index), which is fine at small scale but doesn't stay fast as chunk count grows into the thousands.
