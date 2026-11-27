import { json, bad } from "../../../_lib.js";

// Los pedidos especiales aceptan un precio variable antes de la revisión.
// En ambos flujos todavía se requiere presencia para avanzar.
export async function onRequestPost({ params, env, request }) {
  const folio = String(params.folio || "").toUpperCase();
  if (!/^[0-9]{6}-[A-Z2-9]{4}$/.test(folio)) return bad("Folio inválido.", 404);

  const row = await env.DB.prepare(
    `SELECT status, total, claim_code, purged_at FROM jobs WHERE folio = ?`
  ).bind(folio).first();
  if (!row) return bad("No encontramos ese folio.", 404);
  if (["review_pending", "review_held"].includes(row.status)) {
    if (row.purged_at) return bad("Este pedido caducó. Sube los archivos de nuevo.", 410);
    if (row.status === "review_held") {
      return json({ folio, status: row.status, total: null, code: row.claim_code });
    }
    const body = await request.json().catch(() => null);
    if (body?.price_terms !== "variable") {
      return bad("Confirma que autorizas la impresión con precio variable.");
    }
    const changed = await env.DB.prepare(
      `UPDATE jobs SET status = 'review_held',
                       plan_json = json_set(COALESCE(plan_json, '{}'), '$.price_terms', 'variable')
        WHERE folio = ? AND status = 'review_pending' AND purged_at IS NULL
        RETURNING status, claim_code`
    ).bind(folio).first();
    const current = changed || await env.DB.prepare(
      `SELECT status, claim_code, total, quote_json FROM jobs WHERE folio = ? AND purged_at IS NULL`
    ).bind(folio).first();
    if (!current) return bad("Este pedido caducó. Sube los archivos de nuevo.", 410);
    return json({ folio, status: current.status, total: current.quote_json ? current.total : null, code: current.claim_code });
  }
  // El pedido NO se imprime al confirmar: queda esperando el código que el
  // cliente dicta en el mostrador.
  if (["held", "queued", "printing", "done"].includes(row.status)) {
    return json({ folio, status: row.status, total: row.total, code: row.claim_code });
  }
  if (row.status !== "quoted") return bad("Este pedido todavía no tiene cotización.", 409);

  await env.DB.prepare(
    `UPDATE jobs SET status = 'held', confirmed_at = ? WHERE folio = ? AND status = 'quoted'`
  ).bind(new Date().toISOString(), folio).run();

  console.log(JSON.stringify({ evt: "job_held", folio }));
  return json({ folio, status: "held", total: row.total, code: row.claim_code });
}
