"""Gera a cópia estática do site para o GitHub Pages e, se pedido, publica.

Lê o site em funcionamento (local ou no Render), salva cada página como HTML e
copia CSS, JS e fotos. A cópia não tem painel: para mudar o estoque, use o painel
e gere a cópia de novo.

Uso:
    uv run python scripts/exportar_pages.py                       # lê http://localhost:8050
    uv run python scripts/exportar_pages.py --origem https://rcar-veiculos.onrender.com
    uv run python scripts/exportar_pages.py --publicar            # gera e envia ao branch gh-pages
"""

import argparse
import re
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit
from xml.etree import ElementTree

RAIZ_PROJETO = Path(__file__).resolve().parent.parent
PADRAO_RAIZ = "/rcar-veiculos"
PADRAO_URL = "https://vampira-lady-gacha.github.io/rcar-veiculos"

# data-foto: miniaturas da galeria do veículo, trocadas pelo site.js.
ATRIBUTO_URL = re.compile(r'(\s(?:href|src|data-foto)=")(/[^"]*)(")')


def baixar(url: str, cabecalhos: dict[str, str] | None = None, aceitar_404: bool = False) -> bytes:
    pedido = urllib.request.Request(url, headers=cabecalhos or {})
    try:
        with urllib.request.urlopen(pedido, timeout=60) as resp:
            return resp.read()
    except urllib.error.HTTPError as erro:
        if aceitar_404 and erro.code == 404:
            return erro.read()
        raise


def destino_da_pagina(caminho: str) -> str:
    """Caminho da página no site → arquivo index.html na pasta de saída."""
    limpo = urlsplit(caminho).path.strip("/")
    return f"{limpo}/index.html" if limpo else "index.html"


def reescrever_url(caminho: str, raiz: str) -> str:
    partes = urlsplit(caminho)
    if partes.path.startswith(("/static/", "/media/")):
        return raiz + caminho
    ancora = f"#{partes.fragment}" if partes.fragment else ""
    if partes.path in ("", "/"):
        return f"{raiz}/{ancora}"
    return f"{raiz}{partes.path.rstrip('/')}/{ancora}"


def exportar(origem: str, raiz: str, url_publica: str, saida: Path) -> list[str]:
    origem = origem.rstrip("/")
    cabecalhos = {"X-Exportar-Estatico": "1", "X-Url-Publica": url_publica}

    mapa = ElementTree.fromstring(baixar(f"{origem}/sitemap.xml"))
    paginas = [urlsplit(loc.text).path for loc in mapa.iter("{http://www.sitemaps.org/schemas/sitemap/0.9}loc")]

    if saida.exists():
        shutil.rmtree(saida)
    saida.mkdir(parents=True)

    arquivos: set[str] = {"/static/img/logo.png"}

    def salvar_html(html: str, arquivo: str) -> None:
        def trocar(m: re.Match) -> str:
            caminho = m.group(2)
            if caminho.startswith(("/static/", "/media/")):
                arquivos.add(urlsplit(caminho).path)
            return m.group(1) + reescrever_url(caminho, raiz) + m.group(3)

        destino = saida / arquivo
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(ATRIBUTO_URL.sub(trocar, html), encoding="utf-8")

    for pagina in paginas:
        salvar_html(baixar(origem + pagina, cabecalhos).decode("utf-8"), destino_da_pagina(pagina))
    salvar_html(baixar(f"{origem}/__pagina-inexistente__", cabecalhos, aceitar_404=True).decode("utf-8"), "404.html")

    for caminho in sorted(arquivos):
        destino = saida / caminho.lstrip("/")
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(baixar(origem + caminho))

    hoje = date.today().isoformat()
    urls = "".join(
        f"<url><loc>{url_publica}/{destino_da_pagina(p).removesuffix('index.html')}</loc><lastmod>{hoje}</lastmod></url>"
        for p in paginas
    )
    (saida / "sitemap.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>',
        encoding="utf-8",
    )
    (saida / "robots.txt").write_text(f"User-agent: *\nSitemap: {url_publica}/sitemap.xml\n", encoding="utf-8")
    (saida / ".nojekyll").write_text("", encoding="utf-8")
    return paginas


def publicar(saida: Path) -> None:
    """Envia a pasta gerada para o branch gh-pages do mesmo repositório (histórico só da cópia)."""
    remoto = subprocess.run(
        ["git", "remote", "get-url", "origin"], cwd=RAIZ_PROJETO, check=True, capture_output=True, text=True
    ).stdout.strip()
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "site"
        shutil.copytree(saida, repo)

        def git(*args: str) -> None:
            subprocess.run(["git", *args], cwd=repo, check=True)

        git("init", "-q", "-b", "gh-pages")
        git("add", "-A")
        git("-c", "user.name=Site R-CAR", "-c", "user.email=site@users.noreply.github.com",
            "commit", "-q", "-m", f"Cópia estática gerada em {date.today().isoformat()}")
        git("push", "-q", "--force", remoto, "gh-pages")


def main() -> None:
    args = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    args.add_argument("--origem", default="http://localhost:8050", help="Site em funcionamento para copiar")
    args.add_argument("--raiz", default=PADRAO_RAIZ, help="Caminho do site no Pages (vazio para domínio próprio)")
    args.add_argument("--url-publica", default=PADRAO_URL, help="Endereço público da cópia")
    args.add_argument("--saida", default=str(RAIZ_PROJETO / "site"), help="Pasta onde gerar o site")
    args.add_argument("--publicar", action="store_true", help="Envia ao branch gh-pages depois de gerar")
    opcoes = args.parse_args()

    saida = Path(opcoes.saida)
    paginas = exportar(opcoes.origem, opcoes.raiz.rstrip("/"), opcoes.url_publica.rstrip("/"), saida)
    print(f"{len(paginas)} páginas geradas em {saida}")
    if opcoes.publicar:
        publicar(saida)
        print("Cópia enviada ao branch gh-pages.")


if __name__ == "__main__":
    main()
