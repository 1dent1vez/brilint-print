import { PRICES } from "../_prices.js";
import { json, bad, makeFolio, r2Key, clientIp } from "../_lib.js";


const TYPES = new Set(["application/pdf", "image/jpeg", "image/png"]);

export async function onRequestPost({ request, env }) {
  try {
    const declared = Number(request.headers.get("content-length") || 0);
    if (declared > (PRICES.max_mb + 4) * 1024 * 1024) {
      return bad(`El pedido pasa de ${PRICES.max_mb} MB. Sube menos archivos.`, 413);
    }

    const form = await request.formData();
    const mode = String(form.get("mode") || "");
    const copies = Number(form.get("copies") || 1);
    // Sin nombre ni teléfono: el pedido se identifica por folio en el mostrador.
    const customer = String(form.get("customer") || "").trim().slice(0, 60);
    const phone = String(form.get("phone") || "").trim().slice(0, 20);
    const notes = String(form.get("notes") || "").trim().slice(0, 400);
    // Con notas, el pedido pasa por revisión del mostrador antes de imprimir.
    const review = String(form.get("review") || "") === "1" && notes.length > 0 ? 1 : 0;
    let clientPages = [];
    try { clientPages = JSON.parse(String(form.get("pages") || "[]")); } catch { clientPages = []; }

    if (mode !== "bw" && mode !== "color") return bad("Elige color o blanco y negro.");
    if (!Number.isInteger(copies) || copies < 1 || copies > PRICES.max_copies) {
      return bad(`El número de copias debe estar entre 1 y ${PRICES.max_copies}.`);
    }
    if (String(form.get("review") || "") === "1" && notes.length < 4) {
      return bad("Escribe la indicación, o desactiva la casilla para imprimir directo.");
    }

    const files = form.getAll("files").filter((f) => typeof f === "object" && f && "arrayBuffer" in f);
    if (!files.length) return bad("No llegó ningún archivo.");
    if (files.length > PRICES.max_files) return bad(`Máximo ${PRICES.max_files} archivos por pedido.`);

    let bytes = 0;
    for (const f of files) {
      if (!TYPES.has(f.type)) return bad(`Formato no aceptado: ${f.name}. Solo PDF, JPG o PNG.`);
      bytes += f.size;
    }
    if (bytes > PRICES.max_mb * 1024 * 1024) return bad(`El pedido pasa de ${PRICES.max_mb} MB.`);

    // Páginas: el cliente las leyó del PDF; el agente las verifica al imprimir.
    let pages = 0;
    const perFile = files.map((f, i) => {
      const n = Math.max(1, Math.min(500, parseInt(clientPages[i], 10) || 1));
      pages += n;
      return n;
    });
    if (pages > 2000) return bad("Son demasiadas páginas para un pedido en línea. Pásalo en el mostrador.");

    // La nota se interpreta en la laptop (agente), no aquí: el mostrador no debe
    // depender de una cuota de nube para cotizar.
    const plan = { ops: [], no_entendido: "", pendiente: true };

    // El total NO se calcula aquí: lo calcula el servidor cuando la laptop del
    // mostrador mide la tinta real de cada página (estado 'quoting' → 'quoted').
    const folio = makeFolio();
    const createdAt = new Date().toISOString();

    const stored = [];
    for (const [i, f] of files.entries()) {
      const key = r2Key(folio, i, f.name);
      // KV: sin costo ni método de pago, 25 MB por valor.
      if (f.size > 25 * 1024 * 1024) return bad(`${f.name} pasa de 25 MB. Súbelo en dos partes.`, 413);
      await env.BUCKET.put(key, await f.arrayBuffer(), {
        metadata: { contentType: f.type, folio, original: String(f.name).slice(0, 120) },
      });
      stored.push({ name: String(f.name).slice(0, 120), type: f.type, size: f.size, pages: perFile[i], key });
    }

    await env.DB.prepare(
      `INSERT INTO jobs (folio, created_at, status, mode, copies, pages, total, customer, phone, notes, files_json, plan_json, review)
       VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?)`
    ).bind(folio, createdAt, review ? "review" : "quoting", mode, copies, pages, customer, phone, notes,
           JSON.stringify(stored), JSON.stringify(plan), review).run();

    console.log(JSON.stringify({ evt: "job_created", folio, files: stored.length, pages, bytes, ip: clientIp(request) }));

    return json({
      folio,
      status: review ? "review" : "quoting",
      review,
      mode, copies, pages,
      currency: PRICES.currency,
      plan,
      files: stored.map((f) => ({ name: f.name, pages: f.pages })),
    });
  } catch (e) {
    console.error("jobs_error", e?.stack || String(e));
    return bad("No pudimos registrar el pedido. Intenta de nuevo o entrégalo en el mostrador.", 500);
  }
}
