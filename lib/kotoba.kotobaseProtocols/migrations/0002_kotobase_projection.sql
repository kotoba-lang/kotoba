ALTER TABLE refs ADD COLUMN kotobase_graph TEXT;
ALTER TABLE refs ADD COLUMN kotobase_commit_cid TEXT;
CREATE INDEX IF NOT EXISTS idx_refs_kotobase_commit ON refs(kotobase_commit_cid);
