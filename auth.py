"""JWT issuing/verification and the `@token_required` route decorator."""

import datetime
from functools import wraps

import jwt
from bson import ObjectId
from bson.errors import InvalidId
from flask import g, request

from config import Config
from errors import AuthError
from extensions import get_db


def generate_token(user_id, email):
    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        "user_id": str(user_id),
        "email": email,
        "iat": now,
        "exp": now + datetime.timedelta(hours=Config.JWT_EXPIRES_HOURS),
    }
    return jwt.encode(payload, Config.JWT_SECRET_KEY, algorithm="HS256")


def decode_token(token):
    try:
        return jwt.decode(token, Config.JWT_SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise AuthError("Token has expired")
    except jwt.InvalidTokenError:
        raise AuthError("Invalid authentication token")


def token_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            raise AuthError("Missing or malformed Authorization header. Expected: Bearer <token>")

        token = auth_header.split(" ", 1)[1].strip()
        payload = decode_token(token)

        try:
            user_oid = ObjectId(payload["user_id"])
        except (InvalidId, TypeError, KeyError):
            raise AuthError("Invalid authentication token")

        user = get_db().users.find_one({"_id": user_oid})
        if not user:
            raise AuthError("User for this token no longer exists")

        g.current_user = user
        return view_func(*args, **kwargs)

    return wrapper
