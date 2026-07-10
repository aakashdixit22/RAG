import os

from flask import Flask, jsonify

from config import Config
from errors import register_error_handlers

app = Flask(__name__)
app.config.from_object(Config)

os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)

register_error_handlers(app)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


# Imported after `app` is created because these modules register routes onto
# it via `@app.route` decorators (and themselves do `from app import app`) —
# importing any earlier would be a circular import.
from routes import auth_routes, notes_routes  # noqa: E402,F401


