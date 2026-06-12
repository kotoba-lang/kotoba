-- HuggingFace dataset text for training: records with sensitivity=0 and sufficient length.
MODEL (
  name dev.mv_hf_dataset_text_for_training,
  kind FULL,
  dialect postgres,
  description 'Training-eligible HF dataset records: sensitivity_ord=0, length>=20, no signal prefix.',
  grain [vertex_id],
  tags [hf, dataset, training]
);

SELECT
  vertex_id,
  slug,
  record_id,
  split,
  lang,
  text_for_training,
  text_byte_size,
  'hf:' || slug AS label
FROM vertex_hf_dataset_record
WHERE sensitivity_ord = 0
  AND LENGTH(text_for_training) >= 20
  AND text_for_training NOT LIKE 'signal:v1:%'
