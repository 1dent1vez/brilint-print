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
