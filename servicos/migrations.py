from __future__ import annotations
from sqlalchemy import text
from extensions import db

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_faturamentos_empresa_comp ON faturamentos (empresa_id, competencia)",
    "CREATE INDEX IF NOT EXISTS idx_folhas_empresa_comp ON folhas (empresa_id, competencia)",
    "CREATE INDEX IF NOT EXISTS idx_apuracoes_empresa_comp ON apuracoes (empresa_id, competencia)",
    "CREATE INDEX IF NOT EXISTS idx_auditoria_data_hora ON auditoria (data_hora)",
    "CREATE INDEX IF NOT EXISTS idx_calculos_regime_empresa ON calculos_regime (empresa_id)",
]

def aplicar_migracoes_seguras() -> None:
    """Migrações aditivas/idempotentes; nunca apagam nem renomeiam dados existentes."""
    try:
        for sql in INDEXES:
            db.session.execute(text(sql))
        db.session.commit()
    except Exception:
        db.session.rollback()
