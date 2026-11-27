(() => {
  const info = document.getElementById("info");
  const res = document.getElementById("res");
  const btn = document.getElementById("probar");
  const ua = navigator.userAgent;
  const lines = [
    "NDEFReader: " + ("NDEFReader" in window ? "SÍ" : "NO"),
    "Chrome: " + (navigator.userAgentData ? "sí" : "¿?"),
    "seguro (https): " + (window.isSecureContext ? "sí" : "NO"),
    "Android: " + (/Android/i.test(ua) ? "sí" : "no"),
    "navegador: " + ua,
  ];
  info.textContent = lines.join("\n");

  btn.addEventListener("click", async () => {
    res.textContent = "Escuchando… acerca la etiqueta al teléfono";
    if (!("NDEFReader" in window)) { res.textContent = "Este navegador no tiene Web NFC."; return; }
    try {
      const ndef = new NDEFReader();
      await ndef.scan();
      res.textContent = "Escuchando… acerca la etiqueta ahora";
      ndef.onreadingerror = () => { res.textContent = "Se acercó una etiqueta pero no se pudo leer."; };
      ndef.onreading = (e) => {
        const recs = [];
        for (const r of e.message.records) recs.push(r.recordType + ": " + JSON.stringify(r.data ? "…" : ""));
        res.textContent = "ETIQUETA LEÍDA\nserial: " + (e.serialNumber || "(sin serial)") +
          "\nregistros: " + (recs.join(" | ") || "ninguno");
      };
    } catch (err) {
      res.textContent = "Error: " + err.name + " · " + err.message;
    }
  });
})();
