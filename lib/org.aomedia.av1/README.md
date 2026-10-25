# kotoba-lang/org-aomedia-av1

Zero-dep, mostly-portable `.cljc` AV1 (AOMedia Video 1, AV1 Bitstream &
Decoding Process Specification) bitstream **framing + symbol decoder
primitives**, pixel reconstruction (decode), and, as of 2026-07, a first
narrow-scope pixel **encoder** too (see the "Encode" section below --
`av1.bool-encoder` is JVM Clojure only, a documented exception to this
repo's usual `.cljc` portability). Named `org-aomedia-av1` (not
`org-iso-*`/`org-ietf-*`) because AV1 is published by the Alliance for
Open Media, not ISO/IEC or the IETF -- see `kotoba-lang/org-iso-h264`'s
README for the sibling naming rationale.

## Scope (Phase 0 + Phase 1, now with real pixel reconstruction)

This is **Phase 0/1** of AV1 support per `com-junkawasaki/root` ADR-2607122000
(`90-docs/adr/2607122000-utsushi-pixel-codec-r05-cljc-datomic.md`) Migration
step 9. Phase 0/1 started as the foundation layer *before* pixel
reconstruction (OBU/header/bool-decoder/partition-tree framing), mirroring
how `org-iso-h264` started with NAL/SPS/PPS framing before intra pixel
decode was added -- **this phase's continuation now adds that pixel
reconstruction**, at `org-iso-h264`'s equivalent first-pixel-decode
milestone: real bit-exact luma (and, per the chroma-decode extension below,
Cb/Cr) reconstruction against real encoded data, deliberately scoped narrow
(see `av1.decode-block`'s namespace docstring for the exact boundary:
BLOCK_32X32 leaves (single- or, for the V_PRED/H_PRED mode-coverage
extension below, real multi-leaf) / TX_32X32 / DCT_DCT / DC_PRED+V_PRED+
H_PRED+PAETH_PRED+SMOOTH_PRED (per the PAETH/SMOOTH mode-coverage
extensions below) for luma;
TX_16X16 / DCT_DCT / UV_DC_PRED-only, 4:2:0, single- or (per
the multi-leaf-chroma extension below, for the simple 1:1 luma-leaf/chroma-
block correspondence only) multi-leaf for chroma). AV1's spec is far larger than H.264's, so
per the ADR this repo does **not** attempt broad common-code sharing with
H.264 -- only `codec-primitives`'s narrow generic shapes
(`BlockTransform`/`QuantScale` protocols, `scan`/`unscan`) are candidates
for reuse; this phase still doesn't lean on them (av1.transform/av1.tables
implement AV1's own dequant/DCT/scan tables directly, since AV1's are
structurally different enough from H.264's that a shared abstraction would
have been leakier than just implementing both natively -- see
`codec-primitives`'s README for the same conclusion reached from the H.264
side).

Implemented, transcribed field-for-field from the spec (not reconstructed
from memory -- see each namespace's docstring for the exact spec section
and source snapshot used: `AOMediaCodec/av1-spec` master,
`06.bitstream.syntax.md`/`07.bitstream.semantics.md`/`08.decoding.process.md`/
`09.parsing.process.md`/`10.additional.tables.md`/`04.conventions.md`,
fetched 2026-07-12 for the framing namespaces, 2026-07-13 for the pixel-
reconstruction namespaces added below):

| ns | role |
|---|---|
| `av1.bitreader` | MSB-first bit reader + descriptor primitives: `f(n)`, `uvlc()`, `le(n)`, `leb128()`, `su(n)`, `ns(n)`, `byte_alignment()`, `skip-bits` (position-only advance, for `exit_symbol()`) |
| `av1.obu` | `obu_header()` / `obu_extension_header()` / the top-level OBU loop -- every OBU is self-delimiting via `leb128 obu_size`, so unparsed payload can always be skipped byte-exactly to the next OBU |
| `av1.sequence-header` | full `sequence_header_obu()`: profile/still-picture/timing-info/decoder-model-info/operating-points/frame dimensions/`color_config()` |
| `av1.frame-header` | **the full `uncompressed_header()`** for intra frames (`KEY_FRAME`/`INTRA_ONLY_FRAME`), plus, per the inter zero-motion-baseline extension below, `INTER_FRAME` within a narrow `error_resilient_mode==1`/`enable_order_hint==0` scope: frame_type/show_frame/showable_frame, frame size (`frame_size()`/`superres_params()`/`render_size()`), the inter-only `ref_frame_idx[]`/`read_interpolation_filter()`/`is_motion_mode_switchable`/`use_ref_frame_mvs` fields, `tile_info()`, `quantization_params()`, `segmentation_params()`, `delta_q_params()`/`delta_lf_params()`, the `CodedLossless`/`AllLossless` computation, `loop_filter_params()`, `cdef_params()`, `lr_params()`, `read_tx_mode()`, `frame_reference_mode()`/`skip_mode_params()`/`global_motion_params()` (real reads for inter frames now, not just zero-bit intra passthroughs), `reduced_tx_set`, and `film_grain_params()`. Also now carries `use-128x128-superblock`/`mono-chrome`/`num-planes`/`subsampling-x`/`subsampling-y` through to the top-level returned map (bugfix, see below) |
| `av1.bool-decoder` | the AV1 "Symbol decoder" (daala-derived non-binary arithmetic coder, spec 8.2): `init_symbol`/`read_bool`/`read_literal`/`read_symbol`/`exit_symbol` with CDF adaptation. Wholly separate implementation from H.264's CAVLC/CABAC (`h264.cavlc`) -- different coding scheme entirely |
| `av1.tile-group` | `tile_group_obu()`'s entry (tile start/end, per-tile `init_symbol`/`exit_symbol`) + `decode_partition()` (spec 5.11.4) fully implemented: real default CDF tables (`Default_Partition_W8/W16/W32/W64/W128_Cdf`), real `partition`/`split_or_horz`/`split_or_vert` context derivation (AvailU/AvailL via a MiSizes grid this namespace maintains), real bool-decoder symbol reads -- down to every leaf partition. `decode_block()` is now called at every leaf **when the caller supplies** an injectable `:decode-block-fn` (see `av1.decode-block` below) -- existing callers that don't supply one keep the original "leaf recorded, no further bits consumed" behavior this namespace has always documented |
| `av1.tables` | AV1 constant tables for coefficient decode/dequant/inverse transform/intra prediction: `Dc-Qlookup-8bit`/`Ac-Qlookup-8bit` (8-bit dequant lookup), `Cos128-Lookup`, `Default-Scan-32x32`, `Intra-Mode-Context-Dc-V-H`/`MAX_ANGLE_DELTA`/`Default-Angle-Delta-Cdf` (mode-coverage extension, see below), `Sm-Weights-Tx-4x4`/`8x8`/`16x16`/`32x32`/`64x64` (SMOOTH mode-coverage extension, see below), and the `Default_*_Cdf` tables (`Skip`/`Intra-Frame-Y-Mode`/`Txb-Skip`/`Eob-Pt-1024`/`Eob-Extra`/`Dc-Sign`/`Coeff-Base-Eob`/`Coeff-Base`/`Coeff-Br`) sliced to this phase's supported scope (TX_32X32 only, luma only). Chroma extension (see below): the SAME q-ctx-idx x TX_16X16 x chroma(ptype=1) slices of those same spec tables (`Default-Txb-Skip-Cdf-16x16-Chroma`/`Default-Eob-Pt-256-Cdf-Chroma`/`Default-Eob-Extra-Cdf-16x16-Chroma`/`Default-Dc-Sign-Cdf-Chroma`/`Default-Coeff-Base-Eob-Cdf-16x16-Chroma`/`Default-Coeff-Base-Cdf-16x16-Chroma`/`Default-Coeff-Br-Cdf-16x16-Chroma`), plus `Default-Scan-16x16` and `Default-Uv-Mode-Cfl-Allowed-Cdf-Dc-V-H` (see namespace docstring's chroma section for exactly how each was extracted/spot-checked). Inter zero-motion-baseline extension (see below): `Default-Is-Inter-Cdf`/`Default-Single-Ref-Cdf`/`Default-New-Mv-Cdf`/`Default-Zero-Mv-Cdf`/`Default-Ref-Mv-Cdf`/`Default-Inter-Tx-Type-Set3-Cdf`/`Tx-Type-Inter-Inv-Set3` and the full MV-syntax table family (`Default-Mv-Joint-Cdf`/`Default-Mv-Sign-Cdf`/`Default-Mv-Class-Cdf`/`Default-Mv-Class0-Bit-Cdf`/`Default-Mv-Class0-Fr-Cdf`/`Default-Mv-Class0-Hp-Cdf`/`Default-Mv-Bit-Cdf`/`Default-Mv-Fr-Cdf`/`Default-Mv-Hp-Cdf`) |
| `av1.transform` | dequantization (`dequantize`) + the AV1 inverse DCT (`inverse-dct!`, spec 7.13.2.3's generic butterfly-network algorithm, transcribed in full for n=2..6/TX_4X4..TX_64X64) + the 2D inverse transform process (`inverse-transform-2d`, row transform -> clip -> column transform) -- already fully generic over transform size, so the chroma extension below (TX_16X16) needed NO changes here at all: `inverse-dct!`'s n=4 branch and `dq-denom`'s TX_16X16 case were already transcribed in full generality alongside luma's n=5/TX_32X32 (only n=5/TX_32X32 was exercised against real data before the chroma extension; n=4/TX_16X16 now is too) |
| `av1.intra-pred` | DC/V/H/PAETH/SMOOTH intra prediction (`dc-predict`/`v-predict`/`h-predict`/`paeth-predict`/`smooth-predict`, spec 7.11.2.4/7.11.2.5/7.11.2.2/7.11.2.6) -- DC's all four haveLeft/haveAbove cases implemented (though the original single-block fixtures only exercise the "neither available" case); V_PRED/H_PRED added in the mode-coverage extension below, both exercised against real multi-leaf data with a genuine avail-above/avail-left neighbor (not just the degenerate no-neighbor fallback); PAETH_PRED added in the PAETH mode-coverage extension below (the first mode here needing the topleft-corner `AboveRow[-1]`/`LeftCol[-1]` sample, via the new `above-row-corner` helper), also exercised against real multi-leaf data; SMOOTH_PRED added in the SMOOTH mode-coverage extension below (a genuine two-edge weighted blend via `Sm-Weights-Tx-*`, reusing the same `above-row-fn`/`left-col-fn` accessors PAETH_PRED uses), also exercised against real multi-leaf data with both a genuine avail-above AND avail-left neighbor. `dc-predict` is plane-agnostic (frame-w/frame-h/x/y/log2W/log2H are all caller-supplied), so the chroma extension below reuses it as-is for UV_DC_PRED -- no changes needed here either |
| `av1.decode-block` | **decode_block()** (spec 5.11.5) for this phase's narrow validated scope: `intra_frame_mode_info()` (`read_skip`/`read_cdef`/`intra_frame_y_mode`/`intra_angle_info_y`/`uv_mode`/`filter_intra_mode_info`'s conditional guard), `read_block_tx_size()`, `residual()`/`transform_block()`/`coeffs()` (all_zero/transform_type/eob_pt_1024 or eob_pt_256/eob_extra/coeff_base/coeff_base_eob/coeff_br/dc_sign/sign_bit/golomb, with real per-context CDF persistence+adaptation, including cross-block dc_sign/txb_skip context via per-plane AboveDcContext/LeftDcContext/AboveLevelContext/LeftLevelContext), and reconstruction (predict_intra + dequantize + inverse_transform_2d + clip) -- for BOTH luma (plane 0, TX_32X32) and, per the chroma extension below, U/V (planes 1/2, TX_16X16, 4:2:0). Per the inter zero-motion-baseline extension below, also `inter_frame_mode_info()`/`inter_block_mode_info()` (`read_is_inter`/`read_ref_frames`/a degenerate `find_mv_stack()`/`new_mv`/`zero_mv`/`ref_mv`/`assign_mv`/`read_mv`) and `predict_inter` (a reference-frame-copy motion compensation, `predict-inter-block`, for the one supported motion vector, `(0,0)`) for `INTER_FRAME`s. See its namespace docstring for the exact scope boundary and why each boundary was chosen (frame-level `guard-frame-scope!` throws for out-of-scope streams) |

**Explicitly NOT implemented (next phase)**: inter frames beyond the
narrow zero-motion-baseline scope added below (`### Inter zero-motion-
baseline extension`) -- `SWITCH_FRAME`, `frame_size_override_flag &&
!error_resilient_mode` (`frame_size_with_refs()`), `enable_order_hint ==
1` inter frames, compound/multi-reference prediction, any nonzero motion
vector, and more, see that section's "Explicitly NOT covered" list -- and
`show_existing_frame == 1` (needs cross-frame `RefFrameType` state this
phase doesn't track -- `av1.frame-header/parse` throws `ex-info` rather
than silently mis-parsing it), `segmentation_params()`
when `primary_ref_frame != PRIMARY_REF_NONE` (needs cross-frame segmentation-
map state -- structurally unreachable for the intra frames this phase
supports, since `primary-ref-frame` is always forced to `PRIMARY_REF_NONE`
when `frame-is-intra?`, but throws rather than silently mis-parsing if that
invariant is ever violated), `temporal_point_info()` (needs
`frame_presentation_time_length_minus_1` plumbing not carried; throws if a
stream's `decoder_model_info_present_flag && !equal_picture_interval` would
require it). `decode_partition()`'s recursive partition-tree structure IS
bit-exact all the way through `decode_block()` now (when `av1.decode-block`
is wired in as the `:decode-block-fn`), including real MULTI-leaf frames
(mode-coverage extension below), but **only** for the narrow shape
`av1.decode-block`'s namespace docstring specifies -- FLIPADST/IDTX/V_DCT/
H_DCT transform types (DCT_DCT/ADST_DCT/DCT_ADST/ADST_ADST ARE supported,
the latter three only for the ADST extension's TX_4X4/luma leaves, see
below), any intra mode other than DC_PRED/V_PRED/H_PRED/PAETH_PRED/
SMOOTH_PRED (luma) or UV_DC_PRED (chroma, see below), any transform size other than TX_32X32/
TX_4X4 (luma)/TX_16X16 (chroma), 4:2:2/4:4:4 chroma subsampling, and
segmentation/delta-Q/delta-LF/screen-content-tools/intra-BC are all
explicitly out of scope and throw `ex-info` rather than silently
mis-decoding. Inter prediction is now implemented for the narrow
zero-motion-baseline scope described below (`### Inter zero-motion-
baseline extension`) -- everything outside that scope (subpel motion
compensation, compound/multi-reference prediction, OBMC/warped motion,
etc.) remains unimplemented. Loop-filter/CDEF/loop-restoration in-loop
filtering and film grain synthesis remain fully unimplemented (this
phase's fixtures disable all in-loop filtering at the encoder, so the raw
reconstruction this phase produces already matches the reference
decoder's output without needing to implement any of them -- see
Validation below).

