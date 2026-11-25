"""Verifica el preflight y decodifica las salidas reales, sin imprimir."""

import argparse
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from PIL import Image
from pypdf import PdfReader
from zxingcpp import BarcodeFormat, read_barcodes

ROOT = Path(__file__).resolve().parent
URL = 'https://brilint-print.pages.dev/'
PT_PER_MM = 72 / 25.4
STEMS = tuple(f'brilint-print-{color}' for color in ('negra', 'blanca'))


def lecturas(png):
    with Image.open(png) as image:
        return [code.text for code in read_barcodes(image, formats=BarcodeFormat.QRCode)]


class PreprensaTest(unittest.TestCase):
    def test_los_dos_pdf_vectoriales_con_corte_sangrado_y_qr(self):
        with tempfile.TemporaryDirectory(prefix='stand-test-') as tmp:
            root = Path(tmp)
            subprocess.run(['node', str(ROOT / 'generar.mjs'), '--salida', str(root)],
                           check=True, capture_output=True)
            for stem in STEMS:
                with self.subTest(pieza=stem):
                    subprocess.run([sys.executable, str(ROOT / 'preprensa.py'), str(root / f'{stem}.svg'),
                                    '--salida', str(root)], check=True, capture_output=True)
                    comprobar_pdf(self, root / f'{stem}.pdf', root)

    def test_qr_suelto_con_la_misma_liga(self):
        with tempfile.TemporaryDirectory(prefix='stand-qr-') as tmp:
            png = Path(tmp) / 'qr.png'
            svg = ROOT / 'recursos' / 'qr-brilint-print.svg'
            subprocess.run(['inkscape', str(svg), '--export-width=592', f'--export-filename={png}'],
                           check=True, capture_output=True)
            self.assertEqual(lecturas(png), [URL])


def comprobar_pdf(test, pdf, tmp):
    pages = PdfReader(pdf).pages
    test.assertEqual(len(pages), 1)
    page = pages[0]
    for box, expected in ((page.trimbox, (3, 3, 83, 123)), (page.bleedbox, (0, 0, 86, 126)),
                          (page.mediabox, (0, 0, 86, 126)), (page.cropbox, (0, 0, 86, 126))):
        for actual, mm in zip(box, expected, strict=True):
            test.assertAlmostEqual(float(actual), mm * PT_PER_MM, places=4)
    test.assertEqual(len(page.images), 0)
    test.assertFalse(page['/Resources'].get('/Font'))
    for dpi in (150, 300):
        prefix = tmp / f'{pdf.stem}-{dpi}'
        subprocess.run(['pdftoppm', '-r', str(dpi), '-singlefile', '-png', str(pdf), str(prefix)],
                       check=True, capture_output=True)
        test.assertEqual(lecturas(prefix.with_suffix('.png')), [URL], f'{pdf.name} a {dpi} dpi')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pdf-dir', type=Path, help='Verifica los archivos de la entrega en vez de regenerarlos.')
    args = parser.parse_args()
    if args.pdf_dir:
        test = unittest.TestCase()
        test.assertEqual(sorted(path.stem for path in args.pdf_dir.glob('*.pdf')), sorted(STEMS))
        with tempfile.TemporaryDirectory(prefix='stand-preflight-') as tmp:
            for stem in STEMS:
                pdf = args.pdf_dir / f'{stem}.pdf'
                comprobar_pdf(test, pdf, Path(tmp))
                print(f'{pdf.name}: 80 × 120 mm + 3 mm, vectorial, QR verificado a 150 y 300 dpi.')
    else:
        unittest.main(argv=[sys.argv[0]])
