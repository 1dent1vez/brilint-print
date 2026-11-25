-- Cola de trabajos de Print with Brilint
CREATE TABLE IF NOT EXISTS jobs (
  folio          TEXT PRIMARY KEY,
  created_at     TEXT NOT NULL,
  status         TEXT NOT NULL DEFAULT 'queued',   -- queued | printing | done | error
  mode           TEXT NOT NULL,                     -- bw | color
  copies         INTEGER NOT NULL,
  pages          INTEGER NOT NULL,                  -- páginas por juego, según el navegador
  total          REAL NOT NULL,
  customer       TEXT NOT NULL,
  phone          TEXT NOT NULL,
  notes          TEXT NOT NULL DEFAULT '',
  files_json     TEXT NOT NULL,
  pages_verified INTEGER,                           -- páginas reales, medidas por el agente
  quote_json     TEXT,                              -- desglose por nivel medido
  claimed_at     TEXT,
  quoted_at      TEXT,
  confirmed_at   TEXT,
  printed_at     TEXT,
  error          TEXT
);

CREATE INDEX IF NOT EXISTS idx_jobs_queue ON jobs (status, created_at);
