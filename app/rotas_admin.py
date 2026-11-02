"""Painel da loja: veículos, fotos, situação (disponível, reservado, vendido) e configurações."""

import time
from collections import defaultdict
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload
# request.form() devolve o UploadFile do Starlette; o do FastAPI é subclasse e não casaria no isinstance.
from starlette.datastructures import FormData, UploadFile

from app.db import obter_sessao
from app.models import CAMBIOS, COMBUSTIVEIS, MARCAS, SITUACOES, Foto, Usuario, Veiculo
from app.servicos import (
    ROTULOS_CONFIG,
    apagar_arquivo_foto,
    autenticar,
    conferir_senha,
    gerar_hash,
    ler_centavos,
    ler_inteiro,
    mudar_situacao,
    salvar_config,
    salvar_foto,
    slug_unico,
)
from app.web import avisar, render

roteador = APIRouter(prefix="/admin")

_tentativas: dict[str, list[float]] = defaultdict(list)


class PrecisaEntrar(Exception):
    pass


def usuario_logado(request: Request, sessao: Session = Depends(obter_sessao)) -> Usuario:
    usuario_id = request.session.get("usuario_id")
    usuario = sessao.get(Usuario, usuario_id) if usuario_id else None
    if usuario is None:
        raise PrecisaEntrar()
    return usuario


async def formulario(request: Request) -> FormData:
    """Lê o formulário e confere o token CSRF de todo POST do painel."""
    dados = await request.form()
    if not request.session.get("csrf") or dados.get("csrf") != request.session["csrf"]:
        raise HTTPException(400, "Formulário expirado. Volte, recarregue a página e tente de novo.")
    return dados


def voltar(url: str) -> RedirectResponse:
    return RedirectResponse(url, status_code=303)


# ---------------------------------------------------------------- acesso


@roteador.get("/entrar")
def tela_entrar(request: Request, sessao: Session = Depends(obter_sessao)):
    return render(request, sessao, "admin/entrar.html", {"erro": None})


@roteador.post("/entrar")
async def entrar(request: Request, sessao: Session = Depends(obter_sessao)):
    dados = await formulario(request)
    ip = request.client.host if request.client else "?"
    agora = time.monotonic()
    _tentativas[ip] = [t for t in _tentativas[ip] if agora - t < 600]
    if len(_tentativas[ip]) >= 8:
        return render(request, sessao, "admin/entrar.html", {"erro": "Muitas tentativas. Espere 10 minutos."}, 429)
    usuario = autenticar(sessao, str(dados.get("email", "")), str(dados.get("senha", "")))
    if usuario is None:
        _tentativas[ip].append(agora)
        return render(request, sessao, "admin/entrar.html", {"erro": "E-mail ou senha não conferem."}, 401)
    _tentativas.pop(ip, None)
    request.session.clear()
    request.session["usuario_id"] = usuario.id
    return voltar("/admin")


@roteador.post("/sair")
async def sair(request: Request):
    await formulario(request)
    request.session.clear()
    return voltar("/admin/entrar")


@roteador.get("/conta")
def tela_conta(request: Request, usuario: Usuario = Depends(usuario_logado), sessao: Session = Depends(obter_sessao)):
    return render(request, sessao, "admin/conta.html", {"usuario": usuario, "erro": None})


@roteador.post("/conta")
async def salvar_conta(request: Request, usuario: Usuario = Depends(usuario_logado), sessao: Session = Depends(obter_sessao)):
    dados = await formulario(request)
    atual, nova = str(dados.get("senha_atual", "")), str(dados.get("senha_nova", ""))
    erro = None
    if not conferir_senha(atual, usuario.senha_hash):
        erro = "A senha atual não confere."
    elif len(nova) < 8:
        erro = "A nova senha precisa de pelo menos 8 caracteres."
    elif nova != dados.get("senha_confirma"):
        erro = "A confirmação não é igual à nova senha."
    if erro:
        return render(request, sessao, "admin/conta.html", {"usuario": usuario, "erro": erro}, 422)
    usuario.senha_hash = gerar_hash(nova)
    sessao.commit()
    avisar(request, "Senha alterada.")
    return voltar("/admin/conta")


