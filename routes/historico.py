from __future__ import annotations

import csv
import io
import json

from flask import Blueprint, Response, render_template

from helpers import login_required
from models import Apuracao, CalculoRegime, ComparacaoTributaria

bp = Blueprint("historico", __name__)


@bp.route("/historico")
@login_required
def index():
    return render_template(
        "historico.html",
        simples=Apuracao.query.order_by(Apuracao.criado_em.desc()).limit(100).all(),
        outros=CalculoRegime.query.order_by(CalculoRegime.criado_em.desc()).limit(100).all(),
        comparacoes=ComparacaoTributaria.query.order_by(ComparacaoTributaria.criado_em.desc()).limit(100).all(),
    )


@bp.route("/historico.csv")
@login_required
def csv_export():
    sio = io.StringIO()
    w = csv.writer(sio, delimiter=";")
    w.writerow(["tipo", "empresa", "competencia", "regime", "total", "versao_regra", "data"])
    for x in Apuracao.query.order_by(Apuracao.criado_em.desc()).all():
        w.writerow(["apuracao", x.empresa.razao_social, x.competencia, "Simples Nacional", f"{x.das_total:.2f}", x.versao_regra or "", x.criado_em.isoformat()])
    for x in CalculoRegime.query.order_by(CalculoRegime.criado_em.desc()).all():
        try:
            versao = json.loads(x.resultado_json).get("versao_regra", "")
        except Exception:
            versao = ""
        w.writerow(["simulacao", x.empresa.razao_social if x.empresa else "Cálculo avulso", x.competencia or "", x.regime,
                    f"{x.total_estimado:.2f}", versao, x.criado_em.isoformat()])
    data = "\ufeff" + sio.getvalue()
    return Response(data, mimetype="text/csv; charset=utf-8",
                    headers={"Content-Disposition": "attachment; filename=historico_motor_tributario_jsm.csv"})
