# kotoba-lang/org-iso-h264

The bounded Kotoba SPS path now accepts canonical H.264 EBSP NAL units as
well as already-unescaped RBSP. `src/h264/rbsp.kotoba` validates every byte,
limits a NAL to 128 bytes, removes only valid `00 00 03 {00..03}` emulation
prevention sequences, and rejects trailing, unnecessary, or missing
prevention bytes. `parse-ebsp-baseline` then delegates to the existing nominal
Baseline SPS parser without weakening its profile/POC/dimension checks.

Zero-dep portable `.cljc` H.264 (ITU-T H.264 / ISO/IEC 14496-10 AVC)
bitstream **framing** — Annex B NAL unit splitting/writing, NAL header
parsing, and SPS/PPS (Sequence/Picture Parameter Set) decode **and
encode**. Named
`org-iso-h264` (ISO/IEC numbering, consistent with `org-iso-aac`/
`org-iso-isobmff`/`org-iso-jpeg`/`org-iso-pdf`/`org-iso-opentype` in the
same batch — H.264 is jointly published by ITU-T and ISO/IEC, see
`org-iso-jpeg`'s README for the same joint-body naming rationale).

**New implementation, not an extraction** — `kotoba-lang/utsushi`'s
`utsushi.bitstream/split-annexb` was an unimplemented `(throw (ex-info
"TODO..."))` stub (discovered while decomposing `utsushi` into
per-format-spec repos; see `com-junkawasaki/root` ADR precedent
2607072500). This repo originally filled that gap only for framing/
metadata (NAL splitting, SPS/PPS), matching the "entropy-coded pixels stay
opaque" design boundary `kasane`/`utsushi` establish for JPEG/AVIF/etc
(ADR-2606272200 §3) — actual pixel decode was explicitly out of scope.

**That framing-only boundary has since been amended for a narrow "R0.5"
pixel-decode scope** (ADR-2607122000, `com-junkawasaki/root`): this repo
now also implements a real, non-realtime, CAVLC + intra-only H.264
baseline pixel decoder (`h264.decode` et al., see "Pixel decode" below),
chroma (4:2:0) decode, the encode-side counterpart (`h264.encode`, Migration
step 8, initially luma-only), real chroma (Cb/Cr) encode (see "Pixel
encode" below), **P-slice inter prediction decode** (`decode-gop`,
Migration step 7: P_Skip + P_L0_16x16, single reference frame — see "Pixel
decode: P-slice (inter)" below), **real sub-pel/non-zero motion
compensation** for that same P_Skip/P_L0_16x16 path (luma quarter-sample +
chroma eighth-sample interpolation, `h264.interp` — see "Sub-pel motion
compensation" below), and — most recently — the **P-slice inter ENCODE
counterpart** (`h264.encode/encode-gop`, Migration step 7's encode
increment: integer-pel full-search + quarter-pel local-refinement motion
estimation, P_Skip mode decision, P_L0_16x16 CAVLC-coded residual — see
"Pixel encode: P-slice (inter)" below), and — most recently — a first
**CABAC (main/high-profile entropy coding) decode** increment
(`h264.cabac`, I-slice/Intra_16x16 scope initially, validated bit-exact
including multi-macroblock/multi-coefficient content — see "Pixel decode:
CABAC" below for exactly what's validated), and — most recently —
**CABAC + P-slice/inter prediction** (`P_Skip` + `P_L0_16x16`, the CABAC
counterpart of the CAVLC-only P-slice increment above — see "Pixel
decode: CABAC + P-slice (inter)" below), and — most recently — **CAVLC
P-slice sub-partitioned inter prediction** (`P_L0_L0_16x8`/`P_L0_L0_8x16`/
`P_8x8` decode — see "Pixel decode: P-slice sub-partitioned inter" below
for exactly what's covered). The original framing-only boundary still
holds for multi-reference/B-slice inter prediction, `P_8x8ref0` and
finer-than-8x8 sub_mb_type splits (`P_L0_8x4`/`P_L0_4x8`/`P_L0_4x4`),
sub-partitioned motion ENCODE, intra-coded macroblocks within a CABAC
P-slice (CAVLC P-slices DO decode these, CABAC P-slices don't yet), CABAC
sub-partitioned inter, and CABAC encode — those remain out of scope (see
below for exactly what is/isn't covered).

## Namespaces

| ns | role |
|---|---|
| `h264.bitstream` | decode: Annex B start-code scan → NAL unit `[start,end)` ranges + 1-byte NAL header (`nal_ref_idc`/`nal_unit_type`). encode: `write-nal-unit` (escape + start code) / `write-annexb-stream` (concatenate) |
| `h264.rbsp` | decode: emulation-prevention byte (`0x000003`→`0x0000`) removal (`unescape`), required before any bit-level SPS/PPS parsing. encode: `escape`, the exact inverse |
| `h264.expgolomb` | decode: MSB-first bit reader + Exp-Golomb `ue(v)`/`se(v)` decode (H.264 §9.1). encode: matching bit `writer` + `write-ue!`/`write-se!`/`write-bits!`/`write-flag!`/`rbsp-trailing-bits!`/`bytes!` |
| `h264.sps` | decode: SPS (NAL type 7) parse: profile/level + picture width/height (handles high-profile chroma/scaling-list fields correctly so the bit position stays aligned, though scaling-list *values* aren't surfaced). encode: `encode`, non-high-profile only, no frame-cropping (width/height must be multiples of 16) — see Encoding below |
| `h264.pps` | decode: PPS (NAL type 8) parse: entropy coding mode (CAVLC/CABAC), reference index defaults, QP/deblocking/intra-pred flags. Covers the common case (`num_slice_groups_minus1 == 0` — FMO is essentially absent from real-world encoders); throws rather than silently mis-parsing if FMO is present. High-Profile-only trailing fields (`transform_8x8_mode_flag` etc., gated by `more_rbsp_data()`) aren't parsed — this reader doesn't track exact bit position precisely enough to detect that condition. encode: `encode`, covers the same field set as `parse` |
| `h264.slice` | decode: slice header parse (`first_mb_in_slice`/`slice_type`/`pic_parameter_set_id`/`frame_num`/`idr_pic_id`/POC (type 0 or 2 only)/IDR dec_ref_pic_marking flags/`slice_qp_delta`/deblocking-control fields, read-and-discarded). `parse-header!` advances the SAME reader `h264.decode` continues using for macroblock data (unlike `sps`/`pps`'s private-reader `parse`). ALSO: P-slice fields (`num_ref_idx_active_override_flag`/`num_ref_idx_l0_active_minus1` — must resolve to exactly 1 active reference — `ref_pic_list_modification_flag_l0`/weighted-prediction/non-IDR `dec_ref_pic_marking` — all throw if set to anything beyond this repo's single-reference-frame, no-reordering, no-weighting scope), see "Pixel decode: P-slice (inter)" below. encode: `encode-header!` (I-slice) AND `encode-p-header!` (P-slice, new — see "Pixel encode: P-slice (inter)" below) |
| `h264.syntax` | **not a parser — a reader for parsers.** Generic interpreter for ISO/IEC 14496-10 §7.3-style *syntax tables* expressed as EDN data: rows of `[:u n name]` / `[:ue name]` / `[:se name]` / `[:f n name]` plus `[:when cond rows]` / `[:for count rows]` / `[:infer name v]` / `[:escape key & args]`, over a closed expression grammar (`[:var k]`, `[:at k i]`, `[:idx]`, comparisons, arithmetic). Reads §7.3 only; §7.4 semantics stay code, exactly as the standard splits them. `ae(v)` is refused, not faked — see "Table-driven syntax" below |
| `h264.sps-table` | the table-driven counterpart of `h264.sps/parse`, built to be COMPARED with it rather than to replace it: `resources/h264/syntax/sps.edn` (§7.3.2.1.1 as data) + `h264.syntax` + a 12-line §7.4.2.1.1 `semantics` fn + an 8-line `scaling-list-escape`. `h264.sps` remains the shipping parser |
| `h264.quant` | dequantization: the `normAdjust4x4` V-table (§8.5.9) + per-position `ac-qmul`/single-scalar `dc-qmul`. Implements `codec-primitives.quant/QuantScale`. Baseline scope only — no custom scaling lists (flat weight 16 everywhere) |
| `h264.transform` | decode: the integer 4x4 inverse transform (`inverse-4x4`, §8.5.10) + the Intra16x16 luma DC Hadamard transform (`luma-dc-hadamard`) + the chroma-DC 2x2 Hadamard transform (`chroma-dc-hadamard`). Arithmetic ported 1:1 from FFmpeg's reference decoder for bit-exactness, including an internal coefficient-array transpose whose necessity was discovered empirically (see "Pixel decode" below). encode: `forward-4x4` (textbook forward transform, API symmetry/DC-extraction only) + `forward-luma-dc-hadamard` (exact derived inverse of `luma-dc-hadamard`) + `forward-chroma-dc-hadamard` (exact derived inverse of `chroma-dc-hadamard`, same probe-and-invert methodology) — see "Pixel encode" below |
| `h264.transform` (`.kotoba`) | the same 8.5.12 inverse transform as a JVM-free guest kernel: the 1-D butterfly `idct4-1d` plus `idct4-1d-dc` (+32 DC bias folded in), `idct4-1d-scaled` (final `>>6` folded in) and `dc-only-sample`. Compiles to wasm32 with ZERO host imports and to aarch64/x86_64 machine code. The `.cljc` above stays authoritative; see "A residual kernel that runs with no JVM under it" below |
| `h264.quant` (`.kotoba`) | the 8.5.9 dequant chain and 8.5.8 `chroma-qp` as a JVM-free guest kernel: `group-idx`, `level-scale`, `ac-qmul`, `dc-qmul`, `dequant-ac`, `chroma-qp`. Same shape and same rules as the transform kernel |
| `h264.cavlc` | decode: CAVLC residual entropy decode (§9.2): `coeff_token`/`total_zeros`/`run_before` VLC tables (luma AND the ChromaArrayType 1 chroma-DC `nC==-1` special case) + `residual-block!` (coeff_token → trailing-ones signs → level_prefix/suffix → total_zeros → run_before → position reconstruction). encode: `encode-residual-block!`, reusing the same tables as reverse lookups (already generic over `:chroma-dc` — no chroma-specific CAVLC encode code was needed; also reused UNCHANGED for P_L0_16x16's full 16-coefficient regular luma blocks, see "Pixel encode: P-slice (inter)") |
| `h264.encode` | encode-side orchestration: quantization (exact least-squares solve, NOT a memorized MF table, reused unchanged for chroma via QPc) → CAVLC → simplified SAD-based mode decision (luma Intra_16x16 AND chroma Intra_Chroma, jointly for Cb+Cr) → macroblock loop → NAL assembly. LUMA AND CHROMA (Cb/Cr, 4:2:0). See "Pixel encode" below. ALSO: `encode-gop` — P-slice (P_Skip/P_L0_16x16) inter encode: integer-pel full-search + quarter-pel local-refinement motion estimation (`h264.interp`-scored), P_Skip mode decision, full-16-coefficient-regular-block luma residual quantization, chroma residual UNCHANGED from the intra path — see "Pixel encode: P-slice (inter)" below |
| `h264.intra-pred` | Intra_16x16 luma prediction (§8.3.3): DC/Vertical/Horizontal (modes 0/1/2) only — Plane (mode 3) throws. **Intra_4x4 luma prediction (§8.3.1.2, `predict-4x4`): ALL NINE modes** (Vertical/Horizontal/DC/Diagonal_Down_Left/Diagonal_Down_Right/Vertical_Right/Horizontal_Down/Vertical_Left/Horizontal_Up), including §8.3.1.2's `p[4..7,-1]` substitution — see "Pixel decode: Intra_4x4" below; Intra_8x8 (§8.3.2) is refused, not approximated. Note Table 8-2's Intra_4x4 numbering is a THIRD numbering, distinct from both Intra_16x16's and Table 8-5's chroma one. Intra_Chroma prediction (§8.3.4, 4:2:0 8x8 blocks, `predict-chroma-8x8`): ALL FOUR modes (DC/Horizontal/Vertical/Plane) on decode — see "Chroma decode" below for why Plane is implemented here but not for luma; encode's mode decision only ever selects DC/Horizontal/Vertical (see "Pixel encode") |
| `h264.quant` | (also) `chroma-qp`: QPc derivation from QPy + PPS `chroma_qp_index_offset` (§8.5.8 Table 8-15) — reused unchanged by `h264.encode`'s chroma path (intra AND inter) |
| `h264.decode` | orchestration: NAL → SPS/PPS/slice header → macroblock loop → (Intra_16x16/**Intra_4x4**/Intra_Chroma prediction + CAVLC residual + dequant + inverse transform) → reconstructed luma AND chroma (Cb/Cr) planes. Intra_4x4 (`mb_type` 0 / `I_NxN`, CAVLC I-slices) covers the §8.3.1.1 neighbour-derived `predIntra4x4PredMode`, §7.3.5.1's per-block pred-mode syntax, Table 9-4's INTRA `coded_block_pattern` column and the above-right neighbour macroblock — see "Pixel decode: Intra_4x4" below. `decode-idr-frame` (single IDR picture, unchanged public API) AND `decode-gop` (a whole IDR+P sequence, new). Also: `P_16x8`/`P_8x16`/`P_8x8` sub-partitioned P-slice inter decode (`mv-predict-partition`/`neighbor-abc`/`mb-quadrant-mv`, a general per-8x8-quadrant §8.4.1.3 motion-vector predictor cross-checked against FFmpeg's `pred_motion`/`pred_16x8_motion`/`pred_8x16_motion`, and `mc-predict-quadrants`, per-quadrant motion compensation). See "Pixel decode", "Pixel decode: P-slice (inter)", and "Pixel decode: P-slice sub-partitioned inter" below for exact scope |
| `h264.interp` | decode: luma quarter-sample (§8.4.2.2.1, 6-tap FIR + averaging) and chroma eighth-sample (§8.4.2.2.2, bilinear) sub-pel motion-compensated interpolation over a picture-boundary-extended plane. Pure functions, no bitstream dependency. `h264.decode/mc-predict` is the decode-side caller; `h264.encode/mc-predict` (a small deliberate duplication, same convention as that namespace's `neighbor-nc`) calls the SAME `h264.interp` functions on the encode side, both for motion-compensated prediction AND to SCORE candidate motion vectors during motion estimation. See "Sub-pel motion compensation" below |
| `h264.cabac` | decode: CABAC (Context-Adaptive Binary Arithmetic Coding, §9.3) entropy decode for main/high-profile streams — the literal per-bit arithmetic decoding engine (§9.3.3.2: `decode-decision!`/`decode-bypass!`/`decode-terminate!`, `range-tab-lps`/`trans-idx-lps`/`trans-idx-mps` per Tables 9-44/9-45), context-model initialization from SliceQPY (§9.3.1.1.1, `init-contexts` — I-slice's single `context-init-i` column OR, new, one of 3 `cabac_init_idc`-selected P-slice columns `context-init-p0/p1/p2`, Tables 9-12..9-24 all 4 columns), `mb_type` binarization for BOTH I-slice (`read-mb-type-i!`) AND P-slice (`read-mb-type-p!`, new — a DIFFERENT binarization tree), `mb_skip_flag` (`read-mb-skip-flag!`, new, P-slice only), `mvd_l0` (`read-mvd!`, new, UEG3 binarization), `coded_block_pattern` for INTER macroblocks (`read-coded-block-pattern-inter-cabac!`, new — a COMPLETELY DIFFERENT binarization from CAVLC's me(v) table lookup), `intra_chroma_pred_mode`/`mb_qp_delta` binarization (shared, slice-type-independent), and `residual-block!` (`coded_block_flag`/`significant_coeff_flag`/`last_significant_coeff_flag`/`coeff_abs_level_minus1` combined, now also covering a `:luma-regular` block category — the full 16-coefficient inter residual block — alongside the pre-existing `:luma-dc`/`:luma-ac`/`:chroma-dc`/`:chroma-ac`, returning the SAME scan-order `{:coeffs :total-coeff}` shape `h264.cavlc/residual-block!` does so `h264.decode` shares its dequant/transform pipeline unchanged regardless of entropy method). **I-slice/Intra_16x16 AND P-slice `P_Skip`/`P_L0_16x16`** — see "Pixel decode: CABAC" and "Pixel decode: CABAC + P-slice (inter)" below for exact scope (sub-partitioned inter, intra-in-P-slice, and B-slices remain out of scope) |

## Validation

`h264.sps-test`/`h264.pps-test` validate against a **real libx264-encoded
baseline-profile Annex B stream** (generated via `ffmpeg -f lavfi -i
testsrc=size=64x48 ... -profile:v baseline -bsf:v h264_mp4toannexb`) — the
SPS-derived width/height match the real 64×48 encode source exactly, and
the PPS's `entropy-coding-mode` decodes to `:cavlc`, cross-checking the
SPS's own `profile-idc=66` (baseline) finding — baseline profile forbids
CABAC by spec, so a wrong PPS parse would very likely produce `:cabac`
instead (an independent correctness signal beyond "the parser didn't
throw").

### Kotoba safety profile

`src/h264/expgolomb.kotoba` is the canonical bounded, immutable bit-reader
profile for new Kotoba consumers. It accepts at most 128 signed-i64 byte
values, validates bytes at the SPS boundary, carries the bit index explicitly,
and returns typed `:result` errors for EOF, invalid widths, and oversized
codes. It uses no ambient capability or mutable host state.

`src/h264/sps.kotoba` is the first real consumer. Its admitted profile is an
unescaped SPS RBSP with the NAL header included, Baseline profile 66, picture
order count type 0 or 2, progressive or interlaced dimensions, and optional
4:2:0 cropping. Invalid headers, reserved bits, malformed dimensions, EOF,
POC type 1, and non-Baseline profiles fail closed. The existing `.cljc`
implementation remains the wider semantic oracle; unsupported high-profile
and scaling-list syntax has not been silently claimed by the Kotoba profile.

`src/h264/transform.kotoba` and `src/h264/quant.kotoba` are a different kind
of consumer: not a bounded reader over a bitstream, but the decode
*arithmetic* — the §8.5.12 inverse transform and the §8.5.9 dequant chain.
They are the two that actually reach a backend and get executed today, and the
only ones with no `:require` and no typed value anywhere, which is why. See "A
residual kernel that runs with no JVM under it" below.

The conformance roots are `test/h264/expgolomb_conformance.kotoba` and
`test/h264/sps_conformance.kotoba`. Both must return `42` on the restricted Web
backend and the typed Wasm browser host with an empty capability set. The SPS
vector is the repository's real libx264 64×48 fixture after Annex B extraction
and emulation-prevention removal.

## Usage

```clojure
(require '[h264.bitstream :as bs] '[h264.rbsp :as rbsp]
         '[h264.sps :as sps] '[h264.pps :as pps])

(def units (bs/nal-units annexb-bytes))   ; => [{:start :end :bytes :nal-unit-type :kind ...} ...]
(def sps-u (first (filter #(= :sps (:kind %)) units)))
(def pps-u (first (filter #(= :pps (:kind %)) units)))
(sps/parse (rbsp/unescape (:bytes sps-u)))
;; => {:profile-idc :level-idc :chroma-format-idc :frame-mbs-only? :width :height}
(pps/parse (rbsp/unescape (:bytes pps-u)))
;; => {:pic-parameter-set-id :seq-parameter-set-id :entropy-coding-mode
;;     :num-ref-idx-l0-default-active :num-ref-idx-l1-default-active
;;     :weighted-pred? :weighted-bipred-idc :pic-init-qp :pic-init-qs
;;     :chroma-qp-index-offset :deblocking-filter-control-present?
;;     :constrained-intra-pred? :redundant-pic-cnt-present?}
```

## Encoding (Wave 2, kotoba-lang/root ADR-2607121400)

Adds the encode-side counterpart of the framing/SPS/PPS decode above —
`utsushi.codec`'s decode path already delegates real SPS parsing here
(ADR-2606272200 §H.264 wiring); this is the matching encode capability for
that same delegation boundary, not a change to `utsushi` itself.

**What's implemented and tested:**
- Exp-Golomb `ue(v)`/`se(v)` bit writer, RBSP trailing-bits padding
- Emulation-prevention byte insertion (`h264.rbsp/escape`)
- SPS encode: baseline/extended/main-profile-shaped (non-high-profile),
  progressive-only (`frame_mbs_only_flag=1`), no frame-cropping (width and
  height must both be multiples of 16 — real 1080p needs padding to 1088
  the same way real encoders do; cropping to exactly 1080 isn't
  implemented)
- PPS encode: full field set `parse` reads (CAVLC/CABAC entropy mode
  selectable, though only CAVLC is spec-legal for baseline profile — that
  constraint lives in the *SPS* profile-idc, not enforced by
  `pps/encode` itself)
- NAL unit wrapping (`bitstream/write-nal-unit`/`write-annexb-stream`):
  start code + escaping, round-trips through `nal-units`/`split-annexb`

**What's explicitly NOT implemented** (be aware before assuming this
produces a decodable video frame):
- **Slice header and macroblock/pixel data are not implemented at all** —
  no CAVLC/CABAC entropy coding, no DCT/quantization, no intra/inter
  prediction. This repo (both decode and encode) stops at the
  container/parameter-set framing layer by design (see the "framing only"
  scope note above) — actual pixel encoding is a capability-gated native
  concern, same as decode.
- High-profile SPS encode (chroma_format_idc signaling, scaling lists) —
  `sps/encode` throws if given a high-profile `profile-idc`.
- Frame cropping on encode (arbitrary width/height) — only MB-aligned
  (multiple-of-16) dimensions.

All encode-side correctness claims are backed by round-trip tests against
this repo's own `parse` functions (`sps_test.clj`/`pps_test.clj`/
`bitstream_test.clj`/`expgolomb_test.clj`/`rbsp_test.clj`) — there is no
independent reference decoder (e.g. ffprobe) cross-check for the encode
path the way `sps-from-real-encoder` has for decode, since the output
here is a synthetic parameter-set NAL, not a decodable frame.

## Pixel decode (Wave 3, ADR-2607122000 Phase 1 / "R0.5")

`h264.decode/decode-idr-frame` decodes a real H.264 Annex B elementary
stream to a raw luma pixel plane — the first time this ecosystem can
actually reconstruct pixels from a real encoder's output rather than only
parse framing/metadata. This is explicitly a **non-realtime, correctness-
first reference decoder** (the "R0.5" tier of ADR-2607122000 — it is a
golden model for a future capability-gated *native* realtime decoder
(R1), not a claim that pure cljc decodes video at framerate).

**What's implemented:**
- Baseline profile, CAVLC (no CABAC)
- A single IDR I-slice covering the whole picture (no multi-slice, no
  multiple pictures/GOP, no P/B slices, no reference-picture buffering)
- `mb_type` **Intra_16x16 (1..24) AND `I_NxN`/Intra_4x4 (0)** — Intra_4x4 is
  new, see "Pixel decode: Intra_4x4 (I_NxN)" below for its own scope
  section. **Intra_8x8** — the other thing `mb_type` 0 can mean, told apart
  by `transform_size_8x8_flag` — and `I_PCM` (`mb_type` 25) still throw a
  clear error rather than being silently mis-decoded
- Both `CodedBlockPatternLuma` values I16x16 macroblocks can have: 0 (DC-
  only, no AC residual) and 15 (full AC residual for all four luma 8x8
  groups) — both real CAVLC paths are exercised
- Intra_16x16 luma prediction modes 0 (Vertical), 1 (Horizontal), 2 (DC) —
  mode 3 (Plane) throws
- Multi-macroblock pictures, with real cross-macroblock CAVLC neighbor
  (`nC`) derivation and cross-macroblock Vertical/Horizontal prediction
  using actual reconstructed neighbor pixels (the code path is generic,
  not hardcoded to one macroblock) — see the multi-macroblock golden
  vector below for the extent this is actually validated
- **Chroma (Cb/Cr), ChromaArrayType 1 (4:2:0) only** (Wave 4 addition,
  chroma-decode follow-up to Phase 1): chroma DC (the `nC==-1` special
  CAVLC table + 2x2 Hadamard transform) and chroma AC (regular
  neighbor-derived 4x4 blocks, reusing the luma AC CAVLC/dequant/IDCT
  path with QPc — `h264.quant/chroma-qp` — instead of QPy), for both
  `CodedBlockPatternChroma` values that carry residual (1 = DC only, 2 =
  DC+AC) as well as 0 (prediction only, no residual). All FOUR
  Intra_Chroma prediction modes (DC/Horizontal/Vertical/Plane) are
  implemented — unlike luma, where Plane is out of scope, chroma Plane
  IS implemented because a real x264 encoder was observed selecting it
  even for near-flat chroma content whenever both neighbors are
  available (an RD tie-break, not a genuine gradient) — leaving it
  unimplemented would make chroma decode fail on ordinary real streams,
  not just contrived ones. `decode-idr-frame` returns `:cb`/`:cr` planes
  (each `(width/2)*(height/2)`, flat row-major) alongside `:luma`. Any
  `chroma_format_idc` other than 1 throws.

**What's explicitly NOT implemented** (out of scope, not silently wrong):
P/B slices and all inter prediction/motion compensation, multiple
reference frames, ChromaArrayType 0/2/3 (monochrome/4:2:2/4:4:4), the
deblocking loop filter, **Intra_8x8** (§8.3.2 — needs the 8x8 integer
transform and the §8.3.2.2 reference-sample low-pass filter; deliberately
not half-implemented, see below) and `I_PCM` macroblock types, Plane *luma*
intra prediction (Plane *chroma* IS implemented, see above), frame
cropping (picture width/height must be exact multiples of 16), and
multi-picture streams (only the first IDR slice is decoded). CABAC
(main/high-profile entropy coding) was originally out of scope here too —
**this is no longer entirely true as of the CABAC increment below**, which
adds real (if currently narrower-than-CAVLC) CABAC decode support; see
"Pixel decode: CABAC" for exactly what's covered.

**Golden-vector validation is real but narrow — read this before trusting
a number beyond it.** `test/h264/decode_test.cljk` validates against real
`ffmpeg 8.1.1`/`x264 core 165` — encoded Annex B streams, compared
bit-exact (no tolerance) against the SAME file decoded by a real `ffmpeg`
(not the pre-encode source image, since lossy encoding changes pixel
values) — **luma AND chroma (Cb/Cr) both**, for every fixture below:

1. **`flat16-dc-only.h264`** — a single flat 16x16 macroblock,
   `CodedBlockPatternLuma=0`, DC prediction mode. Exercises: SPS/PPS/
   slice-header parsing, `mb_type`→Intra_16x16 mapping, the luma DC
   Hadamard transform + dequant, DC prediction with unavailable
   neighbors (defaults to 128 per spec). Chroma here is DC-only
   (`CodedBlockPatternChroma` 0 or 1) — no chroma AC.
2. **`gradient16-ac.h264`** — a single 16x16 macroblock with a real
   horizontal luma gradient, forced (`x264 --partitions none`) to
   Intra_16x16 at a QP where `CodedBlockPatternLuma=15`. Exercises: real
   CAVLC `coeff_token`/level/`total_zeros`/`run_before` decode with
   nonzero coefficients, within-macroblock CAVLC neighbor (`nC`)
   derivation across the 16 luma 4x4 sub-blocks, per-position AC
   dequantization, and the full 4x4 inverse transform combined with the
   DC term.
3. **`chroma-multimb32.h264`** — 32x32 (2x2 macroblocks), flat
   (uniform-gray) luma but a real 2-D oscillating (`sin`/`cos`) Cb/Cr
   pattern, so libx264 never has an RD reason to pick anything but
   Intra_16x16 for luma (`mb I  I16..4: 100.0%  0.0%  0.0%`) while
   Cb/Cr get genuine per-macroblock DC **and AC** residual across all 4
   macroblocks (`coded y,uvDC,uvAC intra: 0.0% 100.0% 100.0%`). This is
   the multi-macroblock validation: real cross-macroblock CAVLC neighbor
   (`nC`) derivation for chroma AC (proven across 4 separate macroblocks,
   not just within one), and 3 of the 4 Intra_Chroma modes actually
   selected by a real encoder (DC/Horizontal/Vertical — `:mb-intra-chroma-pred-modes`
   is `[0 1 2 0]`) plus real cross-macroblock luma Vertical prediction
   (`:mb-pred-modes` is `[2 2 0 0]` — DC for the top row with no top
   neighbor, Vertical for the bottom row using actual reconstructed
   neighbor pixels).
4. **`horizontal-multimb64.h264`** — 64x64 (4x4=16 macroblocks), luma
   varying smoothly by ROW only (`sin` of Y, flat chroma), so libx264 has
   a genuine RD reason to pick Intra_16x16 LUMA HORIZONTAL prediction
   (mode 1) for most macroblocks once a left neighbor is available
   (`:mb-pred-modes` is `[2 1 1 1 0 1 1 1 0 1 1 1 0 1 1 1]` — 12 of 16
   Horizontal). This is the first bit-exact-validated real-encoder example
   of luma Horizontal in a multi-macroblock picture — see
   `test/h264/decode_test.cljk`'s `horizontal-multimb64-golden-vector` for
   the fixture's generation recipe and exactly what it exercises (both
   `CodedBlockPatternLuma` 0 and 15 paths, real cross-macroblock nC
   derivation for the Intra16x16 luma DC block specifically). This was a
   real, previously-shipped, tracked bug (see git history / ADR for the
   root-cause writeup): two independent bugs compounded — (a) the luma DC
   block's cross-MB `nC` derivation read the wrong neighbor state, and (b)
   `h264.decode/blk->col-row` used a wrong block-index-to-position mapping
   AND `h264.transform/luma-dc-hadamard` was missing an input transpose —
   both had to be fixed together (fixing either alone still fails, see
   `blk->col-row`'s docstring for why). Root-caused and fixed by
   cross-referencing FFmpeg's own `libavcodec/h264dec.c`/`h264_mb.c`
   source rather than by guessing.

Fixtures 1/2 are **single-macroblock pictures** (mode 0/1 Intra_16x16
luma prediction is implemented but not exercised by either — a real
encoder never selects Vertical/Horizontal for an unavailable neighbor).
Fixture 3 validates real chroma cross-macroblock decode plus luma
DC/Vertical. Fixture 4 validates real cross-macroblock luma Horizontal.
Likewise the deblocking filter is not implemented at all; fixtures 1-3
happen not to need it because they reconstruct to (locally) constant
regions with zero gradient at block boundaries, where deblocking is a
mathematical no-op — fixture 4 has a genuine cross-block-boundary
gradient, so it's encoded with `--no-deblock` (`disable_deblocking_filter_idc=1`
in the slice header, a properly signaled, spec-mandatory flag that any
compliant decoder — including the real ffmpeg used for the reference
output — MUST honor by skipping deblocking, not an encoder-side-only
nicety). Deblocking itself has NOT been shown to be safe to skip in
general beyond these fixtures.

**Nonobvious implementation details, called out because a plausible-
looking alternative silently produces wrong (but not obviously wrong —
i.e. right-shaped, wrong-valued) output:**
- `h264.transform/inverse-4x4`'s coefficient input needs an internal
  transpose relative to the "obvious" row-major reading of FFmpeg's
  `ff_h264_idct_add` C source — this was found empirically (decoding
  `gradient16-ac.h264` first produced a *transposed* picture) rather than
  by static code reading, and is called out in the namespace docstring so
  a future port doesn't "simplify it away."
- `>>6`/`>>8` rounding in `h264.decode`/`h264.transform` is implemented
  with `bit-shift-right` (an arithmetic/floor shift), not `quot` — for
  the negative coefficient values CAVLC can produce, `quot` (truncating
  toward zero) gives a different result than C's `>>` whenever the value
  isn't an exact multiple of 64. This was caught during implementation,
  not by the golden-vector tests (both fixtures' specific coefficient
  values happen not to expose most instances of this — see
  `h264.transform-test/inverse-4x4-negative-dc-rounds-toward-negative-infinity`
  for an isolated regression test of just this).
- **Chroma sub-block bitstream/placement order is plain RASTER order
  (0=top-left, 1=top-right, 2=bottom-left, 3=bottom-right)** —
  `h264.decode/chroma-blk->col-row`. Luma's own 4x4-sub-block order
  (`h264.decode/blk->col-row`) uses the SAME plain-raster convention
  (per-8x8-quadrant TL/TR/BL/BR, quadrants themselves in TL/TR/BL/BR
  order) — see that def's docstring for the derivation (cross-checked
  three ways against FFmpeg's `libavcodec/h264dec.c`/`h264_mb.c` source).
  An EARLIER version of `blk->col-row` used a column-major/Z-order
  variant instead (a transpose of the correct table) that went
  undetected for a full development session because every fixture up to
  that point had luma content that's symmetric under transpose — see the
  "luma Horizontal desync" bullet below for how this was actually caught
  and fixed. Do not assume luma and chroma need DIFFERENT conventions by
  analogy with ffmpeg's shared `16 + 16*chroma_idx + i4x4` index
  arithmetic — that arithmetic is shared, but the ACTUAL raster-vs-Z-order
  choice must be independently verified for each (chroma correctly uses
  raster; luma, after this fix, also correctly uses raster).
- **Two independent bugs compounded to cause a real, previously-shipped,
  multi-macroblock CAVLC desync/wrong-pixel bug whenever libx264 selected
  Intra_16x16 LUMA HORIZONTAL prediction across macroblocks** (see
  `test/h264/decode_test.cljk`'s `horizontal-multimb64-golden-vector`, the
  fixture that finally exercises this path): (1) `h264.decode/decode-macroblock!`'s
  Intra16x16 luma DC block computed its cross-MB CAVLC `nC` from the
  neighbor's OWN `:dc-nnz` (that neighbor macroblock's DC-block
  total-coeff) instead of the neighbor's `:ac-nnz` at luma 4x4 block
  position `[3,0]`/`[0,3]` — per ffmpeg's `pred_non_zero_count`, the DC
  block's `nC` prediction reads the SAME neighbor cache cell as luma AC
  block 0, which is explicitly ZERO-FILLED whenever that neighbor had
  `CodedBlockPatternLuma=0` (DC-only), REGARDLESS of how many nonzero DC
  coefficients that neighbor actually had. Using `:dc-nnz` instead
  silently picks the wrong coeff_token VLC nC-class and desyncs the bit
  reader on the very next macroblock with a real neighbor-derived DC
  `nC`. (2) `h264.decode/blk->col-row` (see bullet above) AND
  `h264.transform/luma-dc-hadamard` (missing the same kind of input
  transpose `inverse-4x4` already has, see below) were BOTH wrong in a way
  that happened to cancel out for every existing single-MB or flat-luma
  fixture — fixing only one of the two, in isolation, produces a THIRD
  wrong permutation, not a partial improvement (verified empirically
  while root-causing this). Both root causes were found by cross-checking
  FFmpeg's actual `libavcodec/h264dec.c`/`h264_mb.c`/`h264_cavlc.c` source
  (`pred_non_zero_count`, `scan8[]`'s neighbor-addressing formula, the
  `ref_index`/`scan8[0|4|8|12]` 8x8-partition assignment, and the
  `dc_mapping[16]` table), not by static guessing — a real,
  content-specific test (luma varying smoothly along ONE screen axis,
  spanning multiple macroblocks with a real left/top neighbor) was
  necessary to distinguish correct from incorrect in the first place.
- **Chroma DC/AC residual bitstream order is Cb-DC, Cr-DC, Cb-AC (×4),
  Cr-AC (×4)** — NOT Cb(DC then AC) followed by Cr(DC then AC). Decoding
  one component fully before starting the other silently desyncs the bit
  reader on the first macroblock that has real chroma AC
  (`CodedBlockPatternChroma == 2`) — DC-only fixtures don't exercise this
  order at all, so this only surfaces with real multi-component AC
  content. See `h264.decode/decode-chroma-ac-blocks!`'s docstring.

## Pixel decode: Intra_4x4 (`I_NxN`)

This is the increment that makes the decoder able to decode content, rather
than content constructed to be decodable.

**Why it was the blocking gap.** Every fixture in this repo before this
increment is flat, or varies along exactly one axis, and that is not an
accident of taste. **libx264 cannot be told to avoid Intra_4x4:**
`--partitions none` still leaves `analyse=0x1:0` in its own encode log, and
that `0x1` is `X264_ANALYSE_I4x4`. Only content with no texture gives the
encoder no RD reason to pick `I_NxN` for any macroblock. So the earlier
fixtures were flat *in order to be decodable at all* — the decoder could
pass its whole suite while rejecting anything a real encoder emits from a
real picture, with `only Intra_16x16 mb_type (1..24) is supported`.

**What is implemented.**

- **`mb_type` 0 (`I_NxN`)** in a CAVLC I-slice, dispatched in
  `decode-macroblock!` to `decode-intra-4x4-macroblock-body!`. The two
  paths diverge in almost every syntax element after `mb_type`, so the
  dispatch is at the top rather than inside a shared body.
- **All nine §8.3.1.2 prediction modes** (`h264.intra-pred/predict-4x4`):
  Vertical, Horizontal, DC, Diagonal_Down_Left, Diagonal_Down_Right,
  Vertical_Right, Horizontal_Down, Vertical_Left, Horizontal_Up. Note
  Table 8-2's mode numbering is a THIRD numbering, distinct from both
  Intra_16x16's and Table 8-5's chroma one; only Horizontal (1) and DC (2)
  coincide across all three.
- **The §8.3.1.1 predicted-mode derivation** (`neighbour-i4x4-mode`) —
  `predIntra4x4PredMode = min(intraMxMPredModeA, intraMxMPredModeB)` over
  the left and above 4x4 blocks, with `dcPredModePredictedFlag` as a
  SINGLE flag (if either neighbouring macroblock is unavailable, BOTH
  become DC — not just the missing one) and with a neighbour that is not
  itself `I_NxN` contributing DC. This is where the real difficulty is: it
  is stateful across macroblock boundaries (each `I_NxN` macroblock stores
  its 16 resolved modes as `:i4x4-modes` for its right/below neighbours),
  and getting it wrong does NOT desync the bit reader — the pred-mode
  syntax elements are fixed-length, so a wrong derived mode only
  mis-predicts pixels. That is why this needs a real ffmpeg pixel
  comparison and cannot be caught by a round-trip test.
- **§7.3.5.1 `mb_pred` syntax**: 16 `prev_intra4x4_pred_mode_flag` u(1) /
  `rem_intra4x4_pred_mode` u(3) pairs, read up front in Figure 6-10 block
  order before `intra_chroma_pred_mode`, but RESOLVED as they are read
  (block b's predictor depends on blocks b-1 and b-4's resolved modes).
- **Table 9-4's Intra `coded_block_pattern` column** (`golomb-to-intra-cbp`)
  — a different permutation from the inter column already present.
- **`mb_qp_delta` conditional on a non-zero cbp**, unlike Intra_16x16 where
  it is unconditional because that mb_type always carries a luma DC block.
- **16 full 4x4 residual blocks** (`decode-regular-block!`, maxNumCoeff 16).
  `I_NxN` has NO macroblock-level luma DC/Hadamard block — the same residual
  shape as an inter macroblock, not Intra_16x16's DC/AC split.
- **The above-right neighbour macroblock (mbAddrC)**, a fourth neighbour the
  Intra_16x16 path never needed: blocks at grid row 0 / col 3 read
  `p[4..7,-1]` out of the macroblock entirely.
- **§8.3.1.2's `p[4..7,-1]` substitution**: when the above-right samples are
  unavailable but `p[3,-1]` is available, `p[4..7,-1]` are replicated from
  `p[3,-1]`. Not optional — Diagonal_Down_Left and Vertical_Left read those
  samples unconditionally, and five of the sixteen 4x4 positions per
  macroblock (`#{3 7 11 13 15}`) always have an unavailable above-right.
- **The per-block sequential reconstruction loop** (`reconstruct-i4x4-luma`):
  block 1 predicts from block 0's RECONSTRUCTED pixels, so unlike
  `add-residual-16x16` the 16 blocks cannot be reordered.

Chroma is unchanged — `I_NxN` changes the luma prediction structure only, so
`decode-chroma-dc!`/`decode-chroma-ac-blocks!`/`reconstruct-chroma-plane`
are reused verbatim.

**What is still out of scope, and refused rather than approximated.**

- **Intra_8x8 (§8.3.2)** — the OTHER thing `mb_type` 0 can mean. It needs
  the 8x8 integer transform and the §8.3.2.2 reference-sample low-pass
  filter, i.e. a separate feature rather than a variation on this one, so
  it is deliberately not half-implemented. It is signalled by
  `transform_size_8x8_flag`, present only when the PPS carries
  `transform_8x8_mode_flag` — a High Profile field `h264.pps` documents
  itself as not parsing (it sits after `more_rbsp_data()`). `reject-intra-8x8!`
  therefore refuses `I_NxN` up front for any High-Profile-family
  `profile_idc`, where the flag COULD be set and cannot be seen, rather
  than assuming Intra_4x4 and decoding an Intra_8x8 macroblock into
  plausible garbage. For a Baseline/Main stream the flag cannot be present
  at all and `I_NxN` unambiguously means Intra_4x4.
- **CABAC-coded `I_NxN`** — `mb_type`, the pred-mode flags and
  `coded_block_pattern` all have their own §9.3.3.1.1.x context models that
  `h264.cabac` does not implement. The CABAC I-slice path still refuses
  `mb_type` 0. Stated follow-up, not a silent gap.
- **`I_NxN` inside a P-slice** (Table 7-13's `p_mb_type - 5` == 0) — the
  P-slice path delegates intra macroblocks to the Intra_16x16 body, which
  refuses `mb_type` 0. Also a stated follow-up.

Both refusals go through a pinned reason literal asserted in
`decode_test.clj`'s `unsupported-mb-type-throws`, which also asserts the
Intra_8x8 refusal does NOT fire for a Baseline `profile_idc` — i.e. that
the check refuses for the reason it names, rather than always.

**Validation** (`i4x4-mandel64-golden-vector` in `test/h264/decode_test.cljk`).

```
ffmpeg -f lavfi -i "mandelbrot=size=64x64:rate=1" -frames:v 1 \
  -pix_fmt yuv420p src64.y4m
x264 --input-res 64x64 --fps 25 -o i4x4-mandel64.h264 --qp 26 \
  --keyint 1 --no-deblock --partitions i4x4 --profile baseline src64.y4m
ffmpeg -i i4x4-mandel64.h264 -pix_fmt yuv420p i4x4-mandel64.ref.yuv
```

A Mandelbrot render — texture at every scale, the opposite of every earlier
fixture. x264's own encode log for this file reports
`mb I  I16..4:  6.2%  0.0% 93.8%` (15 of 16 macroblocks `I_NxN`) and
`i4 v,h,dc,ddl,ddr,vr,hd,vl,hu:  3% 15% 20% 15% 12%  7% 13%  5%  9%` — a
non-zero share for **every one of the nine modes**. `--no-deblock` for the
same reason as `horizontal-multimb64.h264`: real texture produces real
block-boundary discontinuities and this repo has no deblocking filter.
Luma and both chroma planes are bit-exact against ffmpeg 8.1.1's own
reconstruction, no tolerance.

**The pixel comparison is gated on a structural assertion that runs first.**
A fixture that quietly re-encoded as all-Intra_16x16 would let the pixel
comparison pass without executing a line of this code, so
`assert-i4x4-coverage!` refuses to compare pixels unless three things hold:
every macroblock is the type **ffmpeg itself** reported
(`ffmpeg -v debug -debug mb_type`, whose dump for this file is
`I i i i / i i i i / i i i i / i i i i` — ground truth from outside this
repo, not from the decoder under test); `:mb-pred-modes` is nil at exactly
the positions `:mb-i4x4?` is true, so a state map that forgot to set the
flag cannot pass; and all nine prediction modes actually occur, which x264's
own log independently confirms is a property of the bitstream.

**The test was shown to discriminate.** With `neighbour-i4x4-mode`'s single
`dcPredModePredictedFlag` changed to the plausible-looking per-neighbour
form — substituting DC only for the neighbour whose macroblock is
unavailable, instead of for both — the fixture still decodes end to end
with no desync and no exception (as expected: the pred-mode syntax elements
are fixed-length, so a wrong derived mode moves no bits), the macroblock
types still match ffmpeg's dump, and all nine prediction modes still appear
— so the structural assertion passes unchanged. **38 of the 4,096 luma
bytes come out wrong**, first at row 0 column 52, and the luma assertion
fails. Both chroma planes stay bit-exact, as they should: this bug is in
luma prediction only.

38 bytes is a small signal, and that is the point rather than a weakness of
the check. Nothing short of a bit-exact comparison against a real decoder's
own reconstruction would see it: the picture still decodes, still has the
right structure, still looks like a Mandelbrot set. A tolerance, a
checksum-of-a-downsample, or a round-trip through this repo's own encoder
would all report success.

## Pixel decode: CABAC (Wave 8, ADR-2607122000 CABAC increment)

`h264.cabac`, wired into `h264.decode`, adds real CABAC (Context-Adaptive
Binary Arithmetic Coding, §9.3) entropy decode for main/high-profile
streams — the first time this ecosystem decodes anything other than
baseline-profile CAVLC. Same non-realtime, correctness-first reference
tier as every other decode path here.

**What's implemented:**
- **The literal per-bit arithmetic decoding engine** (§9.3.3.2 — NOT
  FFmpeg's own byte-buffered/table-packed variant, see `h264.cabac`'s
  namespace docstring for why): `codIRange`/`codIOffset` init and
  renormalization, `DecodeDecision`/`DecodeBypass`/`DecodeTerminate`.
  `range-tab-lps`/`trans-idx-lps`/`trans-idx-mps` (Tables 9-44/9-45) and
  the I-slice column of the context-init `(m,n)` table (Tables 9-12..9-24,
  `context-init-i`, 460 entries) were extracted PROGRAMMATICALLY (a small
  parser, not hand-transcribed) from Cisco OpenH264's
  `codec/common/src/common_tables.cpp` — chosen over FFmpeg's own
  `ff_h264_cabac_tables` specifically because OpenH264's is a literal,
  un-packed transcription (separate `pStateIdx`/`valMPS`) matching this
  namespace's own engine design, and cross-checked against FFmpeg's
  independently-packed encoding of the SAME tables (both agree exactly:
  pStateIdx 0 → rangeTabLPS `{128,176,208,240}`/transIdxLPS 0/transIdxMPS 1,
  pStateIdx 63 → `{2,2,2,2}`/63/63 — the well-known published values).
- **`mb_type` (I-slice), `intra_chroma_pred_mode`, `mb_qp_delta`
  binarization** (§9.3.2.2/9.3.2.5/9.3.2.7), each cross-referenced against
  OpenH264's own `ParseMBTypeISliceCabac`/`ParseIntraPredModeChromaCabac`/
  `ParseDeltaQpCabac` (`codec/decoder/core/src/parse_mb_syn_cabac.cpp`) —
  not re-derived from spec prose alone.
- **`residual-block!`**: `coded_block_flag` (§9.3.3.1.1.9 — unlike CAVLC's
  `coeff_token`, CABAC always spends an explicit bit per potentially-empty
  block; the unavailable-neighbor default is "1 if the CURRENT macroblock
  is intra" — always true in this repo's always-intra CABAC scope, a
  genuinely different rule than CAVLC's nC "unavailable → 0" default),
  `significant_coeff_flag`/`last_significant_coeff_flag` (§9.3.3.1.2, a
  pure scan-position-indexed context — no neighbor dependence, unlike
  CAVLC's nC), and `coeff_abs_level_minus1` + its bypass sign bit
  (§9.3.2.3/9.3.3.1.3 — the adaptive `c1`/`c2` context-index state machine,
  including the truncated-unary-then-EG0-bypass-suffix continuation for
  `coeff_abs_level_minus1`, ported from OpenH264's `DecodeUEGLevelCabac`/
  `DecodeExpBypassCabac` rather than re-derived). Returns the SAME
  scan-order `{:coeffs :total-coeff}` shape `h264.cavlc/residual-block!`
  does, so `h264.decode` reuses the EXACT SAME entropy-agnostic
  unscan/dequant/(luma-DC-Hadamard or regular-4x4) transform pipeline for
  both entropy methods — only the entropy-decode call and the
  neighbor-derivation rule for context selection differ between
  `decode-luma-dc!`/`decode-ac-block!` (CAVLC) and
  `decode-luma-dc-cabac!`/`decode-ac-block-cabac!` (CABAC).
- **`coded_block_pattern` is NOT separately read for Intra_16x16
  macroblocks** (CABAC OR CAVLC) — it's fully inferred from `mb_type`
  itself (Table 7-11, `h264.decode/i16x16-mb-info`, unchanged), matching
  §7.3.5.1's own `mb_qp_delta`/`residual()` presence condition (which
  explicitly includes `MbPartPredMode==Intra_16x16` as an alternative to
  `CodedBlockPatternLuma>0`). This means `h264.cabac`'s own
  `coded_block_pattern` context model (ctxIdxOffset 73) is unused for
  Intra_16x16 macroblocks specifically — it's used for INTER macroblocks
  instead, see "Pixel decode: CABAC + P-slice (inter)" below
  (`read-coded-block-pattern-inter-cabac!`); `I_NxN`'s own use of this same
  context model remains out of scope. `I_NxN` IS decoded now, but only on
  the **CAVLC** path (see "Pixel decode: Intra_4x4 (I_NxN)" below) — CABAC
  `I_NxN` needs its own `mb_type` binarization branch plus the
  `prev_intra4x4_pred_mode_flag`/`rem_intra4x4_pred_mode` context models,
  none of which exist, so the CABAC I-slice path still refuses `mb_type` 0.

**What's explicitly NOT implemented / not yet working** (out of scope, or
a known limitation — see below for exactly which):
- CABAC + P-slice/inter prediction is now PARTIALLY implemented — see
  "Pixel decode: CABAC + P-slice (inter)" below for exactly what (`P_Skip`/
  `P_L0_16x16`) and what's still out of scope (sub-partitioned inter,
  intra-coded macroblocks within a CABAC P-slice, B-slices).
- CABAC + `I_NxN`/`I_8x8`/`I_PCM` — the throw-on-unsupported-`mb_type`
  discipline via the shared `i16x16-mb-info`. NOTE this is now a real
  ASYMMETRY rather than a shared limitation: CAVLC decodes `I_NxN`
  (Intra_4x4) and CABAC does not.
- `transform_size_8x8_flag`/8x8-transform CABAC contexts (High-Profile-only
  — this repo's `h264.pps` doesn't even parse the field, see that
  namespace's docstring).
- CABAC ENCODE (this increment is decode-only, mirroring how CAVLC decode
  long preceded CAVLC encode in this repo's own history).

**Validated bit-exact (no tolerance), including multi-macroblock/
multi-coefficient content.** `test/h264/decode_cabac_test.cljk` validates 3
real `ffmpeg 8.1.1`/x264-encoded Main-profile fixtures bit-exact:
`flat16-dc-only-cabac.h264` (single macroblock, `coded_block_flag`=0 fast
path for every block), `gradient16-ac-cabac.h264` (single macroblock, ONE
genuinely significant AC coefficient — the first real exercise of
`significant_coeff_flag`/`coeff_abs_level_minus1`), and
`multimb64-cabac.h264` (64x64/16 macroblocks, real DC/Horizontal/Vertical
prediction with several 4x4 blocks having 3+ significant coefficients,
some large enough to exercise the EG0 bypass-suffix continuation).
`gradient16-ac-cabac.h264` required `--no-deblock` (a real libx264 in-loop
deblocking effect this decoder — CABAC or CAVLC alike — doesn't
implement, same limitation as the existing CAVLC
`horizontal-multimb64.h264` fixture; confirmed to be a deblocking
difference and NOT a CABAC bug by manually verifying the pre-deblock
reconstruction from this decoder's own coefficients, fed through the
already-tested `h264.transform` pipeline, matched ffmpeg's output only
once deblocking was disabled).

**Fixed: multi-macroblock / 3+-significant-coefficient bug
(`h264.cabac/decode-exp-golomb-bypass!`).** An earlier version of this
namespace decoded `flat16-dc-only-cabac.h264`/`gradient16-ac-cabac.h264`
bit-exact but was NOT yet confirmed bit-exact on multi-macroblock content
— high-level structure (`mb_type`/inferred `coded_block_pattern`/
Intra_16x16 prediction-mode decisions, cross-checked against an
independently-CAVLC-encoded version of the same source image) and
bitstream framing (`end_of_slice_flag` firing exactly at the picture's
last macroblock) were already correct, but RECONSTRUCTED PIXELS showed
small (±1..3, occasionally more) discrepancies specifically in 4x4
residual blocks with 3 OR MORE significant coefficients.

Root cause: the EG0 (order-0 Exp-Golomb) bypass-suffix accumulator in
`decode-exp-golomb-bypass!` reused the SAME accumulator as the truncated-
unary PREFIX sum (via `bit-or`) instead of a separate one added at the
end. A `count`-length unary prefix always sums to exactly `2^count - 1`
(ALL `count` low bits already 1), so OR-ing `count` MORE suffix bits into
those SAME bit positions is a silent no-op REGARDLESS of the actual
suffix value — every `coeff_abs_level_minus1` large enough to reach this
suffix (i.e. saturating `decode-ueg-level!`'s cMax=13 truncated-unary
bank, `coeff_abs_level_minus1 >= 14`) silently truncated to the prefix's
own value. Invisible on both single-MB fixtures (neither has a
coefficient anywhere near that large); reliably wrong the moment any
block's real decoded magnitude got large enough to need the suffix — which
real complex/multi-macroblock content does routinely, matching the
originally-reported "3 or more significant coefficients" symptom exactly
(more significant coefficients per block statistically raises the odds at
least one hits a large enough magnitude, though the true trigger is
magnitude, not coefficient COUNT per se).

Root-caused via an independent from-scratch Python re-implementation of
the CABAC arithmetic engine + 460-entry context-init table (cross-checked
programmatically, zero diffs, against Cisco OpenH264's own
`common_tables.cpp`/`parse_mb_syn_cabac.cpp`/`decoder_context.h` — the
same reference this namespace's tables were originally ported from) that
reproduced the IDENTICAL wrong bin sequence and coefficient values on a
new multi-macroblock fixture (`multimb64-cabac.h264`) — confirming the
entropy decode's CONTROL FLOW (which bins get read, in what order,
against which contexts) was already correct, and narrowing the bug to
this one arithmetic combination step. Fix (matching OpenH264's own
`DecodeExpBypassCabac`, which uses two separate accumulators `iSymTmp`/
`iSymTmp2` added together at the end): the fixed corrected values (`+29`/
`+89` instead of the previous `+22`/`+78` at the affected block's two
large-magnitude positions) exactly match an independently-CAVLC-encoded
reference of near-identical content, and the fixed decoder reproduces
`multimb64-cabac.h264`'s real ffmpeg reconstruction bit-exact across all
16 macroblocks (luma AND chroma).

## Pixel decode: CABAC + P-slice (inter) (Wave 9, ADR-2607122000 CABAC+P-slice increment)

`h264.cabac`/`h264.decode` combine the two previously-separate increments
above (I-slice-only CABAC decode, and CAVLC-only P-slice inter prediction)
for the first time: a CABAC-coded P-slice's `P_Skip` and `P_L0_16x16`
macroblocks now decode, mirroring the CAVLC P-slice path's own scope
exactly for those two mb_types.

**What's implemented:**
- **`mb_skip_flag`** (§9.3.3.1.1.3/Table 9-11 ctxIdxOffset 11,
  `h264.cabac/read-mb-skip-flag!`) — read for EVERY macroblock address in
  a CABAC P-slice (unlike CAVLC's run-length `mb_skip_run`), with real
  cross-macroblock neighbor-context derivation (`left`/`top` available AND
  not itself skipped).
- **P-slice `mb_type` binarization** (§9.3.2.5/Table 9-37,
  `h264.cabac/read-mb-type-p!`) — a bin-for-bin-different tree from
  I-slice's own `read-mb-type-i!`, ported from OpenH264's
  `ParseMBTypePSliceCabac`. Only `mb_type` 0 (`P_L0_16x16`) is decoded;
  1..4 (sub-partitioned inter) throw explicitly (matching the CAVLC
  P-slice path's own scope), and any intra-coded macroblock within this
  CABAC P-slice ALSO throws explicitly (a narrower scope than the CAVLC
  P-slice path, which DOES decode intra-in-P macroblocks — this
  increment's own real-encoder validation fixtures don't exercise that
  case, and adding it is a separate, not-yet-validated follow-up).
- **`mvd_l0`** (§9.3.2.3 UEG3 binarization, `h264.cabac/read-mvd!`) — both
  horizontal and vertical components, each with their own 7-context bank
  and real neighbor-derived (`|left mvd| + |top mvd|`) ctxIdxInc, including
  the EGk bypass-suffix continuation for large magnitudes (reusing
  `decode-exp-golomb-bypass!`, the SAME helper — and the SAME earlier bug
  fix — `coeff_abs_level_minus1` uses, just with `k0=3` instead of `k0=0`).
- **`coded_block_pattern` for INTER macroblocks**
  (`h264.cabac/read-coded-block-pattern-inter-cabac!`) — a COMPLETELY
  DIFFERENT binarization from CAVLC's `me(v)`+`golomb-to-inter-cbp` table
  lookup: one context-coded bin per 8x8 luma quadrant (context derived from
  whether the spatially adjacent neighbor 8x8 block had residual) plus 2
  more bins for `CodedBlockPatternChroma`.
- **Inter luma residual** via a NEW CABAC block category, `:luma-regular`
  (`h264.cabac/residual-block!`'s 4th category alongside `:luma-dc`/
  `:luma-ac`/`:chroma-dc`/`:chroma-ac`) — the full 16-coefficient "regular"
  4x4 block (no separate DC/Hadamard split), the CABAC counterpart of
  `h264.decode/decode-regular-block!`'s CAVLC shape.
- **Chroma residual is UNCHANGED** — `decode-chroma-dc-cabac!`/
  `decode-chroma-ac-blocks-cabac!` (already validated by the I-slice CABAC
  increment above) are reused for inter macroblocks too, entropy-agnostic
  to the macroblock type — matching CAVLC's own "chroma residual doesn't
  depend on mb_type" design.
- **`cabac_init_idc`** (§7.3.3, `ue(v)` — NOT a fixed-width field, see the
  bug note below) — a P-slice-only slice-header field selecting one of 3
  P/B-only `(m,n)` context-init columns (`h264.cabac/context-init-p0/p1/p2`,
  programmatically extracted from Cisco OpenH264's `common_tables.cpp`
  using the SAME parser that produced the pre-existing I-slice column,
  independently re-confirming that column's values too — zero diffs).

**What's explicitly NOT implemented** (out of scope, not silently wrong):
sub-partitioned inter (`P_L0_L0_16x8`/`P_L0_L0_8x16`/`P_8x8`/`P_8x8ref0`),
intra-coded macroblocks within a CABAC P-slice, B-slices, multiple
reference frames, and everything else every other CABAC/P-slice scope
note in this README already excludes.

**Two real bugs were found and fixed while validating this increment
against real x264/ffmpeg streams** (both root-caused via an independent
from-scratch Python re-implementation, the same methodology the earlier
EG0-bypass-suffix bug above used):

1. **`cabac_init_idc` is `ue(v)` (Exp-Golomb), not a fixed 2-bit field.**
   The first implementation read it as `u(2)` (a plausible-looking but
   wrong guess) — cross-checked against FFmpeg's own `h264_slice.c`
   (`get_ue_golomb_31`), which confirmed `ue(v)`. Caught immediately: the
   wrong-width read desynced the very next field, decoding an
   out-of-range `cabac_init_idc` value (3 — valid range is 0..2) on the
   first real CABAC P-slice fixture tried.
2. **`coded_block_flag`'s unavailable-neighbor default (§9.3.3.1.1.9) is
   `!!IS_INTRA(CURRENT macroblock)`, not a fixed value** — the pre-existing
   I-slice-only CABAC code correctly hardcoded `true` (every macroblock in
   that scope IS intra), but the P-slice increment's first draft of
   `decode-inter-16x16-macroblock-cabac!`'s luma/chroma-DC unavailable-
   neighbor defaults, and the shared `decode-chroma-ac-blocks-cabac!`,
   copied that SAME `true` verbatim instead of adjusting it for the
   current macroblock actually being INTER (where the correct default is
   `false`). Invisible on `p-skip-flat16-cabac.h264` (P_Skip reads no
   residual at all); on `p-l0-16x16-multimb64-cabac.h264` this produced
   real, substantial, plausible-shaped-but-wrong pixel corruption starting
   from the macroblock immediately after the first one (the first
   macroblock has no left/top neighbors at all, coincidentally hiding the
   bug for it alone — confirmed by comparing motion-compensation-only
   reconstruction, verified correct, against the full residual-included
   reconstruction, verified wrong). Fixed by threading an `intra?`
   parameter through the shared chroma-AC helper and using `false` for the
   inter macroblock's own luma/chroma-DC unavailable-neighbor defaults —
   see `h264.decode/decode-chroma-ac-blocks-cabac!`'s own docstring for
   the full root-cause trail.

**Validated bit-exact (no tolerance).** `test/h264/decode_p_slice_cabac_test.cljk`
validates 2 real `ffmpeg 8.1.1`/x264-encoded Main-profile CABAC fixtures
bit-exact: `p-skip-flat16-cabac.h264` (2 identical flat frames, 100%
`P_Skip` — the real-encoder log confirms `skip:100.0%`) and
`p-l0-16x16-multimb64-cabac.h264` (64x64/16 macroblocks, a translating
two-frequency luma texture, 100% `P_L0_16x16` with REAL nonzero luma AC
residual in every one of the 16 macroblocks — the real-encoder log
confirms `skip: 0.0%`/`P16..4: 100.0%`/`inter: 100.0%` luma coded — the
strongest CABAC+P-slice interoperability evidence here: the full
`mb_skip_flag`/`mb_type`/`mvd_l0`/`coded_block_pattern`/`mb_qp_delta`/
16-regular-block-residual pipeline exercised across 16 real macroblocks
with real cross-macroblock `coded_block_flag`/`mvd`/`cbp` neighbor-context
derivation, reconstructing bit-exact against ffmpeg's own independent
decode of the SAME real encoder output).

## Pixel decode: P-slice (inter) (Wave 6, ADR-2607122000 Migration step 7's first increment)

`h264.decode/decode-gop` decodes a whole GOP (one IDR I-frame followed by
zero or more P-frames) in bitstream order — the first time this ecosystem
decodes inter-predicted pixels, not just intra. `decode-idr-frame` (single
IDR picture) is UNCHANGED — it still only ever looks at the first IDR
slice NAL and ignores anything else, so existing callers are unaffected.

**What's implemented:**
- **Five mb_types**: `P_Skip` (§7.3.5, the whole-picture-covering
  `mb_skip_run` bookkeeping in `slice_data()` — no `mb_type`/residual bits
  at all for a skipped macroblock), `P_L0_16x16` (`mb_type` 0 in a
  P-slice: one 16x16 partition, one motion vector, `ref_idx_l0` implicit 0
  since this repo requires `num_ref_idx_l0_active == 1`), and — as of the
  sub-partition increment, see "Pixel decode: P-slice sub-partitioned
  inter" below — `P_L0_L0_16x8`/`P_L0_L0_8x16`/`P_8x8` (`mb_type` 1..3;
  `P_8x8ref0`, `mb_type` 4, and any `P_8x8` `sub_mb_type` other than
  `P_L0_8x8` still throw explicitly, matching this repo's existing
  throw-on-unsupported-mb_type discipline for `I_NxN`/`I_PCM`). Intra
  macroblocks WITHIN a P-slice (`mb_type` >= 5, `intra_mb_type = mb_type -
  5` per Table 7-13) are also decoded — real encoders do choose intra
  macroblocks inside P-slices, and this repo's existing Intra_16x16 decode
  path (`decode-intra-macroblock-body!`) is reused unchanged, since a
  P-slice's intra macroblock is pixel-identical to an I-slice's.
- **Single reference frame**: a P-slice's motion compensation always
  references the IMMEDIATELY PRECEDING decoded picture (no multi-frame
  DPB/reference-picture-list machinery). `h264.slice/parse-header!` throws
  unless `num_ref_idx_l0_active` resolves to exactly 1, unless
  `ref_pic_list_modification_flag_l0` is 0, and unless PPS
  `weighted_pred?` is false — reference reordering and weighted prediction
  are out of scope.
- **Real median motion-vector prediction** (§8.4.1.3, `mv-predict-16x16`,
  now a thin wrapper over the general `mv-predict-partition` the
  sub-partition increment below introduces) and the P_Skip-specific
  predictor special case (§8.4.1.1, `p-skip-mv`) — implemented per spec
  (median of left/top/top-right-or-top-left neighbors, with the correct
  "only one ref-idx matches" special case), NOT hardcoded to always return
  `[0 0]` — see `h264.decode/mv-predict-16x16`'s docstring. Both now derive
  their A/B/C(/D) neighbors at 8x8-QUADRANT granularity
  (`mb-quadrant-mv`/`neighbor-abc`) rather than reading a neighbor's whole-
  macroblock `:mv` in one shot — this is REQUIRED (not just a refactor) once
  a neighbor macroblock can itself be sub-partitioned (`P_16x8`/`P_8x16`/
  `P_8x8`, see below) and carry DIFFERENT motion vectors in different
  quadrants; every mb_type this repo supported BEFORE the sub-partition
  increment happens to have a UNIFORM per-quadrant motion field, so this
  generalization is proven bit-exact-unchanged for every pre-existing
  golden vector (see `test/h264/decode_p_slice_test.cljk`/
  `decode_p_subpel_test.clj`, all still passing unchanged) while being
  necessary for correctness once a sub-partitioned neighbor is possible
  (see "Pixel decode: P-slice sub-partitioned inter" below).
- **Real sub-pel motion compensation** (`mc-predict`, delegating to the new
  `h264.interp` namespace — see "Sub-pel motion compensation" below):
  luma quarter-sample interpolation (§8.4.2.2.1, 6-tap FIR
  `(1,-5,20,20,-5,1)` for half-sample positions + rounded averaging for
  quarter-sample positions) and chroma eighth-sample bilinear interpolation
  (§8.4.2.2.2), for ANY motion vector — integer, half-pel, or quarter-pel,
  in any direction. MV=(0,0) is simply the trivial degenerate case (a
  direct sample read), not a separate code path. This replaces the
  earlier MV=(0,0)-only increment's explicit throw-on-nonzero-mv guards in
  `decode-p-skip-macroblock!`/`decode-inter-16x16-macroblock!` — real
  libx264 was found (during the earlier increment's own development) to
  reliably choose non-zero motion vectors for almost any real motion
  content, so this was the natural next increment, not a hypothetical
  concern.
- **Inter luma residual**: unlike Intra_16x16 (which has a separate
  macroblock-level DC/Hadamard block plus 15-coefficient AC blocks), an
  inter (or `I_NxN`) macroblock's 16 luma 4x4 blocks are each a FULL
  16-coefficient regular block (`decode-regular-block!`, all 16 positions
  — including [0,0] — dequantized via the same per-position `ac-qmul`
  formula AC blocks already use). `CodedBlockPatternLuma` gates each of
  the 4 8x8 quadrants independently (1 bit each, `bit-test`) rather than
  being inferred all-or-nothing from `mb_type` the way Intra16x16's is.
- **`coded_block_pattern` (§9.1.2 Table 9-4 ME(v) mapping, Inter column
  only)**: `golomb-to-inter-cbp`, transcribed from FFmpeg's
  `ff_h264_golomb_to_inter_cbp` (`libavcodec/h264data.c`) and verified to
  be a full permutation of 0..47. Table 9-4's OTHER (Intra) column is now
  also implemented, as `golomb-to-intra-cbp`, for the Intra_4x4 path — it
  is a genuinely different permutation, so reading the inter table for an
  `I_NxN` macroblock yields a wrong-but-plausible cbp and desyncs the
  residual reader a few blocks later. Both are asserted to be full
  permutations of 0..47 in `decode_test.clj`
  (`cbp-tables-are-permutations`).
- **Chroma residual is UNCHANGED** — `decode-chroma-dc!`/
  `decode-chroma-ac-blocks!` are reused as-is for inter macroblocks; the
  chroma DC(2x2 Hadamard)+AC residual structure doesn't depend on the luma
  macroblock type at all.

**What's explicitly NOT implemented** (out of scope, not silently wrong):
CABAC + `P_L0_L0_16x8`/`P_L0_L0_8x16`/`P_8x8`/`P_8x8ref0`/intra-in-P (CABAC
`P_Skip`/`P_L0_16x16` ARE now implemented, see "Pixel decode: CABAC +
P-slice (inter)" above; CAVLC `P_L0_L0_16x8`/`P_L0_L0_8x16`/`P_8x8` ARE now
implemented too, see "Pixel decode: P-slice sub-partitioned inter" below),
B-slices, multiple reference frames / a real DPB, reference-list
reordering, weighted prediction, adaptive (MMCO) reference-picture
marking, `P_8x8ref0` (`mb_type` 4), and any `P_8x8` `sub_mb_type` finer
than `P_L0_8x8` (`P_L0_8x4`/`P_L0_4x8`/`P_L0_4x4` — see "Pixel decode:
P-slice sub-partitioned inter" below for the full scope/rationale).
The encode side has NOT been extended for P-slices at all — `h264.encode`
remains IDR-only.

**Validation.** `test/h264/decode_p_slice_test.cljk` covers 3 golden
vectors (the ORIGINAL MV=(0,0)-only increment, still passing unchanged
now that MV=(0,0) is just the trivial case of the general sub-pel path),
all bit-exact (no tolerance) against real `ffmpeg 8.1.1`:
`p-skip-flat16.h264` (REAL libx264 output — 2 identical flat-gray frames,
100% P_Skip), and `p-16x16-mb0-realac.h264`/
`p-skip-then-16x16-multimb.h264` (hand-authored using this repo's OWN
already-bit-exact-tested encode-side primitives — `h264.encode` for the
IDR reference frame, `h264.expgolomb`/`h264.cavlc` for a hand-built
spec-valid P-slice NAL — because real encoders essentially never choose
`P_L0_16x16` with a genuinely zero final motion vector AND nonzero
residual for content that also keeps the reference frame's own intra
coding within this repo's Intra_16x16-only scope, see that test file's
own docstring for the full explanation and exactly why this is still a
genuine independent-decoder cross-check, not a self-consistency
tautology: real ffmpeg decodes these exact hand-authored bytes without
having seen or trusted anything about how they were constructed). See
"Sub-pel motion compensation" below for the (real + hand-authored)
non-zero/sub-pel golden vectors.

## Pixel decode: P-slice sub-partitioned inter (Migration step 7's sub-partition increment)

`h264.decode` extends the CAVLC P-slice inter path above from whole-16x16-
partition-only (`P_Skip`/`P_L0_16x16`) to the smaller inter sub-partition
`mb_type`s — `P_L0_L0_16x8`, `P_L0_L0_8x16`, and `P_8x8` — each macroblock
now possibly carrying 2 or 4 independent motion vectors instead of one.
Same non-realtime, correctness-first reference tier as every other
decode path here.

**What's implemented:**
- **`P_L0_L0_16x8`** (`mb_type` 1) and **`P_L0_L0_8x16`** (`mb_type` 2)
  (`decode-inter-16x8-macroblock!`/`decode-inter-8x16-macroblock!`): 2
  partitions each (top/bottom 16x8, or left/right 8x16), each with its own
  `mvd_l0` (read in `mb_pred`'s own mbPartIdx order — §7.3.5.1) — no
  `ref_idx_l0` either (same `num_ref_idx_l0_active == 1` simplification
  `P_L0_16x16` already relies on).
- **`P_8x8`** (`mb_type` 3, `decode-inter-8x8-macroblock!`): §7.3.5.2
  `sub_mb_pred` reads all 4 `sub_mb_type` values (one per 8x8 quadrant,
  TL/TR/BL/BR raster order) FIRST, per spec's own bitstream order — but
  ONLY `sub_mb_type` `P_L0_8x8` (value 0 — one 8x8 partition per quadrant,
  no further split) is supported; `P_L0_8x4`/`P_L0_4x8`/`P_L0_4x4` (1/2/3 —
  splitting an 8x8 partition further into 8x4/4x8/4x4 pieces) throw
  explicitly, matching this repo's existing throw-on-unsupported
  discipline. Given that constraint, `P_8x8` always has exactly 4
  sub-partitions, one per quadrant, each with its own `mvd_l0`.
- **`P_8x8ref0`** (`mb_type` 4) throws explicitly and is OUT OF SCOPE for
  this increment — even though this repo's `num_ref_idx_l0_active == 1`
  requirement happens to make its bitstream syntax IDENTICAL to plain
  `P_8x8`'s (`ref_idx_l0` is never present in the bitstream either way,
  since it's only signaled when `num_ref_idx_l0_active_minus1 > 0`), it's
  excluded regardless, per this increment's own scope decision.
- **A general, spec-faithful §8.4.1.3 motion-vector predictor**
  (`mv-predict-partition`/`neighbor-abc`/`classify-4x4`/`mb-quadrant-mv`),
  operating at 8x8-QUADRANT granularity (this repo's finest supported
  partition size) rather than being special-cased per mb_type:
  - `classify-4x4` maps a partition's A/B/(C-or-D) neighbor position
    (4x4-luma-block-unit offsets relative to the current macroblock) to
    one of `:self` (an earlier-decided quadrant of the SAME macroblock —
    always resolvable given this repo's fixed TL/TR/BL/BR decode order),
    `:left`/`:top`/`:topleft`/`:topright` (a specific quadrant of a
    neighbor macroblock), or `:none` (the target macroblock address does
    NOT exist yet in raster-scan order — the only case reachable here is
    one column past the CURRENT macroblock's own right edge at a row
    that's still within the current macroblock, e.g. `P_8x8`'s
    bottom-right quadrant's own "C" neighbor).
  - `neighbor-abc` derives A/B/C for ANY of the 4 supported partition
    shapes (16x16/16x8/8x16/8x8) uniformly, including the §8.4.1.3.1
    mbAddrC→mbAddrD substitution — critically, this substitution is keyed
    on macroblock-ADDRESS availability (`:none`, from `classify-4x4`), NOT
    on whether an EXISTING neighbor happens to be intra-coded (an intra
    neighbor contributes ref-idx -1 directly via `mb-quadrant-mv`, with NO
    D-substitution) — cross-checked against this exact distinction in
    FFmpeg's `fetch_diagonal_mv` (`libavcodec/h264_mvpred.h`).
  - `mv-predict-partition` then dispatches to the `P_16x8`/`P_8x16`
    directional special cases (§8.4.1.3's own bullet list: use ONE named
    neighbor directly when its ref-idx matches, else fall through) before
    falling back to the general median process (§8.4.1.3.1) shared by
    16x16 whole-macroblock partitions AND every 8x8 sub-partition alike —
    all cross-checked against FFmpeg's `pred_motion`/`pred_16x8_motion`/
    `pred_8x16_motion` (`libavcodec/h264_mvpred.h`), not re-derived from
    spec prose alone.
  - Deliberately OMITS the spec's additional "B and C both
    address-unavailable, A available → B=C=A" substitution — in this
    repo's single-reference-frame scope (every real inter neighbor's
    ref-idx is ALWAYS 0) this is PROVABLY REDUNDANT with the "exactly one
    neighbor's ref-idx matches → use it directly" rule already in place
    (verified: without the substitution, an available-but-unmatched-
    neighbor-starved A still ends up the SOLE exact-match, producing the
    IDENTICAL result the substitution would have forced via
    median(A,A,A)=A) — see `h264.decode/median-mv-predict`'s docstring.
  - **This ALSO required generalizing `mv-predict-16x16`/`p-skip-mv`
    themselves** (used by `P_L0_16x16`/`P_Skip`, i.e. every mb_type this
    repo supported BEFORE this increment) to read a neighbor's motion
    vector at the SPECIFIC quadrant §8.4.1.3 requires (`mb-quadrant-mv`)
    rather than a neighbor's flat whole-macroblock `:mv` — a latent
    correctness gap that was harmless before this increment (every
    pre-existing mb_type has a UNIFORM per-quadrant motion field, so a
    flat read was indistinguishable from a quadrant-specific one) but
    would have silently mispredicted whenever `P_L0_16x16`/`P_Skip` is
    adjacent to a NEWLY-sub-partitioned neighbor. Proven a pure
    generalization (not a behavior change) for every pre-existing
    fixture: all of `test/h264/decode_p_slice_test.cljk`/
    `decode_p_subpel_test.clj`/`decode_p_slice_cabac_test.clj` pass
    bit-exact-unchanged.
- **Per-quadrant motion compensation** (`mc-predict-quadrants`): decomposes
  ANY of the 4 supported partition shapes into 4 independent 8x8-luma/
  4x4-chroma `h264.interp` calls (one per quadrant, each with that
  quadrant's OWN motion vector) and assembles the results — reusing
  `h264.interp` COMPLETELY UNCHANGED (motion compensation is a pure
  per-pixel function of position + that pixel's own partition's mv, so
  decomposing into uniform 8x8 quadrants is pixel-identical to a single
  larger-block call even when 2 or 4 quadrants happen to share the SAME
  mv, as for `P_16x8`/`P_8x16`/`P_L0_16x16`). `mc-predict` (the
  `P_L0_16x16`/`P_Skip` path) is now itself implemented as the single-mv
  degenerate case of `mc-predict-quadrants`, for the same reason.
- **`coded_block_pattern`/`mb_qp_delta`/residual/chroma are UNCHANGED** —
  factored into a shared `decode-inter-residual-and-reconstruct!` tail
  used by EVERY inter mb_type (whole-16x16 or sub-partitioned alike),
  since none of that syntax depends on the partition structure above it,
  only on the already-fully-derived per-8x8-quadrant motion-compensated
  prediction.

**What's explicitly NOT implemented** (out of scope, not silently wrong):
`P_8x8ref0` (`mb_type` 4); `P_8x8` `sub_mb_type` `P_L0_8x4`/`P_L0_4x8`/
`P_L0_4x4` (finer-than-8x8 splits within an 8x8 partition); CABAC +
sub-partitioned inter (CABAC P-slice decode remains `P_Skip`/`P_L0_16x16`
only, see "Pixel decode: CABAC + P-slice (inter)" above); B-slices;
sub-partitioned inter ENCODE (`h264.encode` remains `P_Skip`/`P_L0_16x16`-
only on the encode side); and everything else every other P-slice scope
note in this README already excludes (multiple reference frames, weighted
prediction, reference-list reordering, adaptive/MMCO reference marking).

**Validated bit-exact (no tolerance) — all 3 fixtures HAND-AUTHORED**
(real encoders were not found to reliably emit these specific mb_types/
sub_mb_type combinations on demand, and even when they do there is no way
to CONTROL which one comes out for a targeted regression test — same
methodology as `p-16x16-mb0-realac.h264` above, see
`test/h264/decode_p_slice_subpartition_test.cljk`'s own docstring for the
full rationale and why this remains a genuine independent-decoder
cross-check rather than a self-consistency tautology):
- **`p-16x8-mb0.h264`** — single 16x16 macroblock, `P_L0_L0_16x8`, zero
  residual, DIFFERENT top/bottom partition motion vectors — the bottom
  partition's own predictor is derived entirely from the top partition's
  OWN already-decided motion vector (no other neighbor exists), the most
  basic exercise of the new same-macroblock quadrant-lookup machinery.
- **`p-8x16-mb0-realac.h264`** — single 16x16 macroblock, `P_L0_L0_8x16`,
  REAL nonzero luma AC residual in one 8x8 quadrant (mirrors
  `p-16x16-mb0-realac.h264`'s own single-nonzero-block recipe), DIFFERENT
  left/right partition motion vectors — exercises the 8x16-specific
  "use C directly" special case's FALLBACK-to-median path (no topright
  macroblock exists here).
- **`p-8x8-cross-mb-multimb.h264`** — 32x16 (2 macroblocks): MB0 = `P_8x8`
  (`sub_mb_type` `P_L0_8x8` x4) with 4 DIFFERENT per-quadrant motion
  vectors plus real residual; MB1 = plain `P_L0_16x16`. THE direct
  regression test for the neighbor-derivation generalization above: MB1's
  own predictor must read MB0's TR quadrant SPECIFICALLY — a wrong
  quadrant read (e.g. the OLD flat-per-MB read, or any other quadrant)
  would produce a visibly different, ffmpeg-mismatching final motion
  vector, so the bit-exact match is a genuine discriminating proof, not
  an incidental pass. Real 2-D Cb/Cr gradient IDR reference (not flat)
  exercises per-quadrant CHROMA motion-compensated placement too.

Additionally, `test/h264/decode_p_slice_subpartition_test.cljk` covers 2
explicit throw tests (`mb_type` 4/`P_8x8ref0`, and `P_8x8` with an
unsupported `sub_mb_type`), matching this repo's existing
throw-on-unsupported-syntax discipline (see `h264.decode-test`'s
`i16x16-mb-info` throw tests for the established convention).

## Sub-pel motion compensation (`h264.interp`, Migration step 7's sub-pel increment)

`h264.interp` implements real luma quarter-sample (§8.4.2.2.1) and chroma
eighth-sample (§8.4.2.2.2) interpolation, wired into `h264.decode/mc-predict`
so P-slice motion compensation now handles ANY motion vector — this is the
direct successor to the MV=(0,0)-only increment above, and the reason
`decode-p-skip-macroblock!`/`decode-inter-16x16-macroblock!` no longer
throw on a non-zero derived motion vector.

**What's implemented:**
- **Luma quarter-sample interpolation** (`quarter-pel-luma`): the 6-tap FIR
  filter `(1,-5,20,20,-5,1)` for the 3 half-sample positions (`b`
  horizontal, `h` vertical, `j` center), then plain rounded 2-way averaging
  (`(a+b+1)>>1`) for all 12 quarter-sample positions — covers all 16
  `(fx,fy)` fractional combinations (§8.4.2.2.1 Figure 8-4's full naming).
  The center position `j` is the two-pass case that's easy to get subtly
  wrong (see below): it is the vertical 6-tap filter applied to the
  UNROUNDED, UNCLIPPED horizontal 6-tap sums at 6 rows, rounded ONCE at the
  end via `(sum+512)>>10` — NOT independent horizontal-then-vertical
  rounding/clipping.
- **Chroma eighth-sample bilinear interpolation** (`eighth-pel-chroma`):
  weights `A=(8-x)(8-y) B=x(8-y) C=(8-x)y D=xy` over the 2x2 integer-chroma
  neighborhood, `(A·p00+B·p01+C·p10+D·p11+32)>>6` — for ChromaArrayType 1
  (4:2:0), the chroma motion vector in eighth-CHROMA-sample units is
  numerically IDENTICAL to the luma motion vector in quarter-LUMA-sample
  units (chroma sample spacing is exactly 2x luma's, which exactly cancels
  the 2x unit-scale difference — see `h264.interp/mc-chroma-block`'s
  docstring), so no additional per-component MV scaling/derivation step is
  needed beyond reinterpreting the SAME integer mv components.
- **Picture-boundary extension**: reference samples outside the decoded
  picture (needed both for the 6-tap filter's own ±2/+3 reach near picture
  edges and for large motion vectors) are clamped to the nearest boundary
  sample, per §8.4.2.2.1.
- **Cross-checked against FFmpeg's actual reference-decoder source**
  (`libavcodec/h264qpel_template.c`/`h264chroma_template.c`,
  https://github.com/FFmpeg/FFmpeg), matching this repo's existing
  discipline in `h264.quant`/`h264.transform` — NOT reconstructed from
  memory of the spec prose alone. This mattered in practice: the classic
  pitfall here is rounding/clipping the horizontal and vertical passes of
  the center position `j` independently instead of carrying the
  unrounded, unclipped intermediate sums through both passes and rounding
  once — `h264.interp/center-j`'s docstring spells out exactly why the
  two are NOT equivalent (they are, in fact, mathematically identical as
  long as no intermediate rounding is introduced — the bug is introducing
  rounding where the reference implementation doesn't).

**Validation.** `test/h264/decode_p_subpel_test.cljk` covers 3 golden
vectors, all bit-exact (no tolerance) against real `ffmpeg 8.1.1`, plus
`test/h264/interp_test.cljk` unit-tests the interpolation arithmetic
directly (hand-computed 6-tap/bilinear values, flat-plane invariance under
every one of the 16 luma / 64 chroma fractional combinations, and
picture-boundary clamping) independent of the bitstream machinery:
- **`p-subpel-vertical64.h264`/`p-subpel-horizontal64.h264`** — REAL
  libx264 (Constrained Baseline, CAVLC) 2-frame (IDR + P) streams: a
  64x64 sinusoid varying smoothly along ONE axis only (so the IDR
  reference frame stays within Intra_16x16 DC/Vertical/Horizontal, no
  Intra_4x4/luma-Plane — see `horizontal-multimb64.h264` above for the
  same forcing trick), whose phase shifts by a fractional (1.25px) amount
  per frame — genuine temporal sub-pel motion, not merely re-evaluated
  per-frame content. Real libx264 motion estimation (default `--subme`,
  NOT `--subme 0`/`--preset ultrafast`, which would force full-pel-only
  search) independently finds real quarter-pel motion vectors: `[0 -5]`/
  `[0 -7]`/`[0 -9]` (vertical fixture) and `[-5 0]`/`[-7 0]` (horizontal
  fixture) — every value intentionally NOT a multiple of 4, i.e. genuinely
  fractional. Both fixtures mix real P_Skip (with a non-zero PREDICTED
  motion vector — the first real-encoder evidence this repo's `p-skip-mv`
  predictor path is correct for a non-zero case, not just the MV=(0,0)
  case `p-skip-flat16.h264` already covered) and real P_L0_16x16
  macroblocks.
- **`p-subpel-diagonal32.h264`** — HAND-AUTHORED (this repo's OWN
  `h264.encode` for a REAL, non-flat 2-D gradient IDR reference frame, plus
  a hand-built P-slice NAL via `h264.expgolomb`'s writer — same methodology
  as `p-16x16-mb0-realac.h264` above): real libx264, even with the
  single-axis forcing trick, was not observed to select a genuinely 2-D
  (both fx AND fy fractional) motion vector while also keeping every
  P-frame macroblock free of luma Plane-mode intra coding (a real 2-axis
  test image pushes some P-frame macroblocks to Plane, which this decoder
  doesn't implement for luma). This fixture's 2 macroblocks carry motion
  vectors `[6 10]` (fx=2,fy=2 — the CENTER `j` position, the single
  hardest case) and `[13 7]` (fx=1,fy=3 — an "average of two half-samples"
  position), both with zero residual (isolating pure motion compensation).
  Independent check: real ffmpeg decodes these exact hand-authored bytes
  bit-exact, with no `corrupted macroblock`/`error while decoding`
  messages.

Together these 3 fixtures (plus the 3 from the original MV=(0,0)
increment) exercise every distinct arithmetic branch of
`quarter-pel-luma`'s 16-way fractional dispatch at least once: plain
integer position, the 3 half-sample positions (`b`/`h`/`j`), "average of
integer + half-sample" (from the real single-axis fixtures), and "average
of two half-samples" (from the hand-authored diagonal fixture) — not
exhaustively all 16 `(fx,fy)` combinations individually, but every
DISTINCT code path in the implementation.

## Pixel encode (Wave 5, ADR-2607122000 Migration step 8 + chroma-encode follow-up)

`h264.encode/encode-idr-luma-frame` encodes raw luma AND chroma (Cb/Cr)
planes to a real H.264 Annex B elementary stream: quantization → forward
transform → CAVLC → simplified mode decision, the encode-side counterpart
of `h264.decode`'s Phase 1/"R0.5" decoder. Same non-realtime,
correctness-first reference tier. Initially shipped LUMA ONLY (Migration
step 8); chroma (Cb/Cr) DC+AC encode was added as a follow-up (see below).

**Scope, deliberately narrow (be aware before assuming this encodes
arbitrary images):**
- Single IDR I-slice, `mb_type` fixed to Intra_16x16 (matches `h264.decode`'s
  own decode scope exactly).
- **LUMA AND CHROMA (Cb/Cr), ChromaArrayType 1 (4:2:0) only.** Real chroma
  DC (2x2 Hadamard, `nC==-1` special CAVLC table) and chroma AC (regular
  neighbor-derived 4x4 blocks, QPc-scaled) residual is encoded from the
  actual `:cb`/`:cr` source planes passed to `encode-idr-luma-frame` —
  decoded Cb/Cr planes are a real (lossy, quantization-bounded)
  reconstruction of the source's chroma content. `:cb`/`:cr` are OPTIONAL:
  when omitted, they default to flat 128-valued planes, which (since DC
  prediction against a locally-constant 128 source always gives zero
  residual) preserves the ORIGINAL luma-only encoder's exact call
  shape/behavior for existing callers (`CodedBlockPatternChroma`
  degenerates to 0, no chroma bits beyond that declaration — same as
  before this addition).
- **Chroma intra prediction mode decision: DC/Horizontal/Vertical only**
  (Table 8-5 numbering) — no Plane (mode 3), even though `h264.decode`'s
  chroma path DOES implement Plane (a real encoder, libx264, was observed
  selecting it even for near-flat content — see `h264.intra-pred`'s
  docstring). This simplified reference encoder never emits
  `intra_chroma_pred_mode`=3. `intra_chroma_pred_mode` is a SINGLE syntax
  element shared by both Cb and Cr (§7.3.5.1) — mode decision jointly
  minimizes COMBINED Cb+Cr SAD, not per-component.
- **Simplified mode decision**: for each macroblock, DC/Vertical/Horizontal
  Intra_16x16 prediction (whichever are legal given neighbor availability)
  are each tried and the SAD-minimizing one is chosen. No Plane mode, no
  RDO (rate-distortion optimization).
- **Constant QP across the whole frame** (`mb_qp_delta` always 0). QPc
  (`h264.quant/chroma-qp`, from PPS `chroma_qp_index_offset`) is therefore
  ALSO constant across the whole frame, computed once per frame from the
  constant QPy.
- `CodedBlockPatternLuma` is 0 (DC-only) if every block's AC-quantized
  levels are all zero, else 15 (full AC for all 16 4x4 blocks).
- `CodedBlockPatternChroma` is 0 (no chroma residual at all) if BOTH
  components' quantized DC levels are all zero, 1 (DC only) if some DC
  level is nonzero but no AC level is, else 2 (DC+AC) — mirrors
  `h264.decode/i16x16-mb-info`'s three real values.

**Quantizer design — NOT a memorized textbook MF table.** H.264's
encoder-side forward quantization is explicitly non-normative (only the
decoder's dequant + inverse transform is spec-normative). Rather than trust
a memorized "MF table" (empirically found, via probe scripts during this
task's development, to leave measurably MORE cross-coefficient leakage
—~20%— than this pipeline's own inherent ~2% non-orthogonality), the AC
quantizer (`h264.encode/solve-ac-levels`) solves the EXACT least-squares
inverse of this repo's own already bit-exact-vs-real-ffmpeg-tested
`h264.quant/ac-qmul` + `h264.transform/inverse-4x4` pipeline, via exact
Gauss-Jordan elimination over the probed 16x16 "level→pixel" matrix — this
pipeline is IDENTICAL for luma and chroma AC (only the QP input differs,
QPy vs QPc), so `solve-ac-levels` is reused UNCHANGED for chroma, no
separate chroma AC solver needed. The Intra16x16 luma-DC (Hadamard) path is
handled analogously — `h264.transform/forward-luma-dc-hadamard` is the
exact derived linear inverse of the tested `luma-dc-hadamard`
(`H·Hᵀ=16·I`, verified in `transform_test.clj`), not a hand-derived
formula. The chroma-DC (2x2 Hadamard) path mirrors this EXACTLY:
`h264.transform/forward-chroma-dc-hadamard` is the exact derived linear
inverse of the tested `chroma-dc-hadamard`, derived from a 4x4 Sylvester
Hadamard matrix `H4` (empirically probed against the real, tested
`chroma-dc-hadamard` via unit impulses, NOT hand-derived) satisfying
`H4·H4ᵀ=4·I` (also verified in `transform_test.clj`). `h264.transform/forward-4x4`
(a textbook forward-transform butterfly) exists for API symmetry with
`inverse-4x4` and for DC-term extraction (`forward-4x4(block)[0][0]` = sum
of samples, a property true for any correct forward transform's DC term),
but is NOT used for AC quantization — see its own docstring.

CAVLC encode (`h264.cavlc/encode-residual-block!`) reuses the existing
decode-side VLC tables as reverse lookups, plus a mechanically-derived
inverse of the level_prefix/level_suffix/suffix_length state machine
(`h264.cavlc/encode-level!`) — this same fn was ALREADY generic over the
`:chroma-dc` nC selector from its original (luma-only-caller) Migration
step 8 implementation, so no new CAVLC encode code was needed for chroma;
`h264.encode` just calls it with `:chroma-dc`/chroma AC's regular
neighbor-derived `nc` where the luma-only caller never did. Slice-header
encode is `h264.slice/encode-header!`, symmetric with `parse-header!`.

**Validation.** `test/h264/encode_test.cljk` covers:
- Round-trip through this repo's own decoder (flat/gradient, single- and
  multi-macroblock, various QP; luma AND chroma) — bit-exact for flat
  content, small bounded error for real AC content.
- Luma-only fixtures (Migration step 8): `encode-mb0-realac.h264` (single
  macroblock, real nonzero AC residual), `encode-flat32-multimb.h264`
  (32x32, 2x2 macroblocks, flat — multi-macroblock intra-prediction
  chaining without AC residual), and `encode-multimb-realac.h264` (32x32,
  2x2 macroblocks, a real 2-D oscillating luma pattern giving real AC
  residual in every macroblock, real cross-macroblock CAVLC neighbor
  derivation for both AC blocks and the Intra16x16 luma-DC block, and
  Horizontal prediction actually selected for 2 of the 4 macroblocks).
- Chroma fixtures (chroma-encode follow-up), all generated by `h264.encode`
  and independently verified (2026-07, ffmpeg 8.1.1) to be decoded
  **bit-exact by real ffmpeg**, with no `corrupted macroblock`/`error while
  decoding` messages: `encode-mb0-chroma-realac.h264` (single macroblock,
  real DISTINCT per-component Cb/Cr gradients plus real luma AC — Cb varies
  by column, Cr by row, cross-checking Cb/Cr aren't accidentally swapped),
  `encode-multimb-chroma-realac.h264` (32x32, 2x2 macroblocks, flat luma,
  real 2-D oscillating `sin`/`cos` Cb/Cr pattern giving real chroma DC+AC
  residual in every macroblock, real cross-macroblock chroma CAVLC neighbor
  derivation, and 3 distinct Intra_Chroma modes actually selected —
  `[0 1 2 0]`, DC/Horizontal/Vertical/DC — the strongest chroma-encode
  interoperability evidence here), and `encode-multimb-chroma-dconly.h264`
  (32x32, flat-but-nonzero Cb=150/Cr=180 chroma, no AC anywhere —
  exercises `CodedBlockPatternChroma`=1, reproducing the exact uniform
  source value in every pixel).

**Development-time note, kept for traceability.** While building the
ORIGINAL luma-only encoder against the west pin current at the time, two
apparent decode-side gaps surfaced (a macroblock whose neighbor had real AC
residual failed to decode correctly; a single macroblock whose own AC
pushed the neighbor-derived nC to 2 or higher also failed). Both turned out
to be manifestations of the SAME two bugs `h264.decode`/`h264.transform`
had JUST been fixed for upstream in this repo's own history (commit
`14e72ea`, "resolve luma Horizontal multi-macroblock CAVLC desync":
`blk->col-row` was a transposed/wrong block-index mapping, and
`luma-dc-hadamard` was missing an internal transpose — see those two
defs' own docstrings). After syncing to the fixed `h264.decode` and fixing
this encoder's OWN `dc-nc` derivation (`h264.encode/encode-macroblock!`
had the SAME `:dc-nnz`-vs-`:ac-nnz` bug the upstream fix corrected on the
decode side), every previously-failing case — including the original
complex multi-macroblock/real-AC/Horizontal-prediction test image —
decodes bit-exact via real ffmpeg. No known decode-side gap remains open
as of the luma-only encoder's test suite, and the chroma-encode follow-up
above needed no further decode-side fixes (the existing chroma decode path,
already bit-exact-vs-ffmpeg-tested from the earlier chroma-decode work, was
reused unchanged as the mathematical basis for deriving the chroma
encode-side quantizer).

## Pixel encode: P-slice (inter) (Wave 7, ADR-2607122000 Migration step 7's
encode-side counterpart)

`h264.encode/encode-gop` encodes a whole GOP (one IDR I-frame — via the
existing `encode-idr-luma-frame` Intra_16x16 encoder above — followed by
zero or more P-frames) to a single Annex B elementary stream — the
encode-side counterpart of `h264.decode/decode-gop`'s P_Skip/P_L0_16x16
decode support. Same non-realtime, correctness-first reference tier as
every other encode/decode path in this repo.

**What's implemented:**
- **Motion estimation**: integer-pel full search (`me-full-search`, default
  ±8 pixels, configurable via `encode-gop`'s `search-range`) minimizing
  luma SAD, scored against `h264.interp/mc-luma-block` — the SAME sub-pel-
  capable interpolation the decoder uses, not a separate approximation —
  followed by a small quarter-pel LOCAL refinement (`me-subpel-refine`, ±3
  quarter-samples around the best integer position). **Real sub-pel
  (half/quarter-pel) motion vectors ARE found and encoded** when they
  reduce SAD (see the `p-slice-l0-16x16-shift32` fixture below), not just a
  documented gap — this is not integer-pel-only. Not a claim of realtime-
  encoder-grade search (real encoders use hierarchical/diamond search, RDO
  lambda, multiple candidate predictors); this is the "簡易" (simplified)
  search this task's own scope allows.
- **P_Skip mode decision**: for each macroblock, the §8.4.1.1 P_Skip
  predictor motion vector (`p-skip-mv`, the SAME predictor
  `h264.decode/p-skip-mv` uses) is scored first — if it already gives
  EXACT (zero-SAD) luma prediction against the source, P_Skip is chosen
  (no bits beyond `mb_skip_run` bookkeeping). Otherwise, the full
  search + sub-pel refinement above finds a real motion vector and the
  macroblock is coded as P_L0_16x16 with real residual. This is a much
  simpler rule than a real encoder's full RD mode decision (which would
  also skip for small-but-nonzero residual, trading a little quality for
  bits) — see `h264.encode/encode-p-slice-mbs!`'s docstring.
- **P_L0_16x16 encode**: `mvd_l0` (2 se(v), the chosen motion vector minus
  the SAME §8.4.1.3 median predictor (`mv-predict-16x16`) the decoder
  reconstructs — getting this predictor wrong would silently decode to a
  DIFFERENT final motion vector than the one this encoder's own search
  chose), `coded_block_pattern` (me(v) via an exact reverse lookup of
  `h264.decode/golomb-to-inter-cbp`, always present for this mb_type),
  `mb_qp_delta` (only if any residual, constant QP → always 0), luma
  residual as 16 FULL 4x4 "regular" blocks (`solve-regular-levels`/
  `regular-dequant-raster` — the SAME exact-least-squares-inverse
  methodology `solve-ac-levels` uses for Intra16x16 AC, but WITHOUT
  excluding the DC (raster position 0) column, since an inter 4x4 block has
  no separate macroblock-level DC/Hadamard split — see
  `h264.decode/decode-regular-block!`'s own docstring for why), gated
  per-8x8-quadrant by `cbp-luma`'s 4 bits (mirroring
  `golomb-to-inter-cbp`'s Table 9-4 Inter-column CBP semantics exactly).
- **Chroma residual is UNCHANGED from the intra path** — `chroma-component-plan`/
  `encode-chroma-ac-blocks!` (this namespace's existing Intra_Chroma DC/AC
  quantization + CAVLC helpers) are reused VERBATIM for inter macroblocks,
  just fed a motion-compensated (not intra) prediction as the residual's
  base — matches `h264.decode`'s own "chroma residual structure doesn't
  depend on the luma macroblock type at all" design.
- **P-slice header encode**: `h264.slice/encode-p-header!`, the exact
  P-slice counterpart of `encode-header!` (I-slice) — `slice_type`=5 (all
  P), non-IDR (no `idr_pic_id`), `num_ref_idx_active_override_flag`=false
  (relies on the PPS's own default active count, 1 — `h264.pps/encode`'s
  default — exactly this repo's single-reference-frame requirement, so no
  override is ever needed), no reference-list reordering, no weighted
  prediction, `adaptive_ref_pic_marking_mode_flag`=false when
  `nal_ref_idc`≠0 (no MMCO).

**What's explicitly NOT implemented** (out of scope, not silently wrong):
CABAC (unchanged from every other scope note in this README), B-slices,
multiple reference frames / a real DPB, reference-list reordering,
weighted prediction, `P_L0_L0_16x8`/`P_L0_L0_8x16`/`P_8x8`/`P_8x8ref0`
(sub-partitioned motion — this encoder only ever emits ONE 16x16
partition/one motion vector per inter macroblock, matching
`h264.decode`'s own decode-side scope), and intra-in-P macroblocks on
ENCODE (this simplified mode decision never falls back to intra for a
P-frame macroblock — motion estimation always finds SOME candidate,
so there's no RD reason to, even though `h264.decode` CAN decode a
P-slice's intra-coded macroblocks if a real encoder emitted one).
Multi-frame GOPs (more than 2 pictures) work mechanically (`encode-gop`
threads each P-frame's own reconstruction forward as the NEXT P-frame's
single reference, mirroring `h264.decode/decode-gop`'s "always the
immediately preceding decoded picture" design) but are only exercised here
by the 2-frame (IDR+P) fixtures below.

**Validation.** `test/h264/encode_p_slice_test.cljk` covers both round-trip
(fast, own-decoder-only) tests AND fixed real-ffmpeg-validated fixtures,
mirroring `h264.encode-test`'s own two-tier discipline:
1. **`p-skip-flat-roundtrip-bit-exact`** — two IDENTICAL flat 32x32 frames:
   the encoder chooses P_Skip for EVERY macroblock (flat content's IDR
   reconstruction is provably bit-exact at any QP, so the P_Skip
   predictor's zero-SAD condition is guaranteed to trigger), and the
   P-frame reconstructs bit-exact to the source.
2. **`p-l0-16x16-real-motion-roundtrip-bounded-error`** — a real 2-D
   gradient IDR frame followed by a P-frame that's the SAME content
   genuinely translated (a real pixel-domain 2px horizontal shift, wrapped,
   not re-evaluated per-frame noise): the encoder finds a REAL nonzero
   motion vector for at least one macroblock (a 2px shift does not leave
   the skip predictor's zero-SAD condition satisfied against a lossy IDR
   reference) and average per-pixel luma reconstruction error against the
   TRUE (lossless) translated source stays under 3.
3. **`p-slice-skip-flat32.h264`** / **`p-slice-l0-16x16-shift32.h264`** —
   fixtures generated by `encode-gop` from exactly the same two recipes
   above and independently verified (2026-07, ffmpeg 8.1.1) to decode with
   **0 decode errors**, no `corrupted macroblock`/`error while decoding`
   messages:
   ```sh
   ffmpeg -v error -i p-slice-skip-flat32.h264 -pix_fmt yuv420p out.yuv
   ffmpeg -v error -i p-slice-l0-16x16-shift32.h264 -pix_fmt yuv420p out.yuv
   ```
   Both `.ref.yuv` files (checked in alongside the `.h264` fixtures) are
   bit-exact against THIS repo's own `h264.decode/decode-gop` output for
   BOTH frames, luma AND chroma — `p-slice-l0-16x16-shift32` in particular
   is the strongest interoperability evidence here: a real 2px translation,
   encoded by this repo's own motion-estimation search into a genuinely
   nonzero P_L0_16x16 motion vector plus real CAVLC-coded residual, decoded
   bit-exact by an INDEPENDENT real decoder that never saw or trusted
   anything about how these bytes were constructed.

`test/h264/slice_test.cljk` additionally round-trips `encode-p-header!`
against the real, already-tested `parse-header!` (both `nal_ref_idc`=0 and
nonzero cases, and the deblocking-field-absent case), the same discipline
`encode-header-roundtrips` already used for the I-slice header.

## Table-driven syntax (`h264.syntax`, ADR-2608290100)

ISO/IEC 14496-10 §7.3 prints H.264's bitstream syntax as a **table**: rows of
(element name, descriptor, presence condition), where the descriptors are
`u(n)`, `ue(v)`, `se(v)`, `f(n)`, `ae(v)`. `h264.syntax` tests whether that
table can be *data* — one generic reader interpreting an EDN transcription, so
that a new bitstream structure costs one EDN file instead of one hand-written
parser.

`resources/h264/syntax/sps.edn` is §7.3.2.1.1 `seq_parameter_set_data( )`
transcribed as 29 descriptor rows. The seven `constraint_setN_flag` /
`reserved_zero_2bits` rows are written the way the standard writes them rather
than as the incumbent's single `u(8)` shortcut — and consume the same eight
bits.

**Nothing here replaces anything.** `h264.sps`, `h264.pps` and `h264.slice`
are unchanged and remain the shipping parsers; they pass real golden-vector
tests against ffmpeg output. `h264.sps-table` exists so the design can be
judged on evidence, and `test/h264/syntax_equivalence_test.cljk` is that
evidence: it asserts the table-driven parse equals `h264.sps/parse`, whole map,
on 27 SPS NALs across every fixture in the repo, on 90 SPSs spanning
everything `h264.sps/encode` can produce, and on synthetic streams written
bit-by-bit that reach paths the incumbent's own tests never do — high-profile
scaling lists (both the run-to-completion and the `nextScale`-reaches-zero
early-exit branch), `chroma_format_idc` 3 with twelve lists,
`pic_order_cnt_type` 1 with its `num_ref_frames_in_pic_order_cnt_cycle` loop,
interlaced `mb_adaptive_frame_field_flag`, and cropping in every direction.
For the synthetic cases the test also pins that the reader stopped at *exactly*
the bit the writer stopped at.

### How much of a hand-written parser is actually a table?

Measured line by line across `h264.sps/parse`, `h264.sps/skip-scaling-list!`,
`h264.pps/parse` and `h264.slice/parse-header!`
(`docs/measurement/syntax-table-compression.edn` carries the per-line
assignment so the ratio is re-checkable):

| | lines | share |
|---|---|---|
| direct §7.3 syntax-table transcription | 79 | 52.0% |
| reader scaffolding the generic reader subsumes | 16 | 10.5% |
| genuine logic | 57 | 37.5% |

and the 57 lines of genuine logic divide as **31 output-map / API renaming**,
**15 deliberate scope refusals** (`throw` on MMCO, weighted prediction, FMO,
reference-list reordering) and only **11 §7.4 derivations** — SubWidthC /
CropUnitX / width / height, the Table 7-6 `slice_type` mod-5 collapse, and
`scaling_list( )`'s `lastScale`/`nextScale` state machine.

The qualification matters as much as the ratio: these three namespaces are 490
of `src/h264`'s 6,454 lines. The other 5,964 are §8 reconstruction and §9
entropy coding — `decode.cljc` has 14 raw Exp-Golomb read sites in 1,683 lines
against 28 CABAC call sites. Within one codec the compression is real but
narrow; its value is across codecs, because the header parser is the part every
new codec must write from scratch.

### What the format cannot express

Stated as limits, not as future work, and **enforced** rather than merely
documented (each has a test):

- **`ae(v)`.** An arithmetic-coded element's bit cost depends on adaptive
  context state that depends on every previously decoded element. No
  (name, descriptor, condition) triple determines it. `[:unsupported :ae]` is
  the only honest row, and reaching it throws.
- **Spec sub-structures whose body contains assignments rather than descriptor
  rows.** §7.3.2.1.1.1 `scaling_list( )` is the canonical case — the loop's
  continuation depends on a running value the loop computes. Those take
  `[:escape]`, and `h264.sps-table/scaling-list-escape` is eight lines of
  ordinary code, labelled as such.
- **§7.4 derivations** beyond a plain inferred constant.
- **`more_rbsp_data()`-gated tails**, which need the RBSP's exact trailing-bit
  position.
- **Byte-offset arithmetic, little-endian fields, and length-prefixed recursive
  containers** — which is why this format reaches AV1's `sequence_header` /
  `frame_header` but not ISOBMFF's or RIFF's box trees.

A `[:var]` on an element that has not been read **throws** rather than seeing
`nil`, and a presence condition that does not evaluate to a strict boolean is
**rejected** rather than silently taking the `0` branch as true — H.264 flags
are `0`/`1` ints, so `[:= [:var :some_flag] 1]` is required.

Full design, the measurement, the three deliberate breakages that show the
equivalence test fails for the reason it names, and the reach estimate across
this ecosystem's other spec repos: `docs/adr/2608290100-table-driven-bitstream-syntax.edn`.

## A residual kernel that runs with no JVM under it

The decoder above is full Clojure on the JVM. This section is one vertical
slice of it that is not: `src/h264/transform.kotoba` and
`src/h264/quant.kotoba` are compiled by `bin/amu` and executed, on real
fixture data, with `java`, `javac`, `clojure` and `clj` shadowed out of `PATH`
by stubs that exit 127.

The `.cljc` decoder is untouched and remains authoritative. The `.kotoba`
kernels sit beside it with an equivalence corpus, exactly as
`src/h264/syntax.kotoba` sits beside `syntax.cljc`.

### What is in the kernel, and why it is 1-D

`h264.transform` (Kotoba) exports H.264 §8.5.12.2's **1-D inverse integer
butterfly** — `idct4-1d`, plus `idct4-1d-dc` (same butterfly with the +32 DC
bias folded in) and `idct4-1d-scaled` (same butterfly with the final `>>6`
folded in) — and `dc-only-sample`. `h264.quant` (Kotoba) exports the whole
§8.5.9 dequant chain: `group-idx`, `level-scale`, `ac-qmul`, `dc-qmul`,
`dequant-ac`, and §8.5.8's `chroma-qp`.

The exported unit is the 1-D operator rather than `inverse-4x4` because
sixteen coefficients cannot cross an exported boundary at all today. A
`:vector-i64` parameter is rejected by the native backends; sixteen scalar
parameters exceed `guest-grammar.edn`'s `:max-parameters 5`. That is a real
constraint, not a workaround: H.264's 2-D inverse transform is *separable* and
is defined as two passes of exactly this 1-D operator, so the 1-D operator is
the spec's own primitive. The host performs the eight calls and the index
permutation and performs **no arithmetic of its own** — the DC bias and the
final shift live inside the kernel, which is why those two variants exist.

The composition is written once, in `scripts/kotoba_kernel_common.cljk`, and
all three executions drive it.

### What actually ran, and what it agreed with

| path | how it runs | JVM? | result |
|---|---|---|---|
| reference | `kotoba.kir/execute`, the language's own interpreter, under nbb | no | 9,540 values compared, 0 mismatches |
| wasm | the emitted `wasm32` modules, instantiated by node | no | 9,540 values compared, 0 mismatches |
| native | the emitted `aarch64` machine code, extracted by symbol and run through amu's W^X kexe loader | no | 8 real blocks, 128 residual samples, 0 mismatches |

All three drive the same composition and are compared against the same
`.cljc`-derived expectations, so they are held to one answer rather than to
each other. `java`, `javac`, `clojure` and `clj` were shadowed by exit-127
stubs throughout, and the marker file they write was never created.

The native figure is small for a mechanical reason and not a hedged one: the
kexe loader takes one call per process, so 317 blocks × 32 calls is not a
thing you run, and the eight are *chosen* — largest magnitude, most negative
coefficients, DC-only, all-zero, plus the head of the list — rather than
whatever came first.

**The native path is currently blocked, and the block is a regression in the
compiler rather than in this kernel.** The native result above was taken at
amu `02c7e57`. amu has since advanced to `0df9d99`, and at that revision
`extract-native` rejects *both* kernels with
`:kotoba/verification-failed "native export table rejected"` — including the
transform module that had extracted and executed cleanly one revision earlier.
`scripts/verify-kotoba-kernel.cljk --native` therefore reports
`NATIVE-aarch64-transform` and `NATIVE-aarch64-quant` as UNVERIFIED and exits
3 today. It reports them; it does not count them as passes.

The emitted `wasm32` modules declare **zero host imports** — 676 bytes for
`transform`, 1,336 for `quant` — and the verifier fails the run if that ever
stops being true. That is the payoff of keeping every export scalar: a
`:vector-i64` or record parameter compiles for wasm too, but pulls in the
45-function `kotoba:typed` import surface, and the module stops being
self-contained.

The two entrypoints agree byte for byte: compiling `transform.kotoba` to
`wasm32` through the JVM CLI and through `bin/amu`'s JDK-free path at the same
amu revision produces the identical 676-byte module, and the two give the same
answers when run.

The oracle is `resources/h264/kotoba-vectors/kernel-vectors.edn`. Every
expectation in it was produced by *this repo's `.cljc` decoder*, and every
inverse-transform input is a coefficient block the decoder actually passed to
`inverse-4x4` while decoding the real libx264 fixtures — `i4x4-mandel64`,
`gradient16-ac`, `chroma-multimb32`, `horizontal-multimb64`,
`flat16-dc-only`. Nobody invented an input. 317 distinct blocks: 189 with more
than four non-zero coefficients, 287 containing negative coefficients,
coefficients up to 3,584 in magnitude.

```sh
kbb --backend sci --classpath scripts scripts/verify-kotoba-kernel.cljk --amu <amu-checkout>
kbb --backend sci --classpath scripts scripts/verify-kotoba-kernel.cljk --amu <amu-checkout> --native
```

Exit 0 is a clean pass, 1 is a mismatch, and **3 is UNVERIFIED** — a path that
could not be run at all, or an evidence floor that was not met. A check that
could not run must not return the same value as one that ran clean.

`scripts/verify-kotoba-kernel-controls.cljk` is what makes the comparison
worth running. It breaks the guest kernels one edit at a time in a throwaway
copy of the tree — a truncating division where H.264 wants an arithmetic
shift, a wrong `+32` rounding bias, a dropped `>>1` inside the butterfly, one
wrong digit of the `normAdjust4x4` table — and requires the verifier to reject
each broken copy *in the group the edit is in*. That last clause earned its
place: the first run of the controls reported one of them as unproven, because
the verifier printed only its first three sample failures and the broken table
happened to fail `level-scale` three times before it reached `ac-qmul`. The
verifier now prints a `FAILING-GROUPS` line carrying every failing group.

`test/h264/kotoba_kernel_vectors_test.cljk` is the other half. The verifier has
no JVM, so it cannot ask the decoder anything; it can only compare against a
file. That test is what makes the file worth comparing against: it re-derives
every expectation from the current `.cljc` code, re-decodes the fixtures to
prove every recorded coefficient block really came out of a bitstream, and
refuses a corpus too degenerate to discriminate (it requires blocks with real
AC content, blocks with negative coefficients, and coefficients large enough to
exercise both butterfly stages — a corpus of flat blocks would pass an inverse
transform that ignored every AC coefficient, and a corpus with no negatives
would pass a truncating division in place of H.264's arithmetic right shift).

### What this proves, and what it does not

It proves the path is open: a real, bit-exactness-critical piece of H.264
decode arithmetic, written in guest grammar, compiles through the JDK-free
front door to both Wasm and native machine code, executes with no JVM
underneath it, and agrees with the JVM decoder on data that came out of a real
bitstream.

It does not make the decoder JVM-free, and the gap is not small. A profile of
this decoder — taken previously, and *not* re-measured by this work, so treat
the three figures as the order of magnitude they are — attributes about 78% of
leaf samples to Clojure persistent-collection machinery and about 85% of
decoder-attributed samples to picture assembly and residual addition. **The
transform is 3.4%.** What remains is precisely the part this kernel's shape
cannot yet reach: picture assembly moves planes, and
a plane is bulk data, which is what the guest value model has no carrier for.
A 256×256 luma plane exactly exhausts the native arena; 1920×1080 exceeds it
thirtyfold. Closing the rest is a value-model problem, not a translation
problem.

### Compiler blockers met on the way

Minimal reproductions, with exact invocations, exit codes and full diagnostic
maps, are checked in under `test/h264/kotoba-compiler-repro/`
(`reproductions.edn` is the index, and it names which amu answered each one —
amu moved from `02c7e57` to `0df9d99` while this work was in progress, so a
single revision number here would be wrong). In short:

- `bit-shift-left`, `bit-shift-right`, `unsigned-bit-shift-right`, `mod`,
  `rem`, `min`, `max` and `/` have **no admitted lowering**, though
  `guest-grammar.edn`'s `:admitted-builtins` lists all eight. `quot`,
  `bit-and`, `bit-or`, `bit-xor`, `inc`, `dec`, `cond` and `case` from the same
  set are admitted. H.264 is specified in arithmetic shifts, so every shift in
  these kernels is spelled as floor division or as multiplication by a power of
  two. Both are exact; both are commented, so that nobody "simplifies" them
  into `quot`, which truncates toward zero and would move every negative
  residual by one.
- `hetero-vector-at` **crashes the wasm emitter on the JDK-free entrypoint**
  (`:kotoba/internal-error`) on a four-line file that `amu check` accepts.
  Constructing the same tuple without reading it back compiles fine. At the
  same amu revision the JVM entrypoint compiles the crashing file with exit 0,
  so it is a defect on `bin/amu`'s path specifically and not a property of the
  language. This is why `expgolomb.kotoba`, whose every result is read with
  `hetero-vector-at`, has no wasm32 artifact.
- `extract-native` rejects with
  `:kotoba/verification-failed "native export table rejected"`. At `02c7e57`
  this hit `quant.kexe` only, for all six of its exports, while
  `transform.kexe` from the same run extracted all four of its own; at
  `0df9d99` it hits both. The verifier compares the artifact's stored export
  table against a re-emission of the artifact's own KIR, and re-emission is
  deterministic here (running the emitter twice gives the identical table),
  so the disagreement is between compile-time and verify-time emission. Three
  obvious shrink candidates — a self-recursive function, a long `cond` chain,
  one export calling another — do not reproduce it. This is the only reason
  the native column above is 128 samples rather than the whole corpus, and
  the only reason `--native` exits 3 today.
- The native backends reject a `:vector-i64` parameter and accept a
  **sixteen-field `:i64` record** in the same position, at arity 2. So a whole
  4x4 block *can* reach a native export; what it costs is the Wasm module's
  zero-import property. That trade, not the parameter limit, is the next real
  decision for widening this kernel.

## Test

```sh
kbb -M:test
```

## The guest-grammar reader does not pass `amu check` yet

`src/h264/syntax.kotoba` is the table-driven reader written in Kotoba guest
grammar, which is where it has to live for the design to reach a backend at
all — a reader written in full Clojure lands on the JVM permanently. It does
not yet clear the compiler's front door:

```
bin/amu check src/h264/syntax.kotoba   exit 65
  :kotoba.error/namespace-export-clause  line 2
  "only a bounded :export vector is admitted in a guest namespace"

bin/amu check src/h264/sps.kotoba      exit 65   same error
bin/amu check src/h264/expgolomb.kotoba exit 0   admitted, effects #{}
bin/amu check src/h264/rbsp.kotoba      exit 0   admitted, effects #{}
```

Measured 2026-08-30 against amu at `kotoba-lang/amu` tip. So of this repo's
four `.kotoba` namespaces, the two single-file ones are admitted and the two
carrying a `:require` are not. That is a front-door gap, not evidence about
the table design — but it does mean the `.cljc` reader is the only one that
runs today, and the `.kotoba` one is an unexecuted transcription until the
clause is admitted.

The equivalence test compares the `.cljc` reader against the hand-written
`h264.sps` parser, so the evidence for the design is real; the evidence that
this design reaches a backend is not yet.