### Mode-coverage extension: V_PRED / H_PRED (ADR-2607122000 Migration step 9, continued)

The narrow single-leaf/DC_PRED-only milestone above has been extended to
also support `V_PRED` and `H_PRED` (`av1.intra-pred/v-predict`/
`h-predict`, spec 7.11.2.4's directional intra prediction process,
pAngle==90/180 cases), validated against two real **multi-leaf** aomenc
frames (a 64x64-pixel, single-superblock frame forced via
`--min-partition-size=32 --max-partition-size=32` into a real 2x2 grid of
BLOCK_32X32 leaves -- see `test/av1/fixtures.cljk` for the exact content
design and `test/av1/decode_block_test.cljk` for the bit-exact assertions).
This required two real extensions beyond just adding the prediction math:

- **Real cross-block context**, not the single-leaf shortcuts the
  original milestone could get away with: `intra_frame_y_mode`'s ctx now
  comes from an actual `YModes` grid + `Intra_Mode_Context` mapping
  (`av1.decode-block/read-y-mode`, throwing if the mapped ctx is ever
  something other than `(0,0)`, since only that one
  `Default_Intra_Frame_Y_Mode_Cdf[0][0]` table entry is transcribed), and
  `dc_sign`'s ctx now comes from real `AboveDcContext`/`LeftDcContext`
  tracking (`av1.decode-block/get-dc-sign-ctx`, `record-above-dc!`/
  `record-left-dc!`) instead of the hardcoded 0 that was only exactly
  correct (not an approximation) when a frame could only ever have one
  leaf. Both grids are written across each leaf's whole mi footprint
  (`record-footprint!`), fixing a latent bug where the pre-existing
  `Skips` tracking only wrote a single origin point -- invisible before
  because no earlier fixture had a second leaf to query it.
- **`intra_angle_info_y()`** (`av1.decode-block/read-angle-delta-y`): a
  real `angle_delta_y` symbol read that a first implementation attempt
  incorrectly assumed could be skipped because the fixtures are encoded
  with `--enable-angle-delta=0` -- that flag only biases the *encoder's*
  search, it does not remove the syntax element, which is read
  unconditionally whenever `is_directional_mode(YMode)` is true. Missing
  it desynced every bit after a V_PRED/H_PRED block's mode read, producing
  a smoothly-wrong-but-plausible-looking reconstruction that only a real
  bit-exact comparison against dav1d caught (visually it looked like a
  minor rounding difference, not a bug) -- this is exactly the kind of
  error class this repo's "bit-exact against a real independent decoder,
  no tolerance" validation stance exists to catch. The decoded
  `AngleDeltaY` is asserted (not just assumed) to be `0`, since
  `av1.intra-pred`'s V_PRED/H_PRED implementation only handles pAngle
  exactly 90/180.

Luma transform size beyond TX_32X32 (TX_16X16/TX_8X8 for LUMA leaves smaller
than BLOCK_32X32, and the ADST/IDTX transform types `get_tx_set()` can select
for them) was considered but not pursued in this pass, per ADR-2607122000
Migration step 9's guidance to land one narrow, fully-validated extension
rather than spread across both axes. (TX_16X16 itself IS now used below --
for the CHROMA planes of a BLOCK_32X32 leaf under 4:2:0 subsampling, which is
DCT_DCT-forced the same structural way TX_32X32 is for luma, not for a
smaller luma leaf, which would need real ADST support.)

### Chroma (Cb/Cr) decode (ADR-2607122000 Migration step 9, continued)

The luma-only milestones above have been extended to also decode the U (Cb)
and V (Cr) planes, for 4:2:0 content (`subsampling_x=1, subsampling_y=1`)
only. See `av1.decode-block`'s namespace docstring for the exact scope
boundary and rationale; summarized:

- **UV_DC_PRED only.** `uv_mode` (spec #Cdf selection process) is read for
  real (`av1.decode-block/read-uv-mode`, against
  `av1.tables/Default-Uv-Mode-Cfl-Allowed-Cdf-Dc-V-H`, the
  `TileUVModeCflAllowedCdf[YMode]` rows for YMode in {DC_PRED,V_PRED,H_PRED}
  -- always the CFL-allowed cdf variant here since this namespace's only
  block shape has `Max(Block_Width,Block_Height) <= 32`), but the decoded
  result is restricted to `UV_DC_PRED` (0) -- any other value, including
  `UV_CFL_PRED` (which would need `read_cfl_alphas()`), throws. `uv_mode`'s
  ctx is simply the block's own already-decoded `YMode` (not a neighbor
  lookup, unlike `y_mode`/`dc_sign`), so no cross-block state is needed for
  it. `intra_angle_info_uv()` is a real zero-bit no-op for this scope (since
  `is_directional_mode(UV_DC_PRED)` is false) rather than an assumed skip.
- **Chroma transform type needs no bitstream read at all.** Unlike luma
  (where `transform_type()` IS called, itself a zero-bit forced read for
  TX_32X32), `coeffs()` only calls `transform_type()` when `plane==0` --
  chroma's `TxType` comes from `compute_tx_type()`'s
  `Mode_To_Txfm[UVMode]` path, which for `UVMode==UV_DC_PRED` is `DCT_DCT`
  and always `is_tx_type_in_set` (spot-checked against the spec's own
  `Mode_To_Txfm`/`Tx_Type_In_Set_Intra` tables, not assumed) -- so chroma
  `TxType` is `DCT_DCT` with a structural zero-bit guarantee, the same
  strength of guarantee as luma's TX_32X32 case, via a genuinely different
  code path.
- **Chroma transform size is TX_16X16, unconditionally, for this
  namespace's only supported leaf shape.** A BLOCK_32X32 luma leaf
  subsamples (4:2:0) to exactly BLOCK_16X16 chroma
  (`Subsampled_Size[BLOCK_32X32][1][1]`) whose `Max_Tx_Size_Rect` is
  TX_16X16 -- both spot-checked directly against the spec's own tables
  rather than reconstructed from memory. `av1.transform`'s inverse-DCT/
  dequantize/2D-inverse-transform functions were ALREADY fully generic
  over transform size (transcribed in full for n=2..6 from the start, see
  that namespace's docstring) -- so TX_16X16 chroma reconstruction needed
  **zero changes** to `av1.transform`, only to `av1.decode-block`'s
  coefficient-decode plumbing (see below) and new TX_16X16/chroma CDF
  table slices in `av1.tables` (see that namespace's docstring).
- **Coefficient decode (`coeffs()`) is now generalized over plane/tx-size**
  (`av1.decode-block/read-coeffs`, parameterized by a `spec` map -- see
  `luma-spec-base`/`chroma-spec-base`/`u-spec`/`v-spec`) so the SAME
  implementation serves luma (TX_32X32, bwl=5) and chroma (TX_16X16,
  bwl=4) rather than duplicating the ~90-line coefficient-decode loop.
  `get-coeff-base-ctx`/`get-coeff-br-ctx` were generalized the same way
  (parameterized by `bwl`/`w` instead of hardcoded TX_32X32 constants) --
  `Coeff_Base_Ctx_Offset[TX_16X16]` is IDENTICAL to
  `Coeff_Base_Ctx_Offset[TX_32X32]` in the spec's own table (spot-checked,
  not assumed), so `av1.tables/Coeff-Base-Ctx-Offset-32x32` is reused
  directly for chroma without a separate slice.
- **U and V planes share coefficient-CDF adaptation state; per-plane
  cross-block dc/level context is genuinely separate.** Per spec, the
  `ptype` dimension of `TileTxbSkipCdf`/`TileCoeffBaseCdf`/etc. is "luma vs
  chroma", not "Y vs U vs V" -- so U's coefficient reads adapt the SAME cdf
  state V's reads then continue adapting (`u-spec`/`v-spec` intentionally
  share every `:*-cdf-key`, only `:plane`/`:delta-q-dc`/`:delta-q-ac`
  differ). `AboveDcContext`/`LeftDcContext` (now joined by
  `AboveLevelContext`/`LeftLevelContext`, needed for chroma's
  `get_txb_skip_ctx` -- see below) ARE genuinely per-plane (spec indexes
  them by literal plane 1 vs 2), implemented via
  `av1.decode-block/record-above!`/`record-left!`/`get-dc-sign-ctx` keyed
  by `[map-key plane ...]`.
