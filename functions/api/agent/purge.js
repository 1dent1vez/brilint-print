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

  const at = new Date(now).toISOString();
  // Marca primero: desde este momento no se puede liberar ni reclamar el folio.
  const rows = all
    ? await env.DB.prepare(
        `UPDATE jobs SET purged_at = COALESCE(purged_at, ?)
          WHERE files_json IS NOT NULL AND files_json != '[]' RETURNING folio, files_json`
      ).bind(at).all()
    : await env.DB.prepare(
        `UPDATE jobs SET purged_at = COALESCE(purged_at, ?)
          WHERE files_json IS NOT NULL AND files_json != '[]'
            AND (
              purged_at IS NOT NULL
              OR (status IN ('done','error') AND COALESCE(printed_at, created_at) < ?)
              OR (status IN ('quoting','measuring','quoted','review_pending','review_held','review','reviewing','held','queued') AND created_at < ?)
            ) RETURNING folio, files_json`
      ).bind(at, doneCut, oldCut).all();

  let purged = 0;
  let deleted = 0;
  const folios = [];
  for (const row of rows.results || []) {
    let files = [];
    let retry = false;
    try { files = JSON.parse(row.files_json); } catch { files = []; }
    for (const f of files) {
      if (f && f.key) {
        try { await env.BUCKET.delete(f.key); deleted += 1; } catch { retry = true; }
      }
    }
    if (retry) continue;
    await env.DB.prepare(`UPDATE jobs SET files_json = '[]' WHERE folio = ?`).bind(row.folio).run();
    purged += 1;
    folios.push(row.folio);
  }

  console.log(JSON.stringify({ evt: "purge", purged, deleted, all }));
  return json({ ok: true, purged, deleted, folios });
}
