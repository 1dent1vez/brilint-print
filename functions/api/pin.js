import { json } from "../_lib.js";
import { pinMode } from "../_pin.js";

// Estado público: si hace falta el código del mostrador o el local está
// aceptando envíos de fuera. No expone el código.
export async function onRequestGet({ env }) {
  const modo = await pinMode(env);
  return json({ modo, pide_codigo: modo !== "abierto" });
}