- **Chroma's `txb_skip` context (`get_txb_skip_ctx`, plane>0 branch) is a
  genuinely different formula than luma's** (`ctx = 7 + (above!=0) +
  (left!=0)`, from real `AboveLevelContext`/`AboveDcContext` OR-together,
  vs. luma's hardcoded `ctx=0` since `bw==w && bh==h` always holds for
  luma's one block shape) -- implemented as real map lookups
  (`av1.decode-block/get-txb-skip-ctx-chroma`), not a hardcoded constant,
  even though this namespace's current scope (single whole-frame leaf, see
  below) means it always evaluates to exactly 7 in practice.
- **Per-plane quantizer**: `dc-q-idx`/`ac-q-idx` for U/V use
  `base_q_idx + delta_q_u_dc/ac` / `base_q_idx + delta_q_v_dc/ac`
  respectively (`av1.frame-header/parse-quantization-params` already
  parsed all four deltas -- no frame-header changes were needed for this
  extension), vs. luma's `base_q_idx + delta_q_y_dc` (DC) /
  `base_q_idx` (AC, no luma AC delta exists in the spec).
- **Multi-leaf chroma, updated (ADR-2607122000 Migration step 9
  continuation): real multi-leaf color frames are now supported, for the
  simple 1:1 luma-leaf/chroma-block correspondence only.** The original
  chroma-decode milestone above validated ONLY a single BLOCK_32X32 leaf
  covering the entire frame; this extension lifts that guard for the case
  where every leaf's `mi-size` is BLOCK_32X32 (this namespace's only
  supported luma leaf size) -- each such leaf subsamples (4:2:0) to exactly
  ONE independent BLOCK_16X16 chroma block (chroma block size exactly half
  the luma leaf size in each dimension), so multiple BLOCK_32X32 leaves
  each simply get their own chroma block, with no shared state between
  chroma blocks other than the real per-plane
  AboveDcContext/LeftDcContext/AboveLevelContext/LeftLevelContext threading
  (already implemented generally as real map lookups by the original
  milestone, unchanged here) and the U/V planes' shared coefficient-CDF
  adaptation state (also unchanged). `av1.decode-block/make-decode-block-fn`'s
  returned callback now throws `:unsupported-shared-chroma-block` (not
  `:unsupported-multi-leaf-chroma`, which no longer exists) if a
  color-frame leaf's `mi-size` is anything OTHER than BLOCK_32X32 -- this is
  the AV1 spec's "shared chroma block" case (small luma partitions, bw4==1
  or bh4==1, where HasChroma can be false and MULTIPLE luma leaves share
  ONE chroma block), which is NOT implemented and is out of scope for a
  future extension. Before the ADST extension below, this guard was
  unreachable by a real bitstream (`tx-size-for` restricted every leaf,
  color or not, to BLOCK_32X32 via the unrelated `:unsupported-tx-size`
  reason first) -- now that `tx-size-for` also accepts BLOCK_4X4 (see the
  ADST extension), a real *color* frame with a BLOCK_4X4 leaf WOULD reach
  this guard and throw `:unsupported-shared-chroma-block` (this namespace's
  ADST-extension fixtures are all monochrome, so this remains untested
  against a real bitstream, but the guard itself is unchanged and still
  correct). See `av1.decode-block`'s namespace docstring for the full
  rationale and `keyframe-64x64-color-multileaf` below for the real
  bit-exact multi-leaf-chroma regression fixture.
- **Monochrome streams are unaffected.** `guard-frame-scope!`'s
  color-format check now accepts EITHER `mono_chrome=1` (luma-only, all
  pre-existing fixtures/tests) OR `mono_chrome=0` with `num_planes=3`/
  `subsampling_x=1`/`subsampling_y=1` (4:2:0 color) -- every chroma code
  path is gated on whether the frame is actually color, so monochrome
  streams never touch any of the above.

### ADST transform extension (ADR-2607122000 Migration step 9, continued)

The DCT_DCT-only milestones above have been extended to support **ADST**
(Asymmetric Discrete Sine Transform, spec 7.13.2.6-7.13.2.9's "Inverse
ADST process") for a new, smaller luma leaf shape: **BLOCK_4X4/TX_4X4**.
Fetched/transcribed 2026-07-13 from AOMediaCodec/av1-spec master
(same sections as the DCT work: 06.bitstream.syntax.md #Transform type
syntax / #Get transform set function, 08.decoding.process.md #Inverse ADST4
process / #2D inverse transform process, 09.parsing.process.md's
`intra_tx_type` cdf selection, 10.additional.tables.md's
`Default_Intra_Tx_Type_Set1/2_Cdf`); the ADST4 butterfly math was
additionally cross-checked against a second, independent source --
libaom's own C reference implementation (`av1_iadst4`,
`av1/common/av1_inv_txfm1d.c`, AOMediaCodec/aom master) -- confirming the
same SINPI_1_9..SINPI_4_9 constants and the same stage-for-stage algebra,
not just a second read of the same spec paragraph.

- **`get_tx_set()` is now transcribed in full** (`av1.decode-block/get-tx-set`,
  is_inter==0 branch only -- this repo is intra-only): `TX_SET_DCTONLY`
  when `Tx_Size_Sqr_Up[txSz] == TX_32X32` (unchanged, still forces DCT_DCT
  with zero bits for TX_32X32/luma and TX_16X16/chroma), `TX_SET_INTRA_2`
  when `reduced_tx_set` or `Tx_Size_Sqr[txSz] == TX_16X16`, else
  `TX_SET_INTRA_1`. For this extension's only new tx size, TX_4X4, that's
  `TX_SET_INTRA_1` (7 types: `IDTX,DCT_DCT,V_DCT,H_DCT,ADST_ADST,ADST_DCT,
  DCT_ADST`) unless `reduced_tx_set==1`, in which case `TX_SET_INTRA_2` (5
  types, dropping `V_DCT`/`H_DCT`) -- `av1.decode-block/read-transform-type`
  performs a REAL cdf read against whichever set applies (previously,
  before this extension, `transform_type()` was only ever a zero-bit
  forced read since only TX_32X32 was supported).
- **Restricted to {DCT_DCT, ADST_DCT, DCT_ADST, ADST_ADST}.** `IDTX`/
  `V_DCT`/`H_DCT` are structurally reachable decoded values (both
  TX_SET_INTRA_1 and _2 include them) but `av1.transform` has no
  identity-transform or 1D-only (`V_*`/`H_*`) reconstruction path, so
  `read-transform-type` throws `ex-info` (`:unsupported-tx-type`) rather
  than silently mis-decoding if the real bitstream ever decodes one of
  those -- this repo's test fixtures are encoded with `--enable-flip-idtx=0`
  (an aomenc option that removes exactly `IDTX`/`V_DCT`/`H_DCT`/every
  `FLIPADST_*` type from the encoder's RD search), so those fixtures are
  guaranteed by construction never to hit this throw.
- **`av1.transform/inverse-adst4!`**: the spec's Inverse ADST4 process
  (7.13.2.6) transcribed as a flat scalar butterfly (no B/H calls, no
  input/output permutation -- those are only needed for ADST8/ADST16,
  spec 7.13.2.7/7.13.2.8, out of scope: this extension only reaches n=2/
  TX_4X4). `av1.transform/inverse-transform-2d` now takes an optional
  `tx-type` argument (default `:DCT_DCT`, so every pre-existing caller's
  behavior is byte-for-byte unchanged) and dispatches each axis (row/
  column) independently via `row-transform-kind`/`col-transform-kind`,
  per the spec's #2D inverse transform process "PlaneTxType is one of ..."
  lists: `ADST_DCT` -> row=DCT, col=ADST; `DCT_ADST` -> row=ADST,
  col=DCT; `ADST_ADST` -> both axes ADST. (AV1's TxType naming convention
  is "column-type_row-type", not "row_column" -- spot-checked directly
  against the spec's own two axis lists, not assumed from the name.)
  `flipUD`/`flipLR` (the reconstruction step's row/column mirroring for
  `FLIPADST_*`/`*_FLIPADST` types) are never needed for this restricted
  type set, so they aren't implemented.
- **Real, normally-signaled `BLOCK_4X4` leaves.** `av1.tile-group/
  decode-partition` needed NO changes at all: its existing recursive
  `decode_partition()` implementation already handles `bsize < BLOCK_8X8 ->
  PARTITION_NONE` (spec's base case) generically, so a real
  `--min-partition-size=4 --max-partition-size=4` aomenc encode already
  produces real BLOCK_4X4 leaves through the pre-existing partition-tree
  walk (a real, normally-signaled `partition` symbol read at BLOCK_8X8,
  not a zero-bit structural forcing). `av1.decode-block/tx-size-for` now
  accepts both TX_32X32 and TX_4X4 (`Max_Tx_Size_Rect[BLOCK_4X4] ==
  TX_4X4`, throws for anything else); the per-leaf luma cdf-table/
  scan-order spec (`luma-spec-32`/`luma-spec-4x4`) is picked per-leaf
  inside `make-decode-block-fn`'s returned callback (not once per frame),
  since a single frame's partition tree can now mix leaf shapes across a
  monochrome-only scope (color+BLOCK_4X4 remains out of scope, see the
  chroma section above).
- **New TX_4X4/luma-only CDF table slices** (`av1.tables`):
  `Default-Txb-Skip-Cdf-4x4-Luma`/`Default-Eob-Pt-16-Cdf-Luma`/
  `Default-Eob-Extra-Cdf-4x4-Luma`/`Default-Coeff-Base-Eob-Cdf-4x4-Luma`/
  `Default-Coeff-Base-Cdf-4x4-Luma`/`Default-Coeff-Br-Cdf-4x4-Luma`/
  `Default-Scan-4x4`/`Default-Intra-Tx-Type-Set1-Cdf-4x4-Dc-V-H`/
  `Default-Intra-Tx-Type-Set2-Cdf-Uniform` -- extracted with the same
  brace-matching parser as every pre-existing table in this namespace,
  then spot-checked field-for-field against the raw spec markdown at both
  the first and last row of each slice (to rule out the parser having
  grabbed the wrong q-ctx-idx/tx-size/ptype block, the same transcription-
  mistake risk the DCT-phase work already found and fixed 5 instances of).
  `Coeff-Base-Ctx-Offset-32x32` is reused as-is for TX_4X4 (the reachable
  subset, row/col in 0..3 since TX_4X4's `bwl`=2, is identical to that
  table's first 4x4 sub-block, spot-checked against the spec's own table).
  `dc_sign`'s cdf (`Default-Dc-Sign-Cdf-Luma`) is genuinely SHARED between
  TX_32X32 and TX_4X4 luma leaves (the spec's `Default_Dc_Sign_Cdf` has no
  `TX_SIZES` dimension at all, only `PLANE_TYPES` -- confirmed directly
  against the spec table's declared shape, not assumed), so both tx sizes'
  `luma-spec` maps intentionally share the same `:dc-sign-cdf-key`.
- **`Default_Intra_Tx_Type_Set2_Cdf` is genuinely uniform at TX_4X4** (the
  spec's own table has the IDENTICAL 5-symbol-equiprobable row
  `{6554,13107,19661,26214,32768,0}` for every one of the 13 intra modes at
  `Tx_Size_Sqr==TX_4X4` -- spot-checked programmatically across all 13
  rows, not assumed from a single row), so a single constant
  (`Default-Intra-Tx-Type-Set2-Cdf-Uniform`) is exact, not an
  approximation, for the `reduced_tx_set==1` case.
- **Real-decode validation**: two new REAL aomenc-encoded 8x8 monochrome
  fixtures (`keyframe-8x8-adst-diag`/`keyframe-8x8-adst-quad`, see
  test/av1/fixtures.cljk docstrings), each forced into a real 2x2 grid of
  BLOCK_4X4 leaves with a diagonal or per-quadrant step-edge content
  design chosen because ADST responds better than DCT to content that
  isn't symmetric about the block boundary. Both fixtures are confirmed
  (by actually decoding and inspecting the real `TxType`, not assumed) to
  make the real encoder choose ADST-family types -- `ADST_ADST` (2 leaves
  in the diag fixture) and `DCT_ADST` (1 leaf in the quad fixture) --
  and both reconstructions are bit-exact (no tolerance) against dav1d's
  independent decode of the same bitstream. See
  `test/av1/decode_block_test.cljk`'s `adst-diag-8x8-bit-exact-test`/
  `adst-quad-8x8-bit-exact-test`.
- **Explicitly NOT covered by this extension**: `IDTX`/`V_DCT`/`H_DCT`/any
  `FLIPADST_*` type (no identity-transform or flip-reconstruction path in
  `av1.transform`); ADST8/ADST16 (TX_8X8/TX_16X16 luma leaves smaller than
  BLOCK_32X32, which would need real `PARTITION_SPLIT`/`PARTITION_HORZ`/
  `PARTITION_VERT` support down to those sizes plus the ADST8/16 input/
  output permutation processes); ADST for chroma (chroma's TxType remains
  structurally forced to DCT_DCT via `Mode_To_Txfm[UV_DC_PRED]`, unchanged
  by this extension); color (4:2:0) frames with a BLOCK_4X4 leaf (the
  "shared chroma block" case, see the chroma section above).

### PAETH_PRED mode-coverage extension (ADR-2607122000 Migration step 9, continued)

The DC_PRED/V_PRED/H_PRED-only luma mode set above has been extended to
also support **PAETH_PRED** (spec 7.11.2.2 "Basic intra prediction
process", fetched 2026-07-13 from AOMediaCodec/av1-spec master,
08.decoding.process.md #Intra prediction process / #Basic intra prediction
process). This is a smaller, narrower change than the V_PRED/H_PRED
extension because PAETH_PRED is **not a directional mode**:
`is_directional_mode(PAETH_PRED)` is false per spec, so
`intra_frame_mode_info()`'s mode dispatch routes it to the "basic intra
prediction process" (7.11.2.2) rather than the "directional intra
prediction process" (7.11.2.4) that V_PRED/H_PRED use -- and
`intra_angle_info_y()` is itself gated on `is_directional_mode(YMode)`, so
a PAETH_PRED block reads **no `angle_delta_y` bit at all** (unlike V_PRED/
H_PRED, which do -- see the mode-coverage extension above for the bug that
uncovered). This means the extension needed neither new angle-delta
handling nor any edge-filter/upsample reasoning -- `av1.decode-block/
read-angle-delta-y`'s existing `(contains? #{V_PRED H_PRED} y-mode)` gate
already (and correctly) excludes PAETH_PRED with no code change.

- **`av1.intra-pred/paeth-predict`** implements spec 7.11.2.2's exact
  ordered-step formula: for each output sample, `base = AboveRow[j] +
  LeftCol[i] - AboveRow[-1]`, then pick whichever of
  `LeftCol[i]`/`AboveRow[j]`/`AboveRow[-1]` is closest to `base` (ties
  broken toward `LeftCol[i]`, then `AboveRow[j]`, per the spec's own
  ordered `<=` comparisons -- transcribed exactly, not "closest wins" with
  an unspecified tiebreak). This is the first mode in this namespace that
  needs `AboveRow[-1]`/`LeftCol[-1]` (the topleft corner sample --
  `LeftCol[-1] == AboveRow[-1]` per spec, so only one accessor,
  `above-row-corner`, is needed): DC_PRED doesn't use it at all, and
  V_PRED/H_PRED only ever read `AboveRow[0..w-1]`/`LeftCol[0..h-1]`. The
  general "Intra prediction process" section's four-case derivation
  (haveAbove&&haveLeft -> `CurrFrame[y-1][x-1]`; haveAbove-only ->
  `CurrFrame[y-1][x]`; haveLeft-only -> `CurrFrame[y][x-1]`; neither ->
  `1<<(BitDepth-1)`) is a genuinely different formula than `AboveRow[i]`/
  `LeftCol[i]`'s own have-only-one-neighbor fallback (which broadcasts a
  single real sample across the whole row/column) -- spot-checked directly
  against the spec text, not assumed to be the same case list.
- **`av1.decode-block/read-y-mode`'s neighbor-context lookup was widened**
  from the DC/V/H-only 3-entry `Intra-Mode-Context-Dc-V-H` slice to the
  FULL 13-entry spec table (`av1.tables/Intra-Mode-Context`, already
  transcribed in full from the start, just not previously consulted beyond
  index 2) -- since a neighbor's already-decoded YMode can now be
  PAETH_PRED(12) too. This widening is exact and introduces no new
  reachable `(abovemode,leftmode)` ctx pair:
  `Intra_Mode_Context[PAETH_PRED(=12)] == 0`, IDENTICAL to
  `Intra_Mode_Context[DC_PRED(=0)]` (spot-checked against the spec's own
  table, not assumed), so a PAETH_PRED neighbor contributes ctx 0 the same
  way a DC_PRED neighbor already did -- this repo's existing restriction to
  only the `(0,0)` ctx pair (only `Default_Intra_Frame_Y_Mode_Cdf[0][0]` is
  transcribed) still covers every reachable case.
