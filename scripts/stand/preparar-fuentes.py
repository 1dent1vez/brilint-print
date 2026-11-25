#!/usr/bin/env python3
"""Prepara las fuentes de la plantilla a partir de los woff2 del sitio.

Inkscape y fontconfig no leen woff2: sin este paso el SVG cae a una fuente del
sistema y la pieza sale fuera de marca sin ningún error visible.

Uso:  .venv/bin/python preparar-fuentes.py [--instalar]
"""

import argparse
import shutil
from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

AQUI = Path(__file__).resolve().parent
SITIO = AQUI.parent.parent / "site" / "fonts"
SALIDA = AQUI / "fuentes"

# Manrope se sirve como fuente variable con peso por omisión 200 (ExtraLight).
# Hay que fijar cada instancia o el cuerpo de texto sale casi hairline.
INSTANCIAS = [
    (400, "Regular", "Regular"),
    (500, "Medium", "Medium"),
    (700, "Bold", "Bold"),
    (800, "ExtraBold", "ExtraBold"),
]


def renombrar(font, familia, estilo, id_estilo):
    nombre = font["name"]
    nombre.setName(familia, 1, 3, 1, 0x409)
    nombre.setName(estilo, 2, 3, 1, 0x409)
    nombre.setName(f"{familia} {estilo}", 4, 3, 1, 0x409)
    nombre.setName(f"{familia.replace(' ', '')}-{estilo}", 6, 3, 1, 0x409)
    nombre.setName(familia, 16, 3, 1, 0x409)
    nombre.setName(estilo, 17, 3, 1, 0x409)
    font["OS/2"].usWeightClass = id_estilo


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instalar", action="store_true",
                        help="copiar además a ~/.local/share/fonts y refrescar fontconfig")
    args = parser.parse_args()

    SALIDA.mkdir(exist_ok=True)
    destino_fuentes = Path.home() / ".local/share/fonts"

    for peso, estilo, archivo in INSTANCIAS:
        font = TTFont(SITIO / "manrope-var.woff2")
        font.flavor = None
        instantiateVariableFont(font, {"wght": peso}, inplace=True)
        renombrar(font, "Manrope", estilo, peso)
        salida = SALIDA / f"Manrope-{archivo}.ttf"
        font.save(salida)
        print(salida)
        if args.instalar:
            destino_fuentes.mkdir(parents=True, exist_ok=True)
            shutil.copy2(salida, destino_fuentes / salida.name)

    bebas = TTFont(SITIO / "bebas-neue-400.woff2")
    bebas.flavor = None
    renombrar(bebas, "Bebas Neue", "Regular", 400)
    salida = SALIDA / "BebasNeue-Regular.ttf"
    bebas.save(salida)
    print(salida)
    if args.instalar:
        destino_fuentes.mkdir(parents=True, exist_ok=True)
        shutil.copy2(salida, destino_fuentes / salida.name)


if __name__ == "__main__":
    main()
