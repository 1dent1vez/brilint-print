-- 0003 · Código del cliente (estilo app de reparto)
--
-- Cada pedido nace con 4 dígitos que solo ve el cliente. El pedido se cotiza
-- normal, pero al confirmar queda en 'held' (esperando mostrador): nada se
-- imprime hasta que alguien teclea ese código en la caja.
--
--   npx wrangler d1 execute brilint-print --remote --file migrations/0003_codigo_cliente.sql

ALTER TABLE jobs ADD COLUMN claim_code TEXT;
CREATE INDEX IF NOT EXISTS idx_jobs_code ON jobs (claim_code);
