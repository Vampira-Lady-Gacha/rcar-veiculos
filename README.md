# R-CAR Veículos

Site da R-CAR Veículos (Jaru-RO), com showroom, estoque de carros, entregas com laço, financiamento e contato pelo WhatsApp. Tem também um painel para manter o estoque.

## O que tem

**Site (público)**
- Início: o mesmo visual do site original, com a seção "No salão agora" mostrando até 6 carros do estoque.
- Estoque (`/estoque`): todos os carros disponíveis e reservados, com busca e filtro por marca, câmbio e ordem (preço, ano, km). O filtro roda no navegador, então funciona igual na cópia do GitHub Pages.
- Página do veículo: galeria de fotos, preço (ou "Consulte o preço"), ficha (ano, km, câmbio, combustível, cor), opcionais, descrição e botões de WhatsApp com a mensagem pronta: "Tenho interesse" e "Simular financiamento".
- Com o estoque vazio, o site mostra o botão para pedir a lista pelo WhatsApp, como era antes.

**Painel (`/admin`)**
- Início: quantos carros estão disponíveis, reservados e vendidos no mês, além de aviso de carro no site sem foto.
- Veículos: cadastrar, editar, filtrar por situação, buscar e apagar. A situação (disponível, reservado, vendido) muda direto na lista.
  - Reservado continua no site com selo dourado.
  - Vendido sai do site e conta no mês.
- Fotos: enviar várias de uma vez (redimensionadas automaticamente), escolher a capa e apagar.
- Destaque: o carro aparece primeiro, com selo vermelho. "Mostrar no site" desmarcado esconde o carro sem apagar.
- Loja: WhatsApp que recebe os interessados, Instagram, endereço, cidade e horário.
- Minha senha: trocar a senha do painel.

Segurança: senha com scrypt, sessão em cookie assinado, proteção CSRF nos formulários do painel e limite de tentativas de login.

## Rodar no computador

```bash
uv sync
```

```bash
uv run uvicorn app.main:app --reload --port 8050
```

Abra http://localhost:8050. Na primeira execução o banco é criado em `dados/` e o acesso ao painel é salvo em `dados/acesso-painel.txt`. Troque a senha em `/admin/conta`.

Testes:

```bash
uv run pytest
```

## Publicar

No Render, use o `render.yaml` deste repositório: **New → Blueprint**, escolha o repositório e preencha `ADMIN_EMAIL`, `ADMIN_SENHA` e `URL_PUBLICA`. Ele está no **plano gratuito, só para teste**: sem disco, o banco e as fotos se apagam a cada deploy ou reinício, e o serviço dorme sem visitas. Para usar de verdade, troque para o plano Starter com disco (instruções no próprio `render.yaml`).

Em outro serviço que rode Python (Railway, Fly.io, uma VPS), configure as variáveis de ambiente:

| Variável | Para quê |
| --- | --- |
| `SECRET_KEY` | Chave das sessões. Use um valor longo e aleatório. |
| `ADMIN_EMAIL` / `ADMIN_SENHA` | Acesso inicial do painel (só na primeira execução). |
| `LOJA_DADOS` | Pasta do banco e das fotos. Precisa ser um **disco persistente**. |
| `COOKIE_SEGURO=1` | Liga o cookie só em HTTPS (use em produção). |
| `URL_PUBLICA` | Endereço do site, para as prévias de link no WhatsApp (ex.: `https://rcarveiculos.com.br`). |

Comando de início: `uv run uvicorn app.main:app --host 0.0.0.0 --port $PORT`.

Faça backup da pasta `dados/` (banco `loja.db` e `uploads/`).

## Cópia no GitHub Pages

O GitHub Pages só serve arquivos estáticos, então ele recebe uma **cópia do site**: início, estoque e páginas dos veículos, sem o painel. Os carros e preços são os do momento em que a cópia foi gerada.

Para atualizar depois de mudar o estoque no painel, gere a cópia a partir do site no Render (ou do local) e publique:

```bash
uv run python scripts/exportar_pages.py --origem https://rcar-veiculos.onrender.com --publicar
```

Sem `--publicar`, só gera a pasta `site/` para conferir. O envio vai para o branch `gh-pages`. Em **Settings → Pages**, escolha **Deploy from a branch → `gh-pages` / root**. O endereço fica https://vampira-lady-gacha.github.io/rcar-veiculos/.

## Estrutura

| Arquivo | Faz |
| --- | --- |
| `app/models.py` | Tabelas: veículo, foto, configuração, usuário |
| `app/servicos.py` | Formatação de preço e km, situação do veículo, mensagem do WhatsApp, fotos, senhas |
| `app/rotas_loja.py` | Páginas públicas: início, estoque, veículo, sitemap |
| `app/rotas_admin.py` | Painel |
| `app/seed.py` | Cria o banco e o usuário do painel |
| `scripts/exportar_pages.py` | Gera e publica a cópia estática do GitHub Pages |
| `app/templates/` | Páginas (Jinja2) |
| `static/` | CSS, JavaScript, logo e fotos da loja |
