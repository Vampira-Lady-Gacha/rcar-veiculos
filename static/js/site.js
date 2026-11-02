/* Site: copiar número, galeria do veículo e filtro do estoque (no navegador, para valer também na cópia estática). */
(() => {
  "use strict";

  const toast = document.getElementById("toast");
  function show(texto) {
    toast.textContent = texto;
    toast.hidden = false;
    clearTimeout(show.t);
    show.t = setTimeout(() => (toast.hidden = true), 2000);
  }

  document.querySelectorAll("[data-copy]").forEach((botao) =>
    botao.addEventListener("click", async () => {
      const el = document.getElementById(botao.dataset.copy);
      try {
        await navigator.clipboard.writeText(el.textContent);
        show("Número copiado");
      } catch {
        const r = document.createRange();
        r.selectNodeContents(el);
        const s = getSelection();
        s.removeAllRanges();
        s.addRange(r);
        show("Número selecionado");
      }
    })
  );

  const galeria = document.querySelector("[data-galeria]");
  if (galeria) {
    const principal = galeria.querySelector("[data-foto-principal]");
    galeria.querySelectorAll("[data-foto]").forEach((botao) =>
      botao.addEventListener("click", () => {
        principal.src = botao.dataset.foto;
        principal.alt = botao.dataset.alt;
        galeria.querySelectorAll("[data-foto]").forEach((b) => b.removeAttribute("aria-current"));
        botao.setAttribute("aria-current", "true");
      })
    );
  }

  const filtros = document.querySelector("[data-filtros]");
  if (filtros) {
    const lista = document.querySelector("[data-lista]");
    const carros = [...lista.querySelectorAll("[data-carro]")];
    const contagem = filtros.querySelector("[data-contagem]");
    const semResultado = document.querySelector("[data-sem-resultado]");
    const campo = (nome) => filtros.querySelector(`[data-filtro="${nome}"]`);
    const valor = (nome) => (campo(nome) ? campo(nome).value : "");
    const numero = (c, chave, vazio) => (c.dataset[chave] === "" ? vazio : Number(c.dataset[chave]));
    const ordens = {
      "": (a, b) => numero(a, "ordem", 0) - numero(b, "ordem", 0),
      "menor-preco": (a, b) => numero(a, "preco", Infinity) - numero(b, "preco", Infinity),
      "maior-preco": (a, b) => numero(b, "preco", -Infinity) - numero(a, "preco", -Infinity),
      "mais-novo": (a, b) => numero(b, "ano", 0) - numero(a, "ano", 0),
      "menor-km": (a, b) => numero(a, "km", Infinity) - numero(b, "km", Infinity),
    };

    function aplicar() {
      const termos = valor("busca").toLowerCase().split(/\s+/).filter(Boolean);
      const marca = valor("marca");
      const cambio = valor("cambio");
      let visiveis = 0;
      for (const c of carros) {
        const ok =
          (!marca || c.dataset.marca === marca) &&
          (!cambio || c.dataset.cambio === cambio) &&
          termos.every((t) => c.dataset.busca.includes(t));
        c.hidden = !ok;
        if (ok) visiveis++;
      }
      [...carros].sort(ordens[valor("ordem")] || ordens[""]).forEach((c) => lista.append(c));
      contagem.textContent = `${visiveis} carro${visiveis === 1 ? "" : "s"}`;
      semResultado.hidden = visiveis > 0;
    }

    filtros.addEventListener("input", aplicar);
    filtros.addEventListener("change", aplicar);
  }
})();
