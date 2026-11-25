import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { parseArgs } from 'node:util';

const W = 1024;
const H = 1536;
const bleedSpace = 128;
const displayFamily = 'Montserrat, sans-serif';
const palette = {
  black: '#030407', paper: '#ffffff', blue: '#1558c9', lime: '#d4ff24',
};
const themes = {
  negra: { bg: palette.black, ink: palette.paper, accent: palette.lime, qrText: '#619bff', rule: '#696969' },
  blanca: { bg: palette.paper, ink: palette.black, accent: palette.blue, qrText: palette.blue, rule: '#a5a8b1' },
};
const defaults = JSON.parse(readFileSync(new URL('./contenido.json', import.meta.url), 'utf8'));
const brilintTap = readFileSync(new URL('./recursos/brilint-tap.svg', import.meta.url), 'utf8').trim();

const escapeXml = (str) => str.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
const layer = (id, label, body, dy = 0) =>
  `<g id="${id}" inkscape:groupmode="layer" inkscape:label="${label}"${dy ? ` transform="translate(0 ${dy})"` : ''}>\n${body}\n</g>`;
const text = (value, x, y, size, weight, fill, anchor = 'middle') =>
  `<text x="${x}" y="${y}" font-size="${size}" font-weight="${weight}" fill="${fill}" text-anchor="${anchor}">${escapeXml(value)}</text>`;
const line = (d, color, width) =>
  `<path d="${d}" fill="none" stroke="${color}" stroke-width="${width}" stroke-linecap="round" stroke-linejoin="round"/>`;

function fondo(theme) {
  const { blue, lime } = palette;
  return layer('fondo', '01 · Fondo y ondas', `<rect x="${-bleedSpace}" y="${-bleedSpace}" width="${W + 2 * bleedSpace}" height="${H + 2 * bleedSpace}" fill="${theme.bg}"/>
<path fill="${lime}" d="M-128 -128H300C278 68 141 154 -128 270Z"/>
<path fill="${blue}" d="M-128 -128H208C209 50 62 185 -128 258Z"/>`);
}

function titular({ ink, accent, qrText }, copy) {
  const { blue, lime, paper, black } = palette;
  return layer('titular', '02 · Titular y servicio', `<g font-family="${displayFamily}" font-style="italic">
${text(copy.titulo1, 512, 280, 83, 800, ink)}
<path fill="${blue}" d="M275 301H758Q789 301 781 330L754 424Q748 446 721 446H239Q209 446 217 419L245 330Q253 301 275 301Z"/>
${text(copy.titulo2, 498, 427, 139, 800, paper)}
${line('M811 325l42-27 M823 362l56-2 M809 396l42 19', accent, 14)}
<rect x="218" y="465" width="588" height="66" rx="33" fill="${lime}"/>
${text(copy.servicio, 512, 513, 43, 800, black)}
</g>
${text(copy.entrada1, 512, 588, 43, 700, ink)}
<text x="512" y="635" font-size="43" font-weight="700" fill="${ink}" text-anchor="middle">${escapeXml(copy.entrada2)} <tspan fill="${qrText}" font-weight="800">QR</tspan> o <tspan fill="${accent}" font-weight="800">NFC.</tspan></text>`, -122);
}

function qrAsset() {
  const art = readFileSync(new URL('./recursos/qr-brilint-print.svg', import.meta.url), 'utf8');
  const meta = JSON.parse(readFileSync(new URL('./recursos/qr-brilint-print.json', import.meta.url), 'utf8'));
  const viewBox = `-4 -4 ${meta.modulos + 8} ${meta.modulos + 8}`;
  const modules = art.match(/<path fill="#000000" d="[Mhvz0-9 .-]+"\/>/)?.[0];
  if (!modules || !art.includes(`viewBox="${viewBox}"`)) {
    throw new Error('El recurso QR no incluye los cuatro módulos de margen. Ejecuta qr.py.');
  }
  return { url: meta.url, viewBox, modules };
}

function zonaQr({ accent }, copy, qr) {
  const { blue, paper } = palette;
  const y = 576, side = 465;
  const x = (W - side) / 2;
  const l = x - 27, r = W - l, t = y - 25, b = y + side + 25;
  const frame = `M${l} ${t + 65}v-33q0-32 32-32h33 M${r - 65} ${t}h33q32 0 32 32v33 `
    + `M${l} ${b - 65}v33q0 32 32 32h33 M${r - 65} ${b}h33q32 0 32-32v-33`;
  const symbol = qr
    ? `<svg id="qr-codigo" x="${x + 7}" y="${y + 7}" width="${side - 14}" height="${side - 14}" viewBox="${qr.viewBox}" shape-rendering="crispEdges">\n${qr.modules}\n</svg>`
    : `<g id="qr-placeholder" aria-label="Espacio reservado, no es un código escaneable">
<rect x="${x + 16}" y="${y + 16}" width="${side - 32}" height="${side - 32}" rx="8" fill="none" stroke="#555657" stroke-width="3" stroke-dasharray="9 9"/>
${text('QR', 512, y + side / 2, 76, 800, '#555657')}
${text('TU CÓDIGO AQUÍ', 512, y + side / 2 + 45, 28, 700, '#555657')}
</g>`;
  return layer('qr', '03 · QR y llamada', `<g id="qr-marco">${line(frame, accent, 12)}</g>
<rect id="qr-zona" x="${x}" y="${y}" width="${side}" height="${side}" rx="13" fill="${paper}"/>
${symbol}
<g id="cta"><rect x="312" y="1090" width="400" height="84" rx="42" fill="${blue}"/>
${text(copy.cta, 512, 1148, 49, 800, paper)}
</g>`);
}

