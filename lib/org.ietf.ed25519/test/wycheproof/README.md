# Public Ed25519 fixtures

`ed25519_test.json` is copied byte for byte from
[C2SP/wycheproof](https://github.com/C2SP/wycheproof/blob/d17cc89fa5c8f4f4d378b5385ebf75da5d0926c9/testvectors_v1/ed25519_test.json),
commit `d17cc89fa5c8f4f4d378b5385ebf75da5d0926c9`, fetched2026-11-02.
SHA-256: `ea80ffebac085e21cb9d3e903e7fa2b448d96702da5b31f061d0b83b430b74b3`.
The upstream Apache2.0 license is preserved in `LICENSE`.

All210 cases are retained:117 valid,64 invalid,29 acceptable. The latter
include8 small-order and21 mixed-order public keys. The native OS authority
profile deliberately rejects those29 under its canonical nonidentity
prime-order key policy; they are not relabeled as universally invalid RFC
signatures. The pre-existing legacy verifier semantics are unchanged.

The native consumer/observer lives in the AIUEOS owner:
`os/aiueos/native/ed25519_region_gate.kotoba` and
`os/aiueos/scripts/ed25519-region-reference.py`. This data import does not
qualify the whole Ed25519 package, enroll an authority or restore a hosted
test/CI path. The original native static-library gate remains separate.
