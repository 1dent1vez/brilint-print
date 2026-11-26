import { json, bad, isAgent } from "../../_lib.js";

// La laptop confirma qué pasó con el trabajo. Tres avisos:
//   sent  · está por mandarlo a la impresora (registra el intento y da permiso)
//   done  · salió impreso
//   error · no salió y hay que resolverlo en el mostrador
export async function onRequestPost({ request, env }) {
  if (!isAgent(request, env)) return bad("No autorizado.", 401);

  let body;
  try { body = await request.json(); } catch { return bad("Cuerpo inválido."); }

  const folio = String(body.folio || "");
  const status = ["sent", "done", "error"].includes(body.status) ? body.status : null;
  if (!folio || !status) return bad("Falta folio o estado.");
  const pages = Number.isInteger(body.pages_verified) ? body.pages_verified : null;
  const error = status === "error" ? String(body.error || "sin detalle").slice(0, 300) : null;
  const now = new Date().toISOString();

  // Antes de mandar papel: si el mostrador ya cerró el pedido (lo imprimió a
  // mano) o alguien lo canceló, se veta la impresión y no sale hoja doble.
  if (status === "sent") {
    const res = await env.DB.prepare(
      `UPDATE jobs SET attempts = attempts + 1, attempted_at = ?
        WHERE folio = ? AND status = 'printing'`
    ).bind(now, folio).run();

    if (!res.meta || res.meta.changes === 0) {
      const row = await env.DB.prepare(
        `SELECT status, printed_by FROM jobs WHERE folio = ?`
      ).bind(folio).first();
      if (!row) return bad("Pedido no encontrado.", 404);
      const reason = row.status === "done"
        ? `ya se cerró como impreso (${row.printed_by || "mostrador"})`
        : `el pedido está en ${row.status}`;
      console.log(JSON.stringify({ evt: "job_send_vetoed", folio, status: row.status }));
      return json({ ok: true, print: false, folio, status: row.status, reason });
    }
    console.log(JSON.stringify({ evt: "job_sent", folio }));
    return json({ ok: true, print: true, folio, status: "printing" });
  }

  // Solo se mueve un pedido que sigue en la impresora o en la fila: si el
  // mostrador ya lo cerró a mano, no se reabre.
  const res = await env.DB.prepare(
    `UPDATE jobs SET status = ?,
            pages_verified = COALESCE(?, pages_verified),
            printed_at = CASE WHEN ? = 'done' THEN ? ELSE printed_at END,
            printed_by = CASE WHEN ? = 'done' THEN COALESCE(printed_by, 'agente') ELSE printed_by END,
            claimed_at = NULL,
            error = ?
      WHERE folio = ? AND status IN ('printing', 'queued')`
  ).bind(status, pages, status, now, status, error, folio).run();

  if (!res.meta || res.meta.changes === 0) {
    const row = await env.DB.prepare(`SELECT status, printed_by FROM jobs WHERE folio = ?`).bind(folio).first();
    if (!row) return bad("Pedido no encontrado.", 404);
    return json({ ok: true, already: true, folio, status: row.status, printed_by: row.printed_by });
  }

  console.log(JSON.stringify({ evt: `job_${status}`, folio, error }));
  return json({ ok: true, folio, status });
}