function telefono(ink, pantalla) {
  return `<g fill="none" stroke="${ink}" stroke-width="6.2" stroke-linecap="round" stroke-linejoin="round">
<rect x="3" y="3" width="80" height="131" rx="13"/>
<path d="M34 15H52 M39 122H47"/>
${pantalla}</g>`;
}

// Retícula y pictogramas del pie estándar de Maps, sin ocupar su rótulo de reseñas.
function instrucciones({ ink, rule }, copy) {
  return layer('instrucciones', '04 · Cómo usar Tap', `<g id="icono-nfc" transform="translate(109 1205)" aria-hidden="true">
${line('M61 53Q49 68 61 83 M47 44Q27 68 47 92 M33 35Q6 68 33 101', ink, 6.2)}
<g transform="translate(76 0)">${telefono(ink, `<g stroke="none">${text('NFC', 43, 79, 34, 800, ink)}</g>`)}</g>
</g>
${text(copy.acerca, 310, 1263, 40, 800, ink, 'start')}
${text(copy.celular, 310, 1301, 34, 500, ink, 'start')}
${line('M523 1220V1330', rule, 4.6)}
<g id="icono-escaneo" transform="translate(587 1205)" aria-hidden="true">${telefono(ink,
    '<path d="M21 56V46H31 M55 46H65V56 M21 80V90H31 M55 90H65V80"/><path d="M35 68H51" stroke-width="4.6"/>')}</g>
${text(copy.oEscanea, 710, 1263, 40, 800, ink, 'start')}
${text(copy.codigoQr, 710, 1301, 34, 500, ink, 'start')}`);
}

function firma({ ink }) {
  return layer('firma', '05 · Firma Brilint Tap', `<g id="brilint-isotipo" transform="translate(306 1369) scale(1.3125)" aria-hidden="true">
${brilintTap.replace('viewBox="0 0 64 64"', 'viewBox="0 0 64 64" width="64" height="64"')}
</g>
<text x="405" y="1434" font-size="62" fill="${ink}"><tspan font-family="${displayFamily}" font-size="59" font-weight="800">Brilint</tspan><tspan dx="17" font-weight="400">Tap</tspan></text>
<clipPath id="recorte-franja"><rect x="148" y="1483" width="728" height="20" rx="10"/></clipPath>
<g id="franja" clip-path="url(#recorte-franja)">
<rect x="148" y="1483" width="364" height="20" fill="${palette.blue}"/>
<rect x="512" y="1483" width="364" height="20" fill="${palette.lime}"/>
</g>`);
}

function render(variant, width, copy, qr) {
  const theme = themes[variant];
  const alto = Number((width * H / W).toFixed(6));
  return `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" width="${width}mm" height="${alto}mm" viewBox="0 0 ${W} ${H}" font-family="Manrope, sans-serif" xml:lang="es">
<title>Imprime con Brilint · Plantilla ${variant}</title>
<desc>Cartel de copias e impresiones. ${qr ? `QR: ${escapeXml(qr.url)}` : 'Reserva de QR no escaneable.'}</desc>
${fondo(theme)}
${titular(theme, copy)}
${zonaQr(theme, copy, qr)}
${instrucciones(theme, copy)}
${firma(theme)}
</svg>
`;
}

function main() {
  const { values } = parseArgs({ options: {
    salida: { type: 'string', default: 'salida-stand' },
    'ancho-mm': { type: 'string', default: '80' },
    config: { type: 'string' },
    'reserva-qr': { type: 'boolean' },
    ayuda: { type: 'boolean', short: 'h' },
  } });
  if (values.ayuda) {
    console.log('node generar.mjs [--salida directorio] [--ancho-mm 80] [--config cliente.json] [--reserva-qr]');
    return;
  }
  const valor = values['ancho-mm'];
  const width = Number(valor);
  if (!/^\d+(\.\d{1,4})?$/.test(valor) || !Number.isFinite(width) || width < 25 || width > 1000) {
    throw new Error('--ancho-mm debe ser un número entre 25 y 1000 (usa punto decimal).');
  }
  const overrides = values.config ? JSON.parse(readFileSync(values.config, 'utf8')) : {};
  if (!overrides || typeof overrides !== 'object' || Array.isArray(overrides)) {
    throw new Error('--config debe contener un objeto JSON.');
  }
  for (const [clave, texto] of Object.entries(overrides)) {
    if (!Object.hasOwn(defaults, clave)) throw new Error(`Campo de texto desconocido: ${clave}`);
    if (typeof texto !== 'string' || !texto.trim() || /[\u0000-\u0008\u000b\u000c\u000e-\u001f]/.test(texto)) {
      throw new Error(`El campo ${clave} debe contener texto válido.`);
    }
  }
  const copy = { ...defaults, ...overrides };
  const qr = values['reserva-qr'] ? null : qrAsset();
  const suffix = qr ? '' : '-reserva';
  mkdirSync(values.salida, { recursive: true });
  for (const variant of Object.keys(themes)) {
    const archivo = resolve(values.salida, `brilint-print-${variant}${suffix}.svg`);
    writeFileSync(archivo, render(variant, width, copy, qr), { flag: 'wx' });
    console.log(archivo);
  }
}

try {
  main();
} catch (error) {
  console.error(`Imprime con Brilint: ${error.message}`);
  process.exitCode = 1;
}
