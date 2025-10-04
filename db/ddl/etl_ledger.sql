CREATE TABLE IF NOT EXISTS etl_ledger (
  id BIGSERIAL PRIMARY KEY,
  file_hash TEXT NOT NULL,
  raw_source TEXT NOT NULL,
  discovered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  ingested_at TIMESTAMPTZ NULL,
  status TEXT NOT NULL CHECK (status IN ('discovered','ingested','skipped','failed')),
  rows_total INT NULL,
  rows_clean INT NULL,
  rows_quarantined INT NULL,
  errors JSONB NULL,
  CONSTRAINT etl_ledger_uniq UNIQUE (file_hash)
);
CREATE INDEX IF NOT EXISTS etl_ledger_discovered_at_idx ON etl_ledger (discovered_at DESC);