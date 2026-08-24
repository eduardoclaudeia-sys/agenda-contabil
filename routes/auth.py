from __future__ import annotations

import os
import secrets

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db, limiter
from models import Usuario, UsuarioPapel

bp = Blueprint("auth", __name__)


def _senha_forte(senha: str) -> bool:
    return len(senha) >= 8 and any(c.isalpha() for c in senha) and any(c.isdigit() for c in senha)


@bp.route("/setup", methods=["GET", "POST"])
@limiter.limit("5 per 15 minutes", methods=["POST"])
def setup():
    if Usuario.query.count() > 0:
        return redirect(url_for("auth.login"))
    token_esperado = os.environ.get("SETUP_TOKEN", "")
    if not token_esperado:
        return render_template("setup_bloqueado.html"), 503

    if request.method == "POST":
        token = request.form.get("setup_token", "")
        senha = request.form.get("senha", "")
        if not secrets.compare_digest(token, token_esperado):
            flash("Código de primeiro acesso incorreto.", "erro")
        elif senha != request.form.get("confirmar", ""):
            flash("As senhas não coincidem.", "erro")
        elif not _senha_forte(senha):
            flash("Use pelo menos 8 caracteres, contendo letras e números.", "erro")
        else:
            u = Usuario(
                nome=request.form.get("nome", "").strip() or "Administrador",
                usuario=request.form.get("usuario", "").strip(),
                senha_hash=generate_password_hash(senha),
            )
            if not u.usuario:
                flash("Informe o usuário.", "erro")
                return render_template("setup.html")
            db.session.add(u)
            db.session.flush()
            db.session.add(UsuarioPapel(usuario_id=u.id, papel="admin"))
            db.session.commit()
            flash("Administrador criado. Faça login.", "ok")
            return redirect(url_for("auth.login"))
    return render_template("setup.html")


@bp.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per 5 minutes", methods=["POST"])
def login():
    if Usuario.query.count() == 0:
        return redirect(url_for("auth.setup"))
    if request.method == "POST":
        usuario = request.form.get("usuario", "").strip()
        u = Usuario.query.filter_by(usuario=usuario).first()
        if u and check_password_hash(u.senha_hash, request.form.get("senha", "")):
            session.clear()
            session.permanent = True
            session["usuario_id"] = u.id
            session["usuario_nome"] = u.nome
            papel = UsuarioPapel.query.filter_by(usuario_id=u.id).first()
            session["papel"] = papel.papel if papel else "admin"
            return redirect(url_for("dashboard.index"))
        flash("Usuário ou senha inválidos.", "erro")
    return render_template("login.html")


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
