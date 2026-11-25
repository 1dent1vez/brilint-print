# Frente de mostrador · Imprime con Brilint

## Direction contract

**THESIS:** Un cartel de mostrador reconocible por «Imprime con Brilint» y un QR que se pueda escanear sin acercarse al texto.

**OWN-WORLD:** Vector plano, fondo medianoche, cobalto y lima; Montserrat ExtraBold (normal y cursiva real) y Manrope. El blanco alterno conserva geometría, texto y escala. Sin perspectiva, sombras ni foto del soporte.

**STORY:** Describir copias e impresiones y dirigir al portal mediante el QR. NFC es el otro acceso del soporte físico, no una función que programe el archivo.

**FIRST VIEWPORT:** Frente 2:3, 80 × 120 mm. Sin reserva superior de logo; titular partido con bloque oblicuo cobalto, cápsula lima, explicación y QR ampliado. Debajo de la cápsula de acción, se replica la retícula del pie estándar de Maps: dos instrucciones con pictogramas, separador vertical, isotipo y firma Brilint Tap al fondo y franja en colores del cartel.

**FORM:** Titular del mockup entregado por el dueño y pie del stand estándar de Maps. Los contrastes y la zona de silencio del QR tienen prioridad. `seed: none (unavailable)`.

**FINISH:** unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance. Es una extensión impresa: no modifica el diseño web.

## Verificación de entrega

- Comparación con el SVG estándar de Maps en Inkscape: coinciden las cajas de las instrucciones, ambos pictogramas, el isotipo y el conjunto de la firma. Revisión visual de negra y blanca a corte: el pie está completo y no hay solapes ni reserva superior.
- Los dos PDF tienen una página, corte 80 × 120 mm y sangrado de 3 mm, sin imágenes ni fuentes activas. El QR de cada PDF decodifica la URL literal a 150 y 300 dpi.
- Pendiente fuera del archivo: prueba en el soporte y grabación/lectura física del chip NFC.
