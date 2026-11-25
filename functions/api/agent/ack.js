import { json, bad, isAgent } from "../../_lib.js";

// La laptop confirma que el trabajo salió (o que falló y necesita revisión).
export async function onRequestPost({ request, env }) {
  if (!isAgent(request, env)) return bad("No autorizado.", 401);

  let body;
  try { body = await request.json(); } catch { return bad("Cuerpo inválido."); }

  const folio = String(body.folio || "");
  const status = body.status === "done" ? "done" : body.status === "error" ? "error" : null;
  if (!folio || !status) return bad("Falta folio o estado.");
  const pages = Number.isInteger(body.pages_verified) ? body.pages_verified : null;
  const error = status === "error" ? String(body.error || "sin detalle").slice(0, 300) : null;

  const res = await env.DB.prepare(
    `UPDATE jobs SET status = ?, pages_verified = COALESCE(?, pages_verified),
            printed_at = ?, error = ?
      WHERE folio = ?`
  ).bind(status, pages, status === "done" ? new Date().toISOString() : null, error, folio).run();

  if (!res.meta || res.meta.changes === 0) return bad("Pedido no encontrado.", 404);
  return json({ ok: true, folio, status });
}
