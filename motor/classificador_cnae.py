from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_GERAL = os.path.join(BASE_DIR, "regras", "cnae_regras.json")
BASE_TRIB = os.path.join(BASE_DIR, "regras", "regras_tributarias_cnae.json")


def _norm(cnae: Any) -> str:
    nums = "".join(c for c in str(cnae or "") if c.isdigit())
    if len(nums) == 7:
        return f"{nums[:2]}.{nums[2:4]}-{nums[4]}-{nums[5:]}"
    return str(cnae or "").strip()


@lru_cache(maxsize=1)
def _bases() -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    try:
        with open(BASE_TRIB, encoding="utf-8") as f:
            trib = json.load(f).get("regras", [])
    except Exception:
        trib = []
    try:
        with open(BASE_GERAL, encoding="utf-8") as f:
            geral = json.load(f).get("regras", [])
    except Exception:
        geral = []
    geral_idx = {_norm(r.get("cnae")): r for r in geral}
    return trib, geral_idx


def limpar_cache_cnae() -> None:
    _bases.cache_clear()


def classificar_cnae(cnae: Any) -> dict[str, Any]:
    c = _norm(cnae)
    trib, geral_idx = _bases()
    for r in trib:
        if _norm(r.get("cnae")) == c:
            out = dict(r)
            out["classificacao_confiavel"] = r.get("status") in ("validado", "validado_oficialmente")
            return out
    desc = geral_idx.get(c, {}).get("descricao", "")
    return {
        "cnae": c,
        "descricao": desc,
        "permitido_simples": None,
        "anexo": None,
        "fator_r": None,
        "status": "nao_validado",
        "classificacao_confiavel": False,
        "observacao": "CNAE encontrado, mas ainda não há regra tributária curada/validada no motor. Selecione o enquadramento manualmente e valide profissionalmente.",
    }
