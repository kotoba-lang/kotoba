# Hardware and recovery production qualification

W3 and W5 now share the production evidence-plane gate. Hardware E4 requires
verified attestation, non-export, signing and KEM operations, rotation, and an
outage fail-closed drill. Recovery E4 requires encrypted immutable backups in
independent regions, a destructive digest-verified restore within RTO/RPO, and
distinct hardware-protected custodians satisfying the recovery threshold.

Both paths also require a fresh, artifact-bound, authority-signed entry in a
remote immutable hash-linked log with durable replay detection and an
independently signed head. Failure of either the domain checks or evidence-plane
checks rejects qualification.

The code and tests do not constitute operational E4 evidence. Apple Secure
Enclave remains qualified only for its scoped non-exportable signing behavior;
it does not supply general HSM KEM, cluster HA, or vendor-attestation claims.
