from __future__ import annotations

from flask import Blueprint, render_template

from helpers import login_required
from models import Apuracao, CalculoRegime, ComparacaoTributaria, Empresa

bp = Blueprint("dashboard", __name__)


@bp.route("/")
@login_required
def index():
    return render_template(
        "dashboard.html",
        empresas=Empresa.query.count(),
        simples_count=Apuracao.query.count(),
        outros_count=CalculoRegime.query.count(),
        comparacoes=ComparacaoTributaria.query.count(),
        recentes_simples=Apuracao.query.order_by(Apuracao.criado_em.desc()).limit(4).all(),
        recentes_outros=CalculoRegime.query.order_by(CalculoRegime.criado_em.desc()).limit(4).all(),
        empresas_recentes=Empresa.query.order_by(Empresa.atualizado_em.desc()).limit(5).all(),
    )


@bp.route("/gestao")
@login_required
def gestao():
    return render_template(
        "gestao.html",
        empresas=Empresa.query.count(),
        apuracoes=Apuracao.query.count(),
        calculos=CalculoRegime.query.count(),
        comparacoes=ComparacaoTributaria.query.count(),
        recentes=Apuracao.query.order_by(Apuracao.criado_em.desc()).limit(8).all(),
    )
