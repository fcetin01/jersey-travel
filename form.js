// Hizmet sayfaları: menü + talep formu. Form, Google Apps Script web uygulamasına gönderir;
// betik talebi info@gustovaturizm.com adresine e-posta olarak iletir (kaynak: ~/jersey-travel/tedarikci-hizmet-icerik/apps-script/).
// FORM_URL, Apps Script "Dağıt → Web uygulaması" adımından sonra verilen /exec adresidir.
const FORM_URL = "";

(function () {
  const yr = document.getElementById("yr");
  if (yr) yr.textContent = new Date().getFullYear();

  const burger = document.querySelector(".burger"), menu = document.getElementById("menu");
  if (burger && menu) burger.addEventListener("click", () => {
    const acik = menu.classList.toggle("open");
    burger.setAttribute("aria-expanded", acik);
  });

  const utm = {};
  new URLSearchParams(location.search).forEach((v, k) => { if (k.startsWith("utm_")) utm[k] = v.slice(0, 100); });

  document.querySelectorAll("form[data-talep]").forEach((form) => {
    const durum = form.querySelector(".durum"), btn = form.querySelector("button[type=submit]");
    const yaz = (metin, tur) => { durum.textContent = metin; durum.className = "tam durum " + (tur || ""); };
    form.querySelectorAll("input,select,textarea").forEach((el) => el.addEventListener("blur", () => el.setAttribute("data-dokundu", "")));

    form.addEventListener("submit", async (ev) => {
      ev.preventDefault();
      form.querySelectorAll("input,select,textarea").forEach((el) => el.setAttribute("data-dokundu", ""));
      if (!form.checkValidity()) {
        const ilk = form.querySelector(":invalid");
        yaz(ilk && ilk.name === "kvkk" ? "Lütfen KVKK aydınlatma metnini onaylayın." : "Lütfen yıldızlı alanları doldurun.", "hata");
        if (ilk) ilk.focus();
        return;
      }
      if (!FORM_URL) { yaz("Form şu an bağlı değil. Lütfen WhatsApp'tan ya da info@gustovaturizm.com adresinden yazın.", "hata"); return; }
      const veri = new URLSearchParams(new FormData(form));
      veri.set("sayfa", location.pathname);
      Object.entries(utm).forEach(([k, v]) => veri.set(k, v));
      btn.disabled = true; yaz("Gönderiliyor…");
      try {
        const yanit = await fetch(FORM_URL, { method: "POST", body: veri });
        const j = await yanit.json().catch(() => ({}));
        if (!yanit.ok || j.ok !== true) throw new Error(j.hata || "gönderilemedi");
        form.reset();
        yaz("Talebiniz alındı. Hafta içi aynı iş günü size dönüş yapacağız.", "ok");
      } catch (e) {
        yaz("Gönderilemedi. Lütfen tekrar deneyin ya da WhatsApp'tan yazın.", "hata");
      } finally { btn.disabled = false; }
    });
  });
})();
