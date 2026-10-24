# kotoba-lang/org-ietf-opus

Zero-dep portable `.cljc` Opus (IETF RFC 6716) implementation: packet
**framing** (TOC byte parsing and frame-packing) plus a scoped, real
**CELT-mode audio decode**. Named `org-ietf-opus`, same `org-ietf-<spec>`
pattern as `org-ietf-deflate`/`org-ietf-turn`/`org-ietf-cbor`.

**New implementation, not an extraction** — `kotoba-lang/utsushi` had no
Opus support at all, not even a TODO stub (discovered while decomposing
`utsushi` into per-format-spec repos; see `com-junkawasaki/root` ADR
precedent 2607072500).

## Namespaces

| ns | role |
|---|---|
| `opus.toc` | TOC byte → config (mode/bandwidth/frame-size, RFC 6716 §3.1 Table 2), stereo flag, frame-count code |
| `opus.packet` | Frame-count-code-driven packet splitting (RFC 6716 §3.2): code 0 (1 frame), code 1 (2 equal frames), code 2 (2 explicit-length frames), code 3 (arbitrary count, CBR or VBR with padding) |
| `opus.range-decoder` | Entropy decoder shared by SILK/CELT (RFC 6716 §4.1): symbol/bit/icdf/uint/raw-bits decode, `ec-tell`/`ec-tell-frac` |
| `opus.pvq` | CELT Pyramid Vector Quantizer combinatorics (RFC §4.3.4.2): V(N,K) codebook size, index↔pulse-vector, unit-norm, spreading rotation (§4.3.4.3) |
| `opus.mdct` | CELT inverse MDCT + synthesis window + overlap-add (RFC §4.3.7) |
| `opus.celt` | CELT-mode frame decode orchestration (RFC §4.3) — see its docstring for the exact scope of this increment |

## CELT decode scope

CELT (RFC 6716 §4.3, the MDCT-based layer used for music/high-quality
audio) is a large spec. Matching this repo family's prior per-increment
scoping (`org-iso-h264`'s CABAC = "I-slice single-MB", `org-aomedia-av1`'s
intra = "DC_PRED single leaf"), this repo implements a real,
spec-faithful decode restricted to: a single isolated CELT-only frame,
mono, 20 ms/48 kHz (LM=3, 960 samples); non-transient (single long MDCT
block); post-filter off; intra-only coarse energy (no cross-frame state,
the correct real-first-frame path); coarse-only energy resolution (fine
energy not implemented); no band splitting for wide codebooks (RFC
§4.3.4.4); and the trailing per-band "skip" mechanism only partially
implemented (every band must clear its minimum-allocation threshold). See
`opus.celt`'s namespace docstring for the full, precise rationale of each
boundary. Everything actually decoded — the range coder, frame header,
Laplace-distributed coarse energy, the dynamic bit-allocation boost/trim
loop, PVQ shape decoding + spreading, denormalization, and inverse
MDCT + synthesis + de-emphasis — is real math against real, RFC-derived
tables (several cross-checked against the verified RFC 6716 Appendix A
reference implementation), not stubbed or faked.

SILK (the speech layer) and Hybrid mode remain entirely out of scope.

## Usage

```clojure
(require '[opus.toc :as toc] '[opus.packet :as pkt] '[opus.celt :as celt])

(toc/parse toc-byte)      ; => {:config :mode :bandwidth :frame-size-ms :stereo? :frame-count-code}
(pkt/frames packet-bytes) ; => {:toc {...} :frames [{:start :end} ...]}  (opaque byte ranges)

;; Given a CELT-only, mono, 20 ms/48 kHz frame's payload bytes (one entry
;; of (:frames (pkt/frames packet)), sliced out of the packet):
(celt/decode-frame celt-payload-bytes)
;; => {:pcm [...960 doubles...] :silence? bool ...decode metadata...}
```

## Test

The RFC 6716 §3.1 config table and §3.2 frame-packing rules are precisely
and unambiguously specified (fixed lookup tables / byte-level length
codings) — tests check hand-computed byte layouts against them directly,
the same validation style this repo family uses for cases where a real
encoder isn't the deciding source of truth (contrast `org-iso-h264`'s SPS
parser and `org-iso-aac`'s ADTS parser, both validated against real
`ffmpeg`-encoded fixtures where the spec has header-field freedom a real
encoder pins down).

The CELT decode tests use a mix of: exhaustive brute-force verification
(PVQ's V(N,K) and index↔vector bijection, against every enumerated
codevector for several (N,K)); an independently-transcribed second
implementation cross-check (inverse MDCT); real cross-checks against the
verified RFC 6716 Appendix A reference implementation (range coder, via
bytes produced by compiling and running the reference's actual
`ec_enc_*` functions); and full end-to-end round trips through a
companion test-only CELT encoder (`test/opus/support/`) that shares this
decoder's exact tables and bit-allocation function, so the two sides can
never disagree by construction.

```sh
kbb -M:test
```
