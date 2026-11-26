-- 0002 · Impresión a mano desde el mostrador
--
-- Qué resuelve: cuando la gente imprime un pedido desde la impresora (no desde
-- la app), el agente tiene que poder evitarlo o cerrarlo sin dejar el pedido en
-- error ni reimprimir hojas.
--
--   attempts     · cuántas veces se mandó a la impresora. Con attempts > 0 el
--                  servidor ya no reimprime solo un pedido atorado.
--   attempted_at · cuándo fue el último envío.
--   printed_by   · 'agente' o 'mostrador': quién sacó el trabajo.
--
-- Se aplica una sola vez por base (SQLite no tiene ADD COLUMN IF NOT EXISTS):
--   npx wrangler d1 execute brilint-print --remote --file migrations/0002_mostrador.sql

ALTER TABLE jobs ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0;
ALTER TABLE jobs ADD COLUMN attempted_at TEXT;
ALTER TABLE jobs ADD COLUMN printed_by TEXT;
