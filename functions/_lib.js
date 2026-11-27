const JSON_HEADERS = { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" };

export const json = (data, status = 200) =>
  new Response(JSON.stringify(data), { status, headers: JSON_HEADERS });

export const bad = (error, status = 400) => json({ error }, status);

/** Folio legible: AAMMDD-XXXX sin caracteres ambiguos (sin I, O, 0, 1). */
export function makeFolio(now = new Date()) {
  const alpha = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
  const y = String(now.getUTCFullYear()).slice(2);
  const m = String(now.getUTCMonth() + 1).padStart(2, "0");
  const d = String(now.getUTCDate()).padStart(2, "0");
  let tail = "";
  const bytes = crypto.getRandomValues(new Uint8Array(4));
  for (const b of bytes) tail += alpha[b % alpha.length];
  return `${y}${m}${d}-${tail}`;
}

/** Código de 4 dígitos que el cliente dicta en el mostrador para que se imprima. */
export function makeClaimCode() {
  const n = crypto.getRandomValues(new Uint32Array(1))[0] % 10000;
  return String(n).padStart(4, "0");
}

/** Nombre de archivo seguro para R2 (conserva la extensión y el original para el humano). */
export function safeName(name) {
  const base = String(name || "archivo").normalize("NFKD").replace(/[\u0300-\u036f]/g, "");
  const clean = base.replace(/[^A-Za-z0-9._-]+/g, "_").replace(/_{2,}/g, "_").slice(-80);
  return clean || "archivo";
}

export const r2Key = (folio, i, name) => `jobs/${folio}/${String(i).padStart(2, "0")}_${safeName(name)}`;

export function isAgent(request, env) {
  const token = request.headers.get("x-agent-token") || "";
  const expected = env.AGENT_TOKEN || "";
  if (!expected || token.length !== expected.length) return false;
  let diff = 0;
  for (let i = 0; i < expected.length; i++) diff |= token.charCodeAt(i) ^ expected.charCodeAt(i);
  return diff === 0;
}

export function clientIp(request) {
  return request.headers.get("cf-connecting-ip") || "0.0.0.0";
}

// Freno para el código del cliente: 3 fallos y se cierra 5 minutos. Sin esto,
// 10 000 combinaciones se prueban a mano en un rato.
const MAX_FALLOS = 3;
const BLOQUEO_S = 300;

export async function bloqueoActivo(env, tipo) {
  const hasta = await env.BUCKET.get(`lock:${tipo}`);
  const restante = hasta ? Math.ceil((new Date(hasta).getTime() - Date.now()) / 1000) : 0;
  return restante > 0 ? restante : 0;
}

export async function fallo(env, tipo) {
  if ((await bloqueoActivo(env, tipo)) > 0) return { bloqueado: true, restante: await bloqueoActivo(env, tipo) };
  const k = `fails:${tipo}`;
  const n = (Number(await env.BUCKET.get(k)) || 0) + 1;
  if (n >= MAX_FALLOS) {
    await env.BUCKET.put(`lock:${tipo}`, new Date(Date.now() + BLOQUEO_S * 1000).toISOString(),
                        { expirationTtl: BLOQUEO_S + 60 });
    await env.BUCKET.delete(k);
    return { bloqueado: true, restante: BLOQUEO_S, fallos: n };
  }
  await env.BUCKET.put(k, String(n), { expirationTtl: BLOQUEO_S });
  return { bloqueado: false, restante: 0, fallos: n, quedan: MAX_FALLOS - n };
}

export async function acierto(env, tipo) {
  await env.BUCKET.delete(`fails:${tipo}`);
}
