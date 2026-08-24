"""Motor gerencial de Lucro Presumido — V5.

Destaques:
- múltiplas atividades no mesmo trimestre;
- proporcionalização do limite trimestral de 2026 entre atividades;
- receitas financeiras e ganhos de capital informados separadamente e
  adicionados integralmente às bases de IRPJ/CSLL;
- PIS/Cofins cumulativos sobre a receita operacional informada no motor;
- memória de cálculo e versão da regra.

O módulo é ferramenta de apoio. Atividades com percentuais especiais, receitas
com tratamento próprio e particularidades setoriais devem ser parametrizadas e
validadas pelo responsável fiscal.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGRAS_DIR = os.path.join(BASE_DIR, "regras", "presumido")
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


def _atividade(tipo: str, regra: dict[str, Any]) -> dict[str, Any]:
    key = str(tipo or "comercio").lower().strip()
    aliases = {
        "serviço": "servico", "serviços": "servico", "servicos": "servico",
        "combustível": "combustivel", "comércio": "comercio", "industria": "industria",
        "indústria": "industria",
    }
    key = aliases.get(key, key)
    if key not in regra["atividades"]:
        raise ValueError(f"Tipo de atividade não parametrizado: {tipo}")
    item = dict(regra["atividades"][key])
    item["codigo"] = key
    return item


def calcular_lucro_presumido_misto_2026(
    atividades: list[dict[str, Any]],
    trimestre: int = 1,
    receitas_financeiras: float = 0,
    ganhos_capital: float = 0,
    outras_receitas_integrais: float = 0,
    aliquota_iss: float = 0.0,
    aliquota_icms: float = 0.0,
    cpp_trimestre: float = 0.0,
) -> dict[str, Any]:
    """Calcula cenário trimestral de Lucro Presumido 2026 com atividades mistas.

    O limite de R$ 1,25 milhão é distribuído proporcionalmente entre as receitas
    operacionais sujeitas aos coeficientes de presunção, conforme orientação
    oficial da Receita Federal para 2026.
    """
    regra = carregar_regra_2026()
    tri = int(trimestre or 1)
    if tri not in (1, 2, 3, 4):
        raise ValueError("Trimestre deve ser 1, 2, 3 ou 4.")

    itens: list[dict[str, Any]] = []
    total_operacional = 0.0
    for entrada in atividades or []:
        valor = _n(entrada.get("receita"))
        if valor < 0:
            raise ValueError("Receitas por atividade não podem ser negativas.")
        if valor == 0:
            continue
        info = _atividade(str(entrada.get("tipo") or "comercio"), regra)
        total_operacional += valor
        itens.append({"tipo": info["codigo"], "rotulo": info["rotulo"], "receita": valor,
                      "presuncao_irpj": float(info["presuncao_irpj"]),
                      "presuncao_csll": float(info["presuncao_csll"])})

    if total_operacional < 0:
        raise ValueError("Receita operacional inválida.")

    limite_total = float(regra["limite_presuncao_trimestral"])
    acrescimo = float(regra["acrescimo_percentual_presuncao"])
    aplica_csll_acrescimo = tri >= int(regra["csll_acrescimo_a_partir_trimestre"])

    base_irpj_oper = 0.0
    base_csll_oper = 0.0
    detalhamento = []
    for item in itens:
        proporcao = (item["receita"] / total_operacional) if total_operacional else 0.0
        limite_atividade = min(item["receita"], limite_total * proporcao)
        excedente = max(item["receita"] - limite_atividade, 0.0)
        p_ir_normal = item["presuncao_irpj"]
        p_ir_exc = p_ir_normal * (1 + acrescimo)
        p_cs_normal = item["presuncao_csll"]
        p_cs_exc = p_cs_normal * (1 + acrescimo) if aplica_csll_acrescimo else p_cs_normal
        base_ir = limite_atividade * p_ir_normal + excedente * p_ir_exc
        base_cs = limite_atividade * p_cs_normal + excedente * p_cs_exc
        base_irpj_oper += base_ir
        base_csll_oper += base_cs
        detalhamento.append({
            **item,
            "proporcao_receita": proporcao,
            "limite_normal": limite_atividade,
            "receita_excedente": excedente,
            "presuncao_irpj_normal": p_ir_normal,
            "presuncao_irpj_excedente": p_ir_exc,
            "presuncao_csll_normal": p_cs_normal,
            "presuncao_csll_excedente": p_cs_exc,
            "base_irpj": base_ir,
            "base_csll": base_cs,
        })

    receitas_integrais = max(_n(receitas_financeiras), 0) + max(_n(ganhos_capital), 0) + max(_n(outras_receitas_integrais), 0)
    base_irpj = base_irpj_oper + receitas_integrais
    base_csll = base_csll_oper + receitas_integrais

    aliq_irpj = float(regra["irpj"]["aliquota"])
    aliq_adicional = float(regra["irpj"]["adicional"])
    limite_adicional = float(regra["irpj"]["limite_adicional_mes"]) * 3
    aliq_csll = float(regra["csll"]["aliquota_padrao"])
    irpj = base_irpj * aliq_irpj
    adicional = max(base_irpj - limite_adicional, 0) * aliq_adicional
    csll = base_csll * aliq_csll

    # Regime cumulativo padrão. Receitas integrais são mantidas fora desta base
    # por padrão no simulador, pois podem ter tratamento próprio. Usuário deve validar.
    pis = total_operacional * float(regra["pis_cofins"]["pis"])
    cofins = total_operacional * float(regra["pis_cofins"]["cofins"])
    iss = total_operacional * max(_n(aliquota_iss), 0)
    icms = total_operacional * max(_n(aliquota_icms), 0)
    cpp = max(_n(cpp_trimestre), 0)

    total = irpj + adicional + csll + pis + cofins + iss + icms + cpp
    alertas = [
        "Receitas financeiras, ganhos de capital e outras receitas integrais foram somados integralmente às bases de IRPJ/CSLL informadas neste cenário.",
        "PIS/Cofins foram calculados no regime cumulativo padrão apenas sobre as receitas operacionais informadas; receitas com tratamento específico devem ser validadas separadamente.",
        "ISS, ICMS e CPP são parâmetros gerenciais informados pelo usuário e não substituem apuração estadual, municipal ou previdenciária.",
    ]
    if total_operacional > limite_total:
        alertas.insert(0, "A receita operacional excedeu R$ 1.250.000 no trimestre; o limite normal de presunção foi distribuído proporcionalmente entre as atividades e o excedente recebeu acréscimo de 10% no percentual de presunção aplicável em 2026.")
    if tri == 1 and total_operacional > limite_total:
        alertas.append("No 1º trimestre de 2026, o acréscimo foi considerado no IRPJ, mas não na CSLL, conforme a parametrização oficial usada pela V5.")

    return {
        "trimestre": tri,
        "receita_trimestre": total_operacional,
        "receitas_financeiras": max(_n(receitas_financeiras), 0),
        "ganhos_capital": max(_n(ganhos_capital), 0),
        "outras_receitas_integrais": max(_n(outras_receitas_integrais), 0),
        "atividades": detalhamento,
        "limite_presuncao_normal": limite_total,
        "receita_excedente": max(total_operacional - limite_total, 0),
        "base_irpj_operacional": base_irpj_oper,
        "base_csll_operacional": base_csll_oper,
        "base_irpj": base_irpj,
        "base_csll": base_csll,
        "IRPJ": irpj,
        "Adicional IRPJ": adicional,
        "CSLL": csll,
        "PIS/Pasep": pis,
        "COFINS": cofins,
        "ISS estimado": iss,
        "ICMS estimado": icms,
        "CPP estimada": cpp,
        "total_trimestre": total,
        "media_mensal": total / 3,
        "carga_efetiva": (total / total_operacional * 100) if total_operacional else 0.0,
        "alertas": alertas,
        "versao_regra": regra["versao"],
        "fonte_regra": regra["fonte_oficial"],
        "memoria": {
            "limite_total": limite_total,
            "acrescimo_percentual": acrescimo,
            "atividades": detalhamento,
            "receitas_integrais": receitas_integrais,
            "formula_adicional": "10% sobre a parcela da base IRPJ que excede R$ 60.000 no trimestre",
        },
    }


def calcular_lucro_presumido_2026(
    receita_trimestre: float,
    tipo_atividade: str = "comercio",
    trimestre: int = 1,
    aliquota_iss: float = 0.0,
    aliquota_icms: float = 0.0,
    cpp_trimestre: float = 0.0,
    outras_receitas_trimestre: float = 0.0,
) -> dict[str, Any]:
    resultado = calcular_lucro_presumido_misto_2026(
        atividades=[{"tipo": tipo_atividade, "receita": receita_trimestre}],
        trimestre=trimestre,
        outras_receitas_integrais=outras_receitas_trimestre,
        aliquota_iss=aliquota_iss,
        aliquota_icms=aliquota_icms,
        cpp_trimestre=cpp_trimestre,
    )
    at = resultado["atividades"][0] if resultado["atividades"] else {
        "rotulo": "Comércio / indústria", "presuncao_irpj_normal": 0.08,
        "presuncao_irpj_excedente": 0.088, "presuncao_csll_normal": 0.12,
        "presuncao_csll_excedente": 0.12, "limite_normal": 0.0, "receita_excedente": 0.0,
    }
    resultado.update({
        "tipo_atividade": at.get("rotulo"),
        "receita_normal": at.get("limite_normal", 0.0),
        "presuncao_irpj_normal": at.get("presuncao_irpj_normal", 0.0),
        "presuncao_irpj_excedente": at.get("presuncao_irpj_excedente", 0.0),
        "presuncao_csll_normal": at.get("presuncao_csll_normal", 0.0),
        "presuncao_csll_excedente": at.get("presuncao_csll_excedente", 0.0),
    })
    return resultado


def calcular_lucro_presumido(receita_mensal: float, tipo_atividade: str = "comercio",
                             aliquota_iss: float = 0.0, aliquota_icms: float = 0.0,
                             cpp_mensal: float = 0.0, outras_receitas_trimestre: float = 0.0) -> dict[str, Any]:
    """Compatibilidade histórica: encaminha para o motor 2026 usando receita mensal x 3."""
    r = calcular_lucro_presumido_2026(
        receita_trimestre=float(receita_mensal or 0) * 3,
        tipo_atividade=tipo_atividade,
        trimestre=1,
        aliquota_iss=aliquota_iss,
        aliquota_icms=aliquota_icms,
        cpp_trimestre=float(cpp_mensal or 0) * 3,
        outras_receitas_trimestre=outras_receitas_trimestre,
    )
    at = r["atividades"][0] if r.get("atividades") else {}
    r["presuncao_irpj"] = at.get("presuncao_irpj_normal", 0)
    r["presuncao_csll"] = at.get("presuncao_csll_normal", 0)
    return r


def comparar_com_simples(das_simples_mensal: float, trimestre: int = 1, **kwargs) -> dict[str, Any]:
    """Comparador legado corrigido para usar o motor 2026."""
    if "receita_mensal" in kwargs:
        receita_tri = _n(kwargs.pop("receita_mensal")) * 3
    else:
        receita_tri = _n(kwargs.pop("receita_trimestre", 0))
    tipo = kwargs.pop("tipo_atividade", "comercio")
    cpp_tri = _n(kwargs.pop("cpp_trimestre", 0))
    if "cpp_mensal" in kwargs:
        cpp_tri = _n(kwargs.pop("cpp_mensal")) * 3
    lp = calcular_lucro_presumido_2026(
        receita_trimestre=receita_tri,
        tipo_atividade=tipo,
        trimestre=trimestre,
        cpp_trimestre=cpp_tri,
        **kwargs,
    )
    simples = float(das_simples_mensal)
    dif = lp["media_mensal"] - simples
    return {
        "simples_mensal": simples,
        "presumido_mensal": lp["media_mensal"],
        "diferenca_mensal": dif,
        "diferenca_anual": dif * 12,
        "cenario_mais_economico": "Simples Nacional" if dif > 0 else "Lucro Presumido" if dif < 0 else "Equivalente",
        "lucro_presumido": lp,
        "versao_regra": lp.get("versao_regra"),
    }
