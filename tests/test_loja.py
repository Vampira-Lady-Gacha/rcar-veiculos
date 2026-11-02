from io import BytesIO
from urllib.parse import unquote

from PIL import Image
from sqlalchemy import select

from app.models import Veiculo
from app.servicos import ler_centavos, ler_inteiro, quilometros, reais, slugificar
from tests.conftest import ONIX, csrf_de


def _veiculo(sessao, modelo="Onix") -> Veiculo:
    sessao.expire_all()
    return sessao.scalar(select(Veiculo).where(Veiculo.modelo == modelo))


def _jpeg() -> bytes:
    saida = BytesIO()
    Image.new("RGB", (40, 30), "red").save(saida, "JPEG")
    return saida.getvalue()


def test_utilidades():
    assert reais(8990000) == "R$ 89.900"
    assert reais(8990050) == "R$ 89.900,50"
    assert ler_centavos("89.900") == 8990000
    assert ler_centavos("R$ 89.900,00") == 8990000
    assert ler_centavos("89900") == 8990000
    assert ler_centavos("") is None
    assert ler_inteiro("45.000 km") == 45000
    assert quilometros(45000) == "45.000 km" and quilometros(0) == "0 km"
    assert slugificar("Citroën C4 Cactus 2022") == "citroen-c4-cactus-2022"


def test_paginas_publicas_com_estoque_vazio(cliente):
    for url in ["/", "/estoque", "/sitemap.xml", "/robots.txt"]:
        assert cliente.get(url).status_code == 200, url
    assert "Pedir a lista" in cliente.get("/estoque").text
    assert cliente.get("/veiculo/nao-existe").status_code == 404


def test_painel_exige_login(cliente):
    resp = cliente.get("/admin/veiculos", follow_redirects=False)
    assert resp.status_code == 303 and resp.headers["location"] == "/admin/entrar"


def test_login_errado(cliente):
    pagina = cliente.get("/admin/entrar")
    r = cliente.post("/admin/entrar", data={"email": "teste@rcar.com", "senha": "x", "csrf": csrf_de(pagina.text)})
    assert r.status_code == 401


def test_post_sem_csrf_e_recusado(admin):
    assert admin.post("/admin/veiculos/novo", data={"marca": "Fiat", "modelo": "Uno"}).status_code == 400


def test_cadastrar_veiculo_aparece_no_site(cadastrar, cliente, sessao):
    r = cadastrar()
    assert r.status_code == 303
    v = _veiculo(sessao)
    assert v.preco == 8990000 and v.km == 45000
    assert v.slug == "chevrolet-onix-1-0-turbo-ltz-2022"
    assert v.ano == "2021/2022"
    assert v.lista_opcionais == ["Ar-condicionado", "Câmera de ré"]

    estoque = cliente.get("/estoque").text
    assert "Onix" in estoque and "R$ 89.900" in estoque and "45.000 km" in estoque
    pagina = cliente.get(f"/veiculo/{v.slug}")
    assert pagina.status_code == 200
    assert "Câmera de ré" in pagina.text
    texto = unquote(pagina.text)
    assert "Tenho interesse no Chevrolet Onix 1.0 Turbo LTZ 2021/2022 (R$ 89.900)." in texto


def test_preco_vazio_mostra_consulte(cadastrar, cliente):
    cadastrar(preco="")
    assert "Consulte o preço" in cliente.get("/estoque").text


def test_validacao_dos_anos(cadastrar):
    r = cadastrar(ano_fabricacao="2021", ano_modelo="2024")
    assert r.status_code == 422 and "ano do modelo" in r.text
    assert cadastrar(ano_fabricacao="1900").status_code == 422
    assert cadastrar(marca="").status_code == 422


def test_vendido_sai_do_site_e_conta_no_mes(cadastrar, admin, cliente, sessao):
    cadastrar()
    v = _veiculo(sessao)
    csrf = csrf_de(admin.get("/admin/veiculos").text)
    admin.post(f"/admin/veiculos/{v.id}/situacao", data={"csrf": csrf, "situacao": "vendido"})
    v = _veiculo(sessao)
    assert v.situacao == "vendido" and v.vendido_em is not None
    assert cliente.get(f"/veiculo/{v.slug}").status_code == 404
    assert "Onix" not in cliente.get("/estoque").text
    assert "Onix" in admin.get("/admin/veiculos?situacao=vendido").text

    admin.post(f"/admin/veiculos/{v.id}/situacao", data={"csrf": csrf, "situacao": "disponivel"})
    assert _veiculo(sessao).vendido_em is None


