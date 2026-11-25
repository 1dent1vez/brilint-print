import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, readFileSync, readdirSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

const cli = fileURLToPath(new URL('./generar.mjs', import.meta.url));
const run = (...args) => spawnSync(process.execPath, [cli, ...args], { encoding: 'utf8' });

function workspace(t) {
  const dir = mkdtempSync(join(tmpdir(), 'brilint-print-'));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  return dir;
}

const ediciones = ['negra', 'blanca'];
const svgPath = (dir, edicion) => join(dir, `brilint-print-${edicion}.svg`);
// Fuera del color, las dos ediciones deben ser el mismo documento.
const comparable = (art) => art
  .replace(/<title>.*?<\/title>/, '')
  .replace(/\b(fill|stroke)="#([\da-f]{6})"/gi, '$1="color"');

test('reproduce el cartel Imprime con Brilint en el corte de Maps con QR vectorial', (t) => {
  const dir = workspace(t);
  const result = run('--salida', dir);
  assert.equal(result.status, 0, result.stderr);
  assert.deepEqual(readdirSync(dir).sort(), ediciones.map((edicion) => `brilint-print-${edicion}.svg`).sort());
  for (const edicion of ediciones) {
    const svg = readFileSync(svgPath(dir, edicion), 'utf8');
    assert.match(svg.split('\n')[1], /width="80mm" height="120mm" viewBox="0 0 1024 1536"/);
    assert.match(svg, /id="qr-zona"[^>]*fill="#ffffff"/);
    assert.match(svg, /id="qr-codigo"[^>]*>[\s\S]*?<path/);
    assert.match(svg, /id="icono-nfc"/);
    assert.doesNotMatch(svg, /logo-placeholder|TU LOGO/i);
    for (const copy of ['Imprime con', 'Brilint', 'Copias e impresiones',
      'Accede a nuestros servicios', 'Escanea aquí', 'Acerca', 'tu celular', 'o escanea', 'el código QR', 'Tap']) {
      assert.ok(svg.includes(`>${copy}<`), `Falta el texto ${copy}`);
    }
    assert.match(svg, /https:\/\/brilint-print\.pages\.dev\//);
    assert.doesNotMatch(svg, /<(?:image|script|foreignObject)\b/);
    assert.doesNotMatch(svg, /id="qr-placeholder"/);
  }
});

test('negra y blanca comparten retícula, textos y formas; solo cambia el color', (t) => {
  const dir = workspace(t);
  const result = run('--salida', dir);
  assert.equal(result.status, 0, result.stderr);
  const [negra, blanca] = ediciones.map((edicion) => readFileSync(svgPath(dir, edicion), 'utf8'));
  assert.notEqual(negra, blanca);
  assert.ok(comparable(negra) === comparable(blanca),
    'Fuera del color, la geometría, el texto y los objetos deben ser idénticos.');
});

test('la reserva de QR convive con la pieza terminada y no incrusta código', (t) => {
  const dir = workspace(t);
  assert.equal(run('--salida', dir).status, 0);
  const result = run('--salida', dir, '--reserva-qr');
  assert.equal(result.status, 0, result.stderr);
  for (const edicion of ediciones) {
    const reserva = readFileSync(join(dir, `brilint-print-${edicion}-reserva.svg`), 'utf8');
    assert.match(reserva, /id="qr-placeholder"/);
    assert.doesNotMatch(reserva, /id="qr-codigo"/);
    assert.match(reserva, /id="qr-zona"[^>]*fill="#ffffff"/);
  }
});

test('el pie usa el orden de Maps: instrucciones en dos columnas y firma con isotipo al final', (t) => {
  const dir = workspace(t);
  assert.equal(run('--salida', dir).status, 0);
  for (const edicion of ediciones) {
    const svg = readFileSync(svgPath(dir, edicion), 'utf8');
    assert.match(svg, /id="qr-zona"[^>]*width="465"/);
    assert.match(svg, /id="instrucciones"[\s\S]*id="icono-nfc"[\s\S]*>Acerca<[\s\S]*>tu celular<[\s\S]*id="icono-escaneo"[\s\S]*>o escanea<[\s\S]*>el código QR<[\s\S]*id="firma"[\s\S]*id="brilint-isotipo"[\s\S]*>Brilint<[\s\S]*>Tap</);
  }
});

test('aplica texto propio, conserva la proporción y escapa el marcado', (t) => {
  const dir = workspace(t);
  const contenido = join(dir, 'cliente.json');
  writeFileSync(contenido, JSON.stringify({ titulo1: 'Café & Té <Local>' }));
  const result = run('--salida', dir, '--config', contenido, '--ancho-mm', '74');
  assert.equal(result.status, 0, result.stderr);

  for (const edicion of ediciones) {
    const svg = readFileSync(svgPath(dir, edicion), 'utf8');
    assert.match(svg.split('\n')[1], /width="74mm" height="111mm" viewBox="0 0 1024 1536"/);
    assert.ok(svg.includes('>Café &amp; Té &lt;Local&gt;<'));
  }
});

test('no genera archivos con tamaños inválidos ni claves de personalización desconocidas', (t) => {
  const dir = workspace(t);
  const salida = join(dir, 'salida');
  const contenido = join(dir, 'cliente.json');
  writeFileSync(contenido, '{"titlo":"Error"}');
  const tamano = run('--salida', salida, '--ancho-mm', 'NaN');
  assert.equal(tamano.status, 1);
  assert.match(tamano.stderr, /ancho-mm/);
  const campo = run('--salida', salida, '--config', contenido);
  assert.equal(campo.status, 1);
  assert.match(campo.stderr, /titlo/);
  assert.deepEqual(readdirSync(dir), ['cliente.json']);
});
