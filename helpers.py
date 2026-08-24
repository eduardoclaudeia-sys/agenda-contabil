from __future__ import annotations

import json
from functools import wraps
from typing import Any, Callable

from flask import flash, redirect, request, session, url_for

from extensions import db
from models import AuditoriaV5, CompetenciaResumo, FechamentoCompetencia, Folha, Faturamento, UsuarioPapel


def numeros(v: Any) -> str:
    return "".join(c for c in str(v or "") if c.isdigit())


def num(v: Any) -> float:
    if v is None or v == "":
        return 0.0
    s = str(v).strip().replace("R$", "").replace(" ", "")
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    return float(s)


def login_required(view: Callable):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "usuario_id" not in session:
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view: Callable):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        papel = UsuarioPapel.query.filter_by(usuario_id=session["usuario_id"]).first()
        if papel and papel.papel != "admin":
            flash("Esta ação exige perfil de administrador.", "erro")
            return redirect(url_for("dashboard.index"))
        return view(*args, **kwargs)
    return wrapped


def hist_faturamento(emp_id: int) -> list[dict[str, Any]]:
    rows = Faturamento.query.filter_by(empresa_id=emp_id).order_by(Faturamento.competencia.asc()).all()
    return [
        {"competencia": x.competencia, "receita_interna": x.receita_interna, "receita_externa": x.receita_externa}
        for x in rows
    ]


def hist_folha(emp_id: int) -> list[dict[str, Any]]:
    rows = Folha.query.filter_by(empresa_id=emp_id).order_by(Folha.competencia.asc()).all()
    return [
        {
            "competencia": x.competencia,
            "salarios": x.salarios,
            "pro_labore": x.pro_labore,
            "encargos": x.encargos,
            "outros_fs12": x.outros_fs12,
        }
        for x in rows
    ]


def auditar(acao: str, empresa_id: int | None = None, registro_tipo: str | None = None,
            registro_id: int | None = None, detalhe: dict | str | None = None) -> None:
    if isinstance(detalhe, str):
        detalhe = {"mensagem": detalhe}
    db.session.add(AuditoriaV5(
        usuario_id=session.get("usuario_id"),
        empresa_id=empresa_id,
        acao=acao,
        registro_tipo=registro_tipo,
        registro_id=registro_id,
        detalhe_json=json.dumps(detalhe or {}, ensure_ascii=False),
        ip_origem=request.headers.get("X-Forwarded-For", request.remote_addr or "")[:64],
    ))


def competencia_fechada(empresa_id: int, competencia: str) -> bool:
    row = FechamentoCompetencia.query.filter_by(empresa_id=empresa_id, competencia=competencia).first()
    return bool(row and row.fechado)


def moeda(v: Any) -> str:
    return f"R$ {float(v or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def pct(v: Any) -> str:
    return f"{float(v or 0):,.2f}%".replace(",", "X").replace(".", ",").replace("X", ".")


def cnpjfmt(v: Any) -> str:
    n = numeros(v)
    if len(n) != 14:
        return str(v or "")
    return f"{n[:2]}.{n[2:5]}.{n[5:8]}/{n[8:12]}-{n[12:]}"


def sincronizar_competencia(empresa_id: int, competencia: str, *, rbt12: float | None = None, fs12: float | None = None) -> CompetenciaResumo:
    """Atualiza o resumo relacional da competência sem apagar o histórico original."""
    row = CompetenciaResumo.query.filter_by(empresa_id=empresa_id, ano_mes=competencia).first()
    if not row:
        row = CompetenciaResumo(empresa_id=empresa_id, ano_mes=competencia)
        db.session.add(row)
    fat = Faturamento.query.filter_by(empresa_id=empresa_id, competencia=competencia).first()
    folha = Folha.query.filter_by(empresa_id=empresa_id, competencia=competencia).first()
    row.faturamento_bruto = (float(fat.receita_interna or 0) + float(fat.receita_externa or 0)) if fat else 0.0
    row.folha_pagamento = (float(folha.salarios or 0) + float(folha.pro_labore or 0) + float(folha.encargos or 0) + float(folha.outros_fs12 or 0)) if folha else 0.0
    if rbt12 is not None: row.rbt12 = float(rbt12)
    if fs12 is not None: row.fs12 = float(fs12)
    fechamento = FechamentoCompetencia.query.filter_by(empresa_id=empresa_id, competencia=competencia).first()
    row.status = "FECHADA" if fechamento and fechamento.fechado else "ABERTA"
    return row
