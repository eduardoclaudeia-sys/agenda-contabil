"""Simulador gerencial de Lucro Real — V5.

O motor parte do lucro contábil, permite ajustes agregados ou lançamentos
individualizados, aplica a trava geral de compensação parametrizada, calcula
IRPJ/adicional/CSLL e PIS/Cofins não cumulativos com créditos informados.

Não decide a dedutibilidade/tributabilidade de ajustes nem a elegibilidade de
créditos. Esses fatos dependem da escrituração e da validação profissional.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGRAS_DIR = os.path.join(BASE_DIR, "regras", "real")
INDICE = os.path.join(REGRAS_DIR, "indice.json")
REGRA_2026 = os.path.join(REGRAS_DIR, "2026.01.json")



@lru_cache(maxsize=16)
def carregar_regra_por_data(data_ref: str = "2026-01-01") -> dict[str, Any]:
    """Seleciona arquivo versionado pela vigência declarada no índice."""
    from datetime import date
    ref = date.fromisoformat((str(data_ref)[:10] if data_ref else "2026-01-01"))
    with open(INDICE, encoding="utf-8") as f:
        indice = json.load(f)
    candidatos=[]
    for item in indice.get("versoes", []):
        ini=date.fromisoformat(item["vigencia_inicio"])
        fim=date.fromisoformat(item["vigencia_fim"]) if item.get("vigencia_fim") else None
        if ini <= ref and (fim is None or ref <= fim): candidatos.append(item)
    if not candidatos:
        raise ValueError(f"Não há regra parametrizada para {ref.isoformat()}.")
    candidatos.sort(key=lambda x:x["vigencia_inicio"], reverse=True)
    arquivo=candidatos[0]["arquivo"]
    with open(os.path.join(REGRAS_DIR, arquivo), encoding="utf-8") as f:
        return json.load(f)

@lru_cache(maxsize=8)
def carregar_regra_2026() -> dict[str, Any]:
    return carregar_regra_por_data("2026-01-01")


def _n(v: Any) -> float:
    return float(v or 0)


def _soma_lancamentos(lancamentos: list[dict[str, Any]] | None, natureza: str) -> float:
    return sum(max(_n(x.get("valor")), 0) for x in (lancamentos or []) if x.get("natureza") == natureza)


def calcular_lucro_real(
    receita_periodo: float,
    lucro_contabil: float,
    meses_periodo: int = 3,
    adicoes_irpj: float = 0,
    exclusoes_irpj: float = 0,
    prejuizo_fiscal_disponivel: float = 0,
    adicoes_csll: float = 0,
    exclusoes_csll: float = 0,
    base_negativa_csll_disponivel: float = 0,
    receita_pis_cofins: float | None = None,
    creditos_pis: float = 0,
    creditos_cofins: float = 0,
    aliquota_csll: float | None = None,
    aliquota_pis: float | None = None,
    aliquota_cofins: float | None = None,
    icms_estimado: float = 0,
    iss_estimado: float = 0,
    cpp_estimada: float = 0,
    lancamentos_ajustes: list[dict[str, Any]] | None = None,
    creditos_detalhados: list[dict[str, Any]] | None = None,
    limite_compensacao: float | None = None,
) -> dict[str, Any]:
    regra = carregar_regra_2026()
    receita = _n(receita_periodo)
    lucro = _n(lucro_contabil)
    meses = int(meses_periodo or 3)
    if meses < 1:
        raise ValueError("O período deve possuir pelo menos 1 mês.")
    if receita < 0:
        raise ValueError("A receita não pode ser negativa.")

    # Lançamentos detalhados complementam os totais agregados.
    ad_ir = _n(adicoes_irpj) + _soma_lancamentos(lancamentos_ajustes, "adicao_irpj")
    ex_ir = _n(exclusoes_irpj) + _soma_lancamentos(lancamentos_ajustes, "exclusao_irpj")
    ad_cs = _n(adicoes_csll) + _soma_lancamentos(lancamentos_ajustes, "adicao_csll")
    ex_cs = _n(exclusoes_csll) + _soma_lancamentos(lancamentos_ajustes, "exclusao_csll")

    limite_comp = float(regra["compensacao"]["limite_padrao"] if limite_compensacao is None else limite_compensacao)
    if not 0 <= limite_comp <= 1:
        raise ValueError("O limite de compensação deve estar entre 0 e 1.")

    lucro_aj_irpj_antes_comp = max(lucro + ad_ir - ex_ir, 0.0)
    limite_comp_irpj = lucro_aj_irpj_antes_comp * limite_comp
    compensacao_irpj = min(max(_n(prejuizo_fiscal_disponivel), 0), limite_comp_irpj)
    base_irpj = max(lucro_aj_irpj_antes_comp - compensacao_irpj, 0)

    aliq_irpj = float(regra["irpj"]["aliquota"])
    aliq_adicional = float(regra["irpj"]["adicional"])
    irpj = base_irpj * aliq_irpj
    limite_adicional = float(regra["irpj"]["limite_adicional_mes"]) * meses
    adicional_irpj = max(base_irpj - limite_adicional, 0) * aliq_adicional

    lucro_aj_csll_antes_comp = max(lucro + ad_cs - ex_cs, 0.0)
    limite_comp_csll = lucro_aj_csll_antes_comp * limite_comp
    compensacao_csll = min(max(_n(base_negativa_csll_disponivel), 0), limite_comp_csll)
    base_csll = max(lucro_aj_csll_antes_comp - compensacao_csll, 0)
    aliq_csll_final = float(regra["csll"]["aliquota_padrao"] if aliquota_csll is None else aliquota_csll)
    if not 0 <= aliq_csll_final <= 1:
        raise ValueError("Alíquota de CSLL inválida.")
    csll = base_csll * aliq_csll_final

    receita_pc = receita if receita_pis_cofins in (None, "") else _n(receita_pis_cofins)
    aliq_pis_final = float(regra["pis_cofins"]["pis_padrao"] if aliquota_pis is None else aliquota_pis)
    aliq_cofins_final = float(regra["pis_cofins"]["cofins_padrao"] if aliquota_cofins is None else aliquota_cofins)
    debito_pis = max(receita_pc, 0) * aliq_pis_final
    debito_cofins = max(receita_pc, 0) * aliq_cofins_final

    cred_pis_det = sum(max(_n(x.get("credito_pis")), 0) for x in (creditos_detalhados or []))
    cred_cof_det = sum(max(_n(x.get("credito_cofins")), 0) for x in (creditos_detalhados or []))
    credito_pis = max(_n(creditos_pis), 0) + cred_pis_det
    credito_cofins = max(_n(creditos_cofins), 0) + cred_cof_det
    pis = max(debito_pis - credito_pis, 0)
    cofins = max(debito_cofins - credito_cofins, 0)

    icms = max(_n(icms_estimado), 0)
    iss = max(_n(iss_estimado), 0)
    cpp = max(_n(cpp_estimada), 0)
    total = irpj + adicional_irpj + csll + pis + cofins + icms + iss + cpp
    carga = (total / receita * 100) if receita > 0 else 0

    alertas = [
        "Lucro Real permanece como módulo gerencial Beta: adições, exclusões e créditos precisam de validação profissional.",
        f"A compensação foi limitada a {limite_comp:.0%} do lucro ajustado positivo informado no cenário.",
        "PIS/Cofins usam sistemática não cumulativa padrão com créditos informados; o motor não valida a elegibilidade jurídica de cada crédito.",
        "A alíquota de CSLL é parametrizável; setores especiais exigem que o usuário informe a alíquota aplicável e valide a legislação vigente.",
    ]
    if credito_pis > debito_pis or credito_cofins > debito_cofins:
        alertas.append("Créditos informados superaram o débito do período. O simulador limitou o valor a recolher a zero e não transportou saldo credor para períodos futuros.")

    return {
        "receita_periodo": receita,
        "lucro_contabil": lucro,
        "meses_periodo": meses,
        "adicoes_irpj_total": ad_ir,
        "exclusoes_irpj_total": ex_ir,
        "adicoes_csll_total": ad_cs,
        "exclusoes_csll_total": ex_cs,
        "lancamentos_ajustes": lancamentos_ajustes or [],
        "lucro_ajustado_irpj_antes_compensacao": lucro_aj_irpj_antes_comp,
        "limite_compensacao_percentual": limite_comp,
        "limite_compensacao_irpj": limite_comp_irpj,
        "compensacao_irpj": compensacao_irpj,
        "base_irpj": base_irpj,
        "IRPJ": irpj,
        "Adicional IRPJ": adicional_irpj,
        "limite_adicional_irpj": limite_adicional,
        "lucro_ajustado_csll_antes_compensacao": lucro_aj_csll_antes_comp,
        "limite_compensacao_csll": limite_comp_csll,
        "compensacao_csll": compensacao_csll,
        "base_csll": base_csll,
        "aliquota_csll": aliq_csll_final,
        "CSLL": csll,
        "receita_pis_cofins": receita_pc,
        "aliquota_pis": aliq_pis_final,
        "aliquota_cofins": aliq_cofins_final,
        "debito_pis": debito_pis,
        "credito_pis": credito_pis,
        "PIS/Pasep": pis,
        "debito_cofins": debito_cofins,
        "credito_cofins": credito_cofins,
        "COFINS": cofins,
        "creditos_detalhados": creditos_detalhados or [],
        "ICMS estimado": icms,
        "ISS estimado": iss,
        "CPP estimada": cpp,
        "total_periodo": total,
        "carga_efetiva": carga,
        "alertas": alertas,
        "versao_regra": regra["versao"],
        "memoria": {
            "formula_irpj": "(lucro contábil + adições - exclusões - compensação permitida) x 15%",
            "formula_adicional": f"10% sobre a parcela da base IRPJ acima de R$ {limite_adicional:,.2f} no período",
            "formula_csll": "(lucro contábil + adições CSLL - exclusões CSLL - compensação permitida) x alíquota informada",
            "formula_pis_cofins": "débitos - créditos informados, limitado a zero no período",
        },
    }
