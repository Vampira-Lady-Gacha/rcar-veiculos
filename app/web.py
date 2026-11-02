"""Templates e utilidades compartilhadas entre o site e o painel."""

import secrets
from typing import Any

from fastapi import Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app import config
from app.models import SITUACOES
from app.servicos import formatar_telefone, ler_config, link_whatsapp, milhar, quilometros, reais

templates = Jinja2Templates(directory=str(config.RAIZ / "app" / "templates"))
templates.env.filters["reais"] = reais
templates.env.filters["milhar"] = milhar
templates.env.filters["km"] = quilometros
templates.env.filters["telefone"] = formatar_telefone
templates.env.globals.update(link_whatsapp=link_whatsapp, SITUACOES=SITUACOES)


def token_csrf(request: Request) -> str:
    token = request.session.get("csrf")
    if not token:
        token = secrets.token_urlsafe(24)
        request.session["csrf"] = token
    return token


CABECALHO_ESTATICO = "x-exportar-estatico"


def eh_exportacao(request: Request) -> bool:
    """Pedido feito pelo exportador da cópia estática (GitHub Pages)."""
    return request.headers.get(CABECALHO_ESTATICO) == "1"


def url_publica(request: Request) -> str:
    if eh_exportacao(request) and request.headers.get("x-url-publica"):
        return request.headers["x-url-publica"].rstrip("/")
    return config.URL_PUBLICA or str(request.base_url).rstrip("/")


def render(request: Request, sessao: Session, nome: str, contexto: dict[str, Any] | None = None, status: int = 200):
    dados = {
        "request": request,
        "loja": ler_config(sessao),
        "csrf": token_csrf(request),
        "estatico": eh_exportacao(request),
        "url_publica": url_publica(request),
        "aviso": request.session.pop("aviso", None),
    }
    dados.update(contexto or {})
    return templates.TemplateResponse(request, nome, dados, status_code=status)


def avisar(request: Request, texto: str) -> None:
    request.session["aviso"] = texto
