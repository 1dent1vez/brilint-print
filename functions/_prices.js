// Tarifario real (flyer del negocio) y reglas de clasificación automática.
// El precio NO lo elige nadie: se mide la tinta de cada página y cae en un nivel.
//
// `cov`    = fracción de la página cubierta de tinta (0..1), medida con ghostscript inkcov
//            sobre el PDF ya normalizado (el que de verdad se imprime).
// `chroma` = tinta cromática media (C+M+Y)/3 de la página, también 0..1.

export const PRICES = {
  currency: "MXN",
  max_mb: 80,
  max_files: 8,
  max_copies: 200,
  paper: "letter",
  shop: "Print with Brilint",

  // Blanco y negro: dos niveles, "según el contenido de tu documento".
  bw: [
    { id: "texto", label: "Texto normal", price: 1.5, max_cov: 0.10 },
    { id: "grafico", label: "Gráficos o fondo oscuro", price: 3.0, max_cov: 1.01 },
  ],

  // Color: cuatro niveles del flyer; el rango $12–15 se resuelve con un quinto
  // escalón para la página realmente saturada.
  color: [
    { id: "ligero", label: "Color ligero", price: 3.0, max_chroma: 0.03 },
    { id: "normal", label: "Color normal", price: 5.0, max_chroma: 0.10 },
    { id: "abundante", label: "Color abundante", price: 8.0, max_chroma: 0.30 },
    { id: "total", label: "Color total", price: 12.0, max_chroma: 0.70 },
    { id: "saturado", label: "Página saturada", price: 15.0, max_chroma: 1.01 },
  ],
};

/** Nivel de una página. `cov` y `chroma` son fracciones 0..1. */
export function tierFor(mode, cov, chroma) {
  const table = mode === "color" ? PRICES.color : PRICES.bw;
  const key = mode === "color" ? "max_chroma" : "max_cov";
  const value = mode === "color" ? chroma : cov;
  return table.find((t) => value <= t[key]) || table[table.length - 1];
}

/**
 * Cotiza el pedido a partir de la medición real de cada página.
 * `pages` = [{cov, chroma}] con una entrada por página, sin contar copias.
 */
export function quoteJob(mode, pages) {
  const table = mode === "color" ? PRICES.color : PRICES.bw;
  const counts = new Map(table.map((t) => [t.id, 0]));
  for (const p of pages) {
    const t = tierFor(mode, Number(p.cov) || 0, Number(p.chroma) || 0);
    counts.set(t.id, counts.get(t.id) + 1);
  }
  const lines = table
    .filter((t) => counts.get(t.id) > 0)
    .map((t) => ({
      id: t.id,
      label: t.label,
      pages: counts.get(t.id),
      price: t.price,
      subtotal: Math.round(counts.get(t.id) * t.price * 100) / 100,
    }));
  const perCopy = Math.round(lines.reduce((s, l) => s + l.subtotal, 0) * 100) / 100;
  return { lines, perCopy, pages: pages.length };
}