# ---------------------------------------------------------------- painel


def _contagem_situacao(sessao: Session) -> dict[str, int]:
    return dict(sessao.execute(select(Veiculo.situacao, func.count(Veiculo.id)).group_by(Veiculo.situacao)).all())


@roteador.get("")
def painel(request: Request, usuario: Usuario = Depends(usuario_logado), sessao: Session = Depends(obter_sessao)):
    inicio_mes = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    vendidos_mes = sessao.scalar(
        select(func.count(Veiculo.id)).where(Veiculo.situacao == "vendido", Veiculo.vendido_em >= inicio_mes)
    )
    no_site = list(
        sessao.scalars(
            select(Veiculo)
            .where(Veiculo.ativo.is_(True), Veiculo.situacao != "vendido")
            .options(selectinload(Veiculo.fotos))
            .order_by(Veiculo.criado_em.desc())
        )
    )
    return render(
        request,
        sessao,
        "admin/painel.html",
        {
            "usuario": usuario,
            "contagem": _contagem_situacao(sessao),
            "vendidos_mes": vendidos_mes,
            "no_site": no_site,
            "sem_foto": [v for v in no_site if not v.fotos],
            "sem_preco": [v for v in no_site if v.preco is None],
        },
    )


# ---------------------------------------------------------------- veículos


@roteador.get("/veiculos")
def lista_veiculos(
    request: Request,
    situacao: str = "",
    q: str = "",
    usuario: Usuario = Depends(usuario_logado),
    sessao: Session = Depends(obter_sessao),
):
    consulta = select(Veiculo).options(selectinload(Veiculo.fotos))
    if situacao in SITUACOES:
        consulta = consulta.where(Veiculo.situacao == situacao)
    if q.strip():
        termo = f"%{q.strip()}%"
        consulta = consulta.where(Veiculo.marca.ilike(termo) | Veiculo.modelo.ilike(termo) | Veiculo.versao.ilike(termo))
    veiculos = list(sessao.scalars(consulta.order_by(Veiculo.criado_em.desc(), Veiculo.id.desc())))
    return render(
        request,
        sessao,
        "admin/veiculos.html",
        {"usuario": usuario, "veiculos": veiculos, "situacao": situacao, "q": q, "contagem": _contagem_situacao(sessao)},
    )


def _contexto_form(usuario: Usuario, veiculo: Veiculo | None, erro: str | None = None, dados=None) -> dict:
    return {
        "usuario": usuario,
        "veiculo": veiculo,
        "erro": erro,
        "dados": dados or {},
        "MARCAS": MARCAS,
        "CAMBIOS": CAMBIOS,
        "COMBUSTIVEIS": COMBUSTIVEIS,
        "ano_atual": datetime.now().year,
    }


@roteador.get("/veiculos/novo")
def novo_veiculo(request: Request, usuario: Usuario = Depends(usuario_logado), sessao: Session = Depends(obter_sessao)):
    return render(request, sessao, "admin/veiculo_form.html", _contexto_form(usuario, None))


def _ler_ano(dados: FormData, campo: str, rotulo: str) -> int:
    ano = ler_inteiro(str(dados.get(campo, "")))
    limite = datetime.now().year + 1
    if ano is None or not 1950 <= ano <= limite:
        raise ValueError(f"Informe o {rotulo} entre 1950 e {limite}.")
    return ano


