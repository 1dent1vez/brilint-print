#!/usr/bin/env python3
"""Genera el QR vectorial de la plantilla del mostrador.

El QR tiene que ser un trazo vectorial dentro del SVG: una imagen rasterizada
pierde calidad al imprimir y hace fallar la comprobación de preprensa.

Uso:  .venv/bin/python qr.py [--url https://brilint-print.pages.dev/]
"""

import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit

import segno

AQUI = Path(__file__).resolve().parent
RECURSOS = AQUI / "recursos"
URL = "https://brilint-print.pages.dev/"
# Q tolera ~25 % de daño: cubre el desgaste de una pieza de mostrador.
ERROR = "q"
MARGEN = 4


def matriz(url):
    qr = segno.make_qr(url, error=ERROR)
    return qr.matrix, qr.version, qr.error


def trazo(matrix):
    """Un solo path con run-length por fila: bordes limpios, sin costuras."""
    filas = []
    for y, fila in enumerate(matrix):
        x = 0
        ancho = len(fila)
        while x < ancho:
            if not fila[x]:
                x += 1
                continue
            inicio = x
            while x < ancho and fila[x]:
                x += 1
            filas.append(f"M{inicio} {y}h{x - inicio}v1h-{x - inicio}z")
    return "".join(filas)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=URL)
    args = parser.parse_args()
    uri = urlsplit(args.url)
    if uri.scheme != 'https' or not uri.hostname or any(c.isspace() for c in args.url):
        parser.error('La URL debe ser completa, HTTPS y sin espacios.')
    RECURSOS.mkdir(exist_ok=True)
    matrix, version, error = matriz(args.url)
    modulos = len(matrix)
    total = modulos + 2 * MARGEN
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{-MARGEN} {-MARGEN} {total} {total}" '
        f'width="{total}" height="{total}" shape-rendering="crispEdges">\n'
        f'<rect x="{-MARGEN}" y="{-MARGEN}" width="{total}" height="{total}" fill="#ffffff"/>\n'
        f'<path fill="#000000" d="{trazo(matrix)}"/>\n'
        "</svg>\n"
    )
    salida = RECURSOS / "qr-brilint-print.svg"
    salida.write_text(svg, encoding="utf-8")
    meta = {"url": args.url, "modulos": modulos, "version": version, "correccion": error, "margen": MARGEN}
    (RECURSOS / "qr-brilint-print.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False))


if __name__ == "__main__":
    main()
