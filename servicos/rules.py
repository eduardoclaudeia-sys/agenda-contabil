from __future__ import annotations

import hashlib
import json
from pathlib import Path

from extensions import db
from models import RegraTributariaRegistro

BASE = Path(__file__).resolve().parents[1] / "regras"


def _checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def _checksum_many(*paths: Path) -> str:
    h = hashlib.sha256()
    for path in paths:
        h.update(path.read_bytes())
    return h.hexdigest()


def _upsert(regime: str, versao: str, inicio: str, fim: str | None, fonte: str, path: Path, checksum: str | None = None) -> None:
    row = RegraTributariaRegistro.query.filter_by(regime=regime, versao=versao).first()
    if not row:
        row = RegraTributariaRegistro(regime=regime, versao=versao, vigencia_inicio=inicio)
        db.session.add(row)
    row.vigencia_fim = fim
    row.fonte = fonte
    row.checksum = checksum or _checksum(path)
    row.ativa = True


def registrar_regras_arquivo() -> None:
    """Registra no banco metadados/checksum das regras versionadas em arquivo.

    As regras permanecem versionadas no repositório; o banco guarda rastreabilidade,
    sem permitir que uma edição administrativa acidental altere fórmulas em produção.
    """
    try:
        # Simples
        idx = json.loads((BASE / "simples" / "indice.json").read_text(encoding="utf-8"))
        for item in idx.get("versoes", []):
            path = BASE / "simples" / item["regras"]
            repart = BASE / "simples" / item["reparticao"]
            fonte = "; ".join(item.get("fontes", []))
            _upsert("Simples Nacional", item["versao"], item["vigencia_inicio"], item.get("vigencia_fim"), fonte, path, _checksum_many(path, repart))

        # Presumido e Real
        for pasta, regime in (("presumido", "Lucro Presumido"), ("real", "Lucro Real")):
            idx = json.loads((BASE / pasta / "indice.json").read_text(encoding="utf-8"))
            for item in idx.get("versoes", []):
                path = BASE / pasta / item["arquivo"]
                dados = json.loads(path.read_text(encoding="utf-8"))
                fonte = dados.get("fonte_oficial") or "; ".join(dados.get("fontes", []))
                _upsert(regime, item["versao"], item["vigencia_inicio"], item.get("vigencia_fim"), fonte, path)
        db.session.commit()
    except Exception:
        db.session.rollback()
        # Não derruba a aplicação por falha de registro auxiliar; os motores leem
        # as regras diretamente dos arquivos versionados.
