-- Cola de trabajos de Print with Brilint
-- Estados: review_pending | review_held | review | reviewing | quoting |
--          measuring | quoted | held | queued | printing | done | error
CREATE TABLE IF NOT EXISTS jobs (
  folio           TEXT PRIMARY KEY,
  created_at      TEXT NOT NULL,
  status          TEXT NOT NULL DEFAULT 'queued',
  mode            TEXT NOT NULL,                     -- bw | color
  copies          INTEGER NOT NULL,
  pages           INTEGER NOT NULL,                  -- páginas por juego, según el navegador
  total           REAL NOT NULL,
  customer        TEXT NOT NULL,
  phone           TEXT NOT NULL,
  notes           TEXT NOT NULL DEFAULT '',
  files_json      TEXT NOT NULL,
  plan_json       TEXT,                              -- interpretación de la nota (reservado)
  review          INTEGER NOT NULL DEFAULT 0,        -- 1 = pasa por el mostrador antes de imprimir
  claim_code      TEXT,                              -- 4 dígitos que el cliente dicta para imprimir
  pages_verified  INTEGER,                           -- páginas reales, medidas por el agente
  quote_json      TEXT,                              -- desglose por nivel medido
  claimed_at      TEXT,                              -- el agente tomó el pedido
  attempted_at    TEXT,                              -- último envío a la impresora
  attempts        INTEGER NOT NULL DEFAULT 0,        -- veces que se mandó a la impresora
  quoted_at       TEXT,
  confirmed_at    TEXT,
  printed_at      TEXT,
  printed_by      TEXT,                              -- agente | mostrador
  error           TEXT,
  purged_at       TEXT                               -- contenido del cliente ya borrado
);

CREATE INDEX IF NOT EXISTS idx_jobs_queue ON jobs (status, created_at);
CREATE INDEX IF NOT EXISTS idx_jobs_code ON jobs (claim_code);
