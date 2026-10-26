CREATE TABLE IF NOT EXISTS repos (
  name TEXT PRIMARY KEY,
  owner_did TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS delegates (
  repo TEXT NOT NULL,
  did TEXT NOT NULL,
  active INTEGER NOT NULL DEFAULT 1,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (repo, did)
);
CREATE TABLE IF NOT EXISTS refs (
  repo TEXT NOT NULL,
  ref TEXT NOT NULL,
  sha TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  signer_did TEXT NOT NULL,
  PRIMARY KEY (repo, ref)
);
CREATE TABLE IF NOT EXISTS heads (
  repo TEXT PRIMARY KEY,
  ref TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS objects (
  repo TEXT NOT NULL,
  sha TEXT NOT NULL,
  oid_sha256 TEXT NOT NULL,
  size INTEGER NOT NULL,
  parents_json TEXT NOT NULL DEFAULT '[]',
  signer_did TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (repo, sha)
);
CREATE TABLE IF NOT EXISTS nonces (
  did TEXT NOT NULL,
  nonce TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (did, nonce)
);
CREATE TABLE IF NOT EXISTS audit (
  id TEXT PRIMARY KEY,
  op TEXT NOT NULL,
  repo TEXT,
  subject TEXT,
  signer_did TEXT,
  evidence_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_refs_repo ON refs(repo);
CREATE INDEX IF NOT EXISTS idx_audit_repo ON audit(repo, created_at);
