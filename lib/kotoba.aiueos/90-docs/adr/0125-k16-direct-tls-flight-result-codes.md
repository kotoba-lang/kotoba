# ADR-0125: Preserve the exact failing K16 TLS flight gate

## Status

Superseded by ADR-0127 (2026-08-30)

## Context

The physical GMKtec K16 loaded the exact Qwen3.8 27B artifact, executed the
frozen first-token path, and opened three fresh TLS connections to
`api.murakumo.cloud`.  Every connection received the server handshake flight,
but none sent ClientFinished or the signed result POST.  The one-shot then
returned retained qualification code 8609.

Code 8609 previously combined four independent gates: CertificateVerify,
ClientFinished construction, HTTP application-record construction, and the
final flight bound.  A retained result therefore could not identify which
local operation refused after the server handshake.

The same TLS engine accepted a live `api.murakumo.cloud` CertificateVerify
vector and three independently generated P-256 vectors in QEMU.  A host probe
also completed the Murakumo handshake and protected an 826-byte request.  Those
are useful negative bounds, but they do not replace another physical result.

## Decision

Keep code 8609 for CertificateVerify refusal and assign distinct retained
errors to the remaining local gates:

- 8612: the configured request cannot fit the static TLS flight;
- 8613: ClientFinished construction refused;
- 8614: HTTP record construction or the final combined bound refused.

The size check runs before either record writer.  Success remains code 8160
and still requires an admitted HTTP 2xx response from Murakumo.

## Evidence boundary

The physical result proves model inference reached TLS and that retry control
works.  It does not prove a POST, node registration, heartbeat, or inference
throughput until the K16 returns code 8160 and Murakumo records the signed
result.

ADR-0127 corrects an overlooked Device-P256 `+1` error-code transform: the
observed 8609 was receive-pump stage 8, not CertificateVerify stage 9.
