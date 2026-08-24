from __future__ import annotations

import json
import os
import tempfile

from flask import Blueprint, after_this_request, flash, redirect, render_template, request, send_file, url_for

from extensions import db
from helpers import auditar, competencia_fechada, hist_faturamento, hist_folha, login_required, num, sincronizar_competencia
from models import Apuracao, Empresa
from motor.classificador_cnae import classificar_cnae
from motor.simples_avancado import calcular_apuracao, calcular_fator_r, calcular_fs12, calcular_rbt12
from servicos.relatorios import gerar_relatorio_pdf

bp = Blueprint("simples", __name__)

TIPOS_SEG = [
    ("normal", "Receita normal"),
    ("monofasico", "Monofásico"),
    ("icms_st", "ICMS-ST"),
    ("monofasico_icms_st", "Monofásico + ICMS-ST"),
    ("iss_retido", "ISS retido"),
    ("exportacao", "Exportação"),
    ("locacao_sem_iss", "Locação sem ISS"),
]


def _segmentos_form(form, anexo_padrao: str, cnae_padrao: str) -> list[dict]:
    tipos = form.getlist("seg_tipo[]")
    valores = form.getlist("seg_valor[]")
    anexos = form.getlist("seg_anexo[]")
    cnaes = form.getlist("seg_cnae[]")
    obs = form.getlist("seg_obs[]")
    segs = []
    for i, tipo in enumerate(tipos):
        valor = num(valores[i] if i < len(valores) else 0)
        if valor <= 0:
            continue
        segs.append({
            "tipo": tipo or "normal",
            "valor": valor,
            "anexo": (anexos[i] if i < len(anexos) and anexos[i] else anexo_padrao),
            "cnae": (cnaes[i] if i < len(cnaes) and cnaes[i] else cnae_padrao),
            "observacoes": (obs[i] if i < len(obs) else ""),
        })
    # Compatibilidade com V4
    if not segs:
        for chave, _ in TIPOS_SEG:
            valor = num(form.get(chave))
            if valor > 0:
                segs.append({"tipo": chave, "valor": valor, "anexo": anexo_padrao, "cnae": cnae_padrao})
    return segs


