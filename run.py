"""Entrypoint: `python run.py` starts the dev server.

Kept separate from app.py so app.py is only ever imported (never executed
directly as a script) — see the comment above the route imports in app.py
for why that distinction matters.
"""

import os

from app import app

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=os.environ.get("FLASK_DEBUG", "0") == "1",
    )
