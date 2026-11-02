"""Configuração lida do ambiente (com padrões para desenvolvimento)."""

import os
import secrets
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PASTA_DADOS = Path(os.environ.get("LOJA_DADOS", RAIZ / "dados"))
PASTA_UPLOADS = PASTA_DADOS / "uploads"

DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{(PASTA_DADOS / 'loja.db').as_posix()}")


def _chave_secreta() -> str:
    """Usa SECRET_KEY do ambiente; sem ela, guarda uma chave gerada em dados/."""
    if chave := os.environ.get("SECRET_KEY"):
        return chave
    arquivo = PASTA_DADOS / ".secret_key"
    PASTA_DADOS.mkdir(parents=True, exist_ok=True)
    if not arquivo.exists():
        arquivo.write_text(secrets.token_urlsafe(48), encoding="utf-8")
    return arquivo.read_text(encoding="utf-8").strip()


SECRET_KEY = _chave_secreta()
COOKIE_SEGURO = os.environ.get("COOKIE_SEGURO", "0") == "1"
URL_PUBLICA = os.environ.get("URL_PUBLICA", "").rstrip("/")

TAMANHO_MAX_FOTO = 10 * 1024 * 1024
LADO_MAX_FOTO = 1600
