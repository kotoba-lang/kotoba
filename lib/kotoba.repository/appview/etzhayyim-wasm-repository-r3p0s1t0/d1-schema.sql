-- ADR-0039 Phase B+ strong-consistency side-index
--
-- Supplements the RisingWave graph (~25s checkpoint lag on cross-isolate
-- reads) with D1 (serializable, per-database consistency) for operations
-- that need CAS semantics.
--
-- Applied on the repository Worker's REPOSITORY_CAS_D1 binding
-- (database_id=76495db5-f4a0-4ccb-b3a5-3b9aa51d89e6).

-- bootstrap_first_commit: enforces "bootstrap signature only valid for the
-- very first commit authored by a given DID". PRIMARY KEY ensures atomic
-- reject on second attempt regardless of RW read visibility.
CREATE TABLE IF NOT EXISTS bootstrap_first_commit (
  author_did   TEXT PRIMARY KEY,
  commit_hash  TEXT NOT NULL,
  recorded_at  TEXT NOT NULL
);

-- ref_head: authoritative mutable ref→commit pointer for CAS on updateRef.
-- Composite PK (owner_did, ref_name). Writes happen via UPDATE ... WHERE
-- expected_current match — mismatch rejected without race.
CREATE TABLE IF NOT EXISTS ref_head (
  owner_did         TEXT NOT NULL,
  ref_name          TEXT NOT NULL,
  head_commit_hash  TEXT NOT NULL,
  kind              TEXT NOT NULL,
  updated_at        TEXT NOT NULL,
  PRIMARY KEY (owner_did, ref_name)
);

CREATE INDEX IF NOT EXISTS idx_ref_head_owner ON ref_head(owner_did);
