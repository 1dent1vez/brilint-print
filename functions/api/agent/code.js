import { json, bad, isAgent } from "../../_lib.js";
import { currentPin, pinMode, setPinMode } from "../../_pin.js";

// La caja pide el código del mostrador y decide si acepta envíos de fuera.
export async function onRequestGet({ request, env }) {
  if (!isAgent(request, env)) return bad("No autorizado.", 401);
  const pin = await currentPin(env);
  return json({ ...pin, modo: await pinMode(env) });
}

export async function onRequestPost({ request, env }) {
  if (!isAgent(request, env)) return bad("No autorizado.", 401);
  let body;
  try { body = await request.json(); } catch { return bad("Cuerpo inválido."); }

  const modo = body.modo === "abierto" ? "abierto" : "cerrado";
  const minutos = Number.isFinite(body.minutos) ? Number(body.minutos) : 60;
  const ahora = await setPinMode(env, modo, minutos);

  console.log(JSON.stringify({ evt: "pin_modo", modo: ahora, minutos }));
  const pin = await currentPin(env);
  return json({ ok: true, modo: ahora, minutos, ...pin });
}
