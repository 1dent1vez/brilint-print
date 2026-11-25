"""Exporta un SVG del mostrador a PDF vectorial con cajas de preprensa."""

import argparse
import math
from pathlib import Path
import re
import subprocess
import tempfile
from xml.etree import ElementTree

from pypdf import PdfWriter, Transformation
from pypdf.generic import RectangleObject


MM_TO_PT = 72 / 25.4
SVG_NAMESPACE = 'http://www.w3.org/2000/svg'
SODIPODI_NAMESPACE = 'http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd'
ElementTree.register_namespace('', SVG_NAMESPACE)
ElementTree.register_namespace('inkscape', 'http://www.inkscape.org/namespaces/inkscape')


def medidas(root):
    if root.tag != f'{{{SVG_NAMESPACE}}}svg':
        raise ValueError('La entrada debe ser un SVG.')
    result = []
    for name in ('width', 'height'):
        match = re.fullmatch(r'(\d+(?:\.\d+)?)mm', root.get(name, '').strip())
        if not match or not 0 < float(match[1]) <= 1500:
            raise ValueError(f'El SVG debe declarar {name} en mm.')
        result.append(float(match[1]))
    return result


def extender_pagina(tree, width, height, bleed):
    root = tree.getroot()
    viewbox = [float(value) for value in re.split(r'[\s,]+', root.get('viewBox', '').strip())]
    if len(viewbox) != 4 or not all(map(math.isfinite, viewbox)) or min(viewbox[2:]) <= 0:
        raise ValueError('El SVG debe tener un viewBox válido.')
    x, y, w, h = viewbox
    if not math.isclose(w / width, h / height, rel_tol=1e-6):
        raise ValueError('El viewBox y las medidas físicas deben compartir proporción.')
    # Un viewBox mayor incluye el arte que ya existe fuera del corte. Inkscape
    # puede ignorar --export-margin cuando el SVG no define una página nativa.
    bx, by = bleed * w / width, bleed * h / height
    root.set('viewBox', ' '.join(f'{value:.8f}' for value in (x - bx, y - by, w + 2 * bx, h + 2 * by)))
    root.set('width', f'{width + 2 * bleed:.8f}mm')
    root.set('height', f'{height + 2 * bleed:.8f}mm')
    for named_view in root.findall(f'{{{SODIPODI_NAMESPACE}}}namedview'):
        root.remove(named_view)


def exportar(svg, output_dir, bleed):
    tree = ElementTree.parse(svg)
    width, height = medidas(tree.getroot())
    if not math.isfinite(bleed) or not 0 <= bleed <= min(width, height) / 8:
        raise ValueError('Sangrado fuera del área prevista por la plantilla.')
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f'{svg.stem}.pdf'
    if output.exists():
        raise FileExistsError(f'Ya existe {output}; usa otra carpeta de salida.')

    # El temporal vive junto a la salida: Inkscape en flatpak no siempre puede
    # leer /tmp, y el sandbox solo ve el directorio del usuario.
    with tempfile.TemporaryDirectory(prefix='.stand-', dir=output_dir) as tmp:
        padded_svg = Path(tmp) / 'con-sangrado.svg'
        extender_pagina(tree, width, height, bleed)
        tree.write(padded_svg, encoding='utf-8', xml_declaration=True)
        staged = Path(tmp) / 'inkscape.pdf'
        subprocess.run(['inkscape', str(padded_svg), '--export-area-page', '--export-text-to-path',
                        f'--export-filename={staged}'], check=True)
        writer = PdfWriter(clone_from=staged)
        if len(writer.pages) != 1:
            raise ValueError('La plantilla debe generar exactamente una página.')
        page = writer.pages[0]
        if len(page.images) or page['/Resources'].get('/Font'):
            raise ValueError('Exportación no vectorial o con fuentes activas. Usa logo y QR vectoriales, sin filtros rasterizados.')

        # Fijar las cajas con precisión sin reescalar los trazados.
        outer_width = (width + 2 * bleed) * MM_TO_PT
        outer_height = (height + 2 * bleed) * MM_TO_PT
        dx = (outer_width - float(page.mediabox.width)) / 2
        dy = (outer_height - float(page.mediabox.height)) / 2
        if abs(dx) > 0.75 or abs(dy) > 0.75:
            raise ValueError('Inkscape exportó medidas inesperadas; comprueba el SVG y el sangrado.')
        page.add_transformation(Transformation().translate(dx, dy))
        outer_box = (0, 0, outer_width, outer_height)
        trim_box = tuple(v * MM_TO_PT for v in (bleed, bleed, width + bleed, height + bleed))
        page.mediabox = RectangleObject(outer_box)
        page.cropbox = RectangleObject(outer_box)
        page.bleedbox = RectangleObject(outer_box)
        page.trimbox = RectangleObject(trim_box)
        complete = Path(tmp) / 'preprensa.pdf'
        with complete.open('wb') as finalized:
            writer.write(finalized)
        with output.open('xb') as target:
            target.write(complete.read_bytes())
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('svg', type=Path)
    parser.add_argument('--salida', type=Path, default=Path('impresion-stand'))
    parser.add_argument('--sangrado-mm', type=float, default=3)
    args = parser.parse_args()
    try:
        print(exportar(args.svg.resolve(), args.salida.resolve(), args.sangrado_mm))
    except (OSError, ValueError, ElementTree.ParseError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f'Print with Brilint: {exc}\n')


if __name__ == '__main__':
    main()
