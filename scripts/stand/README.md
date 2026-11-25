# Imprime con Brilint · cartel de mostrador

Frente vectorial de «Imprime con Brilint» en **80 × 120 mm (8 × 12 cm)**. Ambas variantes, negra y blanca, son sin reserva de logo y conservan la misma geometría. El pie sigue el stand estándar de Google Maps: dos pictogramas con «Acerca tu celular» y «o escanea el código QR», y al final el isotipo y la firma Brilint Tap.

El QR incluido apunta literalmente a **https://brilint-print.pages.dev/**. Es negro sobre blanco, corrección Q, con cuatro módulos de margen como mínimo. Para NFC, graba esa misma URL como registro URI NDEF en el chip físico; el archivo no programa el chip. Escanea y prueba el NFC por separado en un ejemplar físico antes del tiraje.

## Editar o regenerar

Instala las fuentes de `fuentes/` (Manrope 400/500/700/800 y Montserrat ExtraBold normal y cursiva) y abre el SVG en Inkscape. Usa Node 22+, Python con `pip install -r requirements.txt`, Inkscape y Poppler (`pdftoppm`).

En el paquete, los SVG están en `editables/`, los PDF en `pdf/`, las vistas a corte en `vistas/` y el QR suelto en `qr/`. Ejecuta los siguientes comandos dentro de `codigo/` en el paquete o de `scripts/stand/` en el proyecto.

```sh
python qr.py
node generar.mjs --salida salida-stand
python preprensa.py salida-stand/brilint-print-negra.svg --salida pdf
node --test plantillas.test.mjs
python test_preprensa.py
```

No hace falta regenerar el QR si no cambia la URL. `qr.py --url https://…/` actualiza el SVG suelto y su ficha en `recursos/`; vuelve a generar los másteres y comprueba el destino real si lo cambias. Las pruebas de esta entrega fijan su URL literal. `--reserva-qr` crea un máster sin código para sustituir manualmente; `--config cliente.json` acepta las mismas claves de texto que `contenido.json`. Revisa cualquier texto nuevo en Inkscape. `--ancho-mm` mantiene la proporción 2:3; los archivos existentes no se sobrescriben.

## Imprimir

PDF vectorial RGB con las fuentes trazadas, **3 mm de sangrado por lado**, página de **86 × 126 mm** y TrimBox de **80 × 120 mm**. Seleccionar **tamaño real / 100 %** y cortar por la TrimBox. No es PDF/X ni CMYK. `python test_preprensa.py --pdf-dir <carpeta>` comprueba cajas, ausencia de imágenes y fuentes activas, y decodifica el QR de cada PDF rasterizado a 150 y 300 dpi.

Procedencia: titular y paleta del mockup; pie, pictogramas e isotipo de `scripts/tap/` del proyecto Brilint. Las vistas se renderizan desde los PDF. Manrope procede del WOFF2 variable del portal, instanciado localmente; Montserrat ExtraBold normal y cursiva proceden del paquete Fedora `julietaula-montserrat-fonts`. Las licencias SIL OFL 1.1 acompañan a las fuentes.
