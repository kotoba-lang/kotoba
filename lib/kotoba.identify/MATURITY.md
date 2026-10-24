# Maturity

**Level: R2 live adapter**

Implemented:
- Identifier and candidate subject models.
- Host port for candidate resolution.
- Identifier type and value validation.
- Candidate subject and confidence-range validation.
- Confidence-descending result ordering and thresholded top-candidate selection.
- Confidence calibration by resolver source or asserter.
- Same-subject candidate merge with evidence and assertion aggregation.
- Conflict detection for closely ranked cross-subject candidates.
- Datom emitters for identifier and candidate records.
- External resolver adapter boundary.
- Production resolver routing for DID, email, wallet, and device identifiers.
- Durable EDN resolver implementation.
- Contract tests for resolver delegation, invalid candidates, threshold selection, calibration, candidate merge, conflict detection, resolver payload mapping, and durable EDN resolution.

Not yet R2:
- None.
