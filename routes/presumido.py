from __future__ import annotations

import json
import os
import tempfile

from flask import Blueprint, after_this_request, flash, render_template, request, send_file

from extensions import db
from helpers import auditar, login_required, num
from models import CalculoRegime, Empresa
from motor.lucro_presumido import calcular_lucro_presumido_misto_2026
from servicos.relatorios import gerar_relatorio_regime_pdf

bp = Blueprint("presumido", __name__)

ATIVIDADES = [
    ("comercio", "Comércio"), ("industria", "Indústria"),
    ("servico", "Prestação de serviços"), ("combustivel", "Revenda de combustíveis"),
]


def _atividades(form):
    tipos = form.getlist("atividade_tipo[]")
    receitas = form.getlist("atividade_receita[]")
    itens = []
    for i, tipo in enumerate(tipos):
        valor = num(receitas[i] if i < len(receitas) else 0)
        if valor > 0:
            itens.append({"tipo": tipo, "receita": valor})
    if not itens and num(form.get("receita_trimestre")) > 0:
        itens = [{"tipo": form.get("tipo_atividade", "comercio"), "receita": num(form.get("receita_trimestre"))}]
    return itens


@bp.route("/lucro-presumido", methods=["GET", "POST"])
@login_required
def motor():
    empresas = Empresa.query.order_by(Empresa.razao_social.asc()).all()
    resultado = None
    calculo_id = None
    empresa_sel = None
    if request.method == "GET" and request.args.get("empresa_id"):
        try: empresa_sel = db.session.get(Empresa, int(request.args["empresa_id"]))
        except Exception: empresa_sel = None
    if request.method == "POST":
        try:
            atividades = _atividades(request.form)
            if not atividades:
                raise ValueError("Informe pelo menos uma receita operacional.")
            tri = int(request.form.get("trimestre") or 1)
            resultado = calcular_lucro_presumido_misto_2026(
                atividades=atividades,
                trimestre=tri,
                receitas_financeiras=num(request.form.get("receitas_financeiras")),
                ganhos_capital=num(request.form.get("ganhos_capital")),
                outras_receitas_integrais=num(request.form.get("outras_receitas_integrais")),
                aliquota_iss=num(request.form.get("aliquota_iss")) / 100,
                aliquota_icms=num(request.form.get("aliquota_icms")) / 100,
                cpp_trimestre=num(request.form.get("cpp_trimestre")),
            )
            empresa_id = request.form.get("empresa_id") or None
            if request.form.get("salvar") == "on":
                row = CalculoRegime(
                    empresa_id=int(empresa_id) if empresa_id else None,
                    regime="Lucro Presumido", competencia=f"2026-T{tri}",
                    dados_json=json.dumps(request.form.to_dict(flat=False), ensure_ascii=False),
                    resultado_json=json.dumps(resultado, ensure_ascii=False), total_estimado=resultado["total_trimestre"],
                )
                db.session.add(row); db.session.flush(); calculo_id = row.id
                auditar("calculo_presumido", int(empresa_id) if empresa_id else None, "calculo_regime", row.id,
                        {"total": row.total_estimado, "regra": resultado.get("versao_regra")})
                db.session.commit(); flash("Simulação do Lucro Presumido salva.", "ok")
        except Exception as exc:
            db.session.rollback(); flash(str(exc), "erro")
    return render_template("presumido_motor.html", empresas=empresas, resultado=resultado,
                           atividades_opcoes=ATIVIDADES, calculo_id=calculo_id, empresa_sel=empresa_sel)


@bp.route("/lucro-presumido/<int:calculo_id>/pdf")
@login_required
def pdf(calculo_id: int):
    row = db.get_or_404(CalculoRegime, calculo_id)
    if row.regime != "Lucro Presumido":
        raise ValueError("Cálculo não pertence ao Lucro Presumido.")
    resultado = json.loads(row.resultado_json)
    empresa = {"razao_social": row.empresa.razao_social if row.empresa else "Cálculo avulso",
               "cnpj": row.empresa.cnpj if row.empresa else ""}
    fd, caminho = tempfile.mkstemp(prefix="jsm_lp_", suffix=".pdf"); os.close(fd)
    gerar_relatorio_regime_pdf("Lucro Presumido", empresa, row.competencia or "", resultado, caminho)
    @after_this_request
    def cleanup(response):
        try: os.unlink(caminho)
        except OSError: pass
        return response
    return send_file(caminho, as_attachment=True, download_name=f"Relatorio_Lucro_Presumido_{row.id}.pdf")
