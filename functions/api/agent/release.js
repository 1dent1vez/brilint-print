import { json, bad, isAgent } from "../../_lib.js";

// El mostrador terminó de ajustar el archivo: pasa a medir y cotizar.
export async function onRequestPost({ request, env }) {
  if (!isAgent(request, env)) return bad("No autorizado.", 401);

  let body;
  try { body = await request.json(); } catch { return bad("Cuerpo inválido."); }
  const folio = String(body.folio || "").toUpperCase();
  if (!/^[0-9]{6}-[A-Z2-9]{4}$/.test(folio)) return bad("Folio inválido.");

  const row = await env.DB.prepare(`SELECT status FROM jobs WHERE folio = ?`).bind(folio).first();
  if (!row) return bad("No encontramos ese folio.", 404);
  if (!["review", "reviewing"].includes(row.status)) {
    return bad(`El pedido está en estado ${row.status}.`, 409);
  }

  const changed = await env.DB.prepare(
    `UPDATE jobs SET status = 'quoting', claimed_at = NULL
      WHERE folio = ? AND purged_at IS NULL
        AND ((status IN ('review','reviewing') AND confirmed_at IS NULL)
          OR (status = 'reviewing' AND json_extract(plan_json, '$.prepared_at') IS NOT NULL))
      RETURNING status`
  ).bind(folio).first();
  if (!changed) return bad("El pedido no está listo para medir o ya caducó.", 409);

  console.log(JSON.stringify({ evt: "job_released", folio }));
  return json({ ok: true, folio, status: "quoting" });
}
