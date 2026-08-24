"""Motor avançado do Simples Nacional — V5.

O núcleo preserva as fórmulas validadas da V4 e adiciona:
- carregamento de regras por vigência/competência;
- alerta/controle explícito de sublimite de ICMS/ISS;
- memória de cálculo mais detalhada;
- type hints e cache de JSON.

O sistema NÃO presume automaticamente que ICMS/ISS devam sair do DAS apenas
porque o RBT12 superou o sublimite. Essa retirada só ocorre quando o usuário
confirma explicitamente a situação para a competência.
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime
from decimal import Decimal, ROUND_DOWN
from functools import lru_cache
from typing import Any

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGRAS_DIR = os.path.join(BASE_DIR, "regras", "simples")
INDICE = os.path.join(REGRAS_DIR, "indice.json")


@lru_cache(maxsize=32)
def _load(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _parse_data_ref(competencia: str | None) -> date:
    if not competencia:
        return date.today().replace(day=1)
    s = str(competencia).strip()
    if "/" in s:
        m, y = s.split("/")[:2]
        return date(int(y), int(m), 1)
    if "-" in s:
        y, m = s.split("-")[:2]
        return date(int(y), int(m), 1)
    raise ValueError("Competência deve estar em MM/AAAA ou AAAA-MM.")


def _selecionar_versao(competencia: str | None = None) -> dict[str, Any]:
    ref = _parse_data_ref(competencia)
    indice = _load(INDICE)
    candidatas = []
    for item in indice.get("versoes", []):
        ini = datetime.strptime(item["vigencia_inicio"], "%Y-%m-%d").date()
        fim = datetime.strptime(item["vigencia_fim"], "%Y-%m-%d").date() if item.get("vigencia_fim") else None
        if ini <= ref and (fim is None or ref <= fim):
            candidatas.append(item)
    if not candidatas:
        raise ValueError(f"Não existe regra do Simples parametrizada para {ref:%m/%Y}.")
    candidatas.sort(key=lambda x: x["vigencia_inicio"], reverse=True)
    return candidatas[0]


def carregar_regras(competencia: str | None = None) -> tuple[dict[str, Any], dict[str, Any], str]:
    ver = _selecionar_versao(competencia)
    regras = _load(os.path.join(REGRAS_DIR, ver["regras"]))
    reparticao = _load(os.path.join(REGRAS_DIR, ver["reparticao"]))
    return regras, reparticao, ver["versao"]


def _competencia_tuple(comp: str) -> tuple[int, int]:
    d = _parse_data_ref(comp)
    return d.year, d.month


def _meses_entre(data_abertura: Any, competencia: str) -> int | None:
    if not data_abertura:
        return None
    if isinstance(data_abertura, str):
        s = data_abertura.strip()
        try:
            if "-" in s:
                y0, m0 = [int(x) for x in s.split("-")[:2]]
            elif "/" in s:
                partes = [int(x) for x in s.split("/")]
                if len(partes) == 3:
                    _, m0, y0 = partes
                else:
                    m0, y0 = partes[:2]
            else:
                return None
        except Exception:
            return None
    else:
        y0, m0 = data_abertura.year, data_abertura.month
    y, m = _competencia_tuple(competencia)
    return (y - y0) * 12 + (m - m0)


def _anteriores(historico: list[dict[str, Any]], competencia: str, campo_total) -> list[tuple[tuple[int, int], float]]:
    alvo = _competencia_tuple(competencia)
    itens: list[tuple[tuple[int, int], float]] = []
    for item in historico:
        c = item.get("competencia")
        if not c:
            continue
        if _competencia_tuple(c) < alvo:
            itens.append((_competencia_tuple(c), float(campo_total(item))))
    itens.sort(key=lambda x: x[0])
    return itens


def calcular_rbt12(historico: list[dict[str, Any]], competencia: str,
                    data_abertura: Any = None, receita_pa: float | None = None) -> float:
    """Calcula o RBT12 de enquadramento.

    Regra preservada:
    - mês de início: receita do próprio PA x 12;
    - 2º ao 12º mês: média dos meses anteriores x 12;
    - empresa madura: soma dos 12 PA anteriores.
    """
    meses = _meses_entre(data_abertura, competencia)
    ant = _anteriores(
        historico,
        competencia,
        lambda x: x.get("receita_interna", 0) + x.get("receita_externa", 0),
    )
    if meses == 0:
        if receita_pa is None:
            raise ValueError("No mês de abertura, informe a receita do próprio PA para proporcionalizar o RBT12.")
        return float(receita_pa) * 12
    if meses is not None and 0 < meses < 12:
        if not ant:
            raise ValueError("Não há receitas anteriores suficientes para calcular o RBT12 proporcionalizado.")
        return (sum(v for _, v in ant) / len(ant)) * 12
    if not ant:
        if receita_pa is not None:
            return float(receita_pa) * 12
        raise ValueError("Não há histórico para calcular o RBT12.")
    return sum(v for _, v in ant[-12:])


def calcular_fs12(historico_folha: list[dict[str, Any]], competencia: str,
                   data_abertura: Any = None, folha_pa: float | None = None) -> float:
    meses = _meses_entre(data_abertura, competencia)
    ant = _anteriores(
        historico_folha,
        competencia,
        lambda x: x.get("salarios", 0) + x.get("pro_labore", 0) + x.get("encargos", 0) + x.get("outros_fs12", 0),
    )
    if meses == 0:
        return float(folha_pa or 0)
    if meses is not None and 0 < meses < 13:
        return sum(v for _, v in ant)
    return sum(v for _, v in ant[-12:])


def calcular_fator_r(fs12: float, rbt12: float) -> float:
    fs12 = float(fs12 or 0)
    rbt12 = float(rbt12 or 0)
    if fs12 <= 0 and rbt12 <= 0:
        return 0.01
    if fs12 <= 0 and rbt12 > 0:
        return 0.01
    if fs12 > 0 and rbt12 <= 0:
        return 0.28
    bruto = fs12 / rbt12
    return float(Decimal(str(bruto)).quantize(Decimal("0.01"), rounding=ROUND_DOWN))


def resolver_anexo_fator_r(anexo_base: str, sujeito_fator_r: bool, fator_r: float | None) -> str:
    if not sujeito_fator_r:
        return anexo_base
    return "Anexo III" if float(fator_r or 0) >= 0.28 else "Anexo V"


def _faixa(anexo: str, rbt12: float, regras: dict[str, Any]) -> dict[str, Any] | None:
    for f in regras["anexos"][anexo]["faixas"]:
        if float(f["limite_inferior"]) <= rbt12 <= float(f["limite_superior"]):
            return f
    return None


def _partilha(anexo: str, faixa_num: int, reparticao: dict[str, Any]) -> dict[str, float]:
    return dict(reparticao["anexos"][anexo][str(faixa_num)])


def _composicao_base(anexo: str, faixa_num: int, aliquota_efetiva: float,
                     reparticao: dict[str, Any]) -> dict[str, float]:
    part = _partilha(anexo, faixa_num, reparticao)
    comp = {k: aliquota_efetiva * v for k, v in part.items()}
    if "ISS" in comp and comp["ISS"] > 0.05 and faixa_num <= 5:
        excesso = comp["ISS"] - 0.05
        comp["ISS"] = 0.05
        redist = reparticao.get("redistribuicao_iss_excedente", {}).get(anexo, {})
        for trib, peso in redist.items():
            comp[trib] = comp.get(trib, 0) + excesso * peso
    return comp


def _exclusoes_por_tipo(tipo: str, anexo: str) -> set[str]:
    tipo = (tipo or "normal").lower()
    if tipo in ("normal", "mercado_interno"):
        return set()
    if tipo == "monofasico":
        return {"PIS/Pasep", "COFINS"}
    if tipo in ("monofasico_icms_st", "monofasico_st"):
        return {"PIS/Pasep", "COFINS", "ICMS"}
    if tipo in ("icms_st", "substituicao_tributaria"):
        return {"ICMS"}
    if tipo == "iss_retido":
        return {"ISS"}
    if tipo == "exportacao":
        exc = {"PIS/Pasep", "COFINS"}
        if anexo in ("Anexo I", "Anexo II"):
            exc.add("ICMS")
            if anexo == "Anexo II":
                exc.add("IPI")
        else:
            exc.add("ISS")
        return exc
    if tipo == "locacao_sem_iss":
        return {"ISS"}
    return set()


def calcular_segmento(anexo: str, rbt12: float, valor: float, tipo: str = "normal",
                      competencia: str | None = None, retirar_icms_iss_sublimite: bool = False) -> dict[str, Any]:
    if valor < 0:
        raise ValueError("Valor da receita segregada não pode ser negativo.")
    tipos_validos = {
        "normal", "mercado_interno", "monofasico", "monofasico_icms_st", "monofasico_st",
        "icms_st", "substituicao_tributaria", "iss_retido", "exportacao", "locacao_sem_iss",
    }
    if (tipo or "normal").lower() not in tipos_validos:
        raise ValueError(f"Tipo de receita não reconhecido: {tipo}")

    regras, reparticao, versao = carregar_regras(competencia)
    f = _faixa(anexo, rbt12, regras)
    if not f:
        raise ValueError("RBT12 fora das faixas parametrizadas do Simples Nacional.")

    nominal = float(f["aliquota_nominal"])
    ded = float(f["parcela_deduzir"])
    aliq = ((rbt12 * nominal) - ded) / rbt12
    comp = _composicao_base(anexo, int(f["faixa"]), aliq, reparticao)
    exclusoes = _exclusoes_por_tipo(tipo, anexo)
    if retirar_icms_iss_sublimite:
        exclusoes |= {"ICMS", "ISS"}
    comp_ajustada = {k: (0.0 if k in exclusoes else v) for k, v in comp.items()}
    aliq_ajustada = sum(comp_ajustada.values())
    valores = {k: valor * p for k, p in comp_ajustada.items()}
    return {
        "tipo": tipo,
        "valor": valor,
        "anexo": anexo,
        "faixa": int(f["faixa"]),
        "aliquota_efetiva_base": aliq,
        "aliquota_efetiva_segmento": aliq_ajustada,
        "exclusoes": sorted(exclusoes),
        "percentuais_tributos": comp_ajustada,
        "valores_tributos": valores,
        "das_segmento": sum(valores.values()),
        "versao_regra": versao,
    }


def calcular_apuracao(
    anexo: str,
    rbt12: float,
    receita_mes: float,
    segregacoes: list[dict[str, Any]] | None = None,
    fs12: float = 0,
    fator_r: float | None = None,
    sujeito_fator_r: bool = False,
    validar_total: bool = True,
    competencia: str | None = None,
    retirar_icms_iss_sublimite: bool = False,
) -> dict[str, Any]:
    if rbt12 <= 0:
        raise ValueError("RBT12 deve ser maior que zero.")
    if receita_mes < 0:
        raise ValueError("Receita mensal não pode ser negativa.")

    regras, _, versao = carregar_regras(competencia)
    limite = float(regras["limites"]["simples_nacional"])
    sublimite = float(regras["limites"]["sublimite_icms_iss"])
    if rbt12 > limite:
        raise ValueError(f"RBT12 acima do limite parametrizado do Simples Nacional ({limite:.2f}).")

    if retirar_icms_iss_sublimite and rbt12 <= sublimite:
        raise ValueError("Não é permitido retirar ICMS/ISS por sublimite quando o RBT12 não supera o sublimite parametrizado.")

    if fator_r is None:
        fator_r = calcular_fator_r(fs12, rbt12) if sujeito_fator_r else None
    anexo_final = resolver_anexo_fator_r(anexo, sujeito_fator_r, fator_r)

    if not segregacoes:
        segregacoes = [{"tipo": "normal", "valor": float(receita_mes), "anexo": anexo_final}]
    soma = sum(float(s.get("valor", 0)) for s in segregacoes)
    if validar_total and abs(soma - float(receita_mes)) > 0.01:
        raise ValueError(f"Receitas segregadas ({soma:.2f}) não fecham com o faturamento ({receita_mes:.2f}).")

    segmentos: list[dict[str, Any]] = []
    tributos: dict[str, float] = {}
    tributos_sem_tratamentos: dict[str, float] = {}
    das = 0.0
    das_sem_tratamentos = 0.0

    for seg in segregacoes:
        seg_anexo = seg.get("anexo") or anexo_final
        valor_seg = float(seg.get("valor", 0))
        tipo_seg = seg.get("tipo", "normal")
        item = calcular_segmento(
            seg_anexo, rbt12, valor_seg, tipo_seg,
            competencia=competencia,
            retirar_icms_iss_sublimite=retirar_icms_iss_sublimite,
        )
        base_normal = calcular_segmento(seg_anexo, rbt12, valor_seg, "normal", competencia=competencia)
        item["cnae"] = seg.get("cnae")
        item["observacoes"] = seg.get("observacoes", "")
        segmentos.append(item)
        das += item["das_segmento"]
        das_sem_tratamentos += base_normal["das_segmento"]
        for k, v in item["valores_tributos"].items():
            tributos[k] = tributos.get(k, 0) + v
        for k, v in base_normal["valores_tributos"].items():
            tributos_sem_tratamentos[k] = tributos_sem_tratamentos.get(k, 0) + v

    reducoes_por_tratamento = {
        k: max(0.0, float(tributos_sem_tratamentos.get(k, 0)) - float(tributos.get(k, 0)))
        for k in set(tributos_sem_tratamentos) | set(tributos)
    }

    f = _faixa(anexo_final, rbt12, regras)
    assert f is not None
    aliq_base = ((rbt12 * float(f["aliquota_nominal"])) - float(f["parcela_deduzir"])) / rbt12

    alertas: list[tuple[str, str]] = []
    pct_limite = rbt12 / limite
    if pct_limite >= 0.90:
        alertas.append(("CRÍTICO", "RBT12 acima de 90% do limite do Simples Nacional."))
    elif pct_limite >= 0.75:
        alertas.append(("ATENÇÃO", "RBT12 acima de 75% do limite do Simples Nacional."))
    else:
        alertas.append(("NORMAL", "RBT12 dentro de faixa confortável do limite geral."))

    if rbt12 > sublimite:
        if retirar_icms_iss_sublimite:
            alertas.append(("CRÍTICO", "ICMS/ISS foram retirados da composição do DAS porque o usuário confirmou recolhimento fora do DAS para esta competência. Valide no PGDAS-D e na legislação local."))
        else:
            alertas.append(("CRÍTICO", "RBT12 acima do sublimite parametrizado de ICMS/ISS. O motor NÃO retirou automaticamente esses tributos; confirme a situação da competência antes de aplicar o tratamento."))
    elif rbt12 >= sublimite * 0.90:
        alertas.append(("ATENÇÃO", "Empresa próxima ao sublimite de ICMS/ISS."))

    if sujeito_fator_r and fator_r is not None:
        if fator_r >= 0.28:
            alertas.append(("NORMAL", f"Fator R em {fator_r:.2%}: cenário enquadrado no Anexo III para atividade sujeita ao Fator R."))
        elif fator_r >= 0.20:
            alertas.append(("ATENÇÃO", f"Fator R em {fator_r:.2%}: abaixo de 28%, com proximidade relevante do corte."))
        else:
            alertas.append(("CRÍTICO", f"Fator R em {fator_r:.2%}: abaixo de 20%; confira folha e enquadramento da atividade."))

    memoria = {
        "formula_aliquota_efetiva": "((RBT12 x aliquota nominal) - parcela a deduzir) / RBT12",
        "rbt12": rbt12,
        "fs12": fs12,
        "fator_r": fator_r,
        "anexo_informado": anexo,
        "anexo_aplicado": anexo_final,
        "faixa": int(f["faixa"]),
        "aliquota_nominal": float(f["aliquota_nominal"]),
        "parcela_deduzir": float(f["parcela_deduzir"]),
        "aliquota_efetiva_base": aliq_base,
        "segmentos": segmentos,
        "tributos": tributos,
        "tributos_sem_tratamentos": tributos_sem_tratamentos,
        "reducoes_por_tratamento": reducoes_por_tratamento,
        "das_sem_tratamentos": das_sem_tratamentos,
        "sublimite": sublimite,
        "retirar_icms_iss_sublimite": retirar_icms_iss_sublimite,
        "alertas": alertas,
        "versao_regra": versao,
    }
    return {
        "anexo": anexo_final,
        "rbt12": rbt12,
        "fs12": fs12,
        "fator_r": fator_r,
        "receita_mes": float(receita_mes),
        "faixa": int(f["faixa"]),
        "aliquota_nominal": float(f["aliquota_nominal"]) * 100,
        "aliquota_efetiva": aliq_base * 100,
        "parcela_deduzir": float(f["parcela_deduzir"]),
        "das_mensal": das,
        "tributos": tributos,
        "segmentos": segmentos,
        "alertas": alertas,
        "tributos_sem_tratamentos": tributos_sem_tratamentos,
        "reducoes_por_tratamento": reducoes_por_tratamento,
        "das_sem_tratamentos": das_sem_tratamentos,
        "economia_tratamentos": max(0.0, das_sem_tratamentos - das),
        "carga_efetiva_final": (das / float(receita_mes) * 100 if float(receita_mes) > 0 else 0.0),
        "sublimite_superado": rbt12 > sublimite,
        "icms_iss_fora_das_confirmado": retirar_icms_iss_sublimite,
        "memoria": memoria,
        "versao_regra": versao,
    }


def projetar_receita(historico: list[dict[str, Any]], meses_futuros: int = 6, janela_media: int = 3) -> dict[str, Any]:
    """Projeção simples e explicitamente não preditiva pela média dos últimos meses."""
    valores = [float(x.get("receita_interna", 0)) + float(x.get("receita_externa", 0)) for x in historico]
    if not valores:
        return {"media_mensal": 0.0, "projecao": [], "rbt12_projetado": 0.0}
    janela = max(1, min(int(janela_media), len(valores)))
    media = sum(valores[-janela:]) / janela
    proj = [media for _ in range(int(meses_futuros))]
    base = list(valores[-12:])
    for v in proj:
        base.append(v)
        base = base[-12:]
    return {"media_mensal": media, "projecao": proj, "rbt12_projetado": sum(base)}
