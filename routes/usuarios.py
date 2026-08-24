from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for
from werkzeug.security import generate_password_hash

from extensions import db
from helpers import admin_required, auditar
from models import Usuario, UsuarioPapel

bp = Blueprint("usuarios", __name__, url_prefix="/usuarios")


@bp.route("/", methods=["GET", "POST"])
@admin_required
def index():
    if request.method == "POST":
        usuario = request.form.get("usuario", "").strip()
        senha = request.form.get("senha", "")
        papel = request.form.get("papel", "operador")
        if papel not in {"admin", "operador"}:
            papel = "operador"
        if len(senha) < 8 or not any(c.isalpha() for c in senha) or not any(c.isdigit() for c in senha):
            flash("A senha deve ter pelo menos 8 caracteres, letras e números.", "erro")
        elif not usuario:
            flash("Informe o usuário.", "erro")
        elif Usuario.query.filter_by(usuario=usuario).first():
            flash("Esse usuário já existe.", "erro")
        else:
            u = Usuario(nome=request.form.get("nome", "").strip() or usuario, usuario=usuario,
                        senha_hash=generate_password_hash(senha))
            db.session.add(u)
            db.session.flush()
            db.session.add(UsuarioPapel(usuario_id=u.id, papel=papel))
            auditar("criar_usuario", registro_tipo="usuario", registro_id=u.id, detalhe={"papel": papel})
            db.session.commit()
            flash("Usuário criado.", "ok")
            return redirect(url_for("usuarios.index"))
    return render_template("usuarios.html", usuarios=Usuario.query.order_by(Usuario.nome.asc()).all())
