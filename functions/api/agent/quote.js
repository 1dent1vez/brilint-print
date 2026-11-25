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
    `SELECT mode, copies, status, pages, files_json FROM jobs WHERE folio = ?`
  ).bind(folio).first();
  if (!row) return bad("Pedido no encontrado.", 404);
  if (row.status === "quoted" || row.status === "queued" || row.status === "printing") {
    return json({ ok: true, already: true });
  }
  if (row.status !== "measuring" && row.status !== "quoting") {
    return bad(`El pedido está en estado ${row.status}.`, 409);
  }

  // Coherencia mínima: el número de páginas no puede inventarse.
  if (Math.abs(pages.length - row.pages) > Math.max(2, row.pages * 0.2)) {
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

  await env.DB.prepare(
    `UPDATE jobs SET status = 'quoted', total = ?, pages_verified = ?, quote_json = ?, quoted_at = ?
      WHERE folio = ?`
  ).bind(total, pages.length, JSON.stringify(quote), quote.measured_at, folio).run();

  console.log(JSON.stringify({ evt: "job_quoted", folio, pages: pages.length, total }));
  return json({ ok: true, folio, total, lines: q.lines });
}
