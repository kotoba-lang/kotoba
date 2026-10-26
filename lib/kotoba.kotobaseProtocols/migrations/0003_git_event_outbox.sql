CREATE TABLE IF NOT EXISTS event_outbox (
  id TEXT PRIMARY KEY,
  event_json TEXT NOT NULL,
  delivered_at TEXT,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_event_outbox_pending ON event_outbox(delivered_at, created_at);
