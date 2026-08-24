"""
Motor de cálculo do Simples Nacional.

Este módulo NÃO deve conter interface gráfica (isso fica em analise_empresa.py).
Ele só carrega as faixas do JSON e calcula a alíquota efetiva e o DAS.
"""

import json
import os

# ============================================================
# CAMINHOS
# ============================================================
BASE_ANEXOS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "regras",
    "regras_simples.json"
)

_cache_anexos = None


def _carregar_anexos():
    """Carrega (com cache) o JSON de faixas dos Anexos do Simples Nacional."""
    global _cache_anexos

    if _cache_anexos is not None:
        return _cache_anexos

    if not os.path.exists(BASE_ANEXOS):
        raise FileNotFoundError(
            f"Arquivo de regras dos Anexos não encontrado:\n{BASE_ANEXOS}"
        )

    with open(BASE_ANEXOS, "r", encoding="utf-8") as arquivo:
        dados = json.load(arquivo)

    _cache_anexos = dados.get("anexos", {})
    return _cache_anexos


def _encontrar_faixa(faixas, rbt12):
    """Retorna a faixa (dict) cujo intervalo [limite_inferior, limite_superior] contém o RBT12."""
    for faixa in faixas:
        inferior = float(faixa.get("limite_inferior", 0))
        superior = float(faixa.get("limite_superior", 0))
        if inferior <= rbt12 <= superior:
            return faixa
    return None


def calcular_simples(anexo, rbt12, faturamento_mensal):
    """
    Calcula a alíquota efetiva e o DAS estimado para um Anexo do Simples Nacional.

    Parâmetros:
        anexo (str): ex. "Anexo I", "Anexo II"
        rbt12 (float): receita bruta dos últimos 12 meses
        faturamento_mensal (float): faturamento do mês de referência

    Retorna um dict:
        {
            "faixa": int,
            "aliquota_nominal": float,
            "aliquota_efetiva": float,   # em % (ex.: 6.5432)
            "parcela_deduzir": float,
            "das_mensal": float,
            "ano_base": int
        }
    """
    if rbt12 is None or rbt12 <= 0:
        raise ValueError("RBT12 deve ser maior que zero para calcular a alíquota efetiva.")

    anexos = _carregar_anexos()

    dados_anexo = anexos.get(anexo)
    if dados_anexo is None:
        raise ValueError(f"Anexo '{anexo}' não encontrado na base de regras.")

    faixas = dados_anexo.get("faixas", [])
    faixa = _encontrar_faixa(faixas, rbt12)

    if faixa is None:
        raise ValueError(
            f"Nenhuma faixa encontrada para RBT12 = {rbt12:.2f} no {anexo}. "
            "Verifique se o valor está dentro do teto do Simples Nacional."
        )

    aliquota_nominal = float(faixa.get("aliquota_nominal", 0))
    parcela_deduzir = float(faixa.get("parcela_deduzir", 0))

    # Fórmula oficial do Simples Nacional (LC 123/2006):
    # Alíquota efetiva = ((RBT12 * Alíquota nominal) - Parcela a deduzir) / RBT12
    aliquota_efetiva = ((rbt12 * aliquota_nominal) - parcela_deduzir) / rbt12

    # Não deixar a alíquota efetiva ficar negativa por erro de faixa/dados
    if aliquota_efetiva < 0:
        aliquota_efetiva = 0.0

    das_mensal = faturamento_mensal * aliquota_efetiva

    return {
        "faixa": faixa.get("faixa"),
        "aliquota_nominal": aliquota_nominal * 100,   # em %
        "aliquota_efetiva": aliquota_efetiva * 100,   # em %
        "parcela_deduzir": parcela_deduzir,
        "das_mensal": das_mensal,
        "ano_base": dados_anexo.get("ano_base", 2026),
    }


if __name__ == "__main__":
    # Teste rápido isolado do motor (sem GUI)
    exemplo = calcular_simples("Anexo I", rbt12=360000.0, faturamento_mensal=30000.0)
    for chave, valor in exemplo.items():
        print(f"{chave}: {valor}")
