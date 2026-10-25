# Production software supply-chain qualification

W7 now combines a regulated release packet, two fresh hermetic builds with an
identical artifact digest, full dependency commit pins and exact fetches,
artifact/source-bound signed SBOM and provenance, isolated builder evidence,
two-party digest-bound promotion, and the production evidence plane.

The gate rejects local overrides, unpinned or non-HTTPS dependencies, artifact
or SBOM substitution, unsigned provenance, non-isolated builders, builder
self-promotion, missing release claims, and local or replayed evidence.

This verifier does not make current builds bit-for-bit reproducible and does not
turn fixture attestations into E4. W7 remains pending until a real isolated
builder, independent promoters, and remote receipt authority pass the gate.
