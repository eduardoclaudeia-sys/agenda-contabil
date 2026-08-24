from __future__ import annotations

from dataclasses import dataclass, asdict
from decimal import Decimal
from typing import Any

from defusedxml import ElementTree as ET


@dataclass
class ItemNFe:
    descricao: str
    ncm: str
    cfop: str
    valor_produto: float
    cst_icms: str
    cst_pis: str
    cst_cofins: str
    tem_st: bool
    indicio_monofasico: bool


def _tag(el) -> str:
    return el.tag.split("}")[-1]


def _texto_filho(el, nome: str, padrao: str = "") -> str:
    for filho in list(el):
        if _tag(filho) == nome:
            return (filho.text or padrao).strip()
    return padrao


def _buscar_descendente(el, nome: str) -> str:
    for filho in el.iter():
        if _tag(filho) == nome:
            return (filho.text or "").strip()
    return ""


def validar_xml_bytes(conteudo: bytes) -> None:
    ini = conteudo.lstrip()[:100].lower()
    if not ini.startswith(b"<?xml") and b"<nfe" not in ini and b"<procnfe" not in ini:
        raise ValueError("O arquivo não parece ser um XML de NF-e válido.")


def analisar_nfe_bytes(conteudo: bytes) -> dict[str, Any]:
    validar_xml_bytes(conteudo)
    try:
        raiz = ET.fromstring(conteudo)
    except Exception as exc:
        raise ValueError("Não foi possível interpretar o XML da NF-e.") from exc

    itens: list[ItemNFe] = []
    emitente = ""
    cnpj_emitente = ""
    numero = ""
    serie = ""
    chave = ""
    total_nfe = Decimal("0")

    for el in raiz.iter():
        nome = _tag(el)
        if nome == "emit":
            emitente = _buscar_descendente(el, "xNome")
            cnpj_emitente = _buscar_descendente(el, "CNPJ")
        elif nome == "ide":
            numero = _buscar_descendente(el, "nNF")
            serie = _buscar_descendente(el, "serie")
        elif nome == "infNFe" and not chave:
            chave = str(el.attrib.get("Id", "")).replace("NFe", "")
        elif nome == "ICMSTot":
            try:
                total_nfe = Decimal(_buscar_descendente(el, "vNF") or "0")
            except Exception:
                total_nfe = Decimal("0")
        elif nome == "det":
            prod = next((x for x in list(el) if _tag(x) == "prod"), None)
            imposto = next((x for x in list(el) if _tag(x) == "imposto"), None)
            if prod is None:
                continue
            desc = _texto_filho(prod, "xProd")
            ncm = _texto_filho(prod, "NCM")
            cfop = _texto_filho(prod, "CFOP")
            try:
                valor = float(_texto_filho(prod, "vProd", "0") or 0)
            except Exception:
                valor = 0.0
            cst_icms = _buscar_descendente(imposto, "CST") if imposto is not None else ""
            csosn = _buscar_descendente(imposto, "CSOSN") if imposto is not None else ""
            if csosn and not cst_icms:
                cst_icms = csosn
            cst_pis = ""
            cst_cofins = ""
            if imposto is not None:
                for bloco in imposto.iter():
                    tag = _tag(bloco)
                    if tag.startswith("PIS") and tag != "PIS":
                        cst_pis = _buscar_descendente(bloco, "CST") or cst_pis
                    if tag.startswith("COFINS") and tag != "COFINS":
                        cst_cofins = _buscar_descendente(bloco, "CST") or cst_cofins
            tem_st = bool(_buscar_descendente(imposto, "vICMSST") if imposto is not None else "") or cst_icms in {"10", "30", "60", "70", "201", "202", "203", "500"}
            # Apenas INDÍCIO técnico. CST 04/06 em PIS/Cofins pode aparecer em
            # operações monofásicas/alíquota zero, mas não basta para concluir a natureza.
            indicio_mono = cst_pis in {"04", "06"} or cst_cofins in {"04", "06"}
            itens.append(ItemNFe(desc, ncm, cfop, valor, cst_icms, cst_pis, cst_cofins, tem_st, indicio_mono))

    valor_itens = sum(x.valor_produto for x in itens)
    valor_st = sum(x.valor_produto for x in itens if x.tem_st)
    valor_indicio_mono = sum(x.valor_produto for x in itens if x.indicio_monofasico)
    return {
        "emitente": emitente,
        "cnpj_emitente": cnpj_emitente,
        "numero": numero,
        "serie": serie,
        "chave": chave,
        "total_nfe": float(total_nfe),
        "valor_itens": valor_itens,
        "valor_itens_st": valor_st,
        "valor_itens_indicio_monofasico": valor_indicio_mono,
        "itens": [asdict(x) for x in itens],
        "alertas": [
            "A marcação de ICMS-ST é indicativa e baseada em CST/CSOSN e presença de vICMSST no XML.",
            "A marcação de possível monofásico NÃO confirma o tratamento tributário. NCM, produto, CST e legislação específica devem ser validados.",
            "O importador não transmite nem altera a NF-e; apenas lê o XML enviado para apoiar o preenchimento do motor.",
        ],
    }
