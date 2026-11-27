/* Subir archivos · Print with Brilint */
(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const MAX_FILES = 8;
  const ALLOWED = /^(application\/pdf|image\/(jpeg|png))$/;

  const state = {
    prices: null,
    files: [],          // { file, name, pages, ok }
    uploading: false,
    folio: null,
    status: null,
    quote: null,
    folioData: null,
    poll: null,
    waitTimer: null,
  };

  const el = {
    form: $("step-form"), send: $("step-send"), quoteStep: $("step-quote"), done: $("step-done"),
    file: $("file"), drop: $("drop"), list: $("filelist"), empty: $("empty"),
    count: $("filecount"),
    copies: $("copies"), minus: $("copies-minus"), plus: $("copies-plus"),
    notes: $("notes"), needsNotes: $("needsNotes"), notesWrap: $("notes-wrap"),
    sendBtn: $("send"), err: $("err"),
    bar: $("bar"), barFill: $("bar-fill"), sendSub: $("send-sub"), sendMeta: $("send-meta"),
    measuring: $("measuring"), quoteTicket: $("quote-ticket"), quoteTitle: $("quote-title"),
    quoteSub: $("quote-sub"), qTotal: $("q-total"), qLines: $("q-lines"), qMeta: $("q-meta"),
    confirm: $("confirm"), quoteErr: $("quote-err"), quoteWait: $("quote-wait"),
    folio: $("folio"), status: $("status"), statusText: $("status-text"),
    folioCopies: $("folio-copies"), folioPages: $("folio-pages"), folioTotal: $("folio-total"),
    specialConfirm: $("special-confirm"), confirmVariable: $("confirm-variable"), specialErr: $("special-err"),
    claim: $("claim"), claimCode: $("claim-code"), tap: $("tap"), tapMsg: $("tap-msg"),
    claimHelp: $("claim-help"), claimOr: $("claim-or"), nfc: $("nfc"), tapText: $("tap-text"),
    again: $("again"), maxmb: $("maxmb"),
  };

  const money = (n) =>
    new Intl.NumberFormat("es-MX", { style: "currency", currency: "MXN" }).format(n || 0);
  const num = (n) => new Intl.NumberFormat("es-MX").format(n || 0);

  /* ---------------- tarifario ---------------- */
  async function loadPrices() {
    try {
      const r = await fetch("/api/prices", { headers: { accept: "application/json" } });
      if (!r.ok) throw new Error("precios");
      state.prices = await r.json();
    } catch {
      state.prices = { bw: [{ price: 1.5 }], color: [{ price: 3 }], max_mb: 80, currency: "MXN" };
    }
    const min = (t) => Math.min(...(t || []).map((x) => x.price));
    $("rate-bw").textContent = money(min(state.prices.bw));
    $("rate-color").textContent = money(min(state.prices.color));
    el.maxmb.textContent = state.prices.max_mb;
    render();
  }

  /* ---------------- archivos ---------------- */
  async function countPages(file) {
    if (file.type !== "application/pdf") return 1;
    if (!window.PDFLib) throw new Error("No pudimos leer el PDF. Intenta de nuevo.");
    try {
      const doc = await window.PDFLib.PDFDocument.load(await file.arrayBuffer(), {
        ignoreEncryption: false, updateMetadata: false,
      });
      const n = doc.getPageCount();
      if (!n) throw new Error("El PDF no tiene páginas.");
      return n;
    } catch (e) {
      throw new Error(
        /encrypt/i.test(String(e))
          ? "Ese PDF está protegido. Quita la contraseña o tráelo en USB."
          : "Ese PDF está dañado o protegido. Tráelo en USB o expórtalo de nuevo."
      );
    }
  }

  const totalBytes = () => state.files.reduce((s, f) => s + f.file.size, 0);

  async function addFiles(fileList) {
    const errs = [];
    for (const file of Array.from(fileList)) {
      if (state.files.length >= MAX_FILES) { errs.push(`Máximo ${MAX_FILES} archivos por pedido.`); break; }
      if (!ALLOWED.test(file.type)) { errs.push(`${file.name}: solo PDF, JPG o PNG.`); continue; }
      if (state.files.some((f) => f.name === file.name && f.file.size === file.size)) {
        errs.push(`${file.name}: ya está en la lista.`); continue;
      }
      const entry = { file, name: file.name, pages: 0, ok: false };
      try {
        entry.pages = await countPages(file);
        entry.ok = true;
      } catch (e) {
        entry.err = e.message;
      }
      state.files.push(entry);
    }
    if (totalBytes() > state.prices.max_mb * 1024 * 1024) {
      errs.push(`El total pasa de ${state.prices.max_mb} MB. Quita algún archivo.`);
    }
    render(errs.join(" "));
  }

  function render(errMsg = "") {
    el.list.innerHTML = "";
    for (const [i, f] of state.files.entries()) {
      const li = document.createElement("li");
      if (!f.ok) li.className = "bad";
      const nm = document.createElement("span");
      nm.className = "nm"; nm.textContent = f.name;
      const pg = document.createElement("span");
      pg.className = "pg";
      pg.textContent = f.ok ? `${num(f.pages)} ${f.pages === 1 ? "pág." : "págs."}` : "no se pudo leer";
      const rm = document.createElement("button");
      rm.type = "button"; rm.className = "rm"; rm.textContent = "×";
      rm.setAttribute("aria-label", `Quitar ${f.name}`);
      rm.addEventListener("click", () => { state.files.splice(i, 1); render(); });
      li.append(nm, pg, rm);
      el.list.appendChild(li);
    }

    const ok = state.files.filter((f) => f.ok).length;
    el.empty.hidden = state.files.length > 0;
    el.count.textContent = state.files.length;
    el.count.classList.toggle("on", state.files.length > 0);
    el.drop.classList.toggle("has-files", state.files.length > 0);

    const tooBig = totalBytes() > state.prices.max_mb * 1024 * 1024;
    const needsText = el.needsNotes.checked && el.notes.value.trim().length < 4;
    el.sendBtn.disabled = !(ok > 0 && !tooBig && !state.uploading && !needsText);
    el.sendBtn.textContent = state.uploading ? "Enviando…" : el.needsNotes.checked ? "Enviar pedido" : "Enviar y cotizar";
    el.err.textContent = errMsg || (needsText ? "Escribe qué necesitas, o desactiva la casilla." : "");
  }

  /* ---------------- subida ---------------- */
  function buildForm() {
    const fd = new FormData();
    const okFiles = state.files.filter((f) => f.ok);
    okFiles.forEach((f) => fd.append("files", f.file, f.name));
    fd.append("mode", document.querySelector('input[name="mode"]:checked').value);
    fd.append("copies", String(Math.max(1, Math.min(200, parseInt(el.copies.value, 10) || 1))));
    fd.append("pages", JSON.stringify(okFiles.map((f) => f.pages)));
    fd.append("notes", el.notes.value.trim());
    if (el.needsNotes.checked) fd.append("review", "1");
    return fd;
  }

  function screen(name) {
    for (const k of ["form", "send", "quoteStep", "done"]) el[k].hidden = k !== name;
    window.scrollTo({ top: 0 });
  }

  function submit() {
    if (state.uploading) return;
    const fd = buildForm();
    const bytes = totalBytes();
    state.uploading = true;
    render();
    screen("send");
    el.barFill.style.width = "0%";
    el.sendMeta.textContent = `${(bytes / 1048576).toFixed(1)} MB`;

    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/jobs");
    xhr.upload.onprogress = (e) => {
      if (!e.lengthComputable) return;
      const pct = Math.round((e.loaded / e.total) * 100);
      el.barFill.style.width = pct + "%";
      el.bar.setAttribute("aria-valuenow", String(pct));
      el.sendSub.textContent = pct < 100 ? `Subiendo tus archivos · ${pct}%` : "Registrando tu pedido…";
    };
    xhr.onload = () => {
      state.uploading = false;
      let data = {};
      try { data = JSON.parse(xhr.responseText || "{}"); } catch {}
      if (xhr.status >= 200 && xhr.status < 300 && data.folio) { startQuote(data); return; }
      fail(data.error || "No pudimos recibir tus archivos. Intenta de nuevo o entrégalos en el mostrador.");
    };
    xhr.onerror = () => { state.uploading = false; fail("Se cortó la conexión. Revisa tu señal e intenta de nuevo."); };
    xhr.ontimeout = () => { state.uploading = false; fail("Tardó demasiado. Intenta con menos archivos o desde el WiFi del local."); };
    xhr.timeout = 180000;
    xhr.send(fd);
  }

  function fail(msg) {
    screen("form");
    render(msg);
    window.scrollTo({ top: document.body.scrollHeight });
  }

  /* ---------------- cotización ---------------- */
  function startQuote(data) {
    state.folio = data.folio;
    state.status = data.status || "quoting";
    state.quote = null;
    if (state.status === "review_pending") {
      showDone(data);
      return;
    }
    screen("quoteStep");
    el.measuring.hidden = false;
    el.quoteTicket.hidden = true;
    el.quoteWait.hidden = true;
    el.quoteTitle.textContent = "Cotizando";
    el.quoteSub.textContent = "Estamos midiendo la tinta de cada página.";
    pollQuote();
    clearTimeout(state.waitTimer);
    state.waitTimer = setTimeout(() => {
      if (state.status === "measuring" || state.status === "quoting") {
        el.quoteWait.hidden = false;
        el.quoteWait.textContent = "Está tardando más de lo normal. El mostrador puede estar cerrado; tus archivos ya están guardados y el total aparece al abrir.";
      }
    }, 90000);
  }

  async function pollQuote() {
    clearInterval(state.poll);
    await tickQuote();
    state.poll = setInterval(tickQuote, 2500);
  }

  async function tickQuote() {
    if (!state.folio) return;
    try {
      const r = await fetch(`/api/jobs/${encodeURIComponent(state.folio)}`, { headers: { accept: "application/json" } });
      if (!r.ok) return;
      const d = await r.json();
      state.status = d.status;
      if (d.status === "quoted" && d.quote) {
        clearInterval(state.poll);
        clearTimeout(state.waitTimer);
        state.quote = d.quote;
        showTicket(d);
      } else if (d.status === "review" || d.status === "reviewing") {
        el.quoteTitle.textContent = "En revisión";
        el.quoteSub.textContent = "Lo está revisando el mostrador para respetar tus indicaciones. En un momento aparece tu total.";
      } else if (d.status === "error") {
        clearInterval(state.poll);
        clearTimeout(state.waitTimer);
        el.measuring.hidden = true;
        el.quoteTitle.textContent = "No pudimos cotizar";
        el.quoteSub.textContent = "Lleva tus archivos en USB al mostrador.";
      } else if (d.status === "measuring") {
        el.quoteTitle.textContent = "Cotizando";
        el.quoteSub.textContent = "Leyendo tus archivos y midiendo la tinta de cada página.";
      }
    } catch {}
  }

  function showTicket(d) {
    const q = d.quote;
    el.measuring.hidden = true;
    el.quoteTicket.hidden = false;
    el.quoteTitle.textContent = "Tu total";
    el.quoteSub.textContent = "Medimos cada página. Este es el precio exacto de tu pedido.";
    el.qTotal.textContent = money(q.total);

    el.qLines.innerHTML = "";
    for (const l of q.lines) {
      const li = document.createElement("li");
      const name = document.createElement("span");
      name.className = "ql-name";
      name.innerHTML = `${l.label}<em>${num(l.pages)} ${l.pages === 1 ? "página" : "páginas"} × ${money(l.price)}</em>`;
      const sub = document.createElement("b");
      sub.textContent = money(l.subtotal);
      li.append(name, sub);
      el.qLines.appendChild(li);
    }

    el.qMeta.innerHTML = "";
    const rows = [
      ["Copias", num(q.copies)],
      ["Páginas por juego", num(q.pages)],
      ["Por juego", money(q.per_copy)],
    ];
    for (const [k, v] of rows) {
      const dt = document.createElement("dt"); dt.textContent = k;
      const dd = document.createElement("dd"); dd.textContent = v;
      el.qMeta.append(dt, dd);
    }
    el.quoteErr.textContent = "";
  }

  async function confirm() {
    if (!state.folio) return;
    el.confirm.disabled = true;
    el.confirm.textContent = "Confirmando…";
    try {
      const r = await fetch(`/api/jobs/${encodeURIComponent(state.folio)}/confirm`, {
        method: "POST", headers: { "content-type": "application/json" }, body: "{}",
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.error || "No se pudo confirmar.");
      showDone(d);
    } catch (e) {
      el.confirm.disabled = false;
      el.confirm.textContent = "Confirmar e imprimir";
      el.quoteErr.textContent = e.message || "No se pudo confirmar. Intenta de nuevo.";
    }
  }

  /* ---------------- folio ---------------- */
  async function confirmVariable() {
    const folio = state.folio;
    if (!folio || state.status !== "review_pending") return;
    el.confirmVariable.disabled = true;
    el.specialErr.textContent = "";
    try {
      const r = await fetch(`/api/jobs/${encodeURIComponent(folio)}/confirm`, {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ price_terms: "variable" }),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.error || "No se pudo confirmar.");
      if (state.folio === folio && state.status === "review_pending") renderFolio(d);
    } catch (e) {
      if (state.folio === folio) el.specialErr.textContent = e.message || "No se pudo confirmar. Intenta de nuevo.";
    } finally {
      if (state.folio === folio) el.confirmVariable.disabled = false;
    }
  }

  function showDone(data) {
    state.folioData = null;
    el.specialErr.textContent = "";
    el.confirmVariable.disabled = false;
    const hash = `#folio=${state.folio}`;
    if (location.hash !== hash) history.replaceState(null, "", hash);
    screen("done");
    renderFolio(data);
    startStatusPolling();
  }

  async function restoreFolio() {
    const match = /^#folio=([0-9]{6}-[A-Z2-9]{4})$/.exec(location.hash);
    if (!match) return;
    const folio = match[1];
    screen("send");
    el.sendSub.textContent = "Buscando tu folio…";
    try {
      const r = await fetch(`/api/jobs/${encodeURIComponent(folio)}`);
      if (r.status === 410) {
        state.folio = folio;
        showDone({ folio, status: "expired" });
        return;
      }
      if (!r.ok) throw new Error(r.status === 404 ? "No encontramos ese folio." : "No pudimos recuperar el folio.");
      const d = await r.json();
      state.folio = folio;
      if (d.status === "quoted") startQuote(d);
      else showDone(d);
    } catch (e) {
      fail(e.message || "No pudimos recuperar el folio. Vuelve a cargar esta página.");
    }
  }

  function renderFolio(data) {
    const previous = state.folioData;
    const d = state.folioData = { ...previous, ...data };
    state.status = d.status;
    const awaiting = d.status === "held" || d.status === "review_held";
    const showNfc = awaiting && Boolean(d.code && d.nfc) && "NDEFReader" in window;
    el.folio.textContent = d.folio || state.folio;
    if (previous?.status !== d.status) {
      setStatus(d.status);
      if (!awaiting) stopTap();
      el.tap.disabled = false;
      el.tapMsg.hidden = true;
      nfcEstado("", "Toca aquí y acerca el teléfono");
    }
    el.specialConfirm.hidden = d.status !== "review_pending";
    el.claim.hidden = !(awaiting && d.code);
    el.claimCode.textContent = awaiting ? d.code || "—" : "—";
    el.claimHelp.textContent = d.status === "review_held"
      ? "En cuanto lo tecleen, empezamos a preparar tu pedido."
      : "En cuanto lo tecleen, tu pedido se imprime.";
    el.nfc.hidden = !showNfc;
    el.claimOr.hidden = !showNfc;
    const q = d.quote || state.quote;
    const total = d.total ?? q?.total;
    const details = [
      [el.folioCopies, num(q?.copies ?? d.copies ?? 1)],
      [el.folioPages, num(q?.pages ?? d.pages ?? 0)],
      [el.folioTotal, total == null ? "Por calcular" : money(total)],
    ];
    for (const [node, value] of details) {
      if (node.textContent !== value) node.textContent = value;
    }
  }

  const LABEL = {
    quoting: "Cotizando", measuring: "Cotizando", quoted: "Por confirmar",
    review_pending: "Por confirmar", review_held: "Esperando el código",
    review: "Por preparar", reviewing: "Preparando tu pedido", expired: "Pedido caducado",
    held: "Esperando el código", queued: "En fila", printing: "Imprimiendo",
    done: "Listo para recoger", error: "Necesita revisión",
  };
  function setStatus(s) {
    el.statusText.textContent = LABEL[s] || "En fila";
    el.status.classList.toggle("done", s === "done");
  }

  let tapScan = null;
  function stopTap() {
    tapScan?.abort();
    tapScan = null;
  }
  function nfcEstado(estado, texto) {
    if (!el.nfc) return;
    el.nfc.classList.remove("is-listening", "is-ok", "is-error");
    if (estado) el.nfc.classList.add("is-" + estado);
    if (texto) el.tapText.textContent = texto;
  }
  async function tocarEtiqueta() {
    if (!("NDEFReader" in window) || !state.folio) return;
    stopTap();
    const folio = state.folio;
    const special = state.status === "review_held";
    const scan = tapScan = new AbortController();
    el.tap.disabled = true;
    el.tapMsg.hidden = false;
    nfcEstado("listening", "Acerca el teléfono…");
    try {
      nfcEstado("listening", "Acerca el teléfono a la tarjeta…");
      el.tapMsg.hidden = true;
      const reader = new NDEFReader();
      await reader.scan({ signal: scan.signal });
      if (scan.signal.aborted) return;
      // si nadie acerca la etiqueta en 40 s, se dice en vez de quedarse mudo
      setTimeout(() => {
        if (tapScan === scan && el.tap.disabled) {
          stopTap();
          nfcEstado("error", "No se leyó. Pásalo por el reverso del teléfono o dicta el código.");
          el.tap.disabled = false;
        }
      }, 40000);
      reader.onreading = async (e) => {
        if (tapScan !== scan || state.folio !== folio) return;
        stopTap();
        nfcEstado("ok", special ? "¡Leída! Avisando al mostrador…" : "¡Leída! Mandando tu pedido…");
        try {
          const r = await fetch(`/api/jobs/${encodeURIComponent(folio)}/tap`, {
            method: "POST", headers: { "content-type": "application/json" },
            body: JSON.stringify({ tag: e.serialNumber || "" }),
          });
          const d = await r.json();
          if (!r.ok) throw new Error(d.error || "No se pudo liberar.");
          if (state.folio === folio && ["held", "review_held"].includes(state.status)) renderFolio(d);
        } catch (err) {
          if (state.folio !== folio || !["held", "review_held"].includes(state.status)) return;
          nfcEstado("error", err.message || "No se pudo liberar.");
          el.tapMsg.hidden = false; el.tapMsg.textContent = err.message || "";
          el.tap.disabled = false;
        }
      };
    } catch (e) {
      if (scan.signal.aborted) return;
      stopTap();
      nfcEstado("error", e.name === "NotAllowedError"
        ? "Dale permiso de NFC a Chrome y vuelve a tocar."
        : "No pude usar el NFC de este teléfono. Dicta el código.");
      el.tap.disabled = false;
    }
  }

  function startStatusPolling() {
    clearInterval(state.poll);
    const folio = state.folio;
    let busy = false;
    const tick = async () => {
      if (!folio || state.folio !== folio || document.hidden || busy) return;
      const before = state.status;
      busy = true;
      try {
        const r = await fetch(`/api/jobs/${encodeURIComponent(folio)}`, { headers: { accept: "application/json" } });
        if (state.folio !== folio || state.status !== before) return;
        if (r.status === 410) {
          renderFolio({ status: "expired" });
          clearInterval(state.poll);
          return;
        }
        if (!r.ok) return;
        const d = await r.json();
        if (state.folio !== folio || state.status !== before) return;
        renderFolio(d);
        if (d.status === "done" || d.status === "error") clearInterval(state.poll);
      } catch {} finally { busy = false; }
    };
    state.poll = setInterval(tick, 2500);
    tick();
  }

  /* ---------------- eventos ---------------- */
  el.file.addEventListener("change", (e) => { addFiles(e.target.files); e.target.value = ""; });
  el.drop.addEventListener("dragover", (e) => { e.preventDefault(); el.drop.classList.add("over"); });
  el.drop.addEventListener("dragleave", () => el.drop.classList.remove("over"));
  el.drop.addEventListener("drop", (e) => {
    e.preventDefault(); el.drop.classList.remove("over");
    if (e.dataTransfer?.files?.length) addFiles(e.dataTransfer.files);
  });
  document.querySelectorAll('input[name="mode"]').forEach((r) => r.addEventListener("change", () => render()));
  el.copies.addEventListener("input", () => render());
  el.needsNotes.addEventListener("change", () => {
    el.notesWrap.hidden = !el.needsNotes.checked;
    if (!el.needsNotes.checked) el.notes.value = "";
    else el.notes.focus();
    render();
  });
  el.notes.addEventListener("input", () => render());
  el.minus.addEventListener("click", () => { el.copies.value = Math.max(1, (parseInt(el.copies.value, 10) || 1) - 1); render(); });
  el.plus.addEventListener("click", () => { el.copies.value = Math.min(200, (parseInt(el.copies.value, 10) || 1) + 1); render(); });
  el.sendBtn.addEventListener("click", submit);
  el.tap && el.tap.addEventListener("click", tocarEtiqueta);
  el.confirm.addEventListener("click", confirm);
  el.confirmVariable.addEventListener("click", confirmVariable);
  el.again.addEventListener("click", () => {
    clearInterval(state.poll);
    clearTimeout(state.waitTimer);
    stopTap();
    if (location.hash.startsWith("#folio=")) history.replaceState(null, "", location.pathname + location.search);
    state.files = []; state.folio = null; state.quote = null; state.status = null; state.folioData = null;
    el.done.hidden = true; el.send.hidden = true; el.quoteStep.hidden = true; el.form.hidden = false;
    el.notes.value = "";
    el.needsNotes.checked = false;
    el.notesWrap.hidden = true;
    el.copies.value = "1";
    document.querySelector('input[name="mode"][value="bw"]').checked = true;
    render();
    window.scrollTo({ top: 0 });
  });
  document.addEventListener("visibilitychange", () => {
    if (document.hidden || !state.folio) return;
    // Al volver a la pestaña, retomamos el sondeo que el navegador frenó.
    if (!el.done.hidden) startStatusPolling();
    else if (!el.quoteStep.hidden && el.quoteTicket.hidden) pollQuote();
  });

  loadPrices();
  restoreFolio();
})();