def _aplicar_dados(sessao: Session, veiculo: Veiculo, dados: FormData) -> None:
    marca = str(dados.get("marca", "")).strip()
    modelo = str(dados.get("modelo", "")).strip()
    if not marca or not modelo:
        raise ValueError("Informe a marca e o modelo.")
    fabricacao = _ler_ano(dados, "ano_fabricacao", "ano de fabricação")
    ano_modelo = _ler_ano(dados, "ano_modelo", "ano do modelo")
    if not fabricacao <= ano_modelo <= fabricacao + 1:
        raise ValueError("O ano do modelo deve ser igual ao de fabricação ou o seguinte.")
    situacao = str(dados.get("situacao", "disponivel"))
    if situacao not in SITUACOES:
        raise ValueError("Escolha a situação do veículo.")

    veiculo.marca = marca[:40]
    veiculo.modelo = modelo[:60]
    veiculo.versao = str(dados.get("versao", "")).strip()[:80]
    veiculo.ano_fabricacao = fabricacao
    veiculo.ano_modelo = ano_modelo
    veiculo.km = ler_inteiro(str(dados.get("km", "")))
    veiculo.cambio = str(dados.get("cambio", "")).strip()[:20]
    veiculo.combustivel = str(dados.get("combustivel", "")).strip()[:20]
    veiculo.cor = str(dados.get("cor", "")).strip()[:30]
    veiculo.preco = ler_centavos(str(dados.get("preco", "")))
    veiculo.descricao = str(dados.get("descricao", "")).strip()
    veiculo.opcionais = "\n".join(
        linha.strip() for linha in str(dados.get("opcionais", "")).splitlines() if linha.strip()
    )
    veiculo.ativo = dados.get("ativo") == "on"
    veiculo.destaque = dados.get("destaque") == "on"
    veiculo.slug = slug_unico(sessao, f"{veiculo.titulo} {ano_modelo}", veiculo.id)
    mudar_situacao(veiculo, situacao)


@roteador.post("/veiculos/novo")
async def criar_veiculo(request: Request, usuario: Usuario = Depends(usuario_logado), sessao: Session = Depends(obter_sessao)):
    dados = await formulario(request)
    veiculo = Veiculo()
    try:
        _aplicar_dados(sessao, veiculo, dados)
    except ValueError as erro:
        return render(request, sessao, "admin/veiculo_form.html", _contexto_form(usuario, None, str(erro), dados), 422)
    sessao.add(veiculo)
    sessao.commit()
    avisar(request, "Veículo cadastrado. Agora envie as fotos.")
    return voltar(f"/admin/veiculos/{veiculo.id}#fotos")


def _carregar_veiculo(sessao: Session, veiculo_id: int) -> Veiculo:
    veiculo = sessao.scalar(select(Veiculo).where(Veiculo.id == veiculo_id).options(selectinload(Veiculo.fotos)))
    if veiculo is None:
        raise HTTPException(404)
    return veiculo


@roteador.get("/veiculos/{veiculo_id}")
def editar_veiculo(
    veiculo_id: int, request: Request, usuario: Usuario = Depends(usuario_logado), sessao: Session = Depends(obter_sessao)
):
    veiculo = _carregar_veiculo(sessao, veiculo_id)
    return render(request, sessao, "admin/veiculo_form.html", _contexto_form(usuario, veiculo))


@roteador.post("/veiculos/{veiculo_id}")
async def salvar_veiculo(
    veiculo_id: int, request: Request, usuario: Usuario = Depends(usuario_logado), sessao: Session = Depends(obter_sessao)
):
    dados = await formulario(request)
    veiculo = _carregar_veiculo(sessao, veiculo_id)
    try:
        _aplicar_dados(sessao, veiculo, dados)
    except ValueError as erro:
        sessao.rollback()
        veiculo = _carregar_veiculo(sessao, veiculo_id)
        return render(request, sessao, "admin/veiculo_form.html", _contexto_form(usuario, veiculo, str(erro), dados), 422)
    sessao.commit()
    avisar(request, "Dados do veículo salvos.")
    return voltar(f"/admin/veiculos/{veiculo.id}")


