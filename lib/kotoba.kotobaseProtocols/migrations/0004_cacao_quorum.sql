ALTER TABLE repos ADD COLUMN min_signers INTEGER NOT NULL DEFAULT 1 CHECK (min_signers BETWEEN 1 AND 16);
CREATE TABLE IF NOT EXISTS cacao_nonces (
  issuer_did TEXT NOT NULL,
  nonce TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (issuer_did, nonce)
);
CREATE INDEX IF NOT EXISTS idx_cacao_nonces_created ON cacao_nonces(created_at);
