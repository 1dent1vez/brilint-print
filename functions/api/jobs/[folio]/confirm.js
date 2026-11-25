import { json, bad } from "../../../_lib.js";

// El cliente acepta la cotización exacta: el pedido entra a la fila de impresión.
export async function onRequestPost({ params, env }) {
  const folio = String(params.folio || "").toUpperCase();
  if (!/^[0-9]{6}-[A-Z2-9]{4}$/.test(folio)) return bad("Folio inválido.", 404);

  const row = await env.DB.prepare(
    `SELECT status, total, quote_json FROM jobs WHERE folio = ?`
  ).bind(folio).first();
  if (!row) return bad("No encontramos ese folio.", 404);
  if (row.status === "queued" || row.status === "printing" || row.status === "done") {
    return json({ folio, status: row.status, total: row.total });
  }
  if (row.status !== "quoted") return bad("Este pedido todavía no tiene cotización.", 409);

  await env.DB.prepare(
    `UPDATE jobs SET status = 'queued', confirmed_at = ? WHERE folio = ? AND status = 'quoted'`
  ).bind(new Date().toISOString(), folio).run();

  return json({ folio, status: "queued", total: row.total });
}
