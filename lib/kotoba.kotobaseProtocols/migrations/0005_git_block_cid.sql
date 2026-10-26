ALTER TABLE objects ADD COLUMN block_cid TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS idx_objects_block_cid ON objects(repo, block_cid);
