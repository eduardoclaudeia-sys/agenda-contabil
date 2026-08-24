from __future__ import annotations
import json
import urllib.error
import urllib.request
from typing import Any

def consultar_cnpj_brasilapi(cnpj: str, timeout: int = 7) -> dict[str, Any]:
    """Consulta opcional de conveniência. Deve ser conferida no comprovante oficial."""
    n = "".join(c for c in str(cnpj or "") if c.isdigit())
    if len(n) != 14:
        raise ValueError("CNPJ deve possuir 14 dígitos.")
    req = urllib.request.Request(f"https://brasilapi.com.br/api/cnpj/v1/{n}", headers={"User-Agent":"MotorTributarioJSM/5.0","Accept":"application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404: raise ValueError("CNPJ não encontrado na consulta externa.") from exc
        raise ValueError(f"Falha na consulta externa do CNPJ (HTTP {exc.code}).") from exc
    except Exception as exc:
        raise ValueError("Não foi possível consultar o CNPJ agora. Use o cadastro manual ou PDF oficial.") from exc
    secundarios=data.get('cnaes_secundarios') or []
    sec='; '.join(f"{x.get('codigo','')} - {x.get('descricao','')}".strip(' -') for x in secundarios if isinstance(x,dict))
    return {
        'cnpj':n,'razao_social':data.get('razao_social') or data.get('nome_fantasia') or '',
        'nome_fantasia':data.get('nome_fantasia') or '', 'data_abertura':data.get('data_inicio_atividade') or '',
        'cnae_principal':str(data.get('cnae_fiscal') or ''),'cnaes_secundarios':sec,'uf':data.get('uf') or '',
        'municipio':data.get('municipio') or '', 'situacao_cadastral':str(data.get('descricao_situacao_cadastral') or ''),
        'porte':data.get('porte') or '', 'natureza_juridica':data.get('natureza_juridica') or '',
        'logradouro':data.get('logradouro') or '', 'numero':str(data.get('numero') or ''), 'complemento':data.get('complemento') or '',
        'cep':str(data.get('cep') or ''), 'bairro':data.get('bairro') or '', 'origem_cadastro':'Consulta externa BrasilAPI'
    }
