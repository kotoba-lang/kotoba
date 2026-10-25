# kotoba-lang/codec-primitives

Zero-dep(ish) portable `.cljc` primitives shared across pixel-level video/audio
codec implementations in the `kotoba-lang` org (H.264, AV1, and future
codecs).

## Scope

**This is not a shared implementation of H.264/AV1.** The two codecs' actual
transforms (H.264's integer 4x4/8x8 approximate DCT vs. AV1's DCT/ADST
hybrid), quantization tables, entropy coding, and in-loop filters are
different enough that folding them into one library would just hide codec
identity behind a leaky abstraction. What this repo provides instead is the
narrow slice that really is math-shared skeleton across both:

- `codec-primitives.transform` — a `BlockTransform` protocol (`forward`/
  `inverse`) that defines *how* a codec-specific transform is called, without
  specifying *what* the transform does. Coefficient tables live in codec repos
  (e.g. `h264.transform`, `av1.transform`), not here.
- `codec-primitives.quant` — a `QuantScale` protocol (`qp->scale`) for the
  general shape of "QP in, scale out." The actual QP→scale tables are codec
  specific and stay in codec repos.
- `codec-primitives.scan` — a generic `scan`/`unscan` permutation-vector
  reorder, plus one concrete, verified example: `zigzag-4x4`, the standard
  4x4 zig-zag scan order used by H.264 (and structurally similar to
  classic JPEG zigzag patterns). Other codec-specific scan orders (e.g. AV1's
  various scan tables) do not belong here.
- `codec-primitives.motion` — a codec-agnostic `MotionVector` shape
  (`kotoba-lang/spec` data, malli until 2026-09-10)
  (POC, ref index, `[dx dy]` quarter-pel motion vector, ref-frame key) for
  representing motion vectors and reference-frame pointers as data, without
  committing to how any particular codec resolves `:ref-frame` into pixels.

**Explicitly out of scope** (left to codec-specific repos): entropy coding
(CABAC/CAVLC/range coding), in-loop / deblocking / restoration filters,
concrete transform coefficient tables, and film grain synthesis.

Consumers: `kotoba-lang/org-iso-h264` (H.264) depends on this repo;
`kotoba-lang/org-aomedia-av1` (AV1) does as well.

## Related ADR

See `com-junkawasaki/root` ADR-2607122000
(`90-docs/adr/2607122000-utsushi-pixel-codec-r05-cljc-datomic.md`) for the
design rationale behind splitting out this shared skeleton.

## Test

```sh
kbb -M:test
```

## Lint

```sh
kbb -M:lint
```
