"""AICTE Security Deposit / FDR Portal: backend entry point.  Run:  python backend/app.py"""
import threading
import os
from flask import Flask
import config
from database import close_db
from seed import init_db
from services.scanner import scanner
from routes import auth, fdrs, workflow, dashboard, admin


def create_app():
    # Fail closed in production: the bundled demo key must never sign live sessions.
    if config.APP_ENV == "production" and (config.SECRET == "change-me-in-production" or len(config.SECRET) < 32 or "replace-with" in config.SECRET.lower() or "put-a-long" in config.SECRET.lower()):
        raise RuntimeError("Set a strong SECRET_KEY environment variable before production startup")
    app = Flask(__name__, static_folder=config.FRONTEND, static_url_path="")
    app.config["MAX_CONTENT_LENGTH"] = config.MAX_UPLOAD
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0   # browsers always re-check static files, so updates show immediately
    app.teardown_appcontext(close_db)
    for m in (auth, fdrs, workflow, dashboard, admin): app.register_blueprint(m.bp)

    @app.get("/")
    def index(): return app.send_static_file("index.html")

    @app.get("/api/health")
    def health():
        return {"status": "ok", "service": "aicte-fdr-portal"}, 200

    init_db(); threading.Thread(target=scanner, daemon=True).start()
    return app


app = create_app()
if __name__ == "__main__": app.run(host="0.0.0.0", port=config.PORT, debug=False)
