from __future__ import annotations

import json
import os
import tempfile

from flask import Blueprint, after_this_request, flash, render_template, request, send_file

from extensions import db
from helpers import auditar, login_required, num
from models import CalculoRegime, Empresa
from motor.lucro_real import calcular_lucro_real
from servicos.relatorios import gerar_relatorio_regime_pdf

bp = Blueprint("real", __name__)


def _lancamentos(form):
    naturezas = form.getlist("ajuste_natureza[]")
    descricoes = form.getlist("ajuste_descricao[]")
    valores = form.getlist("ajuste_valor[]")
    fundamentos = form.getlist("ajuste_fundamento[]")
    out = []
    for i, natureza in enumerate(naturezas):
        valor = num(valores[i] if i < len(valores) else 0)
        if valor > 0:
            out.append({"natureza": natureza, "descricao": descricoes[i] if i < len(descricoes) else "",
                        "valor": valor, "fundamento": fundamentos[i] if i < len(fundamentos) else ""})
    return out


def _creditos(form):
    descricoes = form.getlist("credito_descricao[]")
    pis = form.getlist("credito_pis[]")
    cof = form.getlist("credito_cofins[]")
    out = []
    for i, desc in enumerate(descricoes):
        vp, vc = num(pis[i] if i < len(pis) else 0), num(cof[i] if i < len(cof) else 0)
        if vp > 0 or vc > 0:
            out.append({"descricao": desc, "credito_pis": vp, "credito_cofins": vc})
    return out


@bp.route("/lucro-real", methods=["GET", "POST"])
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
            resultado = calcular_lucro_real(
                receita_periodo=num(request.form.get("receita_periodo")),
                lucro_contabil=num(request.form.get("lucro_contabil")),
                meses_periodo=int(request.form.get("meses_periodo") or 3),
                adicoes_irpj=num(request.form.get("adicoes_irpj")),
                exclusoes_irpj=num(request.form.get("exclusoes_irpj")),
                prejuizo_fiscal_disponivel=num(request.form.get("prejuizo_fiscal_disponivel")),
                adicoes_csll=num(request.form.get("adicoes_csll")),
                exclusoes_csll=num(request.form.get("exclusoes_csll")),
                base_negativa_csll_disponivel=num(request.form.get("base_negativa_csll_disponivel")),
                receita_pis_cofins=num(request.form.get("receita_pis_cofins")) if request.form.get("receita_pis_cofins") else None,
                creditos_pis=num(request.form.get("creditos_pis")),
                creditos_cofins=num(request.form.get("creditos_cofins")),
                aliquota_csll=num(request.form.get("aliquota_csll")) / 100 if request.form.get("aliquota_csll") else None,
                aliquota_pis=num(request.form.get("aliquota_pis")) / 100 if request.form.get("aliquota_pis") else None,
                aliquota_cofins=num(request.form.get("aliquota_cofins")) / 100 if request.form.get("aliquota_cofins") else None,
                icms_estimado=num(request.form.get("icms_estimado")), iss_estimado=num(request.form.get("iss_estimado")),
                cpp_estimada=num(request.form.get("cpp_estimada")),
                lancamentos_ajustes=_lancamentos(request.form), creditos_detalhados=_creditos(request.form),
            )
            empresa_id = request.form.get("empresa_id") or None
            if request.form.get("salvar") == "on":
                row = CalculoRegime(
                    empresa_id=int(empresa_id) if empresa_id else None,
                    regime="Lucro Real", competencia=(request.form.get("competencia") or "").strip(),
                    dados_json=json.dumps(request.form.to_dict(flat=False), ensure_ascii=False),
                    resultado_json=json.dumps(resultado, ensure_ascii=False), total_estimado=resultado["total_periodo"],
                )
                db.session.add(row); db.session.flush(); calculo_id = row.id
                auditar("calculo_real", int(empresa_id) if empresa_id else None, "calculo_regime", row.id,
                        {"total": row.total_estimado, "regra": resultado.get("versao_regra")})
                db.session.commit(); flash("Simulação do Lucro Real salva.", "ok")
        except Exception as exc:
            db.session.rollback(); flash(str(exc), "erro")
    return render_template("lucro_real_motor.html", empresas=empresas, resultado=resultado, calculo_id=calculo_id, empresa_sel=empresa_sel)


@bp.route("/lucro-real/<int:calculo_id>/pdf")
@login_required
def pdf(calculo_id: int):
    row = db.get_or_404(CalculoRegime, calculo_id)
    if row.regime != "Lucro Real":
        raise ValueError("Cálculo não pertence ao Lucro Real.")
    resultado = json.loads(row.resultado_json)
    empresa = {"razao_social": row.empresa.razao_social if row.empresa else "Cálculo avulso", "cnpj": row.empresa.cnpj if row.empresa else ""}
    fd, caminho = tempfile.mkstemp(prefix="jsm_lr_", suffix=".pdf"); os.close(fd)
    gerar_relatorio_regime_pdf("Lucro Real", empresa, row.competencia or "", resultado, caminho)
    @after_this_request
    def cleanup(response):
        try: os.unlink(caminho)
        except OSError: pass
        return response
    return send_file(caminho, as_attachment=True, download_name=f"Relatorio_Lucro_Real_{row.id}.pdf")
