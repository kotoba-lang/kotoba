# Maturity

**Level: R1 experimental (mixed — see split below)**

This repo has two halves at different real maturity levels. Do not read
"R1" as applying uniformly — the decode/checksum half is deterministic and
conformance-tested; the optical half is an untested algorithm.

## Decode/checksum core — R2-target

Implemented:
- TD1 (3×30) / TD2 (2×36) / TD3 (2×44) field-position tables (`mrz.model`).
- ICAO 9303 Part 3 §4.9 weighted 7-3-1 mod-10 checksum, pure (`mrz.checksum`).
- Full parse + per-field + composite checksum validation for all three
  formats (`mrz.core/parse-td1`, `parse-td2`, `parse-td3`, `parse`, `valid?`).
- Name-field splitting (surname/given-names, `<` handling).
- Conformance test against ICAO Doc 9303's own published TD3 worked example
  (`L898902C36UTO7408122F1204159ZE184226B<<<<<10`) — every check digit
  independently hand-verified against the algorithm before landing, not
  copied without derivation.
- Tamper-detection tests: single-character corruption in any field flips
  that field's check to invalid without affecting unrelated fields.

Not yet R2:
- TD1/TD2 conformance vectors are self-consistent round-trip tests (valid
  MRZ strings constructed with this repo's own checksum function, then
  parsed back) rather than independently-sourced ICAO test vectors — TD3 is
  the only format checked against a third-party-published vector. Sourcing
  independent TD1/TD2 vectors is a real follow-up, not done here.
- No fuzzing / property-based testing across the full MRZ alphabet.

## Optical (photo → text) — R1 experimental, no accuracy claim

Implemented:
- `mrz.ports/IZoneOcr` — a clean host-injection seam.
- `mrz.glyph` — fixed-pitch cell segmentation + cosine-similarity template
  correlation, running through kotoba-lang/num's `IBackend` (CPU by
  default, GPU-capable without code changes).
- `mrz.adapters.template-ocr` — wires the above into `IZoneOcr`.
- Algorithm correctness tests using synthetic template vectors (orthogonal
  unit vectors, near-duplicate noisy vectors) — these prove the
  segmentation/matching LOGIC is correct.
- One integration test exercising the real `kotoba-lang/num` CPU backend
  end-to-end (not a stand-in), still with synthetic (non-photographic)
  glyph data.

Not yet R1 (i.e., explicitly absent, not a rounding-down):
- **No bundled OCR-B glyph template bank.** Hand-authoring pixel data for a
  real font without an actual font-rendering pipeline in this workspace
  would produce data that looks like it works without being derived from
  the real font — the exact false-confidence failure mode this repo exists
  to avoid (see ADR-2607198200). A caller must supply real templates.
- **No document/zone detection.** Input must already be a cropped,
  perspective-corrected MRZ line image.
- **No accuracy number of any kind** (recognition rate, false-positive
  rate) against real photographed documents — none exists, and none is
  claimed. This is a tested algorithm, not a validated OCR product.
- **No adversarial/robustness testing** (glare, low light, worn ink, font
  substitution on damaged documents).

## Downstream consumers

None yet — this repo is intentionally ekyc-agnostic (does not implement
`ekyc.adapters.provider/IEkycProviderClient` itself). A composing provider
(`kotoba-lang/ekyc-native-provider`, not yet built) is the planned consumer.
