# ADR-0116: K16 Qwen3.8 uses an exact-artifact benchmark and a native status screen

Date: 2026-08-29
Status: accepted; display implemented, physical Qwen generation still red

## Context

The physical K16 has completed a native character-bigram job and returned its
result through the Murakumo queue.  That establishes a real execution and
result path, but it is not a GGUF or production-LLM runtime.  The current
kernel also maps only its first GiB, records at most 256 allocated pages, and
has no native NVMe reader, GGUF parser, Qwen3.5 operator runtime, tokenizer,
threaded SIMD backend, or calibrated wall clock.  Reporting a Qwen speed from
the micro model, or converting its TSC delta with a nominal clock, would be a
category error.

The requested target is the official `Qwen/Qwen3.8-27B` checkpoint at revision
`1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0`, using the text-only
`Qwen3.8-27B-UD-IQ3_XXS.gguf` artifact from Unsloth revision
`4ca720788d1e01f1bff70c033e0d0028fd02e502`.  The exact file is
10,934,860,704 bytes with SHA-256
`c0b7c3038681ed2e3040456c1dd45f9858b6c2290bed172c70388a94874f3eee`.
The vision projection is outside the first cell.

## Decision

1. The benchmark identity and gates live in
   `contracts/qwen38-27b-k16-benchmark-v1.edn`.  The record separates cold
   load, prefill, decode, first-token time and peak resident bytes.  Device
   compute and network round-trip are separate measurements.
2. Missing timing is `N/A`, never zero.  Raw TSC cycles remain raw until a
   calibrated monotonic frequency exists.
3. The native GOP surface exposes `aiueos-inference-status/v1`.  It renders
   model, quant, phase, detail, load, prefill, decode, tokens, resident memory,
   first-token time and compute cycles, and updates the desktop generation,
   hash and damage envelope after each frame.
4. The already-working physical micro job drives the same status ABI.  Its
   real cycle delta remains visible during Murakumo liveness and reconnects,
   while its prefill/decode rates remain `N/A` because wall time is not yet
   qualified.
5. The pinned downloader requires the artifact plus 2 GiB headroom, resumes a
   `.partial` file, refuses an existing mismatch, and promotes only after byte
   count and SHA-256 validation.

## Evidence and boundary

`smoke-inference-status.sh` compiles the freestanding renderer with a modeled
GOP aperture, validates blocked and complete transitions, checks the exact
rate arithmetic, and emits a photographed-frame substitute labelled
`QEMU UI TEST`.  The persistent/job QEMU gates also link and boot the new
object.  The larger hash-admitted kernel moved the TCG persistent gate beyond
its old 18-second envelope; its timeout is 35 seconds while the same required
native completion marker remains unchanged.  None of this is physical K16
Qwen generation.

The Qwen cell stays red until the exact artifact is present on the K16, the
native runtime produces a non-empty token sequence, every required timing is
present, and the saved record equals the screen values.  Source, QEMU, an
artifact filename, a `server is listening` line, and the existing micro model
are not substitutes.
