/* Painel: confirmações e troca de situação ao escolher no select. */
(() => {
  "use strict";

  document.querySelectorAll("form[data-confirmar]").forEach((form) => {
    form.addEventListener("submit", (e) => {
      if (!confirm(form.dataset.confirmar)) e.preventDefault();
    });
  });

  document.querySelectorAll("[data-enviar-ao-mudar]").forEach((select) => {
    select.addEventListener("change", () => select.form.requestSubmit());
  });
})();
