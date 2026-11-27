import { json, bad, bloqueoActivo, fallo, acierto } from "../../../_lib.js";

// Acercar el teléfono a la etiqueta NFC del mostrador.
//
// Es lo mismo que dictar el código, pero sin teclear nada: el teléfono lee el
// número de serie de la etiqueta (Web NFC, solo Android/Chrome) y el servidor
// comprueba que sea la del local. Una etiqueta no se puede leer a distancia:
// hay que estar a menos de 4 cm, así que sirve como prueba de presencia.
//
// En iPhone no existe Web NFC: ahí el cliente sigue dictando el código.

const normal = (v) => String(v || "").replace(/[^0-9a-fA-F]/g, "").toUpperCase();

export async function onRequestPost({ params, env, request }) {
  const folio = String(params.folio || "").toUpperCase();
  if (!/^[0-9]{6}-[A-Z2-9]{4}$/.test(folio)) return bad("Folio inválido.", 404);

  const esperado = normal(env.NFC_TAG_ID);
  if (!esperado) {
    return json({ error: "La etiqueta NFC del mostrador todavía no está registrada.",
                  sin_etiqueta: true }, 501);
  }

  const bloqueo = await bloqueoActivo(env, "nfc");
  if (bloqueo > 0) {
    return json({ error: `Bloqueado por intentos fallidos. Espera ${Math.ceil(bloqueo / 60)} min.`,
                  bloqueado_s: bloqueo }, 429);
  }

  let body;
  try { body = await request.json(); } catch { return bad("Cuerpo inválido."); }
  const tag = normal(body.tag);
  if (!tag) return bad("No leí ninguna etiqueta.", 400);

  if (tag !== esperado) {
    const f = await fallo(env, "nfc");
    if (f.bloqueado) {
      return json({ error: `Etiqueta ajena ${f.fallos || 3} veces: bloqueado ${Math.ceil(f.restante / 60)} min.`,
                    bloqueado_s: f.restante }, 429);
    }
    console.log(JSON.stringify({ evt: "tap_rechazado", folio, tag: tag.slice(0, 24) }));
    return json({ error: "Esa etiqueta no es la del mostrador.", quedan: f.quedan }, 403);
  }

  const row = await env.DB.prepare(
    `SELECT folio, status, total FROM jobs WHERE folio = ?`
  ).bind(folio).first();
  if (!row) return bad("No encontramos ese folio.", 404);
  if (["queued", "printing", "done"].includes(row.status)) {
    await acierto(env, "nfc");
    return json({ ok: true, already: true, folio, status: row.status });
  }
  if (["review", "reviewing"].includes(row.status)) {
    // Todavía lo está ajustando el mostrador: no se puede soltar por NFC.
    return bad("El mostrador todavía está revisando tu pedido.", 409);
  }
  if (row.status !== "held" && row.status !== "quoted") {
    return bad(`Este pedido está en ${row.status}.`, 409);
  }

  await env.DB.prepare(
    `UPDATE jobs SET status = 'queued', claimed_at = NULL WHERE folio = ? AND status IN ('held','quoted')`
  ).bind(folio).run();

  await acierto(env, "nfc");
  console.log(JSON.stringify({ evt: "job_tap_released", folio }));
  return json({ ok: true, folio, status: "queued", total: row.total, por: "nfc" });
}
