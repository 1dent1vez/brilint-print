import { json, bad } from "../../../_lib.js";

// El cliente acepta la cotización exacta: el pedido entra a la fila de impresión.
export async function onRequestPost({ params, env }) {
  const folio = String(params.folio || "").toUpperCase();
  if (!/^[0-9]{6}-[A-Z2-9]{4}$/.test(folio)) return bad("Folio inválido.", 404);

  const row = await env.DB.prepare(
    `SELECT status, total, claim_code FROM jobs WHERE folio = ?`
  ).bind(folio).first();
  if (!row) return bad("No encontramos ese folio.", 404);
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
