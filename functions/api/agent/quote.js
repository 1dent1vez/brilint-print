import { quoteJob } from "../../_prices.js";
import { json, bad, isAgent } from "../../_lib.js";

// La laptop del mostrador reporta la tinta medida de cada página; el servidor
// clasifica y pone el precio. Un solo motor de medición, un solo tarifario.
export async function onRequestPost({ request, env }) {
  if (!isAgent(request, env)) return bad("No autorizado.", 401);

  let body;
  try { body = await request.json(); } catch { return bad("Cuerpo inválido."); }

  const folio = String(body.folio || "");
  const pages = Array.isArray(body.pages) ? body.pages : null;
  if (!folio || !pages || pages.length < 1 || pages.length > 2000) {
    return bad("Medición inválida.");
  }
  for (const p of pages) {
    const cov = Number(p.cov), chroma = Number(p.chroma);
    if (!Number.isFinite(cov) || !Number.isFinite(chroma) || cov < 0 || cov > 1 || chroma < 0 || chroma > 1) {
      return bad("Medición fuera de rango.");
    }
  }

  const row = await env.DB.prepare(
    `SELECT mode, copies, status, pages, review, confirmed_at, quote_json, purged_at,
            json_extract(plan_json, '$.price_terms') AS price_terms FROM jobs WHERE folio = ?`
  ).bind(folio).first();
  if (!row) return bad("Pedido no encontrado.", 404);
  if (row.quote_json && ["quoted", "held", "queued", "printing", "done"].includes(row.status)) {
    return json({ ok: true, already: true });
  }
  if (row.purged_at) return bad("El pedido ya no está disponible.", 410);
  if (row.status !== "measuring" && row.status !== "quoting") {
    return bad(`El pedido está en estado ${row.status}.`, 409);
  }

  // Un ajuste de mostrador puede cambiar el número de páginas por diseño.
  if (!row.review && Math.abs(pages.length - row.pages) > Math.max(2, row.pages * 0.2)) {
    return bad("Las páginas medidas no cuadran con el pedido.", 409);
  }

  const q = quoteJob(row.mode, pages);
  const total = Math.round(q.perCopy * row.copies * 100) / 100;
  const quote = {
    lines: q.lines,
    per_copy: q.perCopy,
    total,
    copies: row.copies,
    pages: pages.length,
    measured_at: new Date().toISOString(),
  };

  const authorized = row.review && row.confirmed_at && row.price_terms === "variable";
  const status = authorized ? "queued" : "quoted";
  const updated = await env.DB.prepare(
    `UPDATE jobs SET status = ?, total = ?, pages_verified = ?, quote_json = ?, quoted_at = ?, claimed_at = NULL
      WHERE folio = ? AND status IN ('measuring','quoting') AND purged_at IS NULL
      RETURNING status`
  ).bind(status, total, pages.length, JSON.stringify(quote), quote.measured_at, folio).first();
  if (!updated) {
    const current = await env.DB.prepare(`SELECT status, quote_json FROM jobs WHERE folio = ?`).bind(folio).first();
    if (current?.quote_json) return json({ ok: true, already: true });
    return bad(`El pedido está en estado ${current?.status || "desconocido"}.`, 409);
  }

  console.log(JSON.stringify({ evt: "job_quoted", folio, pages: pages.length, total, status }));
  return json({ ok: true, folio, total, status, lines: q.lines });
}
