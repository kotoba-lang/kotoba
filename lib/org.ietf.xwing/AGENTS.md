# AGENTS.md — org.ietf.xwing

X-Wing (draft-connolly-cfrg-xwing-kem) in native `.kotoba`, for AWAI-102 and JUN-352.

- Hashing, ML-KEM and X25519 come only from this repository's native libraries; no host
  crypto.
- `kotoba/xwing/native_gate.kotoba` is generated: re-run `tools/gen_gate.py`. The vectors
  in `test/` are the draft's, unchanged; a new draft revision means a new pinned file
  and a README update, never an edited vector.
- Follow the draft exactly. Do not add refusals it does not specify (such as a low-order
  X25519 check): they would break interoperability.
