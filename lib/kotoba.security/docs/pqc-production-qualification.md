# Production hybrid PQC qualification

W2 now combines the hybrid envelope policy, deployed ML-KEM provider identity,
module digest, production boundary coverage, rotation/downgrade/rollback drills,
and the shared production evidence plane.

Qualification requires X25519 plus ML-KEM-768 on the current and next production
epochs. Both envelopes must bind the qualified provider ID and executable module
digest. The provider must pass known-answer, encapsulation, decapsulation,
invalid-ciphertext, and missing-module fail-closed checks. All five declared
production boundaries and an authority-signed remote immutable evidence entry
are mandatory.

These checks do not supply an ML-KEM implementation, certify side-channel
resistance, claim FIPS validation, or prove deployment. Until a real provider
and production receipt pass the gate, G-003 remains Partial and stack profiles
remain E3.
