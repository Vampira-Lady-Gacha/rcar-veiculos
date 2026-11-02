from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app import config


class Base(DeclarativeBase):
    pass


def criar_engine(url: str = config.DATABASE_URL):
    if url.startswith("sqlite:///"):
        config.PASTA_DADOS.mkdir(parents=True, exist_ok=True)
    engine = create_engine(url, connect_args={"check_same_thread": False} if url.startswith("sqlite") else {})
    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _pragma(conexao, _):
            cursor = conexao.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()
    return engine


engine = criar_engine()
SessaoLocal = sessionmaker(bind=engine, expire_on_commit=False)


def obter_sessao() -> Iterator[Session]:
    with SessaoLocal() as sessao:
        yield sessao
