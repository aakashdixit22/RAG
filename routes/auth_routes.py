import datetime

import bcrypt
from flask import jsonify, request

from app import app
from auth import generate_token
from errors import AuthError, ConflictError, ValidationError
from extensions import get_db


def _valid_email(email):
    return bool(email) and "@" in email and "." in email.split("@")[-1]


@app.route("/auth/register", methods=["POST"])
def register():
    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""

    if not _valid_email(email):
        raise ValidationError("A valid 'email' is required")
    if len(password) < 8:
        raise ValidationError("'password' must be at least 8 characters long")

    db = get_db()
    if db.users.find_one({"email": email}):
        raise ConflictError("An account with this email already exists")

    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    now = datetime.datetime.now(datetime.timezone.utc)
    result = db.users.insert_one(
        {"email": email, "password_hash": password_hash, "created_at": now}
    )

    token = generate_token(result.inserted_id, email)
    return (
        jsonify({"user": {"id": str(result.inserted_id), "email": email}, "token": token}),
        201,
    )


@app.route("/auth/login", methods=["POST"])
def login():
    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""

    if not email or not password:
        raise ValidationError("'email' and 'password' are required")

    db = get_db()
    user = db.users.find_one({"email": email})
    if not user or not bcrypt.checkpw(password.encode("utf-8"), user["password_hash"]):
        raise AuthError("Invalid email or password")

    token = generate_token(user["_id"], user["email"])
    return jsonify({"user": {"id": str(user["_id"]), "email": user["email"]}, "token": token}), 200