@bp.route("/simples", methods=["GET", "POST"])
@login_required
def motor():
    empresas = Empresa.query.order_by(Empresa.razao_social.asc()).all()
    resultado = None
    empresa_sel = None
    classificacao = None
    form_state = {}
    if request.method == "GET" and request.args.get("empresa_id"):
        try: empresa_sel = db.session.get(Empresa, int(request.args["empresa_id"]))
        except Exception: empresa_sel = None

    if request.method == "POST":
        form_state = request.form.to_dict(flat=False)
        try:
            empresa_id = request.form.get("empresa_id") or None
            if empresa_id:
                empresa_sel = db.get_or_404(Empresa, int(empresa_id))
            cnae = (request.form.get("cnae") or (empresa_sel.cnae_principal if empresa_sel else "") or "").strip()
            classificacao = classificar_cnae(cnae) if cnae else None
            anexo = request.form.get("anexo") or (
                classificacao.get("anexo") if classificacao and classificacao.get("classificacao_confiavel") else ""
            )
            if not anexo:
                raise ValueError("Selecione o Anexo aplicável. O CNAE sem validação tributária não é enquadrado automaticamente.")
            competencia = (request.form.get("competencia") or "").strip()
            if not competencia:
                raise ValueError("Informe a competência.")
            receita_mes = num(request.form.get("receita_mes"))
            if receita_mes < 0:
                raise ValueError("Faturamento não pode ser negativo.")

            rbt12_txt = (request.form.get("rbt12") or "").strip()
            if rbt12_txt:
                rbt12 = num(rbt12_txt)
            elif empresa_sel:
                rbt12 = calcular_rbt12(hist_faturamento(empresa_sel.id), competencia,
                                        data_abertura=empresa_sel.data_abertura, receita_pa=receita_mes)
            else:
                raise ValueError("Informe o RBT12 ou selecione uma empresa com histórico.")

            fs12_txt = (request.form.get("fs12") or "").strip()
            fs12 = num(fs12_txt) if fs12_txt else (
                calcular_fs12(hist_folha(empresa_sel.id), competencia, data_abertura=empresa_sel.data_abertura, folha_pa=0)
                if empresa_sel else 0
            )
            sujeito_fator_r = request.form.get("sujeito_fator_r") == "on"
            fator_r = calcular_fator_r(fs12, rbt12) if sujeito_fator_r else None
            segs = _segmentos_form(request.form, anexo, cnae)
            if not segs:
                segs = [{"tipo": "normal", "valor": receita_mes, "anexo": anexo, "cnae": cnae}]

            resultado = calcular_apuracao(
                anexo=anexo, rbt12=rbt12, receita_mes=receita_mes, segregacoes=segs,
                fs12=fs12, fator_r=fator_r, sujeito_fator_r=sujeito_fator_r,
                validar_total=True, competencia=competencia,
                retirar_icms_iss_sublimite=request.form.get("retirar_icms_iss_sublimite") == "on",
            )
            resultado["classificacao_cnae"] = classificacao or {}

            if empresa_sel and request.form.get("salvar") == "on":
                if competencia_fechada(empresa_sel.id, competencia):
                    raise ValueError("Competência fechada. Reabra antes de salvar nova apuração.")
                ap = Apuracao.query.filter_by(empresa_id=empresa_sel.id, competencia=competencia).first()
                if not ap:
                    ap = Apuracao(empresa_id=empresa_sel.id, competencia=competencia); db.session.add(ap)
                ap.anexo = resultado["anexo"]
                ap.rbt12 = resultado["rbt12"]
                ap.fs12 = resultado.get("fs12", 0)
                ap.fator_r = resultado.get("fator_r")
                ap.receita_mes = resultado["receita_mes"]
                ap.das_total = resultado["das_mensal"]
                ap.aliquota_efetiva = resultado["aliquota_efetiva"]
                ap.faixa = resultado["faixa"]
                ap.versao_regra = resultado.get("versao_regra")
                ap.resultado_json = json.dumps(resultado, ensure_ascii=False)
                db.session.flush()
                auditar("apuracao_simples", empresa_sel.id, "apuracao", ap.id,
                        {"competencia": competencia, "das": resultado["das_mensal"], "regra": ap.versao_regra})
                sincronizar_competencia(empresa_sel.id, competencia, rbt12=resultado["rbt12"], fs12=resultado.get("fs12", 0))
                db.session.commit()
                flash("Apuração do Simples salva no histórico.", "ok")
        except Exception as exc:
            db.session.rollback(); flash(str(exc), "erro")

    return render_template("simples_motor.html", empresas=empresas, resultado=resultado,
                           empresa_sel=empresa_sel, classificacao=classificacao,
                           tipos_seg=TIPOS_SEG, form_state=form_state)


@bp.route("/apuracao/<int:apuracao_id>")
@login_required
def resultado(apuracao_id: int):
    ap = db.get_or_404(Apuracao, apuracao_id)
    return render_template("resultado.html", ap=ap, emp=ap.empresa, resultado=json.loads(ap.resultado_json))


@bp.route("/apuracao/<int:apuracao_id>/pdf")
@login_required
def pdf(apuracao_id: int):
    ap = db.get_or_404(Apuracao, apuracao_id)
    resultado = json.loads(ap.resultado_json)
    fd, caminho = tempfile.mkstemp(prefix=f"jsm_simples_{ap.id}_", suffix=".pdf")
    os.close(fd)
    gerar_relatorio_pdf({"razao_social": ap.empresa.razao_social, "cnpj": ap.empresa.cnpj,
                         "cnae_principal": ap.empresa.cnae_principal}, ap.competencia, resultado, caminho)

    @after_this_request
    def cleanup(response):
        try:
            os.unlink(caminho)
        except OSError:
            pass
        return response

    return send_file(caminho, as_attachment=True, download_name=f"Relatorio_Simples_{ap.competencia}.pdf")
