// Interpreta las notas libres del cliente y las convierte en un plan de impresión.
// El modelo propone; este archivo decide: whitelist, rangos y topes. Nada de lo
// que devuelve la IA se aplica sin pasar por `sanitize`.

const MODEL = "@cf/meta/llama-3.1-8b-instruct";
const MAX_OPS = 6;

const SYSTEM = `Eres el intérprete de notas de una copiadora de barrio en México.
Conviertes la nota del cliente en operaciones de impresión. Devuelves SOLO JSON, sin markdown ni explicación.

Operaciones permitidas:
{"op":"paginas","archivo":0,"desde":2,"hasta":5}   // imprimir solo ese rango
{"op":"tamano","archivo":0,"papel":"carta"}         // "carta" | "a4" | "media-carta"
{"op":"escala","archivo":0,"pagina":2,"fraccion":0.5} // contenido a la mitad de la hoja
{"op":"bn","archivo":0}                             // forzar blanco y negro
{"op":"color","archivo":0}                          // forzar color
{"op":"nup","archivo":0,"porHoja":2}                // 2 páginas por hoja
{"op":"personal","texto":"corte a la mitad"}        // lo que NO puedes hacer: doble cara, engargolado, corte, tamaño distinto

Reglas:
- "ambos lados", "doble cara", "engargolado", "corte", "grapado" => {"op":"personal"} con el texto original.
- Si la nota no pide nada concreto, devuelve {"ops":[],"no_entendido":""}.
- Un archivo por operación; usa el índice de la lista que te doy.
- Salida: {"ops":[...],"no_entendido":"texto que no supiste interpretar o vacío"}`;

function extractJson(text) {
  if (!text) return null;
  const fenced = text.match(/```(?:json)?\s*([\s\S]*?)```/i);
  const body = fenced ? fenced[1] : text;
  const start = body.indexOf("{");
  const end = body.lastIndexOf("}");
  if (start < 0 || end <= start) return null;
  try { return JSON.parse(body.slice(start, end + 1)); } catch { return null; }
}

const int = (v) => (Number.isFinite(Number(v)) ? Math.trunc(Number(v)) : null);
const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

function sanitize(raw, files) {
  const ops = [];
  const seen = new Set();
  for (const o of Array.isArray(raw?.ops) ? raw.ops : []) {
    if (ops.length >= MAX_OPS) break;
    const op = String(o?.op || "");
    const idx = int(o?.archivo);
    const validFile = idx !== null && idx >= 0 && idx < files.length;
    const pages = validFile ? files[idx].pages : 0;

    if (op === "personal") {
      const texto = String(o?.texto || "").trim().slice(0, 120);
      if (texto) ops.push({ op, texto });
      continue;
    }
    if (!validFile) continue;

    if (op === "paginas") {
      let d = int(o?.desde), h = int(o?.hasta);
      if (d === null || h === null) continue;
      d = clamp(d, 1, pages); h = clamp(h, 1, pages);
      if (h < d) [d, h] = [h, d];
      if (d === 1 && h === pages) continue; // no cambia nada
      const key = `paginas:${idx}`;
      if (seen.has(key)) continue;
      seen.add(key);
      ops.push({ op, archivo: idx, desde: d, hasta: h });
    } else if (op === "tamano") {
      const papel = ["carta", "a4", "media-carta"].includes(o?.papel) ? o.papel : null;
      if (!papel) continue;
      const key = `tamano:${idx}`;
      if (seen.has(key)) continue;
      seen.add(key);
      ops.push({ op, archivo: idx, papel });
    } else if (op === "escala") {
      let pagina = int(o?.pagina), f = Number(o?.fraccion);
      if (pagina === null || !Number.isFinite(f)) continue;
      pagina = clamp(pagina, 1, pages);
      f = clamp(f, 0.2, 1);
      const key = `escala:${idx}:${pagina}`;
      if (seen.has(key)) continue;
      seen.add(key);
      ops.push({ op, archivo: idx, pagina, fraccion: Math.round(f * 100) / 100 });
    } else if (op === "bn" || op === "color") {
      // El modo global ya se elige en la web: solo tiene sentido el opuesto.
      ops.push({ op, archivo: idx });
    } else if (op === "nup") {
      const n = int(o?.porHoja);
      if (![2, 4].includes(n)) continue;
      if (pages < 2) continue;
      const key = `nup:${idx}`;
      if (seen.has(key)) continue;
      seen.add(key);
      ops.push({ op, archivo: idx, porHoja: n });
    }
  }
  const noEntendido = String(raw?.no_entendido || "").trim().slice(0, 200);
  return { ops, no_entendido: noEntendido };
}

export async function planFromNotes(env, notes, files) {
  const clean = String(notes || "").trim();
  if (!env?.AI || clean.length < 3) {
    return { ops: [], no_entendido: clean ? "" : "", sin_motor: !env?.AI };
  }
  const inventario = files.map((f, i) => ({ archivo: i, nombre: f.name, paginas: f.pages }));
  try {
    const res = await env.AI.run(MODEL, {
      messages: [
        { role: "system", content: SYSTEM },
        { role: "user", content: `Archivos: ${JSON.stringify(inventario)}\nNota del cliente: "${clean}"` },
      ],
      max_tokens: 400,
      temperature: 0,
    });
    const raw = typeof res === "string" ? res : (res?.response || "");
    const json = extractJson(raw);
    if (!json) return { ops: [], no_entendido: clean.slice(0, 200) };
    const plan = sanitize(json, files);
    plan.modelo = MODEL;
    return plan;
  } catch (e) {
    console.error("planner_error", String(e).slice(0, 200));
    return { ops: [], no_entendido: clean.slice(0, 200), error: true };
  }
}
