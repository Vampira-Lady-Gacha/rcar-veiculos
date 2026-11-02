"""Cria as tabelas e o usuário do painel.

Uso: uv run python -m app.seed            (só cria o que falta)
     uv run python -m app.seed --senha    (gera uma nova senha para o painel)
"""

import os
import secrets
import sys

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import config
from app.db import Base, SessaoLocal, engine
from app.models import Usuario
from app.servicos import gerar_hash


def criar_tabelas() -> None:
    Base.metadata.create_all(engine)


def garantir_admin(sessao: Session, nova_senha: bool = False) -> str | None:
    """Cria o usuário do painel. Devolve onde a senha foi salva quando ela foi gerada agora."""
    email = os.environ.get("ADMIN_EMAIL", "admin@rcarveiculos.com.br").strip().lower()
    usuario = sessao.scalar(select(Usuario).where(Usuario.email == email))
    if usuario and not nova_senha:
        return None
    senha = os.environ.get("ADMIN_SENHA") or secrets.token_urlsafe(9)
    if usuario is None:
        usuario = Usuario(email=email, nome="R-CAR", senha_hash=gerar_hash(senha))
        sessao.add(usuario)
    else:
        usuario.senha_hash = gerar_hash(senha)
    sessao.commit()
    if os.environ.get("ADMIN_SENHA"):
        return None
    arquivo = config.PASTA_DADOS / "acesso-painel.txt"
    arquivo.write_text(f"E-mail: {email}\nSenha: {senha}\nTroque a senha em /admin/conta.\n", encoding="utf-8")
    return str(arquivo)


def preparar(nova_senha: bool = False) -> str | None:
    criar_tabelas()
    with SessaoLocal() as sessao:
        return garantir_admin(sessao, nova_senha)


if __name__ == "__main__":
    gerado = preparar(nova_senha="--senha" in sys.argv)
    if gerado:
        print(f"Acesso ao painel salvo em {gerado}")
    print("Banco pronto.")