@roteador.post("/veiculos/{veiculo_id}/situacao")
async def situacao_veiculo(
    veiculo_id: int, request: Request, usuario: Usuario = Depends(usuario_logado), sessao: Session = Depends(obter_sessao)
):
    """Troca rápida pela lista: marcar como reservado ou vendido sem abrir o cadastro."""
    dados = await formulario(request)
    veiculo = _carregar_veiculo(sessao, veiculo_id)
    nova = str(dados.get("situacao", ""))
    try:
        mudar_situacao(veiculo, nova)
    except ValueError as erro:
        raise HTTPException(400, str(erro)) from erro
    sessao.commit()
    avisar(request, f"{veiculo.titulo}: {SITUACOES[nova].lower()}.")
    destino = str(dados.get("voltar", ""))
    return voltar(destino if destino.startswith("/admin") else "/admin/veiculos")


@roteador.post("/veiculos/{veiculo_id}/fotos")
async def enviar_fotos(
    veiculo_id: int, request: Request, usuario: Usuario = Depends(usuario_logado), sessao: Session = Depends(obter_sessao)
):
    dados = await formulario(request)
    veiculo = _carregar_veiculo(sessao, veiculo_id)
    arquivos = [a for a in dados.getlist("fotos") if isinstance(a, UploadFile) and a.filename]
    proxima = max((f.ordem for f in veiculo.fotos), default=-1) + 1
    erros, enviadas = [], 0
    for arquivo in arquivos[:20]:
        try:
            nome = salvar_foto(await arquivo.read())
        except ValueError as erro:
            erros.append(f"{arquivo.filename}: {erro}")
            continue
        veiculo.fotos.append(Foto(arquivo=nome, ordem=proxima))
        proxima += 1
        enviadas += 1
    sessao.commit()
    avisar(request, "; ".join(erros) if erros else f"{enviadas} foto(s) enviada(s).")
    return voltar(f"/admin/veiculos/{veiculo.id}#fotos")


@roteador.post("/veiculos/{veiculo_id}/fotos/{foto_id}/{acao}")
async def acao_foto(
    veiculo_id: int,
    foto_id: int,
    acao: str,
    request: Request,
    usuario: Usuario = Depends(usuario_logado),
    sessao: Session = Depends(obter_sessao),
):
    await formulario(request)
    veiculo = _carregar_veiculo(sessao, veiculo_id)
    foto = next((f for f in veiculo.fotos if f.id == foto_id), None)
    if foto is None:
        raise HTTPException(404)
    if acao == "apagar":
        veiculo.fotos.remove(foto)
        sessao.commit()
        apagar_arquivo_foto(foto.arquivo)
    elif acao == "capa":
        for posicao, f in enumerate([foto] + [f for f in veiculo.fotos if f is not foto]):
            f.ordem = posicao
        sessao.commit()
    else:
        raise HTTPException(404)
    return voltar(f"/admin/veiculos/{veiculo.id}#fotos")


@roteador.post("/veiculos/{veiculo_id}/apagar")
async def apagar_veiculo(
    veiculo_id: int, request: Request, usuario: Usuario = Depends(usuario_logado), sessao: Session = Depends(obter_sessao)
):
    await formulario(request)
    veiculo = _carregar_veiculo(sessao, veiculo_id)
    arquivos = [f.arquivo for f in veiculo.fotos]
    sessao.delete(veiculo)
    sessao.commit()
    for nome in arquivos:
        apagar_arquivo_foto(nome)
    avisar(request, f"“{veiculo.titulo}” apagado.")
    return voltar("/admin/veiculos")


# ---------------------------------------------------------------- configurações


@roteador.get("/configuracoes")
def tela_config(request: Request, usuario: Usuario = Depends(usuario_logado), sessao: Session = Depends(obter_sessao)):
    return render(request, sessao, "admin/configuracoes.html", {"usuario": usuario, "rotulos": ROTULOS_CONFIG})


@roteador.post("/configuracoes")
async def gravar_config(request: Request, usuario: Usuario = Depends(usuario_logado), sessao: Session = Depends(obter_sessao)):
    dados = await formulario(request)
    salvar_config(sessao, {chave: str(dados.get(chave, "")) for chave in ROTULOS_CONFIG})
    avisar(request, "Configurações salvas.")
    return voltar("/admin/configuracoes")
