from __future__ import annotations

import logging
import sys


def configurar_logs() -> logging.Logger:
    logger = logging.getLogger("motor_tributario_jsm")
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger


def registrar_excecao(exc_type, exc_value, exc_tb):
    configurar_logs().exception("Exceção não tratada", exc_info=(exc_type, exc_value, exc_tb))


def instalar_excepthook():
    sys.excepthook = registrar_excecao
