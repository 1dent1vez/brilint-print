// Código del mostrador: prueba de que el cliente está enfrente.
//
// El QR y la dirección se pueden compartir; el código no, porque solo existe en
// la pantalla de la caja. Se deriva de un secreto con HMAC y cambia cada 5
// minutos, así que no hay que guardar nada: cualquiera con el secreto puede
// calcular el de ahora (lo hace la caja) y el servidor lo verifica igual.

const BUCKET_MS = 5 * 60 * 1000;
const enc = new TextEncoder();

function secret(env) {
  return env.COUNTER_PIN_SECRET || env.AGENT_TOKEN || "";
}

export function bucketAt(now = Date.now()) {
  return Math.floor(now / BUCKET_MS);
}

async function digits(secretStr, bucket) {
  const key = await crypto.subtle.importKey(
    "raw", enc.encode(secretStr), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]
  );
  const sig = new Uint8Array(await crypto.subtle.sign("HMAC", key, enc.encode(`mostrador:${bucket}`)));
  let n = 0;
  for (let i = 0; i < 6; i++) n = (n * 256 + sig[i]) % 10000;
  return String(n).padStart(4, "0");
}

export async function currentPin(env, now = Date.now()) {
  const bucket = bucketAt(now);
  return {
    code: await digits(secret(env), bucket),
    expires_in: Math.round((BUCKET_MS - (now % BUCKET_MS)) / 1000),
    rotacion_s: Math.round(BUCKET_MS / 1000),
  };
}

// Se acepta también el código anterior: alguien lo pudo leer justo antes del
// cambio y tardarse medio minuto en escribirlo.
export async function checkPin(env, given) {
  const code = String(given || "").replace(/\D/g, "");
  if (code.length !== 4) return false;
  const bucket = bucketAt();
  const s = secret(env);
  if (!s) return false;
  return (await digits(s, bucket)) === code || (await digits(s, bucket - 1)) === code;
}

const MODO_KEY = "config:pin_modo";

export async function pinMode(env) {
  const v = await env.BUCKET.get(MODO_KEY);
  return v === "abierto" ? "abierto" : "cerrado";
}

export async function setPinMode(env, modo, minutos = 60) {
  if (modo === "abierto") {
    await env.BUCKET.put(MODO_KEY, "abierto", { expirationTtl: Math.max(60, Math.min(43200, minutos * 60)) });
  } else {
    await env.BUCKET.delete(MODO_KEY);
  }
  return pinMode(env);
}

// Límite de intentos por IP: 12 fallos en 15 minutos y se corta.
const MAX_FALLOS = 12;
const RL_TTL = 900;

export async function pinRateOk(env, ip) {
  const k = `rl:pin:${ip || "sin-ip"}`;
  const n = Number(await env.BUCKET.get(k)) || 0;
  return n < MAX_FALLOS;
}

export async function pinRateFail(env, ip) {
  const k = `rl:pin:${ip || "sin-ip"}`;
  const n = Number(await env.BUCKET.get(k)) || 0;
  await env.BUCKET.put(k, String(n + 1), { expirationTtl: RL_TTL });
}
