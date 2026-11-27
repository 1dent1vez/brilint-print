import { json, bad, isAgent, bloqueoActivo, fallo, acierto, presencial } from "../../_lib.js";

// Lo que pasa en el mostrador cuando el pedido no lo saca la app.
//
// printed_here · la gente lo imprimió desde la impresora (o desde la carpeta),
//                así que el pedido se cierra como impreso: no se reimprime y no
//                queda en error. Es el caso normal cuando el cliente trae
//                indicaciones y alguien lo atiende a mano.
// requeue      · se vuelve a mandar a la fila después de un error real.
const CLOSABLE = ["review", "reviewing", "quoting", "measuring", "quoted", "held", "queued", "printing", "error"];

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
    `SELECT status, quote_json FROM jobs WHERE folio = ?`
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
    if (!row.quote_json) return bad("El pedido todavía no tiene un total medido; revisa el archivo.", 409);
    const changed = await env.DB.prepare(
      `UPDATE jobs SET status = 'queued', claimed_at = NULL, attempts = 0,
              error = NULL, printed_at = NULL
        WHERE folio = ? AND status IN ('error', 'queued', 'printing') AND purged_at IS NULL
        RETURNING status`
    ).bind(folio).first();
    if (!changed) return bad("El pedido ya no se puede reimprimir.", 409);

    console.log(JSON.stringify({ evt: "job_requeued", folio, from: row.status }));
    return json({ ok: true, folio, status: "queued" });
  }

  if (action === "release") {
    // Antes de nada: ¿está bloqueado por intentos fallidos?
    const bloqueo = await bloqueoActivo(env, "codigo");
    if (bloqueo > 0) {
      return json({ error: `Bloqueado por intentos fallidos. Espera ${Math.ceil(bloqueo / 60)} min.`,
                    bloqueado_s: bloqueo }, 429);
    }
    // El cliente dicta su código de 4 dígitos: ese es el permiso para imprimir.
    const code = String(body.code || "").replace(/\D/g, "").slice(0, 4);
    const porCodigo = code.length === 4;
    if (!porCodigo && !body.folio) return bad("Escribe el código de 4 dígitos.", 400);

    const since = new Date(Date.now() - 24 * 3600 * 1000).toISOString();
    const matches = porCodigo ? (await env.DB.prepare(
      `SELECT folio, status, purged_at FROM jobs WHERE claim_code = ? AND created_at > ? LIMIT 2`
    ).bind(code, since).all()).results : [];
    if (matches.length > 1) return bad("Ese código coincide con dos pedidos. Usa NFC o vuelve a subir el pedido.", 409);
    const job = porCodigo ? matches[0] : await env.DB.prepare(
      `SELECT folio, status, purged_at FROM jobs WHERE folio = ?`
    ).bind(folio).first();

    if (!job) {
      if (porCodigo) {
        const f = await fallo(env, "codigo");
        if (f.bloqueado) {
          return json({ error: `Código incorrecto ${f.fallos || 3} veces: bloqueado ${Math.ceil(f.restante / 60)} min.`,
                        bloqueado_s: f.restante }, 429);
        }
        return json({ error: `Ningún pedido esperando con ese código. Te quedan ${f.quedan} intentos.`,
                      quedan: f.quedan }, 404);
      }
      return bad("Ese pedido ya no está esperando.", 409);
    }

    if (job.purged_at) return bad("El pedido ya no está disponible.", 410);
    if (job.status === "review_pending") return bad("El cliente todavía no ha confirmado el pedido.", 409);
    const allowed = ["held", "quoted"].includes(job.status) || (porCodigo && job.status === "review_held");
    if (!allowed) {
      if (porCodigo) return json({ ok: true, already: true, folio: job.folio, status: job.status });
      return bad("Ese pedido ya no está esperando.", 409);
    }
    const changed = await presencial(env, job.folio, job.status);
    if (!changed) {
      const current = await env.DB.prepare(`SELECT status FROM jobs WHERE folio = ? AND purged_at IS NULL`).bind(job.folio).first();
      if (!current) return bad("El pedido ya no está disponible.", 410);
      await acierto(env, "codigo");
      return json({ ok: true, already: true, folio: job.folio, status: current.status });
    }

    await acierto(env, "codigo");
    console.log(JSON.stringify({ evt: "job_released", folio: job.folio, por: porCodigo ? "codigo" : "folio" }));
    return json({ ok: true, folio: job.folio, status: changed.status, total: changed.status === "review" ? null : changed.total });
  }

  return bad(`Acción desconocida: ${action || "(vacía)"}`);
}
