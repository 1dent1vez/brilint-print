import { json, bad, isAgent } from "../../_lib.js";

// La laptop del mostrador pide el siguiente trabajo en cola.
export async function onRequestPost({ request, env }) {
  if (!isAgent(request, env)) return bad("No autorizado.", 401);

  // Etapa: 'review' = preparar para el mostrador; 'quote' = medir; 'print' = imprimir.
  let stage = "print";
  try {
    const body = await request.json();
    if (body && ["quote", "print", "review"].includes(body.stage)) stage = body.stage;
  } catch { /* cuerpo vacío: imprimir */ }

  const from = stage === "review" ? "review" : stage === "quote" ? "quoting" : "queued";
  const to = stage === "review" ? "reviewing" : stage === "quote" ? "measuring" : "printing";

  // Recuperación: si la laptop murió a media medición o impresión, el pedido
  // volvería a quedar atorado para siempre. Se devuelve a la cola.
  const now = new Date().toISOString();
  const staleMeasure = new Date(Date.now() - 10 * 60 * 1000).toISOString();
  const stalePrint = new Date(Date.now() - 30 * 60 * 1000).toISOString();
  await env.DB.prepare(
    `UPDATE jobs SET status = 'quoting', claimed_at = NULL
      WHERE status = 'measuring' AND claimed_at IS NOT NULL AND claimed_at < ?`
  ).bind(staleMeasure).run();
  await env.DB.prepare(
    `UPDATE jobs SET status = 'queued', claimed_at = NULL
      WHERE status = 'printing' AND claimed_at IS NOT NULL AND claimed_at < ?`
  ).bind(stalePrint).run();

  const res = await env.DB.prepare(
    `UPDATE jobs SET status = ?, claimed_at = ?
      WHERE folio = (
        SELECT folio FROM jobs WHERE status = ? ORDER BY created_at LIMIT 1
      ) AND status = ?
      RETURNING folio, created_at, mode, copies, pages, total, customer, phone, notes, files_json, quote_json, review`
  ).bind(to, now, from, from).all();

  const row = res.results && res.results[0];
  if (!row) return json({ job: null });

  let files = [];
  try { files = JSON.parse(row.files_json); } catch { files = []; }

  return json({
    stage,
    job: {
      folio: row.folio,
      created_at: row.created_at,
      mode: row.mode,
      copies: row.copies,
      pages: row.pages,
      total: row.total,
      customer: row.customer,
      phone: row.phone,
      notes: row.notes,
      review: row.review || 0,
      quote: row.quote_json ? JSON.parse(row.quote_json) : null,
      files: files.map((f, i) => ({ index: i, name: f.name, pages: f.pages, size: f.size, type: f.type })),
    },
  });
}
