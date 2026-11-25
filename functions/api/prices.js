import { PRICES } from "../_prices.js";
import { json } from "../_lib.js";

export async function onRequestGet() {
  return json({
    currency: PRICES.currency,
    max_mb: PRICES.max_mb,
    max_files: PRICES.max_files,
    max_copies: PRICES.max_copies,
    paper: PRICES.paper,
    // El navegador sólo muestra etiquetas y el mínimo; el precio final lo calcula
    // el servidor con la medición real de cada página.
    bw: PRICES.bw.map(({ id, label, price }) => ({ id, label, price })),
    color: PRICES.color.map(({ id, label, price }) => ({ id, label, price })),
  });
}
