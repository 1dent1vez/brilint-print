import { json, bad, isAgent } from "../../_lib.js";

// Lo que pasa en el mostrador cuando el pedido no lo saca la app.
//
// printed_here · la gente lo imprimió desde la impresora (o desde la carpeta),
//                así que el pedido se cierra como impreso: no se reimprime y no
//                queda en error. Es el caso normal cuando el cliente trae
//                indicaciones y alguien lo atiende a mano.
// requeue      · se vuelve a mandar a la fila después de un error real.
const CLOSABLE = ["review", "reviewing", "quoting", "measuring", "quoted", "queued", "printing", "error"];

export async function onRequestPost({ request, env }) {
  if (!isAgent(request, env)) return bad("No autorizado.", 401);

  let body;
  try { body = await request.json(); } catch { return bad("Cuerpo inválido."); }

  const folio = String(body.folio || "").toUpperCase();
  const action = String(body.action || "");
  // Liberar puede venir con el código del cliente y sin folio; el resto sí lo necesita.
  const porCodigo = action === "release" && String(body.code || "").trim().length > 0;
  if (!porCodigo && !/^[0-9]{6}-[A-Z2-9]{4}$/.test(folio)) return bad("Folio inválido.");

  const row = porCodigo ? null : await env.DB.prepare(
    `SELECT status, printed_at FROM jobs WHERE folio = ?`
  ).bind(folio).first();
  if (!porCodigo && !row) return bad("No encontramos ese folio.", 404);

  const now = new Date().toISOString();

  if (action === "printed_here") {
    if (row.status === "done") {
      return json({ ok: true, folio, status: "done", already: true });
    }
    if (!CLOSABLE.includes(row.status)) return bad(`El pedido está en ${row.status}.`, 409);

    await env.DB.prepare(
      `UPDATE jobs SET status = 'done', printed_at = COALESCE(printed_at, ?),
              printed_by = 'mostrador', claimed_at = NULL, error = NULL
        WHERE folio = ? AND status != 'done'`
    ).bind(now, folio).run();

    console.log(JSON.stringify({ evt: "job_printed_here", folio, from: row.status }));
    return json({ ok: true, folio, status: "done", printed_by: "mostrador" });
  }

  if (action === "requeue") {
    if (!["error", "queued", "printing"].includes(row.status)) {
      return bad(`No hace falta reimprimir: el pedido está en ${row.status}.`, 409);
    }
    await env.DB.prepare(
      `UPDATE jobs SET status = 'queued', claimed_at = NULL, attempts = 0,
              error = NULL, printed_at = NULL
        WHERE folio = ? AND status IN ('error', 'queued', 'printing')`
    ).bind(folio).run();

    console.log(JSON.stringify({ evt: "job_requeued", folio, from: row.status }));
    return json({ ok: true, folio, status: "queued" });
  }

  if (action === "release") {
    // El cliente dicta su código de 4 dígitos: ese es el permiso para imprimir.
    const code = String(body.code || "").replace(/\D/g, "").slice(0, 4);
    const porCodigo = code.length === 4;
    if (!porCodigo && !body.folio) return bad("Escribe el código de 4 dígitos.", 400);

    const objetivo = porCodigo
      ? `SELECT folio, status, total FROM jobs WHERE claim_code = ? AND status IN ('held','quoted') ORDER BY created_at LIMIT 1`
      : `SELECT folio, status, total FROM jobs WHERE folio = ? AND status IN ('held','quoted')`;
    const arg = porCodigo ? code : String(body.folio).toUpperCase();
    const job = await env.DB.prepare(objetivo).bind(arg).first();

    if (!job) {
      if (porCodigo) {
        const otro = await env.DB.prepare(
          `SELECT folio, status FROM jobs WHERE claim_code = ? ORDER BY created_at DESC LIMIT 1`
        ).bind(code).first();
        if (otro) return json({ ok: true, already: true, folio: otro.folio, status: otro.status });
        return bad("Ningún pedido esperando con ese código.", 404);
      }
      return bad("Ese pedido ya no está esperando.", 409);
    }

    await env.DB.prepare(
      `UPDATE jobs SET status = 'queued', claimed_at = NULL
        WHERE folio = ? AND status IN ('held','quoted')`
    ).bind(job.folio).run();

    console.log(JSON.stringify({ evt: "job_released", folio: job.folio, por: porCodigo ? "codigo" : "folio" }));
    return json({ ok: true, folio: job.folio, status: "queued", total: job.total });
  }

  return bad(`Acción desconocida: ${action || "(vacía)"}`);
}