def test_reservado_continua_no_site_com_selo(cadastrar, cliente):
    cadastrar(situacao="reservado")
    assert "Reservado" in cliente.get("/estoque").text


def test_oculto_nao_aparece(cadastrar, cliente):
    cadastrar(ativo=None)
    assert "Onix" not in cliente.get("/").text


def test_editar_veiculo(cadastrar, admin, sessao):
    cadastrar()
    v = _veiculo(sessao)
    csrf = csrf_de(admin.get(f"/admin/veiculos/{v.id}").text)
    admin.post(f"/admin/veiculos/{v.id}", data={**ONIX, "preco": "85.000", "km": "46.200", "csrf": csrf})
    v = _veiculo(sessao)
    assert v.preco == 8500000 and v.km == 46200


def test_fotos_capa_e_apagar(cadastrar, admin, sessao, cliente):
    cadastrar()
    v = _veiculo(sessao)
    csrf = csrf_de(admin.get(f"/admin/veiculos/{v.id}").text)
    arquivos = [("fotos", ("a.jpg", _jpeg(), "image/jpeg")), ("fotos", ("b.jpg", _jpeg(), "image/jpeg"))]
    admin.post(f"/admin/veiculos/{v.id}/fotos", data={"csrf": csrf}, files=arquivos)
    v = _veiculo(sessao)
    assert len(v.fotos) == 2
    (primeira, arquivo), segunda = (v.fotos[0].id, v.fotos[0].arquivo), v.fotos[1].id
    assert cliente.get(f"/media/{arquivo}").status_code == 200

    admin.post(f"/admin/veiculos/{v.id}/fotos/{segunda}/capa", data={"csrf": csrf})
    assert _veiculo(sessao).foto_capa.id == segunda

    admin.post(f"/admin/veiculos/{v.id}/fotos/{primeira}/apagar", data={"csrf": csrf})
    assert [f.id for f in _veiculo(sessao).fotos] == [segunda]
    assert cliente.get(f"/media/{arquivo}").status_code == 404


def test_foto_invalida_e_recusada(cadastrar, admin, sessao):
    cadastrar()
    v = _veiculo(sessao)
    csrf = csrf_de(admin.get(f"/admin/veiculos/{v.id}").text)
    r = admin.post(f"/admin/veiculos/{v.id}/fotos", data={"csrf": csrf}, files=[("fotos", ("x.jpg", b"nada", "image/jpeg"))])
    assert "não é uma imagem válida" in r.text
    assert _veiculo(sessao).fotos == []


def test_apagar_veiculo(cadastrar, admin, sessao):
    cadastrar()
    v = _veiculo(sessao)
    csrf = csrf_de(admin.get(f"/admin/veiculos/{v.id}").text)
    admin.post(f"/admin/veiculos/{v.id}/apagar", data={"csrf": csrf})
    assert _veiculo(sessao) is None


def test_configuracoes_mudam_whatsapp(admin, cadastrar, cliente, sessao):
    csrf = csrf_de(admin.get("/admin/configuracoes").text)
    admin.post("/admin/configuracoes", data={"csrf": csrf, "whatsapp": "+55 (69) 91111-2222", "nome_loja": "R-CAR Veículos"})
    cadastrar()
    v = _veiculo(sessao)
    assert "https://wa.me/5569911112222?text=" in cliente.get(f"/veiculo/{v.slug}").text


def test_modo_estatico_usa_url_publica(cadastrar, cliente, sessao):
    cadastrar()
    v = _veiculo(sessao)
    cabecalhos = {"X-Exportar-Estatico": "1", "X-Url-Publica": "https://exemplo.github.io/rcar"}
    html = cliente.get(f"/veiculo/{v.slug}", headers=cabecalhos).text
    assert 'class="estatico"' in html
    assert unquote(f"https://exemplo.github.io/rcar/veiculo/{v.slug}/") in unquote(html)
