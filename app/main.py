"""Aplicação FastAPI: site, painel e arquivos estáticos.

Rodar: uv run uvicorn app.main:app --reload --port 8050
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from app import config
from app.db import SessaoLocal
from app.rotas_admin import PrecisaEntrar
from app.rotas_admin import roteador as rotas_admin
from app.rotas_loja import roteador as rotas_loja
from app.seed import preparar
from app.web import render


@asynccontextmanager
async def ciclo(_: FastAPI):
    arquivo = preparar()
    if arquivo:
        print(f"Acesso ao painel salvo em {arquivo}")
    yield


app = FastAPI(title="R-CAR Veículos", lifespan=ciclo, docs_url=None, redoc_url=None)
app.add_middleware(
    SessionMiddleware,
    secret_key=config.SECRET_KEY,
    session_cookie="rcar_sessao",
    max_age=60 * 60 * 12,
    same_site="lax",
    https_only=config.COOKIE_SEGURO,
)

config.PASTA_UPLOADS.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=config.RAIZ / "static"), name="static")
app.mount("/media", StaticFiles(directory=config.PASTA_UPLOADS), name="media")
app.include_router(rotas_loja)
app.include_router(rotas_admin)


@app.exception_handler(PrecisaEntrar)
async def _precisa_entrar(request: Request, _: PrecisaEntrar):
    return RedirectResponse("/admin/entrar", status_code=303)


@app.exception_handler(StarletteHTTPException)
async def _erro_http(request: Request, erro: StarletteHTTPException):
    if request.url.path.startswith(("/static", "/media")):
        return JSONResponse({"erro": erro.detail}, status_code=erro.status_code)
    with SessaoLocal() as sessao:
        return render(request, sessao, "erro.html", {"erro": erro}, erro.status_code)
