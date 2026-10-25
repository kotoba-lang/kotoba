# ADR: encrypted LM-head inference starts with exact Paillier linear algebra

Status: accepted and implemented for the linear slice

Date: 2026-08-27

## Context

Recent encrypted-LLM systems show two distinct maturity levels. EncryptedLLM
(ICML 2025) evaluates GPT-2 forward computation with GPU-accelerated CKKS, while
PUMA and BumbleBee use multi-party protocols for larger models at minutes per
token. None makes a frontier-size, interactive, fully encrypted Transformer a
small implementation task.

Kotoba separates inference orchestration (`kotoba-lang/inference`) from numerical
execution (`kotoba-lang/num`). The Paillier key/ciphertext boundary is a third
concern and is owned by `kotoba-lang/paillier`, rather than by either consumer.
We need an executable cryptographic slice that respects those boundaries and
does not label an approximation or encrypted transport as homomorphic inference.

## Decision

The first slice is the decoder's candidate LM head:

1. The client fixed-point quantizes a hidden-state vector and encrypts every
   integer under a fresh-randomized 2048-bit Paillier public key.
2. The server receives only public key material, dimensions, public range and
   scale contracts, and ciphertexts.
3. `paillier.core/encrypted-matvec` evaluates plaintext model rows and biases as
   `Enc(Wx+b)` without accepting a private key or decrypting an intermediate.
4. The server rerandomizes and returns encrypted candidate logits.
5. The client decrypts, rescales, and performs token selection locally.

The wire map is versioned as `:paillier-phe-v1`. A mandatory, data-independent
input bound lets the Paillier library calculate worst-case row bounds and reject
modular wrap.
The proof uses an independent floating-point oracle and an exact fixed-point
oracle, so quantization error and cryptographic correctness stay separate.

## Threat model and guarantees

- The honest-but-curious inference server does not learn the hidden values or
  candidate logits from request/response ciphertexts.
- The private key never crosses the client API. Model weights remain plaintext
  and private to the server.
- Dimensions, candidate token ids, scales, public magnitude bounds, timing, and
  ciphertext sizes are visible.
- Paillier is malleable and not CCA-secure. A deployment must authenticate the
  request/response envelope and must not expose a client decryption oracle.
- JVM `BigInteger` is not claimed constant-time. This slice is not a hardened
  side-channel boundary.

## Explicit non-claims

This is additive/linear partially homomorphic encryption, not FHE. It does not
evaluate encrypted attention, RMSNorm, GELU/SiLU, Softmax, KV-cache updates, or
all 42 Gemma blocks. A client-provided hidden state is the encrypted boundary;
therefore this proves an encrypted LM-head operation, not end-to-end encrypted
prompt-to-token inference.

## Verification

`kbb -M:verify-encrypted-lm-head` emits a receipt containing:

- a 2048-bit key gate;
- distinct ciphertexts for repeated encryption of the same hidden vector;
- structural absence of plaintext/private fields at server boundaries;
- exact equality with the fixed-point oracle;
- error against the independent floating-point oracle;
- selected token id and measured keygen/encrypt/server/decrypt time.

The next coherent step toward end-to-end encrypted inference is a CKKS/BFV host
backend with ciphertext-ciphertext multiplication and polynomial replacements
for the nonlinear graph, retaining this versioned boundary and proof-receipt
shape.
