# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Cloudflare Pages (static assets + Pages Functions), D1 for the job queue, R2 for uploaded files. No build step on the front end (vanilla HTML/CSS/JS). Django-free, framework-free by decision: the surface is a form, not an app.

## Users

- **Cliente del mostrador (primario):** persona en la calle, de 20 a 60 años, en el local o llegando a él, con el celular en la mano y prisa. Trae archivos en WhatsApp, en Descargas o en una foto de la cámara. No quiere instalar nada, no quiere crear cuenta, no quiere pagar en línea.
- **Dueño/operador (secundario):** una sola persona, frente a una laptop Linux con la impresora conectada por USB. Recibe el pedido impreso y cobra en el mostrador.

## Product Purpose

Recibir archivos de impresión y cotizarlos antes de que el cliente llegue al mostrador, para que el pedido se imprima solo y el cliente solo pase a pagar y recoger. Éxito = el archivo llega completo y con instrucciones claras, sin reimpresiones y sin que nadie tenga que reenviarlo por WhatsApp ni dictar páginas.

## Positioning

No es una app de impresión ni un marketplace: es la puerta de entrada del mostrador físico. El archivo entra por un tap NFC o un escaneo de QR y sale impreso en la misma laptop que ya opera la impresora. Cotización inmediata sin cuenta, sin pago en línea y sin instalar nada; el cobro ocurre en el mostrador, como siempre.

## Operating Context

- Negocio físico de copias e impresiones, volumen bajo y pedidos chicos; la mayoría se resuelve el mismo día.
- Impresora HP Smart Tank 580, conectada por USB a la laptop del mostrador. Se imprime por la cola CUPS directa del sistema (`Smart-Tank-580-590`, `hp:/usb/...`), no por la cola `HP_USB`, que es un puente `ipp://localhost:60000` que solo existe mientras la app del fabricante está abierta: cuando se cierra, CUPS deshabilita esa cola y todo lo que se manda se queda atorado y termina en error. Sin dúplex automático, sin alimentador, 400–800 páginas/mes recomendadas.
- Cliente en el local, de pie, con luz de día o del local, pantalla de teléfono a 20–40 cm.
- El pedido se identifica por folio; el cliente lo dice en el mostrador.
- Papelería y precios en pesos mexicanos; tamaño de hoja Carta por defecto.

## Capabilities and Constraints

Confirmado:
- Subir uno o varios archivos (PDF, JPG, PNG), elegir color o blanco y negro, indicar número de copias, dejar notas libres y ver el total antes de enviar.
- El pedido entra a una cola; la laptop lo recoge, lo imprime y lo marca como listo.
- NFC y QR impresos en el mostrador apuntan a esta misma página.
- Sin pago en línea en esta versión. Sin cuentas de usuario. Sin app.
- La cotización es estimada: la cantidad de páginas se confirma al imprimir y el cobro es en mostrador.
- Doble cara, tamaños especiales y acabados no se automatizan: se piden en el campo de notas y se resuelven en el mostrador.

Abierto / no decidido:
- Precios por página (B/N y color) pendientes de confirmar con la lista del negocio.
- Dominio final: hoy la página vive en un proyecto de Cloudflare Pages; el subdominio propio queda por definir.

## Brand Commitments

- Marca: **Print with Brilint**, dentro del sistema visual Brilint (negro medianoche, cobalto, lima ácido, blanco suave; Bebas Neue como voz de cartel, Manrope como voz que explica). El sistema está documentado en `~/Documents/brilint/docs/brand-guidelines.md` y `docs/brand/tokens.css`.
- Tono: directo, sin jerga y sin adornos; una sola prioridad por pantalla.
- El cliente es de la calle: nada de lenguaje técnico, nada de promesas de resultados.

## Evidence on Hand

- Marca y tokens: `~/Documents/brilint/docs/brand/` (tokens.css, board.template.html), sitio Astro en `~/Documents/brilint`.
- Impresora: capacidades reales tomadas de la ficha HP (12 ppm B/N, 5 ppm color, dúplex manual, sin ADF, 3 000 páginas/mes máx.).
- Sin testimonios, sin métricas de clientes y sin fotos del local: no inventarlos.

## Product Principles

1. **El pedido llega listo, no a medias.** Un archivo que entra debe poder imprimirse sin que nadie lo vuelva a pedir.
2. **Cero fricción antes del mostrador.** Sin cuenta, sin app, sin pago: subir, ver el total, cerrar.
3. **La cotización es una promesa visible.** El número se muestra antes de enviar y se confirma al imprimir.
4. **Una sola acción por pantalla.** El cliente está de pie y con prisa.
5. **El mostrador manda.** Todo lo que la web no pueda resolver (dúplex, acabados, cobro) se resuelve en persona y se dice con claridad.

## Accessibility & Inclusion

- Uso con una mano, en móvil, con prisa: áreas de toque de 44 × 44 px como mínimo, foco visible y contraste 4.5:1 en texto normal.
- Público no técnico y con vista cansada: cuerpo de texto de 16 px o más y etiquetas explícitas, nunca solo color para indicar estado.