- **Chroma + PAETH_PRED luma is explicitly out of scope.**
  `av1.tables/Default-Uv-Mode-Cfl-Allowed-Cdf-Dc-V-H` (uv_mode's cdf-row
  table, indexed by the block's own YMode) only has the DC_PRED/V_PRED/
  H_PRED rows transcribed -- a color frame whose luma leaf decodes to
  PAETH_PRED would need `TileUVModeCflAllowedCdf[12]`, not transcribed.
  `av1.decode-block/read-uv-mode` now throws `ex-info`
  (`:reason :unsupported-y-mode-for-uv-mode-ctx`) up front if this is ever
  reached, rather than letting an out-of-range `nth` crash uncontrolled --
  this extension's own validation fixture is monochrome, so this guard is
  documented but not exercised against real data.
- **Real-decode validation**: one new REAL aomenc-encoded 64x64 monochrome
  fixture (`keyframe-64x64-paeth`, see test/av1/fixtures.cljk's docstring),
  the same real-MULTI-leaf construction as the V_PRED/H_PRED fixtures (one
  64x64 superblock forced via `--min-partition-size=32
  --max-partition-size=32` into a real 2x2 grid of BLOCK_32X32 leaves), but
  with `--enable-paeth-intra=1`/`--enable-directional-intra=0` (V_PRED/
  H_PRED aren't needed for this fixture, so directional modes are disabled
  outright, leaving `{DC_PRED, PAETH_PRED}` as the only structurally legal
  luma modes). Content is a single continuous diagonal linear ramp across
  the whole frame, `pixel(x,y) = clamp(128 + 1.5*(x-32) - 1.5*(y-32))` --
  additively separable (`f(x,y) = g(x) + h(y)`), which makes PAETH_PRED's
  `base` formula (itself a discrete-Laplacian test) reconstruct the ramp
  with near-zero residual, favoring it over DC_PRED's blended average for
  the classic reason PNG's own Paeth filter exists. Confirmed (not
  assumed) by actually decoding and inspecting the real chosen YMode: the
  real encoder chose PAETH_PRED for 2 of the 4 leaves (top-right and
  bottom-left, each with exactly one real neighbor) and DC_PRED for the
  other 2 (top-left, with no neighbors, and -- empirically, not as
  originally expected when this content was designed -- bottom-right,
  which has BOTH real above and left neighbors), and the full
  reconstruction is bit-exact (no tolerance) against dav1d's independent
  decode of the same bitstream. See
  `test/av1/decode_block_test.cljk`'s `paeth-pred-64x64-bit-exact-test`.
- **Explicitly NOT covered by this extension**: chroma (Cb/Cr) + luma
  PAETH_PRED (see above); SMOOTH_PRED/SMOOTH_V_PRED/SMOOTH_H_PRED (spec
  7.11.2.6, a different prediction process entirely -- see next section for
  SMOOTH_PRED, which IS now covered); D45/D135/D113/D157/D203/D67
  (directional modes with nonzero angle, which -- unlike V_PRED/H_PRED's
  pAngle-exactly-90/180 case -- would need real edge-filter/upsample/
  angle-delta support).

### SMOOTH_PRED mode-coverage extension (ADR-2607122000 Migration step 9, continued)

The DC_PRED/V_PRED/H_PRED/PAETH_PRED luma mode set above has been extended
to also support **SMOOTH_PRED** (spec 7.11.2.6 "Smooth intra prediction
process", SMOOTH_PRED case only -- SMOOTH_V_PRED/SMOOTH_H_PRED, the two 1D
simplifications the same spec section also defines, remain out of scope,
fetched 2026-07-13 from AOMediaCodec/av1-spec master,
08.decoding.process.md #Smooth intra prediction process /
10.additional.tables.md for the `Sm_Weights_Tx_*` weight tables). Like
PAETH_PRED, SMOOTH_PRED is **not a directional mode**
(`is_directional_mode(SMOOTH_PRED)` is false per spec, so
`intra_frame_mode_info()`'s mode dispatch routes it to its own dedicated
"smooth intra prediction process" 7.11.2.6, not the directional process
7.11.2.4 that V_PRED/H_PRED use), so this extension needed no new
angle-delta handling either -- `av1.decode-block/read-angle-delta-y`'s
existing `(contains? #{V_PRED H_PRED} y-mode)` gate already (and
correctly) excludes SMOOTH_PRED with no code change.

- **`av1.intra-pred/smooth-predict`** implements spec 7.11.2.6's exact
  SMOOTH_PRED formula: for each output sample `(i,j)`,

  ```c
  smoothPred =   smWeightsY[ i ] * AboveRow[ j ] +
              ( 256 - smWeightsY[ i ] ) * LeftCol[ h - 1 ] +
                smWeightsX[ j ] * LeftCol[ i ] +
              ( 256 - smWeightsX[ j ] ) * AboveRow[ w - 1 ]
  pred[ i ][ j ] = Round2( smoothPred, 9 )
  ```

  where `smWeightsX`/`smWeightsY` are `av1.tables/Sm-Weights-Tx-*` selected
  by `log2W`/`log2H` (2/3/4/5/6 -> 4x4/8x8/16x16/32x32/64x64, per the
  spec's own dispatch table) -- a genuine two-edge bilinear-style blend
  (unlike PAETH_PRED's single-sample corner pick), reusing the same
  `above-row-fn`/`left-col-fn` accessors PAETH_PRED uses (no new
  accessor needed: `smooth-predict` only ever reads
  `AboveRow[0..w-1]`/`LeftCol[0..h-1]`, the same range `paeth-predict`
  reads).
- **`av1.tables/Sm-Weights-Tx-4x4`/`8x8`/`16x16`/`32x32`/`64x64`**
  (all five sizes, transcribed in full even though only the 32x32 table is
  reachable in this phase's scope) were independently cross-checked
  against a SECOND source (`aomedia.googlesource.com/aom` main branch,
  `aom_dsp/intrapred_common.h`'s `smooth_weights[]`/`smooth_weights_u16[]`
  arrays) -- byte-for-byte identical to the spec's own
  `10.additional.tables.md` transcription, with element counts and
  monotonic-decreasing-from-255 shape spot-checked, the same discipline
  the ADST-coefficient re-transcription check used.
- **`av1.decode-block/read-y-mode`'s neighbor-context lookup needed no
  further widening** -- the full 13-entry `av1.tables/Intra-Mode-Context`
  table (already transcribed for the PAETH extension) already covers
  SMOOTH_PRED(9): `Intra_Mode_Context[SMOOTH_PRED(=9)] == 0`, IDENTICAL to
  `Intra_Mode_Context[DC_PRED(=0)]`/`Intra_Mode_Context[PAETH_PRED(=12)]`
  (spot-checked against the spec's own table, not assumed), so a
  SMOOTH_PRED neighbor contributes ctx 0 the same way DC_PRED/PAETH_PRED
  neighbors already did -- this repo's existing restriction to only the
  `(0,0)` ctx pair still covers every reachable case.
- **Chroma + SMOOTH_PRED luma is explicitly out of scope**, for the same
  reason as chroma + PAETH_PRED: `av1.tables/Default-Uv-Mode-Cfl-Allowed-Cdf-Dc-V-H`
  only has the DC_PRED/V_PRED/H_PRED rows transcribed -- a color frame
  whose luma leaf decodes to SMOOTH_PRED would need
  `TileUVModeCflAllowedCdf[9]`, not transcribed. `av1.decode-block/
  read-uv-mode` throws the same `ex-info`
  (`:reason :unsupported-y-mode-for-uv-mode-ctx`) for either SMOOTH_PRED or
  PAETH_PRED YModes -- this extension's own validation fixture is
  monochrome too, so this guard remains documented but not exercised
  against real data.
- **Real-decode validation**: one new REAL aomenc-encoded 64x64 monochrome
  fixture (`keyframe-64x64-smooth`, see test/av1/fixtures.cljk's docstring),
  the same real-MULTI-leaf construction as the vpred/hpred/paeth fixtures
  (one 64x64 superblock forced via `--min-partition-size=32
  --max-partition-size=32` into a real 2x2 grid of BLOCK_32X32 leaves), but
  with `--enable-smooth-intra=1`/`--enable-directional-intra=0`/
  `--enable-paeth-intra=0` (leaving `{DC_PRED, SMOOTH_PRED, SMOOTH_V_PRED,
  SMOOTH_H_PRED}` as the only structurally legal luma modes). Content is
  authored per-quadrant: top-left flat 128 (forces DC_PRED trivially);
  top-right/bottom-left are 1D sinusoids invariant along the other axis
  (same construction as the vpred/hpred fixtures); bottom-right is authored
  as the EXACT spec 7.11.2.6 SMOOTH_PRED formula applied to those two 1D
  edges using the real `Sm_Weights_Tx_32x32` table -- i.e. this block's
  content IS what a real SMOOTH_PRED reconstruction from its real
  neighbors would produce, giving the real encoder's RD search a genuine
  incentive to choose SMOOTH_PRED over DC_PRED (which ignores all spatial
  variation) or SMOOTH_V_PRED/SMOOTH_H_PRED (each of which ignores one of
  the two edges this content varies along). Confirmed (not assumed) by
  actually decoding and inspecting the real chosen YMode: the real encoder
  chose DC_PRED for the first three leaves (eob 0/67/78) and SMOOTH_PRED
  for the bottom-right leaf (eob 1 -- a near-zero residual, consistent with
  the content matching the SMOOTH_PRED formula almost exactly), and the
  full reconstruction is bit-exact (no tolerance) against dav1d's
  independent decode of the same bitstream. See
  `test/av1/decode_block_test.cljk`'s `smooth-pred-64x64-bit-exact-test`.
- **Explicitly NOT covered by this extension**: chroma (Cb/Cr) + luma
  SMOOTH_PRED (see above); SMOOTH_V_PRED/SMOOTH_H_PRED (the two 1D
  simplifications of 7.11.2.6, not implemented -- `av1.decode-block`
  throws `ex-info` if the real encoder ever picks either); D45/D135/D113/
  D157/D203/D67 (directional modes with nonzero angle, same as the PAETH
  extension's note above).

### Inter zero-motion-baseline extension (ADR-2607122000 Migration step 9, continued -- first inter-frame support)

This repo's first pixel-reconstruction milestones above were all
**intra-only** (keyframes). This extension adds the first real support for
**inter frames** (`frame_type == INTER_FRAME`), narrowed the same way
`org-iso-h264`'s task #20 narrowed its own first inter-frame milestone:
start from real, unmodified static content where an actual encoder's own
motion search lands on effectively zero motion, rather than hand-crafting a
bitstream or assuming what the encoder would choose. Fetched/transcribed
2026-07-13 from AOMediaCodec/av1-spec master (06.bitstream.syntax.md
#Uncompressed header syntax / #Interpolation filter syntax / #Frame
reference mode syntax / #Skip mode params syntax / #Global motion params
syntax / #Inter frame mode info syntax / #Is inter syntax / #Ref frames
syntax / #Inter block mode info syntax / #Assign MV syntax / #MV syntax /
#MV component syntax / #Get transform set function / #Transform type
syntax, 07.bitstream.semantics.md, 08.decoding.process.md #Motion vector
prediction processes (7.10.2, "Find MV stack process" and its
sub-processes) / #Inter prediction process, 09.parsing.process.md's cdf
selection for `is_inter`/`single_ref_p1..p6`/`new_mv`/`zero_mv`/`ref_mv`/
`inter_tx_type`/mv syntax elements, 10.additional.tables.md).

**Scope, and why it's narrow enough to still be exact (not an
approximation)**: a single leaf covering the WHOLE frame (`av1.tile-group`
needed no changes at all -- `avail-u?`/`avail-l?` are simply both false
for this shape, the same precondition the very first DC_PRED-only intra
milestone relied on), single reference (`LAST_FRAME` only, no compound),
and `error_resilient_mode == 1` + `enable_order_hint == 0` at the frame
level (both real, checkable frame-header fields, enforced by
`av1.frame-header/parse`'s inter-frame guard and
`av1.decode-block/guard-frame-scope!`'s inter-frame guards) -- these two
flags alone collapse an enormous amount of AV1's inter-frame machinery
into zero-bit or trivially-computed cases, not by luck but by the spec's
own conditionals:

- `error_resilient_mode == 1` forces `primary_ref_frame =
  PRIMARY_REF_NONE` (so CDFs reset to the spec's defaults exactly like a
  keyframe, no cross-frame CDF-state carryover to implement),
  `use_ref_frame_mvs = 0` (no `motion_field_estimation()`/temporal-MV
  scan needed), `allow_warped_motion = 0` (no warped-motion syntax at
  all), and (combined with `frame_size_override_flag` never both true and
  `!error_resilient_mode`) always the plain `frame_size()`/`render_size()`
  path over `frame_size_with_refs()` (which would need cross-frame
  `RefUpscaledWidth`/`RefFrameHeight` state).
- `enable_order_hint == 0` forces `frame_refs_short_signaling = 0`
  (`set_frame_refs()`'s short-signaling derivation never needed -- every
  one of the 7 `ref_frame_idx[i]` slots is a real, always-present `f(3)`
  read) and `skipModeAllowed = 0` unconditionally (`skip_mode_params()`'s
  entire `forwardIdx`/`backwardIdx` `RefOrderHint` search is structurally
  unreachable, not merely unexercised).
- Every `GmType` forced `IDENTITY` (`av1.decode-block/guard-frame-scope!`
  throws otherwise) makes `GLOBALMV`'s predicted motion vector exactly
  `(0,0)` (setup global mv process, spec 7.10.2.1) -- the load-bearing
  fact this whole extension's "zero motion" claim rests on.
- With no available spatial neighbor (this namespace's only supported
  leaf shape) and `use_ref_frame_mvs=0`, **every** candidate-search step
  of `find_mv_stack()` (spec 7.10.2's scan_row/scan_col/scan_point/
  temporal-scan processes) is a structural no-op: `is_inside()` (spec
  #Is inside function) is false for every candidate location adjacent to
  `(0,0)` (they're outside `MiRowStart`/`MiColStart`), so `NumMvFound`
  never leaves 0. The extra search process (7.10.2.12) then fills BOTH
  `RefStackMv[0][0]` and `RefStackMv[1][0]` with `GlobalMvs[0]` (== `(0,0)`)
  without incrementing `NumMvFound` (per the spec's own note) -- this is
  the ONE case `av1.decode-block/find-mv-stack-degenerate` implements
  (throws for any other `avail-u?`/`avail-l?` combination rather than
  silently returning a wrong answer). The context and clamping process
  (7.10.2.14) then gives `NewMvContext = Min(TotalMatches=0,1) = 0`,
  `RefMvContext = TotalMatches = 0`, `ZeroMvContext = 0` -- all fixed,
  real values, not guessed.

**Real-data finding that changed the original design**: this extension was
designed expecting the real encoder to choose `GLOBALMV` or `NEWMV` (the
task's original framing). Actually decoding the real fixture showed the
encoder chose **`NEARESTMV`** instead (`new_mv=1`, `zero_mv=1`, `ref_mv=0`)
-- confirmed by inspection, not assumed. Rather than treat this as
out-of-scope, `av1.decode-block/read-inter-y-mode`/`assign-mv` show
NEARESTMV (and, by the identical argument, NEARMV) resolve to exactly the
same `(0,0)` motion vector as GLOBALMV in this exact degenerate scope --
since `RefStackMv[0][0] == RefStackMv[1][0] == GlobalMvs[0]` per the extra
search process above, whichever of the two stack slots
NEARESTMV/NEARMV's `pos` selects is still `(0,0)`, not an approximation.
`RefMvIdx`'s own `drl_mode` reads are structurally unreachable too
(`NumMvFound > idx+1` is always false when `NumMvFound == 0`). NEWMV
remains supported as designed (`read_mv()`/`read_mv_component()`
transcribed in full, spec #MV syntax / #MV component syntax -- real bits,
not a shortcut) -- `assign-mv` throws if a real bitstream's NEWMV ever
resolves to a nonzero MV, since `av1.decode-block/predict-inter-block`
only implements the `(0,0)` motion-compensation case (see below).

**Reference-frame buffer**: `av1.decode-block/make-decode-block-fn` gained
an optional third `ref-frame` argument -- a map `{:luma-plane
:frame-width :frame-height}` describing the ALREADY-DECODED keyframe's
reconstructed luma plane. Callers decode the keyframe first (this
namespace's existing intra path, unchanged), then pass its `:luma-plane`
through to build the inter frame's `decode-block-fn`. This is the ONLY
"reference frame buffer" this extension implements -- there's no
multi-frame DPB/ref_frame_idx-indexed buffer management, since this
namespace only ever supports a 2-frame (keyframe + one inter frame)
sequence with a single stored reference.

**Motion compensation (`predict-inter-block`)**: per the task's own
sanctioned simplification (mirroring `org-iso-h264`'s zero-motion
baseline), a genuinely `(0,0)` motion vector with no reference-frame
scaling (`av1.decode-block` asserts both, throws otherwise) makes the
general subpel-scaling + 8-tap-convolution machinery (spec #Motion vector
scaling process / #Block inter prediction process) provably reduce to a
direct, integer-aligned sample copy from the reference plane -- not
merely a shortcut assumed equivalent: the motion vector scaling process's
`origX`/`origY` land exactly on the unshifted sample center (`mv`
contributes 0), there is no scale (`xScale`/`yScale` both exactly
`1<<REF_SCALE_SHIFT`), and the block inter prediction process's 8-tap
filter at zero subpel phase is the identity filter (`Subpel_Filters` row
0 is `{0,0,0,128,0,0,0,0}`, i.e. `Round2(128*sample, 7) == sample`).
`av1.transform`/`av1.intra-pred` needed no changes -- inter blocks reuse
the SAME `decode-transform-block`/`read-coeffs`/dequantize/inverse-DCT
pipeline luma intra blocks already use, just with `predict-inter-block`'s
reference-copy prediction (via a new `inter-ref` parameter) instead of
`predict-intra`.

**`transform_type()`/`get_tx_set()` needed a genuinely new branch for
inter blocks** (not reused as-is from intra): unlike intra TX_32X32 (where
`Tx_Size_Sqr_Up[TX_32X32] == TX_32X32` forces `TX_SET_DCTONLY`, zero
bits), the SAME check for `is_inter == 1` forces `TX_SET_INTER_3`
instead (spec #Get transform set function: `if (is_inter) { if
(reduced_tx_set || txSzSqrUp == TX_32X32) return TX_SET_INTER_3 }` --
checked BEFORE the `is_inter==0` branch's own DCTONLY case) -- a REAL
2-symbol `inter_tx_type` cdf read against
`Default-Inter-Tx-Type-Set3-Cdf[Tx_Size_Sqr[TX_32X32]]` (spot-checked:
`TileInterTxTypeSet3Cdf[Tx_Size_Sqr[txSz]]`, NOT indexed by q_ctx_idx like
this repo's other coefficient tables), decoding to `{IDTX, DCT_DCT}` --
`IDTX` throws (no identity-transform reconstruction, same restriction as
the ADST extension's `V_DCT`/`H_DCT`). This means inter TX_32X32 blocks
are NOT zero-bit-forced DCT_DCT the way intra TX_32X32 blocks are --
confirmed by real data (see below): the residual fixture's real inter
block DOES read a real `inter_tx_type` bit (decoding to `:DCT_DCT`).

**`is_inter`/`read_ref_frames()`/`new_mv`/`zero_mv`/`ref_mv` real cdf
reads** (`av1.decode-block/read-is-inter`/`read-ref-frame`/
`read-inter-y-mode`): `is_inter`'s ctx is 0 for this namespace's only
supported (no-neighbor) shape (the full 4-context
`Default-Is-Inter-Cdf` table is transcribed, but only row 0 is ever
exercised); `read-ref-frame` restricts `RefFrame[0]` to `LAST_FRAME`
(`single_ref_p1==0`, `single_ref_p3==0`, `single_ref_p4==0`, ctx=1 for all
three per `count_refs`/`ref_count_ctx` with no neighbors) -- throws for
any other decoded reference (structurally reachable in the general spec,
but this namespace's only stored reference IS `LAST_FRAME`, so this is
exact for its scope, not an artificial restriction). `comp_mode` is never
read at all (`reference_select == 0`, guaranteed by
`guard-frame-scope!`), so `read-ref-frame` never needs the compound
branch.

**Explicitly NOT covered by this extension**: compound prediction (2
references averaged/weighted); any reference other than `LAST_FRAME`;
OBMC/local-warped motion (`read_motion_mode()` -- `is_motion_mode_switchable
== 0` is required at the frame level, guaranteed by
`guard-frame-scope!`, so `motion_mode` is always `SIMPLE` with zero bits,
and the general function's block-size/`GmType`/
`has_overlappable_candidates`/`find_warp_samples` guards are never
reached); interintra (`enable_interintra_compound` must be 0);
`SWITCHABLE` interpolation filter (`interpolation_filter` must be a fixed
frame-level value, not `SWITCHABLE` -- this namespace's fixtures all
decode a fixed `EIGHTTAP`, so no per-block `interp_filter` reads are ever
needed; guarded, not merely unexercised); any nonzero global motion type
(ROTZOOM/TRANSLATION/AFFINE); any real spatial neighbor for
`find_mv_stack()` (multi-leaf inter frames, i.e. more than one leaf per
frame, are out of scope -- `av1.decode-block` throws
`:unsupported-inter-avail-neighbor` rather than silently mis-predicting);
chroma (Cb/Cr) for inter frames (monochrome only, guarded); any nonzero
motion vector (subpel motion compensation, needing the real 8-tap
`Subpel_Filters` convolution, is not implemented); `SWITCH_FRAME`;
`frame_id_numbers_present_flag`'s cross-frame `RefValid`/`mark_ref_frames`
tracking (the per-ref `delta_frame_id_minus_1` bits ARE read to keep bit
position correct -- this repo's real fixtures have
`frame_id_numbers_present_flag == 1`, an aomenc default -- but the
resulting `expectedFrameId[]` is discarded, not tracked).

**Real-decode validation**: two new REAL aomenc (libaom 3.14.1)-encoded
32x32 MONOCHROME 2-frame (keyframe + inter) sequences (see
`test/av1/fixtures.cljk`'s `inter-32x32-zeromv-bytes`/
`inter-32x32-zeromv-residual-bytes` docstrings for the full aomenc
invocations and real-encoder findings):

- `inter-32x32-zeromv`: both frames byte-identical content (the same
  two-axis brightness-ramp family as `keyframe-32x32-gradient-bytes`).
  Confirmed by actually decoding: frame 2 is a real `INTER_FRAME` with
  `error_resilient_mode=1`, `primary_ref_frame=PRIMARY_REF_NONE`,
  `ref_frame_idx=[0 0 0 0 0 0 0]`, `is_motion_mode_switchable=0`,
  `interpolation_filter=EIGHTTAP` (not SWITCHABLE), every `GmType=IDENTITY`
  -- and the one leaf decodes `is_inter=1`, `RefFrame[0]=LAST_FRAME`,
  `YMode=NEARESTMV` (14, the real-data surprise above), real decoded
  `Mv=(0,0)`, `skip=true` (zero residual -- `aomdec --framestats` confirms
  frame 2's `qp,128`, the max qindex, with only 31 bytes of payload). Both
  frames' full reconstructions are bit-exact (no tolerance) against
  dav1d's independent decode of the same bitstream. See
  `test/av1/decode_block_test.cljk`'s `inter-zeromv-bit-exact-test`.
- `inter-32x32-zeromv-residual`: frame 2 adds a per-pixel checkerboard
  perturbation (+/-6, no translational structure for a real motion search
  to exploit) to the same base ramp, forcing a genuine nonzero residual
  while keeping the real motion search at zero motion -- exercises
  `decode-transform-block`'s `inter-ref` residual-add path (predict_inter
  THEN coeffs()/dequantize/inverse-DCT/reconstruct) for the first time.
  Confirmed by actually decoding: same `is_inter=1`/`RefFrame[0]=LAST_FRAME`/
  `YMode=NEARESTMV`/`Mv=(0,0)` as above, but `skip=false`, a real
  `inter_tx_type` cdf read decoding `:DCT_DCT` (not `:IDTX`), `eob=1024`
  (every coefficient position nonzero -- the checkerboard content is
  maximally high-frequency), and the full reconstruction (predict_inter +
  real coefficient decode + dequantize + inverse DCT + reconstruct) is
  bit-exact against dav1d's independent decode. See
  `test/av1/decode_block_test.cljk`'s `inter-zeromv-residual-bit-exact-test`.

## Validation

`av1.obu-test`/`av1.sequence-header-test`/`av1.frame-header-test` validate
against a **real SVT-AV1-encoded stream** (`resources/av1/fixtures/
keyframe-64x48.obu`, checked in), generated with:

```sh
ffmpeg -y -f lavfi -i "testsrc=size=64x48:rate=1" -frames:v 1 \
  -pix_fmt yuv420p -c:v libsvtav1 -f obu keyframe-64x48.obu
```

(ffmpeg 8.1.1, `libsvtav1` encoder -- `-f obu` emits the spec's "low
overhead bitstream format" directly, no container/length-stripping
needed). The decoded `max_frame_width`/`max_frame_height` (sequence
header) and `frame_width`/`frame_height` (frame header, via a completely
different syntax path: `frame_size()`/`superres_params()`/
`compute_image_size()`) both independently come out to exactly 64x48 --
the same "real encoder output, cross-checked dimensions" validation level
as `org-iso-h264`'s `h264.sps-test` against real libx264 output.

`av1.bool-decoder-test` validates the symbol decoder against **hand-
derived bit vectors**: the spec's `init_symbol`/`read_symbol` arithmetic is
executed by hand (documented step by step in the test namespace's
docstring) for two contrasting inputs (all-zero bits, all-one bits) with
`sz=2` bytes, since a real encoded tile requires the full pixel-
reconstruction pipeline this phase doesn't build. Real-data validation of
the bool decoder (through real CDF tables and real symbol reads, just not
yet through `decode_block()`) now happens via `av1.tile-group-test`, below.

`av1.frame-header-test` additionally validates the `segmentation_params()`
through `film_grain_params()` continuation against `keyframe-256x192.obu`
(see below), including an **independent cross-check against `aomdec`** (the
official AOM reference decoder, libaom 3.14.1): `aomdec
--framestats=out.csv keyframe-256x192.obu` reports `qp,116` for this frame,
exactly matching this repo's decoded `:base-q-idx`.

`av1.tile-group-test` validates `tile_group_obu()`/`decode_partition()`
against two more real SVT-AV1-encoded streams:

- `keyframe-256x192.obu` (4x3 grid of 64x64 superblocks, `testsrc2` content
  so the encoder actually produces varied partition splits):
  ```sh
  ffmpeg -y -f lavfi -i "testsrc2=size=256x192:rate=1" -frames:v 1 \
    -pix_fmt yuv420p -c:v libsvtav1 -f obu keyframe-256x192.obu
  ```
  Cross-checked against `libdav1d` (via `ffmpeg -loglevel debug`, a
  completely independent AV1 decoder): `Frame 0: size 256x192 upscaled 256
  render 256x192 subsample 2x2 bitdepth 8 tiles 1x1` matches this repo's
  decoded frame-width/upscaled-width/render-width/render-height/tile-cols/
  tile-rows exactly. Validates that every one of the 12 superblocks'
  `decode-partition` walk completes without throwing or running off the end
  of the tile buffer, and that a real, content-varied encode exercises a
  genuine structural variety of partition types (not just
  `PARTITION_NONE`) through the CDF-table/context-derivation/bool-decoder
  wiring.
- `keyframe-32x32-split.obu` (deliberately sized so `MiRows == MiCols == 8`):
  ```sh
  ffmpeg -y -f lavfi -i "testsrc2=size=32x32:rate=1" -frames:v 1 \
    -pix_fmt yuv420p -c:v libsvtav1 -f obu keyframe-32x32-split.obu
  ```
  With a 64x64 superblock, `decode_partition()`'s top-level call has
  `hasRows = hasCols = false`, which per spec forces `partition =
  PARTITION_SPLIT` with **zero bits/symbols read** -- a deterministic,
  content-independent assertion (unlike the 256x192 tree shape, which past
  the first leaf partition is not bit-exact against the real stream; see
  `av1.tile-group`'s namespace docstring for why).

### Pixel reconstruction (`av1.decode-block`, `av1.tables`, `av1.transform`, `av1.intra-pred`)

`av1.decode-block-test` validates the full decode_block() pipeline --
mode_info, read_block_tx_size, coeffs() (CDF-adapted coefficient decode),
dequantization, inverse DCT, DC prediction, reconstruction -- against TWO
REAL **aomenc** (libaom 3.14.1)-encoded 32x32 monochrome keyframes,
comparing this repo's reconstructed luma plane against **`dav1d`'s
independent decode of the same bitstream, bit-exactly (no tolerance)**:

- `keyframe-32x32-gradient.obu`: a smooth two-axis brightness ramp (base
  128 +/- 20 across x, +/- 4 across y, authored as known raw pixel bytes --
  not a lavfi filter -- so the exact input is reproducible). eob=7 (few
  nonzero coefficients).
- `keyframe-32x32-busy.obu`: a busier two-axis sinusoidal-plus-ramp
  pattern, same encoder scope restrictions, eob=67 -- exercises far more of
  the coefficient-context derivation and per-context CDF adaptation within
  the same single TX_32X32 transform block.

Both were encoded with every non-DC_PRED intra mode, every non-NONE/SPLIT
partition type, CDEF/loop-filter/loop-restoration, and TX_MODE_SELECT
disabled at the encoder, so DC_PRED and TX_32X32/PARTITION_NONE are the
**only options the bitstream could contain** -- not merely the likely
outcome for smooth content (see `av1.decode-block`'s namespace docstring
for why TX_32X32 is also the one size for which `transform_type()` is
*structurally* forced to DCT_DCT, zero bits, by `get_tx_set()`):

```sh
aomenc --codec=av1 --limit=1 --passes=1 --end-usage=q --cq-level=32 \
  --monochrome --enable-cdef=0 --enable-restoration=0 --loopfilter-control=0 \
  --enable-filter-intra=0 --enable-smooth-intra=0 --enable-paeth-intra=0 \
  --enable-directional-intra=0 --enable-angle-delta=0 --enable-intrabc=0 \
  --enable-palette=0 --enable-qm=0 --enable-tx64=0 --enable-rect-tx=0 \
  --enable-rect-partitions=0 --enable-ab-partitions=0 --enable-1to4-partitions=0 \
  --enable-tx-size-search=0 --tile-columns=0 --tile-rows=0 \
  --kf-min-dist=1 --kf-max-dist=1 \
  --obu -o keyframe-32x32-gradient.obu keyframe-32x32-gradient.y4m

dav1d -i keyframe-32x32-gradient.obu -o keyframe-32x32-gradient.dav1d.yuv
```

(aomenc/libaom 3.14.1, dav1d 1.5.3, both from Homebrew, generated
2026-07-13; both `.obu` and the corresponding `.dav1d.yuv` golden output
are checked in under `resources/av1/fixtures/` -- see
`test/av1/fixtures.cljk` docstrings for exactly how each was produced).
`av1.decode-block-test` additionally checks that the frame really did
decode to the expected single BLOCK_32X32/PARTITION_NONE/TX_32X32 leaf
shape (not merely that it happened not to throw), and a third test
(`guard-frame-scope-throws-test`) confirms out-of-scope frame headers
(lossless, non-monochrome, non-TX_MODE_LARGEST) are rejected with
`ex-info` rather than silently mis-decoded.

Not yet exercised against real data (see the "Explicitly NOT implemented"
list above): any transform size other than TX_32X32, ADST/IDTX/FLIPADST
transform types, chroma planes, and inter prediction.

### V_PRED / H_PRED (`av1.decode-block-test`, `keyframe-64x64-vpred`/`keyframe-64x64-hpred`)

Validates the mode-coverage extension against TWO REAL aomenc-encoded
64x64 monochrome keyframes -- unlike the 32x32 fixtures above, each is a
real **multi-leaf** frame (one 64x64 superblock forced into a 2x2 grid of
BLOCK_32X32 leaves):

```sh
aomenc --codec=av1 --limit=1 --passes=1 --end-usage=q --cq-level=32 \
  --monochrome --enable-cdef=0 --enable-restoration=0 --loopfilter-control=0 \
  --enable-filter-intra=0 --enable-smooth-intra=0 --enable-paeth-intra=0 \
  --enable-directional-intra=1 --enable-diagonal-intra=0 \
  --enable-angle-delta=0 --enable-intrabc=0 --enable-palette=0 \
  --enable-qm=0 --enable-tx64=0 --enable-rect-tx=0 \
  --enable-rect-partitions=0 --enable-ab-partitions=0 --enable-1to4-partitions=0 \
  --enable-tx-size-search=0 --min-partition-size=32 --max-partition-size=32 \
  --tile-columns=0 --tile-rows=0 --kf-min-dist=1 --kf-max-dist=1 \
  --obu -o keyframe-64x64-vpred.obu keyframe-64x64-vpred.y4m

dav1d -i keyframe-64x64-vpred.obu -o keyframe-64x64-vpred.dav1d.yuv
```

(same aomenc/dav1d versions, generated 2026-07-13; `keyframe-64x64-hpred`
uses identical flags with transposed content -- see `test/av1/fixtures.cljk`
docstrings for exactly how each fixture's content was designed to make a
real encoder RD decision, not a hand-picked bit pattern, land on this
exact shape). `--enable-directional-intra=1 --enable-diagonal-intra=0` is
a libaom flag pair that permits V_PRED/H_PRED specifically while keeping
every *diagonal* directional mode (D45..D203) disabled, so `{DC_PRED,
V_PRED, H_PRED}` are structurally the only modes these bitstreams could
contain. `--min-partition-size=32 --max-partition-size=32` forces the
64x64 superblock's partition decision to be a real, normally-signaled
`PARTITION_SPLIT` (not a probabilistic RDO outcome), producing exactly 4
BLOCK_32X32 leaves.

`av1.decode-block-test` confirms (not merely infers) that the real
encoder chose `DC_PRED` for the first three leaves (top-left/top-right/
bottom-left) and `V_PRED`/`H_PRED` respectively for the fourth
(bottom-right) -- i.e. this repo observed which mode a real encoder
picked rather than assuming it -- and that the reconstructed 64x64 luma
plane is bit-exact against dav1d's independent decode of the same
bitstream. This is also the regression test for the `intra_angle_info_y()`
bug this extension's own development surfaced (see the mode-coverage
section above): the bitstream desync that bug caused was invisible in a
plain diff-count check (many pixels were "close" -- off by 1-7 levels in
a smooth, plausible-looking pattern) and was only caught by requiring
exact equality against the independent reference decode.

Not yet exercised against real data (in this multi-leaf luma context):
any intra mode other than DC_PRED/V_PRED/H_PRED, a nonzero `AngleDeltaY`
(this repo's V_PRED/H_PRED only handle pAngle exactly 90/180, throwing
otherwise), any transform size other than TX_32X32, ADST/IDTX/FLIPADST
transform types, MULTI-leaf chroma planes (single-leaf chroma IS now
exercised, see below), and inter prediction.

### Chroma (Cb/Cr) decode (`av1.decode-block-test`, `keyframe-32x32-color`/`keyframe-32x32-color-busy`)

Validates the chroma-decode extension against TWO REAL aomenc-encoded
32x32 4:2:0 COLOR keyframes (real, non-flat Cb/Cr data -- NOT
`--monochrome`), comparing this repo's reconstructed luma AND Cb AND Cr
planes against **dav1d's independent decode of the same bitstream,
bit-exactly (no tolerance) on all three planes**:

- `keyframe-32x32-color.obu`: luma is the same two-axis brightness-ramp
  family as `keyframe-32x32-gradient.obu`; Cb is a 16x16 ramp across x
  (base 100, +/-24); Cr is a 16x16 ramp across y (base 160, +/-18) --
  three genuinely different profiles per plane (authored as known raw
  I420 pixel bytes, not a lavfi filter). eob=16 (luma) / 7 (Cb) / 10 (Cr).
- `keyframe-32x32-color-busy.obu`: busier sinusoidal-plus-ramp content on
  all three planes, each at a different frequency/phase, exercising far
  more of `get-coeff-base-ctx`/`get-coeff-br-ctx` (including the
  coeff_br/golomb continuation paths) and the U/V planes' SHARED
  coefficient-cdf adaptation state (see the chroma-decode section above)
  across many more symbol reads. eob=190 (luma) / 66 (Cb) / 105 (Cr).

Both encoded with the same disabled-everything-but-DC-and-NONE/TX_32X32
baseline as the gradient/busy luma fixtures, PLUS `--enable-cfl-intra=0`
(so `UV_CFL_PRED` can never be the encoder's choice -- combined with the
pre-existing `--enable-smooth-intra=0 --enable-paeth-intra=0
--enable-directional-intra=0`, which also gate the corresponding UV
modes, `{DC_PRED}`/`{UV_DC_PRED}` are structurally the only modes left for
the encoder to choose for luma/chroma respectively, not merely the likely
outcome for smooth content):

```sh
aomenc --codec=av1 --limit=1 --passes=1 --end-usage=q --cq-level=32 \
  --enable-cdef=0 --enable-restoration=0 --loopfilter-control=0 \
  --enable-filter-intra=0 --enable-smooth-intra=0 --enable-paeth-intra=0 \
  --enable-directional-intra=0 --enable-angle-delta=0 --enable-intrabc=0 \
  --enable-palette=0 --enable-cfl-intra=0 --enable-qm=0 --enable-tx64=0 \
  --enable-rect-tx=0 --enable-rect-partitions=0 --enable-ab-partitions=0 \
  --enable-1to4-partitions=0 --enable-tx-size-search=0 \
  --tile-columns=0 --tile-rows=0 --kf-min-dist=1 --kf-max-dist=1 \
  --obu -o keyframe-32x32-color.obu keyframe-32x32-color.y4m

dav1d -i keyframe-32x32-color.obu -o keyframe-32x32-color.dav1d.yuv
```

(aomenc/libaom 3.14.1, dav1d 1.5.3, both from Homebrew, generated
2026-07-13; both `.obu` and the corresponding `.dav1d.yuv` golden I420
output -- 1024 Y + 256 U + 256 V bytes -- are checked in under
`resources/av1/fixtures/`; see `test/av1/fixtures.cljk` docstrings for
exactly how each was produced). `av1.decode-block-test` additionally
confirms (not merely infers) the real encoder chose DC_PRED/UV_DC_PRED
and the single BLOCK_32X32/PARTITION_NONE/TX_32X32(luma)/TX_16X16(chroma)
leaf shape.

Not yet exercised against real data (at the time these two fixtures were
authored; see the multi-leaf-chroma extension below): MULTI-leaf color
frames, any UVMode other than UV_DC_PRED (including UV_CFL_PRED),
4:2:2/4:4:4 chroma subsampling, any chroma transform size other than
TX_16X16, and inter prediction.

### Multi-leaf chroma (`av1.decode-block-test`, `keyframe-64x64-color-multileaf`)

Validates the multi-leaf-chroma extension against a REAL aomenc-encoded
64x64 4:2:0 COLOR keyframe, forced (via `--min-partition-size=32
--max-partition-size=32`, same technique as `keyframe-64x64-vpred.obu`) into
a real 2x2 grid of BLOCK_32X32 luma leaves -- each leaf gets its OWN
independent BLOCK_16X16 Cb/Cr block, comparing this repo's reconstructed
luma AND Cb AND Cr planes against **dav1d's independent decode of the same
bitstream, bit-exactly (no tolerance) on all three planes**. Content uses a
DIFFERENT frequency+amplitude sinusoidal combination per quadrant per plane
(not merely a phase shift), so the 4 leaves have genuinely different
coefficient complexity -- confirmed empirically: `:eob`/`:u-eob`/`:v-eob`
are 16/7/6 (top-left), 154/92/78 (top-right), 67/29/16 (bottom-left),
277/121/136 (bottom-right), all pairwise distinct per plane, and the 4
leaves' reconstructed 16x16 Cb/Cr quadrants (pulled directly out of the
shared 32x32 plane buffers) are pairwise distinct pixel content -- both
confirm 4 genuinely independently-decoded chroma blocks, not one leaf's
result reused/broadcast across all 4 (see `test/av1/fixtures.cljk`'s
docstring for the exact aomenc invocation and content formulas, and
`test/av1/decode_block_test.cljk`'s `multi-leaf-color-64x64-bit-exact-test`
for the assertions). A companion test (`shared-chroma-block-throws-test`)
confirms that a leaf whose `mi-size` is NOT BLOCK_32X32 (the AV1 spec's
"shared chroma block" case for small luma partitions) is rejected with
`ex-info` (`:reason :unsupported-shared-chroma-block`) rather than silently
mis-decoded, per this extension's scope boundary (see the multi-leaf-chroma
section above).

Not yet exercised against real data: shared chroma blocks (small luma
partitions below BLOCK_32X32, where multiple luma leaves would share one
chroma block -- this repo's luma leaf-size support doesn't reach that case
via any other guard either, see `av1.decode-block`'s namespace docstring),
any UVMode other than UV_DC_PRED (including UV_CFL_PRED), 4:2:2/4:4:4
chroma subsampling, any chroma transform size other than TX_16X16, and
inter prediction.

### Partition scope boundary (`av1.decode-block-test`, `keyframe-64x64-split16`)

The two extensions above (single-leaf DC_PRED, then real multi-leaf
DC_PRED/V_PRED/H_PRED) both stay at exactly BLOCK_32X32/TX_32X32 per leaf.
This fixture validates the *boundary* of that scope against a REAL encoded
stream, rather than only via direct table lookup: `keyframe-64x64-split16.obu`
is a real aomenc-encoded 64x64 monochrome keyframe forced (via
`--min-partition-size=16 --max-partition-size=16`) two real recursion
levels deep (64x64 -> 32x32 -> 16x16, each level a genuinely coded
`partition` symbol, not a zero-bit structural forcing). Confirmed (not
assumed): `av1.tile-group/decode-partition`'s first bit-exact-valid leaf is
BLOCK_16X16/PARTITION_NONE at (0,0), and wiring `av1.decode-block`'s
`decode-block-fn` in to decode this same real bitstream throws `ex-info`
(`:reason :unsupported-tx-size`, `:mi-size` BLOCK_16X16, `:tx-size`
TX_16X16) at exactly that leaf -- i.e. `av1.decode-block`'s scope guard for
non-BLOCK_32X32 leaves (any deeper `PARTITION_SPLIT` recursion, or a
`PARTITION_HORZ`/`PARTITION_VERT` rectangular leaf, since neither maps to
`Max_Tx_Size_Rect[MiSize] == TX_32X32`) is exercised end-to-end against a
real bitstream and fails safely (a clear `ex-info`, not a silent
mis-decode or an uncontrolled crash) rather than merely being asserted by
inspecting `av1.tables/Max-Tx-Size-Rect` directly. See
`test/av1/fixtures.cljk`/`test/av1/decode_block_test.cljk`
(`split16-throws-on-block16x16-test`) for the exact aomenc invocation and
assertions.

Extending real reconstruction to cover these deeper/rectangular leaf
shapes (BLOCK_16X16 and smaller, and the rectangular HORZ/VERT/HORZ_A/
HORZ_B/VERT_A/VERT_B/HORZ_4/VERT_4 leaf shapes) is next-phase work: it
needs both a non-TX_32X32 `get_tx_set()`/dequant/inverse-transform path
(TX_16X16 alone is DCT_DCT-safe per `get_tx_set()`'s rules the same way
TX_32X32 is, so that specific combination could land without ADST, but
rectangular tx sizes/other square sizes below TX_32X32 are not
structurally DCT_DCT-guaranteed and would need `get_tx_set()`'s general
case plus ADST support) -- deliberately not pursued in this pass per this
repo's practice of landing one narrow, fully-validated extension at a
time rather than spreading across scope axes.

### PAETH_PRED (`av1.decode-block-test`, `keyframe-64x64-paeth`)

Validates the PAETH_PRED mode-coverage extension (see its section above)
against a REAL aomenc-encoded 64x64 monochrome keyframe -- like
`keyframe-64x64-vpred`/`keyframe-64x64-hpred`, a real **multi-leaf** frame
(one 64x64 superblock forced into a 2x2 grid of BLOCK_32X32 leaves):

```sh
aomenc --codec=av1 --limit=1 --passes=1 --end-usage=q --cq-level=32 \
  --monochrome --enable-cdef=0 --enable-restoration=0 --loopfilter-control=0 \
  --enable-filter-intra=0 --enable-smooth-intra=0 --enable-paeth-intra=1 \
  --enable-directional-intra=0 --enable-angle-delta=0 --enable-intrabc=0 \
  --enable-palette=0 --enable-qm=0 --enable-tx64=0 --enable-rect-tx=0 \
  --enable-rect-partitions=0 --enable-ab-partitions=0 --enable-1to4-partitions=0 \
  --enable-tx-size-search=0 --min-partition-size=32 --max-partition-size=32 \
  --tile-columns=0 --tile-rows=0 --kf-min-dist=1 --kf-max-dist=1 \
  --obu -o keyframe-64x64-paeth.obu keyframe-64x64-paeth.y4m

dav1d -i keyframe-64x64-paeth.obu -o keyframe-64x64-paeth.dav1d.yuv
```

(same aomenc/dav1d versions as the rest of this repo's fixtures, generated
2026-07-13). Unlike `--enable-directional-intra=1 --enable-diagonal-intra=0`
(the vpred/hpred fixtures' flag pair, which keeps V_PRED/H_PRED legal),
this fixture disables directional modes outright
(`--enable-directional-intra=0`) since V_PRED/H_PRED aren't needed here --
combined with `--enable-paeth-intra=1` (libaom's default) and the
pre-existing `--enable-smooth-intra=0`/`--enable-palette=0`/etc.,
`{DC_PRED, PAETH_PRED}` are structurally the only legal luma modes this
encode could produce. Content is a single continuous diagonal linear ramp
across the whole 64x64 frame, `pixel(x,y) = clamp(128 + 1.5*(x-32) -
1.5*(y-32))` -- additively separable, so PAETH_PRED's `base =
AboveRow[j]+LeftCol[i]-AboveRow[-1]` formula (a discrete-Laplacian test)
reconstructs it with near-zero residual, the classic content class Paeth
prediction favors (see the extension section above for the derivation).

`av1.decode-block-test` confirms (not merely infers) that the real
encoder chose `DC_PRED` for the top-left (no neighbors) and bottom-right
(both neighbors -- an empirically observed RD outcome, not the a priori
expectation when this content was designed) leaves, and `PAETH_PRED` for
the top-right and bottom-left leaves (each with exactly one real
neighbor) -- i.e. this repo observed which mode a real encoder picked
rather than assuming it -- and that the reconstructed 64x64 luma plane is
bit-exact against dav1d's independent decode of the same bitstream.

Not yet exercised against real data (as of the PAETH_PRED extension):
chroma (Cb/Cr) + luma PAETH_PRED (explicitly guarded against, see the
extension section above), SMOOTH*/D45/D135/D113/D157/D203/D67 intra modes,
any transform size other than TX_32X32, ADST/IDTX/FLIPADST transform types
(for a PAETH_PRED leaf), and inter prediction.

### SMOOTH_PRED (`av1.decode-block-test`, `keyframe-64x64-smooth`)

Validates the SMOOTH_PRED mode-coverage extension (see its section above)
against a REAL aomenc-encoded 64x64 monochrome keyframe -- again a real
**multi-leaf** frame (one 64x64 superblock forced into a 2x2 grid of
BLOCK_32X32 leaves):

```sh
aomenc --codec=av1 --limit=1 --passes=1 --end-usage=q --cq-level=32 \
  --monochrome --enable-cdef=0 --enable-restoration=0 --loopfilter-control=0 \
  --enable-filter-intra=0 --enable-smooth-intra=1 --enable-paeth-intra=0 \
  --enable-directional-intra=0 --enable-angle-delta=0 --enable-intrabc=0 \
  --enable-palette=0 --enable-qm=0 --enable-tx64=0 --enable-rect-tx=0 \
  --enable-rect-partitions=0 --enable-ab-partitions=0 --enable-1to4-partitions=0 \
  --enable-tx-size-search=0 --min-partition-size=32 --max-partition-size=32 \
  --tile-columns=0 --tile-rows=0 --kf-min-dist=1 --kf-max-dist=1 \
  --obu -o keyframe-64x64-smooth.obu keyframe-64x64-smooth.y4m

dav1d -i keyframe-64x64-smooth.obu -o keyframe-64x64-smooth.dav1d.yuv
```

(same aomenc/dav1d versions as the rest of this repo's fixtures, generated
2026-07-13). `--enable-smooth-intra=1` (libaom's default) combined with
`--enable-directional-intra=0`/`--enable-paeth-intra=0`/the pre-existing
`--enable-palette=0`/etc. leaves `{DC_PRED, SMOOTH_PRED, SMOOTH_V_PRED,
SMOOTH_H_PRED}` as the only structurally legal luma modes this encode
could produce (this repo's `read-y-mode` would throw had the encoder ever
picked SMOOTH_V_PRED/SMOOTH_H_PRED -- it didn't). Content: top-left flat
128 (forces DC_PRED trivially); top-right/bottom-left are 1D sinusoids
invariant along the other axis; bottom-right is authored as the EXACT spec
7.11.2.6 SMOOTH_PRED formula applied to those two edges via the real
`Sm_Weights_Tx_32x32` table -- i.e. this block's content IS what a real
SMOOTH_PRED reconstruction from its real neighbors would produce, the
classic content class that favors a genuine two-edge blend over DC_PRED's
single average or SMOOTH_V/H_PRED's single-edge blend (see the extension
section above for the derivation).

`av1.decode-block-test` confirms (not merely infers) that the real
encoder chose `DC_PRED` for the top-left/top-right/bottom-left leaves and
`SMOOTH_PRED` for the bottom-right leaf (the only leaf with both a real
avail-above and avail-left neighbor, eob=1 -- a near-zero residual
consistent with the content matching the SMOOTH_PRED formula almost
exactly) -- i.e. this repo observed which mode a real encoder picked
rather than assuming it -- and that the reconstructed 64x64 luma plane is
bit-exact against dav1d's independent decode of the same bitstream.

Not yet exercised against real data (as of the SMOOTH_PRED extension):
chroma (Cb/Cr) + luma SMOOTH_PRED (explicitly guarded against, see the
extension section above), SMOOTH_V_PRED/SMOOTH_H_PRED/D45/D135/D113/D157/
D203/D67 intra modes, any transform size other than TX_32X32, ADST/IDTX/
FLIPADST transform types (for a SMOOTH_PRED leaf), and inter prediction.

## Usage

```clojure
(require '[av1.bitreader :as br] '[av1.obu :as obu]
         '[av1.sequence-header :as sh] '[av1.frame-header :as fh]
         '[av1.bool-decoder :as bd] '[av1.tile-group :as tg])

(def r (br/make-reader av1-bytes))
(def o (obu/parse-obu r))                      ; => {:header {...} :obu-size N ...}
(def seq-hdr (sh/parse (:reader-at-payload seq-obu)))
(def frame-hdr (fh/parse (:reader-at-payload frame-obu) seq-hdr))
;; => {:frame-type ... :show-frame ... :frame-width :frame-height
;;     :tile-info {...} :base-q-idx ... :quantization-params {...}
;;     :segmentation-params {...} :loop-filter-params {...} :cdef-params {...}
;;     :lr-params {...} :tx-mode ... :film-grain-params {...} ...}

(def bd-state (bd/init-symbol reader tile-size-bytes))
(def [bit bd-state'] (bd/read-bool bd-state))

;; For a combined OBU_FRAME (frame_header + tile_group in one OBU), the
;; whole frame_obu(sz) -> tile_group_obu(sz) -> decode_partition() walk:
(def result (tg/parse-frame-obu frame-obu seq-hdr))
;; => {:frame-header {...} :tile-group {:tg-start ... :tg-end ...
;;     :tiles [{:tile-row ... :tile-col ... :superblock-partitions [...]}]}}
```

To also get real reconstructed pixels (this phase's narrow scope --
BLOCK_32X32/PARTITION_NONE/TX_32X32/DCT_DCT leaves, DC_PRED/V_PRED/H_PRED
luma, and, for 4:2:0 color streams, UV_DC_PRED-only chroma at a single
whole-frame leaf -- see `av1.decode-block`'s namespace docstring), supply
its `:decode-block-fn`:

```clojure
(require '[av1.decode-block :as db])

(def decode-block-fn (db/make-decode-block-fn frame-hdr seq-hdr))
;; throws ex-info immediately if frame-hdr/seq-hdr are out of scope

(def result (tg/parse-frame-obu frame-obu seq-hdr {:decode-block-fn decode-block-fn}))
(def tile (first (:tiles (:tile-group result))))
(def luma-plane (:luma-plane (:final-tile-state tile)))
;; => flat row-major (MiCols*4) x (MiRows*4) vector of reconstructed 8-bit
;;    luma samples
(def u-plane (:u-plane (:final-tile-state tile))) ; Cb, 4:2:0 color streams only
(def v-plane (:v-plane (:final-tile-state tile))) ; Cr, 4:2:0 color streams only
;; => each a flat row-major (MiCols*4/2) x (MiRows*4/2) vector of
;;    reconstructed 8-bit chroma samples
```

## Encode (2026-07 AV1 encode task, ADR-2607122000 Migration step 9 continuation)

Everything above this section is DECODE (the org's original AV1 phase).
This section adds the first AV1 **encode** support, mirroring
`org-iso-h264`'s own decode-\>encode task methodology: derive the encoder
by inverting the decoder's own transcribed logic (the AV1 spec, like
H.264's, only ever defines the decode side -- there is no spec text for a
"symbol encoding process" or a forward transform to transcribe from), then
validate the result against real, independent decoders rather than
assuming correctness from symmetry with the decode side.

**Scope**, deliberately narrowed to this repo's very first pixel-
reconstruction decode milestone's shape (single BLOCK_32X32 leaf, DC_PRED,
TX_32X32/DCT_DCT, luma only -- **now extended to also cover chroma
(Cb/Cr), see the "Chroma (Cb/Cr) encode extension" section below**) --
not the full range of modes/sizes the decode side has since grown to
support (V_PRED/H_PRED/PAETH/SMOOTH/ADST/inter):

| ns | role |
|---|---|
| `av1.bitwriter` | MSB-first bit writer -- the exact structural inverse of `av1.bitreader`'s descriptors (`f`/`uvlc`/`le`/`leb128`/`su`/`ns`/`byte-alignment`), plus `trailing-bits` (spec 5.3.4's `trailing_one_bit`+zero-pad, distinct from plain `byte-alignment` -- see below). Verified by round-tripping every descriptor back through `av1.bitreader` across a wide value range (`test/av1/bitwriter_test.cljk`) |
| `av1.bool-encoder` | the AV1 Symbol ENCODER -- ported from libaom's real `od_ec_enc_*` family (`aom_dsp/entenc.c`/`entenc.h`, AOMediaCodec/aom master), the actual encode-side counterpart of the daala-derived range coder `av1.bool-decoder` implements the decode side of (there is no spec text for this at all). CDF adaptation is shared with `av1.bool-decoder` via a factored-out `av1.bool-decoder/adapt-cdf` public fn, so both sides are structurally guaranteed to adapt identically. Implementation simplification: never flushes `low`/`cnt` mid-stream (correct but unbounded-growing, safe for this repo's tiny single-keyframe scope) -- **JVM Clojure only** (`.clj`, not `.cljc`: needs true `bigint` arithmetic, which does not exist in ClojureScript's numeric tower, confirmed via clj-kondo -- see its namespace docstring for the full portability note and what a cljs port would need). Verified against `av1.bool-decoder` across thousands of mixed-cdf symbol round-trips (`test/av1/bool_encoder_test.cljk`) |
| `av1.transform` (additions) | `forward-transform-2d`/`quantize` -- the exact forward inverse of the pre-existing `inverse-transform-2d`/`dequantize`, derived by NUMERICALLY PROBING the real inverse transform (not re-derived from an external forward-DCT source) to discover its exact orthonormal-basis scale factor, then confirmed point-by-point against multi-coefficient probes before being relied on (see `forward-transform-2d`'s docstring for the full derivation). Verified: exact round-trip for flat/low-frequency residuals, small bounded lossy error for busier content at a fine quantizer (`test/av1/transform_encode_test.cljk`). Chroma encode extension (see below): the final scale is now a size-dependent `forward-scale` closed form (`2^(7-max(log2,4))`) rather than a hardcoded `TX_32X32`-only constant -- a real bug (factor-of-2 error for `TX_16X16`) this extension's own validation caught and fixed |
| `av1.encode-block` | `write-coeffs`/`write-skip`/`write-y-mode` -- the encode-side inverse of `av1.decode-block`'s `read-coeffs`/`read-skip`/`read-y-mode`, for this section's narrow scope only. Reuses `av1.decode-block`'s own context-derivation helpers directly (`get-coeff-base-ctx`/`get-coeff-br-ctx`/`get-dc-sign-ctx`/`get-txb-skip-ctx-chroma`/`record-above!`/`record-left!`, made public there for exactly this reason -- a visibility-only change, no decode-side logic change) rather than re-transcribing them, so context derivation cannot independently drift between encode and decode. Implements the full `coeff_base`/`coeff_base_eob`/`coeff_br` continuation AND the golomb escape code (`write-golomb`) for real -- not just the common case (see the `busy` fixture below). Chroma encode extension (see below): also `write-uv-mode` -- `write-coeffs` itself needed ZERO changes to serve chroma (already generalized over plane/tx-size via its `spec` argument) |
| `av1.sequence-header`/`av1.frame-header` (additions) | `write` -- narrow encode-side inverses of `parse`, covering exactly the field combination this scope needs (`reduced_still_picture_header=1`, monochrome, single tile, `TX_MODE_LARGEST`, no segmentation/delta-q/delta-lf/CDEF/loop-restoration/film-grain/superres) -- NOT a full general inverse of every `parse` branch. Verified by round-tripping back through `parse` itself (`test/av1/sequence_header_encode_test.cljk`/`test/av1/frame_header_encode_test.cljk`). Chroma encode extension (see below): `av1.sequence-header/write` gained optional `:mono-chrome?` (default `true`), `av1.frame-header/write` gained optional `:color?` (default `false`) -- both byte-for-byte unchanged for every pre-existing caller |
| `av1.obu` (addition) | `write-obu`/`write-obu-header` -- OBU framing (header + leb128 `obu_size` + payload), low-overhead format only, no extension header |
| `av1.encode` | top-level orchestration (`encode-keyframe`): pixels -\> DC_PRED residual -\> forward-transform-2d/quantize -\> `av1.encode-block`/bool-encoder -\> `av1.frame-header`/`av1.sequence-header` `write` -\> OBU framing -\> a complete, standalone, legal AV1 bitstream. Chroma encode extension (see below): optional `:cb`/`:cr` args produce a 4:2:0 color keyframe instead |

**A real, spec-conformance bug this task's own validation caught** (not
assumed away): the first working version of this encoder produced a
bitstream this repo's OWN decoder parsed back correctly, but that real
decoders (`ffmpeg`/`dav1d`) rejected outright ("`trailing_one_bit out of
range: 0, but must be in [1,1]`"). Spec 5.3.2's `open_bitstream_unit()`
wrapper calls `trailing_bits()` (a `1` bit then zero-pad) -- NOT plain
zero-padding -- after any `OBU_SEQUENCE_HEADER`/standalone
`OBU_FRAME_HEADER`/`OBU_METADATA` payload that doesn't already end
byte-aligned; this repo's own decode side never validates that pattern
(it only skips to the declared `obu_size`), so the bug was invisible until
tested against real independent decoders -- exactly the class of error
this repo's decode-side "bit-exact against a real independent decoder, no
tolerance" validation stance exists to catch, now caught on the encode
side too. Fixed via `av1.bitwriter/trailing-bits` (distinct from the
pre-existing plain-zero-pad `byte-alignment`, which remains correct for
`byte_alignment()`'s OTHER call site inside `frame_obu()`).

### Validation

Four fixtures (`resources/av1/fixtures/encode-keyframe-32x32-{flat,dc,
gradient,busy}.obu`), all THIS REPO'S OWN encoder output (not a real
encoder's -- see `test/av1/fixtures.cljk` docstrings for the exact
`av1.encode/encode-keyframe` invocation behind each one), validated
against **two independent real decoders**:

- `dav1d` (1.5.3): `dav1d -i <name>.obu -o <name>.dav1d.yuv` -- succeeds
  (no error) for all four, and this repo's own decode of each fixture is
  **bit-exact (no tolerance)** against dav1d's independent decode
  (`test/av1/encode_test.cljk`'s `dav1d-bit-exact-*-test`s, checked against
  the checked-in `.dav1d.yuv` golden files).
- `aomdec` (libaom 3.14.1, `aomdec --i420 -o ... <name>.obu`): also
  succeeds for all four, with its Y-plane output byte-identical to
  dav1d's -- a second independent decoder implementation agreeing with
  the first (recorded in `test/av1/fixtures.cljk`'s docstrings; not
  re-checked at test time, to keep the test suite hermetic like every
  other test namespace in this repo).

Fixture-by-fixture:

- `encode-keyframe-32x32-flat`: flat 128 (== `DC_PRED`'s no-neighbors
  predicted value exactly), `skip=1` (no residual at all) -- decodes back
  to the target exactly.
- `encode-keyframe-32x32-dc`: flat 170, a real (non-skip) DC-only
  residual (a constant residual is exactly the DC basis function, every
  AC coefficient is exactly 0 by DCT orthogonality) -- decodes back to
  the target exactly (no quantization loss possible for a single
  coefficient at this quantizer).
- `encode-keyframe-32x32-gradient`: a smooth single-cycle horizontal
  sinusoid, `base_q_idx=60` -- a genuine multi-coefficient AC residual;
  bit-exact against both real decoders (not bit-exact against the
  original floating-point-designed target -- normal, expected lossy
  transform-coding error, not a bug).
- `encode-keyframe-32x32-busy`: busier multi-frequency content, a FINE
  `base_q_idx=20` chosen specifically so several quantized coefficients'
  magnitude exceeds 14 (confirmed: 18 of 56 nonzero coefficients), forcing
  the `coeff_br` continuation loop's full 4-iteration "maxed out" path AND
  the golomb escape code (`write-golomb`) to actually run -- bit-exact
  against both real decoders, the strongest available confirmation that
  `write-golomb` (the one code path the other three fixtures never reach)
  is correct, not merely that it doesn't crash.

**Not yet covered by this encode pass** (mirrors this section's own
narrow scope, see above): any partition shape other than a single
whole-frame `BLOCK_32X32` leaf, any intra mode other than `DC_PRED`
(luma)/`UV_DC_PRED` (chroma, per the chroma encode extension below), any
transform size other than `TX_32X32` (luma)/`TX_16X16` (chroma), inter
frames, and a `.cljc`/ClojureScript-portable symbol encoder
(`av1.bool-encoder` is JVM Clojure only, see its namespace docstring).

### Chroma (Cb/Cr) encode extension (ADR-2607122000 Migration step 9 continuation)

The luma-only encode pass above has been extended to also encode the U
(Cb) and V (Cr) planes, for 4:2:0 content, by inverting av1.decode-block's
already-validated chroma-decode extension the same way this task's
original luma pass inverted its own luma-only decode milestone -- pass
`:cb`/`:cr` (each a flat row-major 16x16 vector, the 4:2:0 subsample of
the 32x32 luma frame) to `av1.encode/encode-keyframe` to produce a
`mono_chrome=0`/`num_planes=3` color keyframe instead of the original
monochrome-only shape.

- **Scope is exactly the luma pass's shape, mirrored per plane**: one
  `BLOCK_32X32` leaf (subsamples 4:2:0 to exactly one `BLOCK_16X16`
  chroma block), `UV_DC_PRED` (chroma DC prediction with no available
  neighbors -- the SAME `128` no-neighbors constant as luma's `DC_PRED`,
  since `av1.intra-pred/dc-predict` is plane-agnostic, see its namespace
  docstring), `TX_16X16`/`DCT_DCT` (chroma's TxType is `DCT_DCT` with a
  structural zero-bit guarantee for `UV_DC_PRED`, exactly mirroring
  luma's `TX_32X32` guarantee -- see `av1.decode-block`'s chroma-decode
  section above), and zero chroma quantizer delta
  (`delta_q_u_dc=delta_q_u_ac=0`, so chroma shares luma's `base_q_idx`
  directly -- the simplest legal choice, not a scope restriction).
- **`uv_mode` IS a real symbol write** (`av1.encode-block/write-uv-mode`,
  the encode-side inverse of `av1.decode-block/read-uv-mode`) -- real for
  every color frame regardless of the decoded/encoded value or the
  block's skip flag (per spec, `uv_mode` is read right after
  `intra_angle_info_y()`, unconditionally on skip).
- **`av1.encode-block/write-coeffs` needed ZERO changes** to serve chroma
  in addition to luma: it was already fully generalized over plane/
  tx-size via its `spec` argument (the same map shape
  `av1.decode-block`'s `luma-spec-base`/`chroma-spec-base`/`u-spec`/
  `v-spec` use), and chroma's `TxType` is `DCT_DCT` with no
  `transform_type()` write needed for plane>0 -- exactly mirroring
  `av1.decode-block/read-coeffs`'s own plane==0-only `read-transform-type`
  call. `av1.decode-block/get-txb-skip-ctx-chroma` (chroma's plane>0
  `txb_skip` context derivation) was made public (visibility-only
  change) for the same reuse-not-re-derive reason
  `get-coeff-base-ctx`/`get-coeff-br-ctx`/`get-dc-sign-ctx`/
  `record-above!`/`record-left!` already were.
- **A real, size-generalization bug this task's own validation caught**
  (not assumed away): `av1.transform/forward-transform-2d`'s final scale
  had been hardcoded to a constant `4.0`, derived and validated ONLY for
  `TX_32X32` (log2=5) -- a real regression test for this extension's new
  `TX_16X16` (log2=4) size immediately failed with a factor-of-2 error
  (a flat 16x16 residual at value 20 round-tripped to exactly 10). Fixed
  by re-probing `av1.transform/inverse-transform-2d` (the SAME
  numerical-probing methodology the original forward-transform derivation
  used, see that namespace's docstring) across every square transform
  size this repo's tables span, discovering the closed-form
  `forward-scale(log2) = 2^(7 - max(log2,4))` -- which reduces to the
  pre-existing `4.0` EXACTLY for `log2=5`, so every pre-existing
  `TX_32X32` caller's output is byte-for-byte unchanged, while correctly
  giving `8.0` for `TX_16X16`. Confirmed for both the DC and a genuine AC
  (non-DC) frequency, not merely the flat-DC case. See
  `av1.transform`'s namespace docstring's SIZE GENERALIZATION note and
  `test/av1/transform_encode_test.cljk`'s TX_16X16 regression tests.
- **`av1.sequence-header/write`** gained an optional `:mono-chrome?`
  (default `true`, byte-for-byte unchanged for every pre-existing caller)
  -- when `false`, writes the real `mono_chrome=0`/4:2:0 `color_config()`
  path (still `seq_profile=0`, 8-bit, no `color_description`): exactly
  THREE extra bits versus the monochrome path (`chroma_sample_position`
  f(2) + `separate_uv_delta_q` f(1), both 0 -- `subsampling_x`/
  `subsampling_y` remain zero-bit-forced to 1/1 by `seq_profile==0`, same
  as the mono path).
- **`av1.frame-header/write`** gained an optional `:color?` (default
  `false`, byte-for-byte unchanged) -- when `true`, `quantization_params()`
  writes two extra real bits (`delta_q_u_dc`/`delta_q_u_ac`, both
  `delta_coded=0`) per the spec's `num_planes>1` branch; since
  `separate_uv_delta_q=0` (from the paired sequence header), V's deltas
  are forced equal to U's with no further bits, so chroma's DC/AC
  quantizer is uniformly `base_q_idx`.

**Validation**: three fixtures
(`resources/av1/fixtures/encode-keyframe-32x32-color-{flat,gradient,
busy}.obu`), all THIS REPO'S OWN encoder output (`av1.encode/
encode-keyframe` with `:cb`/`:cr` supplied -- see `test/av1/fixtures.cljk`
docstrings for the exact invocation behind each one), validated against
the SAME two independent real decoders the monochrome encode fixtures
use:

- `dav1d` (1.5.3): succeeds (no error) for all three, and this repo's own
  decode of each fixture is **bit-exact (no tolerance, all three planes)**
  against dav1d's independent decode (`test/av1/encode_test.cljk`'s
  `dav1d-bit-exact-color-*-test`s).
- `aomdec` (libaom 3.14.1, `--i420`): also succeeds for all three, with
  its Y+U+V output byte-identical to dav1d's.

Fixture-by-fixture: `encode-keyframe-32x32-color-flat` (Y=Cb=Cr=128,
`skip=1` on every plane -- `uv_mode` is still a real write even though no
plane has residual); `encode-keyframe-32x32-color-gradient` (luma's
existing sinusoid + linear Cb/Cr ramps, `base_q_idx=60` -- a genuine
multi-coefficient AC residual on U and V, exercised via
`av1.encode-block/write-coeffs`'s chroma reuse for the first time);
`encode-keyframe-32x32-color-busy` (busier content on all three planes,
`base_q_idx=20` chosen so several of EACH chroma plane's quantized
coefficients exceed magnitude 14 -- U: 12 of 30 nonzero, V: 8 of 29
nonzero -- forcing `write-golomb`'s escape code to run for chroma
specifically, not just luma).

**Not yet covered by this extension**: any intra mode other than
`UV_DC_PRED`, 4:2:2/4:4:4 chroma subsampling, a nonzero chroma quantizer
delta, and the same partition-shape/inter-frame/`.cljc`-portability
restrictions the luma-only encode pass above already documents.

### Usage

```clojure
(require '[av1.encode :as enc])

(def pixels (vec (repeat (* 32 32) 128))) ;; flat 32x32 luma, 0-255
(def obu-bytes (enc/encode-keyframe pixels 100 {:skip? true}))
;; => a complete, standalone AV1 OBU stream (byte vector) --
;;    decodable by this repo's own av1.decode-block, real dav1d,
;;    real aomdec, `ffmpeg -f obu`, etc.

;; Chroma (Cb/Cr) encode extension: pass :cb/:cr (each a flat 16x16
;; vector, the 4:2:0 subsample of `pixels`) for a color keyframe.
(def cb (vec (repeat (* 16 16) 128)))
(def cr (vec (repeat (* 16 16) 128)))
(def color-obu-bytes (enc/encode-keyframe pixels 100 {:skip? true :cb cb :cr cr}))
;; => a complete mono_chrome=0/4:2:0 AV1 OBU stream.
```

## Test

```sh
kbb -M:test
```

## Lint

```sh
kbb -M:lint
```
