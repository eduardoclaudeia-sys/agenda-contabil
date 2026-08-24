from __future__ import annotations

import json

from flask import Blueprint, flash, render_template, request, session

from extensions import db
from helpers import auditar, hist_faturamento, hist_folha, login_required, num
from models import ComparacaoTributaria, Empresa
from motor.lucro_presumido import calcular_lucro_presumido_misto_2026
from motor.lucro_real import calcular_lucro_real
from motor.simples_avancado import calcular_apuracao, calcular_fator_r, calcular_fs12, calcular_rbt12

bp = Blueprint("comparador", __name__)


def _item(nome: str, total: float, mensal: float, carga: float, disponivel=True, motivo="", detalhe=None):
    return {"nome": nome, "total": total, "mensal": mensal, "anual": mensal * 12,
            "carga": carga, "disponivel": disponivel, "motivo": motivo, "detalhe": detalhe or {}}


@bp.route("/comparador", methods=["GET", "POST"])
@login_required
def index():
    empresas = Empresa.query.order_by(Empresa.razao_social.asc()).all()
    resultado = None
    if request.method == "POST":
        try:
            empresa = None
            if request.form.get("empresa_id"):
                empresa = db.get_or_404(Empresa, int(request.form["empresa_id"]))
            comp = (request.form.get("competencia") or "2026-01").strip()
            receita_mensal = num(request.form.get("receita_mensal"))
            if receita_mensal <= 0:
                raise ValueError("Informe uma receita mensal maior que zero para comparar os cenários.")

            cenarios = []
            avisos = []

            # SIMPLES
            try:
                rbt12 = num(request.form.get("rbt12"))
                if not rbt12 and empresa:
                    rbt12 = calcular_rbt12(hist_faturamento(empresa.id), comp, data_abertura=empresa.data_abertura, receita_pa=receita_mensal)
                fs12 = num(request.form.get("fs12"))
                if not fs12 and empresa:
                    fs12 = calcular_fs12(hist_folha(empresa.id), comp, data_abertura=empresa.data_abertura, folha_pa=0)
                sujeito = request.form.get("sujeito_fator_r") == "on"
                fator = calcular_fator_r(fs12, rbt12) if sujeito else None
                anexo = request.form.get("anexo") or "Anexo I"
                sn = calcular_apuracao(anexo=anexo, rbt12=rbt12, receita_mes=receita_mensal,
                                      segregacoes=[{"tipo": "normal", "valor": receita_mensal, "anexo": anexo}],
                                      fs12=fs12, fator_r=fator, sujeito_fator_r=sujeito,
                                      competencia=comp)
                cenarios.append(_item("Simples Nacional", sn["das_mensal"], sn["das_mensal"], sn["carga_efetiva_final"], detalhe=sn))
            except Exception as exc:
                cenarios.append(_item("Simples Nacional", 0, 0, 0, False, str(exc)))

            # PRESUMIDO — comparação simplificada com uma atividade escolhida.
            try:
                lp = calcular_lucro_presumido_misto_2026(
                    atividades=[{"tipo": request.form.get("tipo_atividade", "comercio"), "receita": receita_mensal * 3}],
                    trimestre=int(request.form.get("trimestre") or 1),
                    receitas_financeiras=num(request.form.get("lp_receitas_financeiras")),
                    ganhos_capital=num(request.form.get("lp_ganhos_capital")),
                    aliquota_iss=num(request.form.get("lp_iss")) / 100,
                    aliquota_icms=num(request.form.get("lp_icms")) / 100,
                    cpp_trimestre=num(request.form.get("lp_cpp")),
                )
                cenarios.append(_item("Lucro Presumido", lp["total_trimestre"], lp["media_mensal"], lp["carga_efetiva"], detalhe=lp))
            except Exception as exc:
                cenarios.append(_item("Lucro Presumido", 0, 0, 0, False, str(exc)))

            # REAL — só entra quando o usuário confirma dados contábeis suficientes.
            if request.form.get("incluir_real") == "on" and request.form.get("lucro_contabil") not in (None, ""):
                try:
                    meses = int(request.form.get("real_meses") or 3)
                    lr = calcular_lucro_real(
                        receita_periodo=num(request.form.get("real_receita")) or receita_mensal * meses,
                        lucro_contabil=num(request.form.get("lucro_contabil")),
                        meses_periodo=meses,
                        adicoes_irpj=num(request.form.get("real_adicoes_irpj")),
                        exclusoes_irpj=num(request.form.get("real_exclusoes_irpj")),
                        prejuizo_fiscal_disponivel=num(request.form.get("real_prejuizo")),
                        adicoes_csll=num(request.form.get("real_adicoes_csll")),
                        exclusoes_csll=num(request.form.get("real_exclusoes_csll")),
                        base_negativa_csll_disponivel=num(request.form.get("real_base_negativa")),
                        creditos_pis=num(request.form.get("real_creditos_pis")),
                        creditos_cofins=num(request.form.get("real_creditos_cofins")),
                        icms_estimado=num(request.form.get("real_icms")), iss_estimado=num(request.form.get("real_iss")),
                        cpp_estimada=num(request.form.get("real_cpp")),
                    )
                    mensal_lr = lr["total_periodo"] / meses
                    cenarios.append(_item("Lucro Real", lr["total_periodo"], mensal_lr, lr["carga_efetiva"], detalhe=lr))
                except Exception as exc:
                    cenarios.append(_item("Lucro Real", 0, 0, 0, False, str(exc)))
            else:
                cenarios.append(_item("Lucro Real", 0, 0, 0, False,
                                      "Dados contábeis insuficientes ou módulo não marcado para comparação."))

            validos = [c for c in cenarios if c["disponivel"]]
            melhor = min(validos, key=lambda x: x["mensal"]) if validos else None
            pior = max(validos, key=lambda x: x["mensal"]) if validos else None
            economia_mensal = (pior["mensal"] - melhor["mensal"]) if melhor and pior else 0
            qualidade = "ALTA" if len(validos) == 3 else "MÉDIA" if len(validos) == 2 else "BAIXA"
            if len(validos) < 3:
                avisos.append("Nem todos os regimes puderam ser comparados com qualidade equivalente. Veja os motivos em cada card.")
            avisos.append("O comparador apresenta cenários estimados; não constitui recomendação automática de enquadramento tributário.")
            resultado = {
                "empresa": empresa.razao_social if empresa else "Cálculo avulso", "competencia": comp,
                "receita_mensal": receita_mensal, "cenarios": cenarios, "melhor": melhor,
                "economia_mensal": economia_mensal, "economia_anual": economia_mensal * 12,
                "qualidade": qualidade, "avisos": avisos,
            }

            if request.form.get("salvar") == "on":
                row = ComparacaoTributaria(
                    empresa_id=empresa.id if empresa else None, competencia=comp,
                    dados_json=json.dumps(request.form.to_dict(flat=False), ensure_ascii=False),
                    resultado_json=json.dumps(resultado, ensure_ascii=False), criado_por=session.get("usuario_id"),
                )
                db.session.add(row); db.session.flush()
                auditar("comparacao_tributaria", empresa.id if empresa else None, "comparacao", row.id,
                        {"qualidade": qualidade, "melhor": melhor["nome"] if melhor else None})
                db.session.commit(); flash("Comparação salva no histórico.", "ok")
        except Exception as exc:
            db.session.rollback(); flash(str(exc), "erro")
    return render_template("comparador.html", empresas=empresas, resultado=resultado)
