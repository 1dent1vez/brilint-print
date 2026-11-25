import { bad, json, isAgent } from "../../_lib.js";

// Autodestrucción: a la hora de impreso, el contenido del cliente se borra.
// La fila se conserva (folio, fecha, páginas, total) para la cuenta del día,
// pero sin archivos ni rutas.
const DONE_AFTER_MS = 60 * 60 * 1000;          // 1 h tras imprimir
const ABANDONED_AFTER_MS = 24 * 60 * 60 * 1000; // 24 h sin confirmar

export async function onRequestPost({ request, env }) {
  if (!isAgent(request, env)) return bad("No autorizado.", 401);

  let body = {};
  try { body = await request.json(); } catch { /* sin cuerpo */ }
  const all = body && body.all === true;

  const now = Date.now();
  const doneCut = new Date(now - DONE_AFTER_MS).toISOString();
  const oldCut = new Date(now - ABANDONED_AFTER_MS).toISOString();

  const rows = all
    ? await env.DB.prepare(
        `SELECT folio, files_json FROM jobs WHERE files_json IS NOT NULL AND files_json != '[]'`
      ).all()
    : await env.DB.prepare(
        `SELECT folio, files_json FROM jobs
          WHERE files_json IS NOT NULL AND files_json != '[]' AND purged_at IS NULL
            AND (
              (status IN ('done','error') AND COALESCE(printed_at, created_at) < ?)
              OR (status IN ('quoting','measuring','quoted','review','reviewing','queued') AND created_at < ?)
            )`
      ).bind(doneCut, oldCut).all();

  let purged = 0;
  let deleted = 0;
  const folios = [];
  for (const row of rows.results || []) {
    let files = [];
    try { files = JSON.parse(row.files_json); } catch { files = []; }
    for (const f of files) {
      if (f && f.key) {
        try { await env.BUCKET.delete(f.key); deleted += 1; } catch { /* ya no estaba */ }
      }
    }
    await env.DB.prepare(
      `UPDATE jobs SET files_json = '[]', purged_at = ? WHERE folio = ?`
    ).bind(new Date().toISOString(), row.folio).run();
    purged += 1;
    folios.push(row.folio);
  }

  console.log(JSON.stringify({ evt: "purge", purged, deleted, all }));
  return json({ ok: true, purged, deleted, folios });
}
