import { bad, isAgent } from "../../_lib.js";

// Descarga un archivo del pedido para la laptop del mostrador.
export async function onRequestGet({ request, env }) {
  if (!isAgent(request, env)) return bad("No autorizado.", 401);

  const url = new URL(request.url);
  const folio = String(url.searchParams.get("folio") || "");
  const index = parseInt(url.searchParams.get("i") || "0", 10);

  const row = await env.DB.prepare(`SELECT files_json FROM jobs WHERE folio = ?`).bind(folio).first();
  if (!row) return bad("Pedido no encontrado.", 404);

  let files = [];
  try { files = JSON.parse(row.files_json); } catch { return bad("Pedido corrupto.", 500); }
  const f = files[index];
  if (!f) return bad("Archivo no encontrado.", 404);

  // KV: el contenido y sus metadatos vienen juntos.
  const obj = await env.BUCKET.getWithMetadata(f.key, "arrayBuffer");
  if (!obj || !obj.value) return bad("El archivo ya no está disponible.", 410);

  return new Response(obj.value, {
    headers: {
      "content-type": obj.metadata?.contentType || f.type || "application/octet-stream",
      "content-length": String(obj.value.byteLength || f.size || 0),
      "content-disposition": `attachment; filename="${encodeURIComponent(f.name)}"`,
      "cache-control": "no-store",
    },
  });
}
