"""Páginas públicas: início, estoque e página do veículo."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import obter_sessao
from app.models import Veiculo
from app.servicos import ler_config, link_whatsapp, mensagem_interesse
from app.web import eh_exportacao, render, url_publica

roteador = APIRouter()

NO_INICIO = 6


def consulta_estoque():
    """Veículos que aparecem no site: ativos e não vendidos. Destaques primeiro, depois os mais novos no salão."""
    return (
        select(Veiculo)
        .where(Veiculo.ativo.is_(True), Veiculo.situacao != "vendido")
        .options(selectinload(Veiculo.fotos))
        .order_by(Veiculo.destaque.desc(), (Veiculo.situacao == "reservado").asc(), Veiculo.criado_em.desc())
    )


@roteador.get("/")
def inicio(request: Request, sessao: Session = Depends(obter_sessao)):
    veiculos = list(sessao.scalars(consulta_estoque()))
    return render(
        request, sessao, "loja/inicio.html", {"veiculos": veiculos[:NO_INICIO], "total_estoque": len(veiculos)}
    )


@roteador.get("/estoque")
def estoque(request: Request, sessao: Session = Depends(obter_sessao)):
    veiculos = list(sessao.scalars(consulta_estoque()))
    marcas = sorted({v.marca for v in veiculos})
    cambios = sorted({v.cambio for v in veiculos if v.cambio})
    return render(request, sessao, "loja/estoque.html", {"veiculos": veiculos, "marcas": marcas, "cambios": cambios})


@roteador.get("/veiculo/{slug}")
def veiculo(slug: str, request: Request, sessao: Session = Depends(obter_sessao)):
    item = sessao.scalar(consulta_estoque().where(Veiculo.slug == slug))
    if item is None:
        raise HTTPException(404)
    loja = ler_config(sessao)
    # Na cópia estática cada página é uma pasta, então o link leva a barra no fim.
    endereco = f"{url_publica(request)}/veiculo/{item.slug}" + ("/" if eh_exportacao(request) else "")
    outros = list(sessao.scalars(consulta_estoque().where(Veiculo.id != item.id).limit(3)))
    return render(
        request,
        sessao,
        "loja/veiculo.html",
        {
            "veiculo": item,
            "outros": outros,
            "url_interesse": link_whatsapp(loja["whatsapp"], mensagem_interesse(item, loja, endereco)),
            "url_financiar": link_whatsapp(
                loja["whatsapp"], f"Olá, {loja['nome_loja']}! Quero simular o financiamento do {item.titulo} {item.ano}."
            ),
        },
    )


# ---------------------------------------------------------------- SEO


@roteador.get("/robots.txt", response_class=PlainTextResponse)
def robots(request: Request):
    return f"User-agent: *\nDisallow: /admin\nSitemap: {str(request.base_url).rstrip('/')}/sitemap.xml\n"


@roteador.get("/sitemap.xml")
def sitemap(request: Request, sessao: Session = Depends(obter_sessao)):
    base = str(request.base_url).rstrip("/")
    hoje = date.today().isoformat()
    urls = [f"{base}/", f"{base}/estoque"]
    urls += [f"{base}/veiculo/{v.slug}" for v in sessao.scalars(consulta_estoque())]
    corpo = "".join(f"<url><loc>{u}</loc><lastmod>{hoje}</lastmod></url>" for u in urls)
    xml = f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{corpo}</urlset>'
    return Response(xml, media_type="application/xml")
