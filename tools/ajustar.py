#!/usr/bin/env python3
"""
Ajusta el archivo de un pedido en revisión, sin adivinar.

Uso típico (desde la raíz del proyecto, con el python del proyecto):
    .venv/bin/python tools/ajustar.py "~/Desktop/Impresiones/261122-76CR/00-foto-listo-para-imprimir.pdf" \
        --cm 10x10

Operaciones:
  --cm 10x10        hoja exacta de 10 x 10 cm
  --cm 10x15        (o cualquier medida en centímetros)
  --scale 0.5       contenido al 50% de la hoja, centrado
  --fit             escalar el contenido para llenar la hoja sin deformar
  --rotate 90       girar el contenido
  --pages 2-5,8     quedarse solo con esas páginas
  --nup 2           dos páginas del original por hoja carta
  --margin 0.5      margen interior en cm
  --out RUTA        guardar en otro archivo (por defecto sobreescribe)

Siempre deja un PDF de una sola medida de hoja, listo para imprimir.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import pymupdf
except ImportError:  # pymupdf < 1.24
    import fitz as pymupdf

CM = 72.0 / 2.54
PAPERS = {"carta": (612, 792), "a4": (595.28, 841.89), "oficio": (612, 1008)}


def parse_pages(spec: str, total: int) -> list[int]:
    out = []
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "-" in chunk:
            a, b = chunk.split("-", 1)
            out.extend(range(int(a), int(b) + 1))
        else:
            out.append(int(chunk))
    # 1-based → 0-based, dentro del documento
    return [p - 1 for p in out if 1 <= p <= total]


def main() -> int:
    ap = argparse.ArgumentParser(description="Ajusta el PDF de un pedido")
    ap.add_argument("pdf")
    ap.add_argument("--cm", help="medida de hoja en cm, ej. 10x10")
    ap.add_argument("--paper", choices=list(PAPERS), help="hoja estándar")
    ap.add_argument("--scale", type=float, help="contenido al N por ciento de la hoja")
    ap.add_argument("--fit", action="store_true", help="llenar la hoja sin deformar")
    ap.add_argument("--rotate", type=int, choices=[0, 90, 180, 270], default=0)
    ap.add_argument("--pages", help="ej. 2-5,8")
    ap.add_argument("--nup", type=int, choices=[1, 2], default=1, help="2 = dos páginas por hoja")
    ap.add_argument("--margin", type=float, default=0.0, help="margen en cm")
    ap.add_argument("--out", help="archivo de salida")
    args = ap.parse_args()

    src_path = Path(args.pdf).expanduser()
    if not src_path.exists():
        print(f"No existe: {src_path}", file=sys.stderr)
        return 2

    src = pymupdf.open(src_path)
    if src.page_count == 0:
        print("El PDF no tiene páginas", file=sys.stderr)
        return 2

    indices = parse_pages(args.pages, src.page_count) if args.pages else list(range(src.page_count))
    if not indices:
        print("Ninguna página coincide con --pages", file=sys.stderr)
        return 2

    # Hoja destino en puntos
    if args.cm:
        try:
            w_cm, h_cm = (float(x) for x in args.cm.lower().replace("×", "x").split("x"))
        except ValueError:
            print("--cm debe ser como 10x15", file=sys.stderr)
            return 2
        sheet = (w_cm * CM, h_cm * CM)
    elif args.paper:
        sheet = PAPERS[args.paper]
    else:
        sheet = (src[0].rect.width, src[0].rect.height)

    margin = args.margin * CM
    avail_w = max(1.0, sheet[0] - 2 * margin)
    avail_h = max(1.0, sheet[1] - 2 * margin)

    out = pymupdf.open()
    rot = pymupdf.Matrix(args.rotate).prerotate(0)

    if args.nup == 2 and not args.cm:
        # Dos originales por hoja, apilados, cada uno a la mitad.
        for i in range(0, len(indices), 2):
            page = out.new_page(width=sheet[0], height=sheet[1])
            half = (sheet[1] - 2 * margin) / 2
            for slot, idx in enumerate(indices[i:i + 2]):
                s = src[idx]
                scale = min(avail_w / s.rect.width, half / s.rect.height)
                w, h = s.rect.width * scale, s.rect.height * scale
                x0 = margin + (avail_w - w) / 2
                y0 = margin + slot * half + (half - h) / 2
                page.show_pdf_page(pymupdf.Rect(x0, y0, x0 + w, y0 + h), src, idx)
        n_pages = out.page_count
    else:
        for idx in indices:
            s = src[idx]
            page = out.new_page(width=sheet[0], height=sheet[1])
            sw, sh = s.rect.width, s.rect.height
            if args.rotate in (90, 270):
                sw, sh = sh, sw
            if args.fit:
                scale = min(avail_w / sw, avail_h / sh)
            elif args.scale:
                scale = (args.scale / 100.0) * min(avail_w / sw, avail_h / sh)
            else:
                scale = min(avail_w / sw, avail_h / sh)
            w, h = sw * scale, sh * scale
            x0 = margin + (avail_w - w) / 2
            y0 = margin + (avail_h - h) / 2
            target = pymupdf.Rect(x0, y0, x0 + w, y0 + h)
            page.show_pdf_page(target, src, idx, rotate=args.rotate)
        n_pages = out.page_count

    dst = Path(args.out).expanduser() if args.out else src_path
    out.save(dst, garbage=3, deflate=True)
    out.close()

    print(f"{dst}")
    print(f"  páginas: {n_pages} (de {src.page_count})")
    print(f"  hoja: {sheet[0] / CM:.1f} x {sheet[1] / CM:.1f} cm")
    if args.rotate:
        print(f"  rotación: {args.rotate}°")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
