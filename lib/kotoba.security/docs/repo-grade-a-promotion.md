# Repo-wide Grade A promotion gate

Individual E4 control receipts do not promote a repository. The repo-wide gate
requires every workstream declared for that repo, with fresh E4-or-higher
receipts bound to the same repo and artifact. Evidence heads must be unique so
one receipt cannot be relabeled across controls.

The candidate profile must independently satisfy model-v2 score provenance,
score 80, every critical control at least 60, L4 maturity, E4 evidence, an
allowed release gate, and Grade A semantics. Missing, stale, foreign-repo,
foreign-artifact, reused, or partially accepted receipts fail closed.

[`remaining-operational-gaps.edn`](../registers/remaining-operational-gaps.edn)
separates completed verifier code from external production operations. Until
those gaps are closed, all current repo profiles remain B/L3/E3/Partial.
