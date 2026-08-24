from __future__ import annotations

import os
from datetime import timedelta


class Config:
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 20 * 1024 * 1024
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)
    WTF_CSRF_TIME_LIMIT = None

    @classmethod
    def apply(cls, app) -> None:
        is_render = bool(os.environ.get("RENDER"))
        secret = os.environ.get("SECRET_KEY")
        database_url = os.environ.get("DATABASE_URL")

        if is_render and not secret:
            raise RuntimeError("SECRET_KEY é obrigatória em produção.")
        if is_render and not database_url:
            raise RuntimeError("DATABASE_URL é obrigatória em produção. Use PostgreSQL/Supabase.")

        app.config.from_object(cls)
        app.config["SECRET_KEY"] = secret or "dev-local-altere-esta-chave"
        app.config["SESSION_COOKIE_SECURE"] = is_render
        app.config["SQLALCHEMY_DATABASE_URI"] = (
            (database_url or "sqlite:///motor_tributario_v5_local.db")
            .replace("postgres://", "postgresql://", 1)
        )
        app.config["RATELIMIT_STORAGE_URI"] = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")
