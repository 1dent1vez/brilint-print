#!/usr/bin/env python3
"""Arte del mostrador: QR + soporte A6 para Print with Brilint."""
from pathlib import Path
import segno, subprocess

URL = "https://brilint-print.pages.dev"
ART = Path(__file__).resolve().parent.parent / "art"
ART.mkdir(exist_ok=True)

# ---- QR (negro sobre blanco, zona de silencio incluida en la tarjeta) ----
qr = segno.make(URL, error="m")
qr.save(ART / "qr-stand.png", scale=20, border=2, dark="#030407", light="#ffffff")
qr.save(ART / "qr-stand.svg", scale=20, border=2, dark="#030407", light="#ffffff")
(ART / "nfc-payload.txt").write_text(
    "Contenido NDEF del tag NFC (tipo URI/URL, una sola vez):\n"
    f"{URL}\n\n"
    "Escríbelo con NFC Tools (Android, Pixel 7a) sobre un NTAG213 antimetal,\n"
    "verifica con una lectura física y solo entonces bloquea el tag.\n",
    encoding="utf-8",
)

# ---- soporte A6 (105 x 148 mm) ----
W, H = 105, 148
svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}mm" height="{H}mm" viewBox="0 0 {W} {H}">
  <rect width="{W}" height="{H}" fill="#030407"/>
  <rect x="0" y="0" width="{W}" height="2.4" fill="#d4ff24"/>

  <text x="10" y="19" font-family="Manrope" font-weight="700" font-size="8.4" fill="#f5f5f1" letter-spacing="-0.1">SUBE TUS</text>
  <text x="10" y="28.4" font-family="Manrope" font-weight="700" font-size="8.4" fill="#f5f5f1" letter-spacing="-0.1">ARCHIVOS</text>

  <text x="10" y="43" font-family="Manrope" font-size="3.6" fill="#a5a8b1">PDF · JPG · PNG · hasta 80 MB</text>

  <rect x="10" y="48" width="85" height="0.4" fill="#1558c9"/>

  <rect x="18.5" y="55" width="68" height="68" fill="#ffffff"/>
  <image x="22.5" y="59" width="60" height="60" href="qr-stand.png"/>

  <text x="10" y="131" font-family="Manrope" font-weight="700" font-size="4.6" fill="#d4ff24" letter-spacing="0.1">ACERCA TU TELÉFONO</text>
  <text x="10" y="138.6" font-family="Manrope" font-size="3.4" fill="#a5a8b1">o escanea el código y sube tus archivos</text>

  <text x="10" y="144.4" font-family="Manrope" font-size="2.8" fill="#a5a8b1">1. Sube · 2. Confirmas el total · 3. Recoges con tu folio</text>

  <g transform="translate(84 17)" stroke="#d4ff24" stroke-width="0.7" fill="none" stroke-linecap="round">
    <path d="M0 2.8a4.6 4.6 0 0 1 4.6-4.6M0 5.6a7.4 7.4 0 0 1 7.4-7.4"/>
  </g>
  <circle cx="84" cy="19.8" r="1.1" fill="#d4ff24"/>
</svg>'''
svg_path = ART / "soporte-a6.svg"
svg_path.write_text(svg, encoding="utf-8")

pdf = ART / "soporte-a6.pdf"
r = subprocess.run(["inkscape", str(svg_path), "--export-type=pdf",
                    f"--export-filename={pdf}"], capture_output=True, text=True)
print("inkscape:", r.returncode, (r.stderr or "")[:200])
print("URL:", URL)
for f in sorted(ART.iterdir()):
    print(f" {f.name:22} {f.stat().st_size/1024:7.1f} KB")
