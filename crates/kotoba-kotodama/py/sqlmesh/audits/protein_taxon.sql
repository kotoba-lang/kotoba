-- SQLMesh audit: mv_protein_taxon_coverage invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_protein_taxon_linked_le_total,
  model dev.mv_protein_taxon_coverage,
  dialect postgres,
  description 'linked_count (sum of kg_linked) must not exceed protein_count.'
);
SELECT *
FROM dev.mv_protein_taxon_coverage
WHERE linked_count > protein_count;

---

AUDIT (
  name assert_protein_taxon_count_positive,
  model dev.mv_protein_taxon_coverage,
  dialect postgres,
  description 'protein_count must be > 0 (group rows imply at least one protein per taxon).'
);
SELECT *
FROM dev.mv_protein_taxon_coverage
WHERE protein_count <= 0;
