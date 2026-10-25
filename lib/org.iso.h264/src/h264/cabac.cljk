(ns h264.cabac
  "H.264 CABAC (Context-Adaptive Binary Arithmetic Coding) entropy decode
   (ITU-T H.264 / ISO/IEC 14496-10 §9.3), main/high-profile CABAC support,
   ADR-2607122000 follow-on to the CAVLC-only \"R0.5\" decoder — see
   `h264.decode`'s namespace docstring for the combined scope statement.
   Scope: **I-slice / Intra_16x16** (the original increment) **AND
   P-slice `P_Skip`/`P_L0_16x16`** (the CABAC+P-slice increment — see
   `read-mb-skip-flag!`/`read-mb-type-p!`/`read-mvd!`/
   `read-coded-block-pattern-inter-cabac!` and the `:luma-regular` block
   category below). Sub-partitioned inter (`P_L0_L0_16x8`/`P_L0_L0_8x16`/
   `P_8x8`/`P_8x8ref0`), intra-coded macroblocks within a CABAC P-slice,
   CABAC + `I_NxN`/`I_PCM`/8x8-transform, B-slices, and CABAC ENCODE are
   all explicitly out of scope — this namespace only ever decodes.

   ## Why these tables are transcribed from Cisco's OpenH264, not FFmpeg

   FFmpeg's own `libavcodec/cabac.c`/`h264_cabac.c` implement a heavily
   byte-buffered/table-driven variant of the arithmetic decoding engine
   (a combined-state `mlps_state` trick, `norm_shift` lookup tables driven
   by 16-bit buffered reads) that is faster but NOT a literal transcription
   of the spec's own per-bit pseudocode (§9.3.3.2) — reverse-engineering
   FFmpeg's bit-packed encoding of `transIdxLPS`/`transIdxMPS` risked a
   transcription error that would be very hard to detect (a subtly wrong
   *state machine* still runs and produces plausible-looking-but-wrong
   output, unlike a wrong bit COUNT which usually desyncs loudly). OpenH264
   (Cisco)'s decoder (`codec/common/src/common_tables.cpp`,
   `codec/decoder/core/src/{cabac_decoder,parse_mb_syn_cabac}.cpp`,
   https://github.com/cisco/openh264) implements the SAME literal per-bit
   engine this namespace does (separate `pStateIdx`/`valMPS`, a straight
   `rangeTabLPS[64][4]` + `transIdxLPS[64]`/`transIdxMPS[64]` table, one
   `RenormD`-equivalent bit at a time) — its context-index constants
   (`NEW_CTX_OFFSET_*`) and per-syntax-element binarization/context-
   derivation functions were used directly as the porting reference for
   this namespace, and were cross-checked against FFmpeg's OWN
   `ff_h264_cabac_tables` (`libavcodec/cabac.c`) by decoding FFmpeg's
   packed/duplicated-state encoding back out and confirming the two
   sources agree on `rangeTabLPS`/`transIdxLPS`/`transIdxMPS` bit-for-bit
   (both give pStateIdx=0 → {128,176,208,240}/transIdxLPS=0/transIdxMPS=1,
   pStateIdx=63 → {2,2,2,2}/transIdxLPS=transIdxMPS=63, matching the well-
   known published H.264 Table 9-44/9-45 values). `range-tab-lps`/
   `trans-idx-lps`/`trans-idx-mps`/`context-init-i` below were extracted
   PROGRAMMATICALLY (a small parser over the fetched OpenH264 C source,
   not hand-transcribed) to eliminate manual-transcription risk for the
   464-row context-init table in particular.

   ## Context-init scope: all 4 columns (I-slice + 3 P/B `cabac_init_idc`)

   `context-init-i` is the `cabac_init_idc`-independent I-slice column of
   OpenH264's combined `g_kiCabacGlobalContextIdx[460][4][2]` table (its own
   comment: \"this table is from Table9-12 to Table 9-24\", i.e. ITU-T
   H.264 Tables 9-12..9-24's (m,n) context-init parameters, §9.3.1.1).
   `context-init-p0/p1/p2` (ADR-2607122000 CABAC+P-slice increment) are the
   other 3 columns (`cabac_init_idc` 0/1/2, selected by a P-slice's own
   slice-header field — see `h264.slice/parse-header!` — B-slice-only
   usage of these same columns remains out of scope, this namespace never
   decodes a B-slice). All 4 columns were extracted with the SAME small
   programmatic parser (not hand-transcribed) — re-parsing column 0
   independently reproduced `context-init-i` exactly, entry-for-entry,
   zero diffs, an incidental cross-check of that pre-existing column too.
   Many entries are `nil` (OpenH264's `CTX_NA` sentinel) for context/column
   combinations this namespace's I-slice+P-slice (`P_Skip`/`P_L0_16x16`
   only) scope never indexes (B-slice-only contexts, sub-partitioned-
   inter-only contexts like `sub_mb_type`, etc.).

   ## Syntax elements NOT implemented (throws or simply never called)

   `coded_block_pattern` (context offset 73, `NEW_CTX_OFFSET_CBP`) is
   implemented for INTER macroblocks (`read-coded-block-pattern-inter-cabac!`,
   ADR-2607122000 CABAC+P-slice increment) but NOT for Intra_16x16: unlike
   I_NxN/inter mb_types, an Intra_16x16 macroblock's CodedBlockPattern is
   fully INFERRED from its `mb_type` value (Table 7-11 —
   `h264.decode/i16x16-mb-info`), the same as the existing CAVLC path — no
   separate `coded_block_pattern` syntax element is read for Intra_16x16
   macroblocks regardless of entropy mode (§7.3.5.1's own
   `if (CodedBlockPatternLuma>0 || ... || MbPartPredMode==Intra_16x16)`
   gate for `mb_qp_delta`/`residual()` presence — note the explicit
   `MbPartPredMode==Intra_16x16` disjunct — confirms `mb_qp_delta` is
   likewise unconditional for Intra_16x16, matching the existing CAVLC
   code's own unconditional `(eg/se! r)` read)."
  (:require [h264.expgolomb :as eg]))

;; --- Arithmetic decoding engine tables (§9.3.3.2, Tables 9-44/9-45) ---
;; Programmatically extracted from Cisco OpenH264's
;; codec/common/src/common_tables.cpp (`g_kuiCabacRangeLps`,
;; `g_kuiStateTransTable`) — see namespace docstring for cross-check
;; methodology against FFmpeg's independently-encoded `ff_h264_cabac_tables`.

(def range-tab-lps
  "Table 9-44: rangeTabLPS[pStateIdx][qCodIRangeIdx] (64 rows x 4 cols)."
  [[128 176 208 240] [128 167 197 227] [128 158 187 216] [123 150 178 205]
   [116 142 169 195] [111 135 160 185] [105 128 152 175] [100 122 144 166]
   [95 116 137 158] [90 110 130 150] [85 104 123 142] [81 99 117 135]
   [77 94 111 128] [73 89 105 122] [69 85 100 116] [66 80 95 110]
   [62 76 90 104] [59 72 86 99] [56 69 81 94] [53 65 77 89]
   [51 62 73 85] [48 59 69 80] [46 56 66 76] [43 53 63 72]
   [41 50 59 69] [39 48 56 65] [37 45 54 62] [35 43 51 59]
   [33 41 48 56] [32 39 46 53] [30 37 43 50] [29 35 41 48]
   [27 33 39 45] [26 31 37 43] [24 30 35 41] [23 28 33 39]
   [22 27 32 37] [21 26 30 35] [20 24 29 33] [19 23 27 31]
   [18 22 26 30] [17 21 25 28] [16 20 23 27] [15 19 22 25]
   [14 18 21 24] [14 17 20 23] [13 16 19 22] [12 15 18 21]
   [12 14 17 20] [11 14 16 19] [11 13 15 18] [10 12 15 17]
   [10 12 14 16] [9 11 13 15] [9 11 12 14] [8 10 12 14]
   [8 9 11 13] [7 9 11 12] [7 9 10 12] [7 8 10 11]
   [6 8 9 11] [6 7 9 10] [6 7 8 9] [2 2 2 2]])

(def trans-idx-lps
  "Table 9-45, transIdxLPS(pStateIdx) — 64 entries."
  [0 0 1 2 2 4 4 5 6 7 8 9 9 11 11 12 13 13 15 15 16 16 18 18 19 19 21 21 22
   22 23 24 24 25 26 26 27 27 28 29 29 30 30 30 31 32 32 33 33 33 34 34 35
   35 35 36 36 36 37 37 37 38 38 63])

(def trans-idx-mps
  "Table 9-45, transIdxMPS(pStateIdx) — 64 entries."
  [1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27
   28 29 30 31 32 33 34 35 36 37 38 39 40 41 42 43 44 45 46 47 48 49 50 51
   52 53 54 55 56 57 58 59 60 61 62 62 63])

(def context-init-i
  "I-slice column of Tables 9-12..9-24 ((m,n) context-init parameters,
   §9.3.1.1), 460 entries indexed by absolute ctxIdx; `nil` = P/B-only
   context (never indexed by this namespace's I-slice-only scope)."
  [[20 -15] [2 54] [3 74] [20 -15] [2 54] [3 74] [-28 127] [-23 104] [-6 53] [-1 54] [7 51] nil nil nil nil nil nil nil nil nil nil nil nil nil nil nil nil nil nil nil nil nil nil nil nil nil nil nil nil nil nil nil nil nil nil nil nil nil nil nil nil nil nil nil nil nil nil nil nil nil [0 41] [0 63] [0 63] [0 63] [-9 83] [4 86] [0 97] [-7 72] [13 41] [3 62] [0 11] [1 55] [0 69] [-17 127] [-13 102] [0 82] [-7 74] [-21 107] [-27 127] [-31 127] [-24 127] [-18 95] [-27 127] [-21 114] [-30 127] [-17 123] [-12 115] [-16 122] [-11 115] [-12 63] [-2 68] [-15 84] [-13 104] [-3 70] [-8 93] [-10 90] [-30 127] [-1 74] [-6 97] [-7 91] [-20 127] [-4 56] [-5 82] [-7 76] [-22 125] [-7 93] [-11 87] [-3 77] [-5 71] [-4 63] [-4 68] [-12 84] [-7 62] [-7 65] [8 61] [5 56] [-2 66] [1 64] [0 61] [-2 78] [1 50] [7 52] [10 35] [0 44] [11 38] [1 45] [0 46] [5 44] [31 17] [1 51] [7 50] [28 19] [16 33] [14 62] [-13 108] [-15 100] [-13 101] [-13 91] [-12 94] [-10 88] [-16 84] [-10 86] [-7 83] [-13 87] [-19 94] [1 70] [0 72] [-5 74] [18 59] [-8 102] [-15 100] [0 95] [-4 75] [2 72] [-11 75] [-3 71] [15 46] [-13 69] [0 62] [0 65] [21 37] [-15 72] [9 57] [16 54] [0 62] [12 72] [24 0] [15 9] [8 25] [13 18] [15 9] [13 19] [10 37] [12 18] [6 29] [20 33] [15 30] [4 45] [1 58] [0 62] [7 61] [12 38] [11 45] [15 39] [11 42] [13 44] [16 45] [12 41] [10 49] [30 34] [18 42] [10 55] [17 51] [17 46] [0 89] [26 -19] [22 -17] [26 -17] [30 -25] [28 -20] [33 -23] [37 -27] [33 -23] [40 -28] [38 -17] [33 -11] [40 -15] [41 -6] [38 1] [41 17] [30 -6] [27 3] [26 22] [37 -16] [35 -4] [38 -8] [38 -3] [37 3] [38 5] [42 0] [35 16] [39 22] [14 48] [27 37] [21 60] [12 68] [2 97] [-3 71] [-6 42] [-5 50] [-3 54] [-2 62] [0 58] [1 63] [-2 72] [-1 74] [-9 91] [-5 67] [-5 27] [-3 39] [-2 44] [0 46] [-16 64] [-8 68] [-10 78] [-6 77] [-10 86] [-12 92] [-15 55] [-10 60] [-6 62] [-4 65] [-12 73] [-8 76] [-7 80] [-9 88] [-17 110] [-11 97] [-20 84] [-11 79] [-6 73] [-4 74] [-13 86] [-13 96] [-11 97] [-19 117] [-8 78] [-5 33] [-4 48] [-2 53] [-3 62] [-13 71] [-10 79] [-12 86] [-13 90] [-14 97] nil [-6 93] [-6 84] [-8 79] [0 66] [-1 71] [0 62] [-2 60] [-2 59] [-5 75] [-3 62] [-4 58] [-9 66] [-1 79] [0 71] [3 68] [10 44] [-7 62] [15 36] [14 40] [16 27] [12 29] [1 44] [20 36] [18 32] [5 42] [1 48] [10 62] [17 46] [9 64] [-12 104] [-11 97] [-16 96] [-7 88] [-8 85] [-7 85] [-9 85] [-13 88] [4 66] [-3 77] [-3 76] [-6 76] [10 58] [-1 76] [-1 83] [-7 99] [-14 95] [2 95] [0 76] [-5 74] [0 70] [-11 75] [1 68] [0 65] [-14 73] [3 62] [4 62] [-1 68] [-13 75] [11 55] [5 64] [12 70] [15 6] [6 19] [7 16] [12 14] [18 13] [13 11] [13 15] [15 16] [12 23] [13 23] [15 20] [14 26] [14 44] [17 40] [17 47] [24 17] [21 21] [25 22] [31 27] [22 29] [19 35] [14 50] [10 57] [7 63] [-2 77] [-4 82] [-3 94] [9 69] [-12 109] [36 -35] [36 -34] [32 -26] [37 -30] [44 -32] [34 -18] [34 -15] [40 -15] [33 -7] [35 -5] [33 0] [38 2] [33 13] [23 35] [13 58] [29 -3] [26 0] [22 30] [31 -7] [35 -15] [34 -3] [34 3] [36 -1] [34 5] [32 11] [35 5] [34 12] [39 11] [30 29] [34 26] [29 39] [19 66] [31 21] [31 31] [25 50] [-17 120] [-20 112] [-18 114] [-11 85] [-15 92] [-14 89] [-26 71] [-15 81] [-14 80] [0 68] [-14 70] [-24 56] [-23 68] [-24 50] [-11 74] [23 -13] [26 -13] [40 -15] [49 -14] [44 3] [45 6] [44 34] [33 54] [19 82] [-3 75] [-1 23] [1 34] [1 43] [0 54] [-2 55] [0 61] [1 64] [0 68] [-9 92] [-14 106] [-13 97] [-15 90] [-12 90] [-18 88] [-10 73] [-9 79] [-14 86] [-10 73] [-10 70] [-10 69] [-5 66] [-9 64] [-5 58] [2 59] [21 -10] [24 -11] [28 -8] [28 -1] [29 3] [29 9] [35 20] [29 36] [14 67]])

(def context-init-p0
  "cabac_init_idc=0 column of Tables 9-12..9-24 (`g_kiCabacGlobalContextIdx`
   model index 1, ADR-2607122000 P-slice CABAC increment) — same 460-entry
   absolute-ctxIdx indexing as `context-init-i`, PROGRAMMATICALLY extracted
   from the SAME Cisco OpenH264 `common_tables.cpp` source (a small parser
   over the fetched C source, not hand-transcribed — cross-checked by
   independently re-parsing column 0 of the SAME source array and confirming
   it matches `context-init-i` exactly, entry-for-entry, zero diffs).
   `nil` = never indexed by this namespace's P-slice scope (still present
   in the raw table for other slice-type/syntax-element combinations this
   namespace doesn't implement, e.g. B-slice-only contexts)."
  [[20 -15] [2 54] [3 74] [20 -15] [2 54] [3 74] [-28 127] [-23 104]
   [-6 53] [-1 54] [7 51] [23 33] [23 2] [21 0] [1 9] [0 49]
   [-37 118] [5 57] [-13 78] [-11 65] [1 62] [12 49] [-4 73] [17 50]
   [18 64] [9 43] [29 0] [26 67] [16 90] [9 104] [-46 127] [-20 104]
   [1 67] [-13 78] [-11 65] [1 62] [-6 86] [-17 95] [-6 61] [9 45]
   [-3 69] [-6 81] [-11 96] [6 55] [7 67] [-5 86] [2 88] [0 58]
   [-3 76] [-10 94] [5 54] [4 69] [-3 81] [0 88] [-7 67] [-5 74]
   [-4 74] [-5 80] [-7 72] [1 58] [0 41] [0 63] [0 63] [0 63]
   [-9 83] [4 86] [0 97] [-7 72] [13 41] [3 62] [0 45] [-4 78]
   [-3 96] [-27 126] [-28 98] [-25 101] [-23 67] [-28 82] [-20 94] [-16 83]
   [-22 110] [-21 91] [-18 102] [-13 93] [-29 127] [-7 92] [-5 89] [-7 96]
   [-13 108] [-3 46] [-1 65] [-1 57] [-9 93] [-3 74] [-9 92] [-8 87]
   [-23 126] [5 54] [6 60] [6 59] [6 69] [-1 48] [0 68] [-4 69]
   [-8 88] [-2 85] [-6 78] [-1 75] [-7 77] [2 54] [5 50] [-3 68]
   [1 50] [6 42] [-4 81] [1 63] [-4 70] [0 67] [2 57] [-2 76]
   [11 35] [4 64] [1 61] [11 35] [18 25] [12 24] [13 29] [13 36]
   [-10 93] [-7 73] [-2 73] [13 46] [9 49] [-7 100] [9 53] [2 53]
   [5 53] [-2 61] [0 56] [0 56] [-13 63] [-5 60] [-1 62] [4 57]
   [-6 69] [4 57] [14 39] [4 51] [13 68] [3 64] [1 61] [9 63]
   [7 50] [16 39] [5 44] [4 52] [11 48] [-5 60] [-1 59] [0 59]
   [22 33] [5 44] [14 43] [-1 78] [0 60] [9 69] [11 28] [2 40]
   [3 44] [0 49] [0 46] [2 44] [2 51] [0 47] [4 39] [2 62]
   [6 46] [0 54] [3 54] [2 58] [4 63] [6 51] [6 57] [7 53]
   [6 52] [6 55] [11 45] [14 36] [8 53] [-1 82] [7 55] [-3 78]
   [15 46] [22 31] [-1 84] [25 7] [30 -7] [28 3] [28 4] [32 0]
   [34 -1] [30 6] [30 6] [32 9] [31 19] [26 27] [26 30] [37 20]
   [28 34] [17 70] [1 67] [5 59] [9 67] [16 30] [18 32] [18 35]
   [22 29] [24 31] [23 38] [18 43] [20 41] [11 63] [9 59] [9 64]
   [-1 94] [-2 89] [-9 108] [-6 76] [-2 44] [0 45] [0 52] [-3 64]
   [-2 59] [-4 70] [-4 75] [-8 82] [-17 102] [-9 77] [3 24] [0 42]
   [0 48] [0 55] [-6 59] [-7 71] [-12 83] [-11 87] [-30 119] [1 58]
   [-3 29] [-1 36] [1 38] [2 43] [-6 55] [0 58] [0 64] [-3 74]
   [-10 90] [0 70] [-4 29] [5 31] [7 42] [1 59] [-2 58] [-3 72]
   [-3 81] [-11 97] [0 58] [8 5] [10 14] [14 18] [13 27] [2 40]
   [0 58] [-3 70] [-6 79] [-8 85] nil [-13 106] [-16 106] [-10 87]
   [-21 114] [-18 110] [-14 98] [-22 110] [-21 106] [-18 103] [-21 107] [-23 108]
   [-26 112] [-10 96] [-12 95] [-5 91] [-9 93] [-22 94] [-5 86] [9 67]
   [-4 80] [-10 85] [-1 70] [7 60] [9 58] [5 61] [12 50] [15 50]
   [18 49] [17 54] [10 41] [7 46] [-1 51] [7 49] [8 52] [9 41]
   [6 47] [2 55] [13 41] [10 44] [6 50] [5 53] [13 49] [4 63]
   [6 64] [-2 69] [-2 59] [6 70] [10 44] [9 31] [12 43] [3 53]
   [14 34] [10 38] [-3 52] [13 40] [17 32] [7 44] [7 38] [13 50]
   [10 57] [26 43] [14 11] [11 14] [9 11] [18 11] [21 9] [23 -2]
   [32 -15] [32 -15] [34 -21] [39 -23] [42 -33] [41 -31] [46 -28] [38 -12]
   [21 29] [45 -24] [53 -45] [48 -26] [65 -43] [43 -19] [39 -10] [30 9]
   [18 26] [20 27] [0 57] [-14 82] [-5 75] [-19 97] [-35 125] [27 0]
   [28 0] [31 -4] [27 6] [34 8] [30 10] [24 22] [33 19] [22 32]
   [26 31] [21 41] [26 44] [23 47] [16 65] [14 71] [8 60] [6 63]
   [17 65] [21 24] [23 20] [26 23] [27 32] [28 23] [28 24] [23 40]
   [24 32] [28 29] [23 42] [19 57] [22 53] [22 61] [11 86] [12 40]
   [11 51] [14 59] [-4 79] [-7 71] [-5 69] [-9 70] [-8 66] [-10 68]
   [-19 73] [-12 69] [-16 70] [-15 67] [-20 62] [-19 70] [-16 66] [-22 65]
   [-20 63] [9 -2] [26 -9] [33 -9] [39 -7] [41 -2] [45 3] [49 9]
   [45 27] [36 59] [-6 66] [-7 35] [-7 42] [-8 45] [-5 48] [-12 56]
   [-6 60] [-5 62] [-8 66] [-8 76] [-5 85] [-6 81] [-10 77] [-7 81]
   [-17 80] [-18 73] [-4 74] [-10 83] [-9 71] [-9 67] [-1 61] [-8 66]
   [-14 66] [0 59] [2 59] [21 -13] [33 -14] [39 -7] [46 -2] [51 2]
   [60 6] [61 17] [55 34] [42 62]])

(def context-init-p1
  "cabac_init_idc=1 column (`g_kiCabacGlobalContextIdx` model index 2) —
   see `context-init-p0`'s docstring for extraction methodology."
  [[20 -15] [2 54] [3 74] [20 -15] [2 54] [3 74] [-28 127] [-23 104]
   [-6 53] [-1 54] [7 51] [22 25] [34 0] [16 0] [-2 9] [4 41]
   [-29 118] [2 65] [-6 71] [-13 79] [5 52] [9 50] [-3 70] [10 54]
   [26 34] [19 22] [40 0] [57 2] [41 36] [26 69] [-45 127] [-15 101]
   [-4 76] [-6 71] [-13 79] [5 52] [6 69] [-13 90] [0 52] [8 43]
   [-2 69] [-5 82] [-10 96] [2 59] [2 75] [-3 87] [-3 100] [1 56]
   [-3 74] [-6 85] [0 59] [-3 81] [-7 86] [-5 95] [-1 66] [-1 77]
   [1 70] [-2 86] [-5 72] [0 61] [0 41] [0 63] [0 63] [0 63]
   [-9 83] [4 86] [0 97] [-7 72] [13 41] [3 62] [13 15] [7 51]
   [2 80] [-39 127] [-18 91] [-17 96] [-26 81] [-35 98] [-24 102] [-23 97]
   [-27 119] [-24 99] [-21 110] [-18 102] [-36 127] [0 80] [-5 89] [-7 94]
   [-4 92] [0 39] [0 65] [-15 84] [-35 127] [-2 73] [-12 104] [-9 91]
   [-31 127] [3 55] [7 56] [7 55] [8 61] [-3 53] [0 68] [-7 74]
   [-9 88] [-13 103] [-13 91] [-9 89] [-14 92] [-8 76] [-12 87] [-23 110]
   [-24 105] [-10 78] [-20 112] [-17 99] [-78 127] [-70 127] [-50 127] [-46 127]
   [-4 66] [-5 78] [-4 71] [-8 72] [2 59] [-1 55] [-7 70] [-6 75]
   [-8 89] [-34 119] [-3 75] [32 20] [30 22] [-44 127] [0 54] [-5 61]
   [0 58] [-1 60] [-3 61] [-8 67] [-25 84] [-14 74] [-5 65] [5 52]
   [2 57] [0 61] [-9 69] [-11 70] [18 55] [-4 71] [0 58] [7 61]
   [9 41] [18 25] [9 32] [5 43] [9 47] [0 44] [0 51] [2 46]
   [19 38] [-4 66] [15 38] [12 42] [9 34] [0 89] [4 45] [10 28]
   [10 31] [33 -11] [52 -43] [18 15] [28 0] [35 -22] [38 -25] [34 0]
   [39 -18] [32 -12] [102 -94] [0 0] [56 -15] [33 -4] [29 10] [37 -5]
   [51 -29] [39 -9] [52 -34] [69 -58] [67 -63] [44 -5] [32 7] [55 -29]
   [32 1] [0 0] [27 36] [33 -25] [34 -30] [36 -28] [38 -28] [38 -27]
   [34 -18] [35 -16] [34 -14] [32 -8] [37 -6] [35 0] [30 10] [28 18]
   [26 25] [29 41] [0 75] [2 72] [8 77] [14 35] [18 31] [17 35]
   [21 30] [17 45] [20 42] [18 45] [27 26] [16 54] [7 66] [16 56]
   [11 73] [10 67] [-10 116] [-23 112] [-15 71] [-7 61] [0 53] [-5 66]
   [-11 77] [-9 80] [-9 84] [-10 87] [-34 127] [-21 101] [-3 39] [-5 53]
   [-7 61] [-11 75] [-15 77] [-17 91] [-25 107] [-25 111] [-28 122] [-11 76]
   [-10 44] [-10 52] [-10 57] [-9 58] [-16 72] [-7 69] [-4 69] [-5 74]
   [-9 86] [2 66] [-9 34] [1 32] [11 31] [5 52] [-2 55] [-2 67]
   [0 73] [-8 89] [3 52] [7 4] [10 8] [17 8] [16 19] [3 37]
   [-1 61] [-5 73] [-1 70] [-4 78] nil [-21 126] [-23 124] [-20 110]
   [-26 126] [-25 124] [-17 105] [-27 121] [-27 117] [-17 102] [-26 117] [-27 116]
   [-33 122] [-10 95] [-14 100] [-8 95] [-17 111] [-28 114] [-6 89] [-2 80]
   [-4 82] [-9 85] [-8 81] [-1 72] [5 64] [1 67] [9 56] [0 69]
   [1 69] [7 69] [-7 69] [-6 67] [-16 77] [-2 64] [2 61] [-6 67]
   [-3 64] [2 57] [-3 65] [-3 66] [0 62] [9 51] [-1 66] [-2 71]
   [-2 75] [-1 70] [-9 72] [14 60] [16 37] [0 47] [18 35] [11 37]
   [12 41] [10 41] [2 48] [12 41] [13 41] [0 59] [3 50] [19 40]
   [3 66] [18 50] [19 -6] [18 -6] [14 0] [26 -12] [31 -16] [33 -25]
   [33 -22] [37 -28] [39 -30] [42 -30] [47 -42] [45 -36] [49 -34] [41 -17]
   [32 9] [69 -71] [63 -63] [66 -64] [77 -74] [54 -39] [52 -35] [41 -10]
   [36 0] [40 -1] [30 14] [28 26] [23 37] [12 55] [11 65] [37 -33]
   [39 -36] [40 -37] [38 -30] [46 -33] [42 -30] [40 -24] [49 -29] [38 -12]
   [40 -10] [38 -3] [46 -5] [31 20] [29 30] [25 44] [12 48] [11 49]
   [26 45] [22 22] [23 22] [27 21] [33 20] [26 28] [30 24] [27 34]
   [18 42] [25 39] [18 50] [12 70] [21 54] [14 71] [11 83] [25 32]
   [21 49] [21 54] [-5 85] [-6 81] [-10 77] [-7 81] [-17 80] [-18 73]
   [-4 74] [-10 83] [-9 71] [-9 67] [-1 61] [-8 66] [-14 66] [0 59]
   [2 59] [17 -10] [32 -13] [42 -9] [49 -5] [53 0] [64 3] [68 10]
   [66 27] [47 57] [-5 71] [0 24] [-1 36] [-2 42] [-2 52] [-9 57]
   [-6 63] [-4 65] [-4 67] [-7 82] [-3 81] [-3 76] [-7 72] [-6 78]
   [-12 72] [-14 68] [-3 70] [-6 76] [-5 66] [-5 62] [0 57] [-4 61]
   [-9 60] [1 54] [2 58] [17 -10] [32 -13] [42 -9] [49 -5] [53 0]
   [64 3] [68 10] [66 27] [47 57]])

(def context-init-p2
  "cabac_init_idc=2 column (`g_kiCabacGlobalContextIdx` model index 3) —
   see `context-init-p0`'s docstring for extraction methodology."
  [[20 -15] [2 54] [3 74] [20 -15] [2 54] [3 74] [-28 127] [-23 104]
   [-6 53] [-1 54] [7 51] [29 16] [25 0] [14 0] [-10 51] [-3 62]
   [-27 99] [26 16] [-4 85] [-24 102] [5 57] [6 57] [-17 73] [14 57]
   [20 40] [20 10] [29 0] [54 0] [37 42] [12 97] [-32 127] [-22 117]
   [-2 74] [-4 85] [-24 102] [5 57] [-6 93] [-14 88] [-6 44] [4 55]
   [-11 89] [-15 103] [-21 116] [19 57] [20 58] [4 84] [6 96] [1 63]
   [-5 85] [-13 106] [5 63] [6 75] [-3 90] [-1 101] [3 55] [-4 79]
   [-2 75] [-12 97] [-7 50] [1 60] [0 41] [0 63] [0 63] [0 63]
   [-9 83] [4 86] [0 97] [-7 72] [13 41] [3 62] [7 34] [-9 88]
   [-20 127] [-36 127] [-17 91] [-14 95] [-25 84] [-25 86] [-12 89] [-17 91]
   [-31 127] [-14 76] [-18 103] [-13 90] [-37 127] [11 80] [5 76] [2 84]
   [5 78] [-6 55] [4 61] [-14 83] [-37 127] [-5 79] [-11 104] [-11 91]
   [-30 127] [0 65] [-2 79] [0 72] [-4 92] [-6 56] [3 68] [-8 71]
   [-13 98] [-4 86] [-12 88] [-5 82] [-3 72] [-4 67] [-8 72] [-16 89]
   [-9 69] [-1 59] [5 66] [4 57] [-4 71] [-2 71] [2 58] [-1 74]
   [-4 44] [-1 69] [0 62] [-7 51] [-4 47] [-6 42] [-3 41] [-6 53]
   [8 76] [-9 78] [-11 83] [9 52] [0 67] [-5 90] [1 67] [-15 72]
   [-5 75] [-8 80] [-21 83] [-21 64] [-13 31] [-25 64] [-29 94] [9 75]
   [17 63] [-8 74] [-5 35] [-2 27] [13 91] [3 65] [-7 69] [8 77]
   [-10 66] [3 62] [-3 68] [-20 81] [0 30] [1 7] [-3 23] [-21 74]
   [16 66] [-23 124] [17 37] [44 -18] [50 -34] [-22 127] [4 39] [0 42]
   [7 34] [11 29] [8 31] [6 37] [7 42] [3 40] [8 33] [13 43]
   [13 36] [4 47] [3 55] [2 58] [6 60] [8 44] [11 44] [14 42]
   [7 48] [4 56] [4 52] [13 37] [9 49] [19 58] [10 48] [12 45]
   [0 69] [20 33] [8 63] [35 -18] [33 -25] [28 -3] [24 10] [27 0]
   [34 -14] [52 -44] [39 -24] [19 17] [31 25] [36 29] [24 33] [34 15]
   [30 20] [22 73] [20 34] [19 31] [27 44] [19 16] [15 36] [15 36]
   [21 28] [25 21] [30 20] [31 12] [27 16] [24 42] [0 93] [14 56]
   [15 57] [26 38] [-24 127] [-24 115] [-22 82] [-9 62] [0 53] [0 59]
   [-14 85] [-13 89] [-13 94] [-11 92] [-29 127] [-21 100] [-14 57] [-12 67]
   [-11 71] [-10 77] [-21 85] [-16 88] [-23 104] [-15 98] [-37 127] [-10 82]
   [-8 48] [-8 61] [-8 66] [-7 70] [-14 75] [-10 79] [-9 83] [-12 92]
   [-18 108] [-4 79] [-22 69] [-16 75] [-2 58] [1 58] [-13 78] [-9 83]
   [-4 81] [-13 99] [-13 81] [-6 38] [-13 62] [-6 58] [-2 59] [-16 73]
   [-10 76] [-13 86] [-9 83] [-10 87] nil [-22 127] [-25 127] [-25 120]
   [-27 127] [-19 114] [-23 117] [-25 118] [-26 117] [-24 113] [-28 118] [-31 120]
   [-37 124] [-10 94] [-15 102] [-10 99] [-13 106] [-50 127] [-5 92] [17 57]
   [-5 86] [-13 94] [-12 91] [-2 77] [0 71] [-1 73] [4 64] [-7 81]
   [5 64] [15 57] [1 67] [0 68] [-10 67] [1 68] [0 77] [2 64]
   [0 68] [-5 78] [7 55] [5 59] [2 65] [14 54] [15 44] [5 60]
   [2 70] [-2 76] [-18 86] [12 70] [5 64] [-12 70] [11 55] [5 56]
   [0 69] [2 65] [-6 74] [5 54] [7 54] [-6 76] [-11 82] [-2 77]
   [-2 77] [25 42] [17 -13] [16 -9] [17 -12] [27 -21] [37 -30] [41 -40]
   [42 -41] [48 -47] [39 -32] [46 -40] [52 -51] [46 -41] [52 -39] [43 -19]
   [32 11] [61 -55] [56 -46] [62 -50] [81 -67] [45 -20] [35 -2] [28 15]
   [34 1] [39 1] [30 17] [20 38] [18 45] [15 54] [0 79] [36 -16]
   [37 -14] [37 -17] [32 1] [34 15] [29 15] [24 25] [34 22] [31 16]
   [35 18] [31 28] [33 41] [36 28] [27 47] [21 62] [18 31] [19 26]
   [36 24] [24 23] [27 16] [24 30] [31 29] [22 41] [22 42] [16 60]
   [15 52] [14 60] [3 78] [-16 123] [21 53] [22 56] [25 61] [21 33]
   [19 50] [17 61] [-3 78] [-8 74] [-9 72] [-10 72] [-18 75] [-12 71]
   [-11 63] [-5 70] [-17 75] [-14 72] [-16 67] [-8 53] [-14 59] [-9 52]
   [-11 68] [9 -2] [30 -10] [31 -4] [33 -1] [33 7] [31 12] [37 23]
   [31 38] [20 64] [-9 71] [-7 37] [-8 44] [-11 49] [-10 56] [-12 59]
   [-8 63] [-9 67] [-6 68] [-10 79] [-3 78] [-8 74] [-9 72] [-10 72]
   [-18 75] [-12 71] [-11 63] [-5 70] [-17 75] [-14 72] [-16 67] [-8 53]
   [-14 59] [-9 52] [-11 68] [9 -2] [30 -10] [31 -4] [33 -1] [33 7]
   [31 12] [37 23] [31 38] [20 64]])

;; --- Absolute ctxIdx offsets (§Table 9-11) for the syntax elements this
;;     namespace's I-slice/Intra_16x16-only scope actually needs. Named
;;     identically to OpenH264's own `NEW_CTX_OFFSET_*` #defines
;;     (`codec/decoder/core/inc/decoder_context.h`) for direct traceability
;;     back to the porting reference. ---

(def ^:const ctx-mb-type-i 3)   ;; mb_type, I/SI slice (ctxIdxOffset 3, 8 ctx: prefix 0..2 + suffix 3..7)
(def ^:const ctx-skip 11)       ;; mb_skip_flag, P/SP slice (ctxIdxOffset 11, 3 ctx) — ALSO the base for
                                 ;; P-slice mb_type below (OpenH264's ParseMBTypePSliceCabac shares this
                                 ;; SAME pBinCtx base, offset by +3.., see `read-mb-type-p!`)
(def ^:const ctx-mb-type-p 14)   ;; P,SP slice mb_type prefix (ctxIdxOffset 14 == ctx-skip+3 — kept as a
                                 ;; separate named const purely for documentation; `read-mb-type-p!` itself
                                 ;; indexes off `ctx-skip` directly, matching the ported C source 1:1)
(def ^:const ctx-mvd 40)        ;; mvd_l0/mvd_l1 (ctxIdxOffset 40, CTX_NUM_MVD=7 ctx per component: comp0 40-46, comp1 47-53)
(def ^:const ctx-ref-no 54)     ;; ref_idx_l0/l1 (ctxIdxOffset 54) — UNUSED in this repo's scope: never
                                 ;; read at all when num_ref_idx_l0_active==1 (h264.slice enforces this),
                                 ;; matching CAVLC's own implicit-ref_idx-0 discipline exactly (OpenH264's
                                 ;; own `ParseRefIdxCabac` early-returns 0 for iActiveRefNum==1 without
                                 ;; touching the engine at all) — kept here purely for documentation/
                                 ;; traceability, matching Table 9-11's numbering.
(def ^:const ctx-delta-qp 60)   ;; mb_qp_delta (ctxIdxOffset 60, 4 ctx: 0/1 first bin + 2/3 continuation)
(def ^:const ctx-cipr 64)       ;; intra_chroma_pred_mode (ctxIdxOffset 64, 4 ctx: 0..2 first bin + 3 continuation)
(def ^:const ctx-cbp 73)        ;; coded_block_pattern, INTER macroblocks only (ctxIdxOffset 73 — luma 4 ctx
                                 ;; @+0..3, `CTX_NUM_CBP`=4; chroma bit0 4 ctx @+4..7; chroma bit1 4 ctx @+8..11.
                                 ;; UNUSED for Intra_16x16, whether CABAC or CAVLC — CBP is inferred from
                                 ;; mb_type there, see `h264.decode/i16x16-mb-info`.)
(def ^:const ctx-cbf 85)        ;; coded_block_flag (ctxIdxOffset 85)
(def ^:const ctx-map 105)       ;; significant_coeff_flag (ctxIdxOffset 105)
(def ^:const ctx-last 166)      ;; last_significant_coeff_flag (ctxIdxOffset 166)
(def ^:const ctx-one 227)       ;; coeff_abs_level_minus1 "greater1" (ctxIdxOffset 227)
(def ^:const ctx-abs 232)       ;; coeff_abs_level_minus1 remainder (ctxIdxOffset 232)

;; --- Block-category parameters (§9.3.3.1.3/Table 9-42's blockCat, scoped
;;     to the 4 categories this namespace needs — LUMA_DC_AC_8/regular
;;     LUMA_DC_AC (inter/I_NxN) are out of scope). Values transcribed from
;;     OpenH264's `g_kMaxPos`/`g_kMaxC2`/`g_kBlockCat2CtxOffset{CBF,Map,Last,One,Abs}`
;;     (`codec/decoder/core/src/parse_mb_syn_cabac.cpp`). Chroma DC/AC use
;;     the SAME offsets for both Cb and Cr (only the coded_block_flag
;;     NEIGHBOR lookup differs per-component, via the caller-supplied nA/nB
;;     — see `h264.decode`)."
(defn- cat-params [cat]
  (case cat
    :luma-dc      {:max-num-coeff 16 :max-pos 15 :max-c2 4 :cbf-off 0  :map-off 0  :one-off 0}
    :luma-ac      {:max-num-coeff 15 :max-pos 14 :max-c2 4 :cbf-off 4  :map-off 15 :one-off 10}
    :chroma-dc    {:max-num-coeff 4  :max-pos 3  :max-c2 3 :cbf-off 12 :map-off 44 :one-off 30}
    :chroma-ac    {:max-num-coeff 15 :max-pos 14 :max-c2 4 :cbf-off 16 :map-off 47 :one-off 39}
    ;; §9.3.3.1.1.9/9.3.3.1.3 blockCat "LumaLevel4x4" (OpenH264's blockCat
    ;; index 3, g_kMaxPos[3]=15/g_kBlockCat2CtxOffset{CBF,Map,Last,One,Abs}[3]
    ;; = 8/29/29/20/20) — the FULL 16-coefficient "regular" 4x4 luma block
    ;; (position 0 included, no separate macroblock-level DC/Hadamard split)
    ;; used by inter (P_L0_16x16) and I_NxN macroblocks — the CABAC
    ;; counterpart of `h264.decode/decode-regular-block!`'s CAVLC residual
    ;; shape. Independently re-derived from the SAME OpenH264 source this
    ;; namespace's other block-category constants came from (see namespace
    ;; docstring) — cross-checked: this fetch's own index1/2/4/5 entries
    ;; (0/15/0, 4/15/10, 12/44/30, 16/47/39 for cbf/map-or-last/one-or-abs)
    ;; match `:luma-dc`/`:luma-ac`/`:chroma-dc`/`:chroma-ac` above exactly,
    ;; entry-for-entry — an independent confirmation of those pre-existing
    ;; values, not just of this new `:luma-regular` entry.
    :luma-regular {:max-num-coeff 16 :max-pos 15 :max-c2 4 :cbf-off 8  :map-off 29 :one-off 20}))

;; --- §9.3.1.1.1 context-model initialization ---

(defn init-context
  "One context model's initial {pStateIdx, valMPS} from its (m,n) pair and
   SliceQPY (§9.3.1.1.1 — contexts are initialized ONCE per slice from the
   slice's OWN QP, not re-initialized as `mb_qp_delta` drifts QP per-MB)."
  [[m n] qp]
  (let [pre-ctx-state (max 1 (min 126 (+ (bit-shift-right (* m qp) 4) n)))]
    (if (<= pre-ctx-state 63)
      {:state (atom (- 63 pre-ctx-state)) :mps (atom 0)}
      {:state (atom (- pre-ctx-state 64)) :mps (atom 1)})))

(defn- context-init-column
  "Select the right (m,n) column (§9.3.1.1.1) for `qp` init: I-slice always
   uses `context-init-i` (`cabac_init_idc` isn't even signaled for I-slices,
   §7.3.3); P-slice uses `context-init-p0/p1/p2` selected by the SLICE
   HEADER's `cabac_init_idc` (0/1/2 — see `h264.slice/parse-header!`'s
   P-slice-only `cabac_init_idc` field, read only when
   `entropy_coding_mode_flag && slice_type != I/SI`, §7.3.3/Table 7-2's own
   `WelsCabacContextInit`: `iIdx = (I_SLICE) ? 0 : cabac_init_idc + 1`)."
  [slice-class cabac-init-idc]
  (if (= slice-class :i)
    context-init-i
    (case cabac-init-idc
      0 context-init-p0
      1 context-init-p1
      2 context-init-p2)))

(defn init-contexts
  "Full 460-entry context-model vector for `qp`. 2-arity: I-slice init
   values only (`context-init-i`, unchanged call shape for existing I-slice
   callers). 4-arity (ADR-2607122000 P-slice CABAC increment): `slice-class`
   (`:i` or `:p`) + `cabac-init-idc` (0/1/2, only meaningful for `:p` —
   ignored for `:i`) select the correct column, see `context-init-column`.
   Entries whose (m,n) is `nil` (never indexed by this namespace's I-slice
   OR P-slice scope) stay `nil`."
  ([qp] (init-contexts qp :i 0))
  ([qp slice-class cabac-init-idc]
   (mapv (fn [mn] (when mn (init-context mn qp)))
         (context-init-column slice-class cabac-init-idc))))

;; --- §9.3.3.2 arithmetic decoding engine (literal per-bit port, NOT
;;     FFmpeg's byte-buffered variant — see namespace docstring) ---

(defn init-engine!
  "§9.3.1.2 initialization of the arithmetic decoding engine: codIRange=510,
   codIOffset = the next 9 bits (read directly off the SAME `h264.expgolomb`
   reader `r` that decoded the slice header — the caller MUST have already
   byte-aligned `r` via `byte-align!`, since slice_data()'s
   `cabac_alignment_one_bit` guarantees codIOffset's first bit is byte-
   aligned in the actual NAL bytes, per spec)."
  [r]
  {:r r :range (atom 510) :offset (atom (eg/bits! r 9))})

(defn- renorm-d!
  [eng]
  (let [r (:r eng) rg (:range eng) off (:offset eng)]
    (while (< @rg 256)
      (swap! rg bit-shift-left 1)
      (swap! off (fn [o] (bit-or (bit-shift-left o 1) (eg/bit! r)))))))

(defn decode-decision!
  "§9.3.3.2.1 DecodeDecision: one context-coded bin against context model
   `ctx` (a {:state (atom pStateIdx) :mps (atom valMPS)} — see
   `init-context`/`init-contexts`), mutating `ctx`'s state in place."
  [eng ctx]
  (let [rg (:range eng) off (:offset eng)
        state @(:state ctx) mps @(:mps ctx)
        q (bit-and (bit-shift-right @rg 6) 3)
        rlps (get-in range-tab-lps [state q])
        new-range (- @rg rlps)
        lps? (>= @off new-range)
        bin (if lps? (- 1 mps) mps)]
    (if lps?
      (do (reset! off (- @off new-range))
          (reset! rg rlps)
          (when (zero? state) (reset! (:mps ctx) (- 1 mps)))
          (reset! (:state ctx) (nth trans-idx-lps state)))
      (do (reset! rg new-range)
          (reset! (:state ctx) (nth trans-idx-mps state))))
    (renorm-d! eng)
    bin))

(defn decode-bypass!
  "§9.3.3.2.3 DecodeBypass: one equiprobable (context-free) bin."
  [eng]
  (let [r (:r eng) rg (:range eng) off (:offset eng)]
    (reset! off (bit-or (bit-shift-left @off 1) (eg/bit! r)))
    (if (>= @off @rg)
      (do (reset! off (- @off @rg)) 1)
      0)))

(defn decode-terminate!
  "§9.3.3.2.4 DecodeTerminate: used ONLY for `end_of_slice_flag` in this
   namespace's I-slice scope (I_PCM detection also uses it, but that mb_type
   throws immediately in `h264.decode` before any further reads)."
  [eng]
  (let [rg (:range eng) off (:offset eng)]
    (swap! rg - 2)
    (if (>= @off @rg)
      1
      (do (renorm-d! eng) 0))))

;; --- §7.3.4 slice_data()'s CABAC-only byte-alignment ---

(defn byte-align!
  "`while (!byte_aligned()) cabac_alignment_one_bit` — consumes 0..7 bits
   up to the next byte boundary. Per spec these MUST all be `1`; validated
   (throws) rather than silently accepting a misaligned/corrupt bitstream."
  [r]
  (while (not (eg/byte-aligned? r))
    (let [b (eg/bit! r)]
      (when (zero? b)
        (throw (ex-info "h264.cabac: cabac_alignment_one_bit was 0 (misaligned or corrupt bitstream)" {}))))))

;; --- §9.3.2.5 / Table 9-36 mb_type binarization, I-slice ---

(defn read-mb-type-i!
  "I-slice `mb_type` (§9.3.2.5, Table 9-36's I-slice binarization + Table
   9-39's ctxIdxInc): prefix bin (ctxIdxInc = neighbor-available count, 0..2)
   distinguishes I_NxN(0) from everything else; if not I_NxN, a
   `decode_terminate` distinguishes I_PCM(25) from Intra_16x16 (1..24); the
   Intra_16x16 suffix (5 more context-coded bins) directly encodes the
   `mb_type` value 1..24 per Table 7-11's own arithmetic (cbp_luma!=0,
   cbp_chroma 0/1/2, pred_mode 0..3) — this repo's scope never decodes
   I_NxN/I_PCM (both throw downstream in `h264.decode/i16x16-mb-info`, same
   as the CAVLC path), so `left-avail?`/`top-avail?` are simply \"neighbor
   MB exists\" (any neighbor this decoder has SUCCESSFULLY decoded is, by
   construction, never I_NxN — the full spec condition also excludes
   I_NxN/I_8x8 neighbors, which is automatically satisfied here)."
  [eng ctxs left-avail? top-avail?]
  (let [ctx-inc (+ (if left-avail? 1 0) (if top-avail? 1 0))
        bin0 (decode-decision! eng (nth ctxs (+ ctx-mb-type-i ctx-inc)))]
    (if (zero? bin0)
      0
      (if (= 1 (decode-terminate! eng))
        25
        (let [b1 (decode-decision! eng (nth ctxs (+ ctx-mb-type-i 3)))
              mb-type (+ 1 (* 12 b1))
              b2 (decode-decision! eng (nth ctxs (+ ctx-mb-type-i 4)))
              mb-type (if (pos? b2)
                        (let [b3 (decode-decision! eng (nth ctxs (+ ctx-mb-type-i 5)))]
                          (+ mb-type 4 (* 4 b3)))
                        mb-type)
              b4 (decode-decision! eng (nth ctxs (+ ctx-mb-type-i 6)))
              mb-type (+ mb-type (* 2 b4))
              b5 (decode-decision! eng (nth ctxs (+ ctx-mb-type-i 7)))]
          (+ mb-type b5))))))

;; --- §9.3.2.2/Table 9-34 intra_chroma_pred_mode binarization (TU, cMax=3) ---

(defn read-intra-chroma-pred-mode!
  "`intra_chroma_pred_mode` (Table 9-34 TU cMax=3 binarization, Table 9-39's
   ctxIdxInc: bin0 = neighbor-nonzero-mode count 0..2, bins 1+ share a single
   fixed context). `left-nonzero?`/`top-nonzero?` = neighbor MB available AND
   its OWN `intra_chroma_pred_mode` != 0 (DC) — see `h264.decode`."
  [eng ctxs left-nonzero? top-nonzero?]
  (let [ctx-inc (+ (if left-nonzero? 1 0) (if top-nonzero? 1 0))
        bin0 (decode-decision! eng (nth ctxs (+ ctx-cipr ctx-inc)))]
    (if (zero? bin0)
      0
      (let [b1 (decode-decision! eng (nth ctxs (+ ctx-cipr 3)))]
        (if (zero? b1)
          1
          (let [b2 (decode-decision! eng (nth ctxs (+ ctx-cipr 3)))]
            (if (zero? b2) 2 3)))))))

;; --- §9.3.2.7 mb_qp_delta binarization (unary, mapped like se(v)) ---

(defn read-mb-qp-delta!
  "`mb_qp_delta`: bin0 ctxIdxInc = (previous mb's mb_qp_delta != 0); if 0,
   delta=0. Else a further unary code (bin1 on its own context, bin2+ on a
   THIRD shared context) gives codeNum k (1-indexed unary length), mapped to
   the signed delta exactly like `se(v)`'s own codeNum mapping
   (`(k+1)>>1`, negated when k is even)."
  [eng ctxs last-delta-nonzero?]
  (let [bin0 (decode-decision! eng (nth ctxs (+ ctx-delta-qp (if last-delta-nonzero? 1 0))))]
    (if (zero? bin0)
      0
      (let [k (loop [k 1 pos 1]
                (let [ctx-idx (+ ctx-delta-qp (if (= pos 1) 2 3))
                      b (decode-decision! eng (nth ctxs ctx-idx))]
                  (if (zero? b) k (recur (inc k) (inc pos)))))
            delta (quot (inc k) 2)]
        (if (odd? k) delta (- delta))))))

;; --- §9.3.3.1.1.3/Table 9-11 mb_skip_flag (P/SP slice only) + §9.3.2.5/
;;     Table 9-37 P,SP slice mb_type binarization (ADR-2607122000 P-slice
;;     CABAC increment). Both ported from OpenH264's `ParseSkipFlagCabac`/
;;     `ParseMBTypePSliceCabac` (`codec/decoder/core/src/parse_mb_syn_cabac.cpp`,
;;     fetched directly from https://github.com/cisco/openh264 — same
;;     porting-reference discipline as every other syntax element in this
;;     namespace, see namespace docstring). B-slice-only offsets (+13 for
;;     mb_skip_flag, the whole `ParseMBTypeBSliceCabac` tree) are NOT
;;     ported — out of scope, this namespace never decodes a B-slice. ---

(defn read-mb-skip-flag!
  "`mb_skip_flag` (§7.3.4, present for EVERY macroblock address in a
   CABAC-coded P-slice — unlike CAVLC's run-length `mb_skip_run`, CABAC
   spends one context-coded bin per address regardless of skip/not-skip,
   see `h264.decode`'s CABAC P-slice macroblock loop). ctxIdxInc
   (§Table 9-39) = (left neighbor available AND NOT itself skipped) +
   (top neighbor available AND NOT itself skipped) — `left-coded?`/
   `top-coded?` are exactly that (nil/false-neighbor and skipped-neighbor
   both contribute 0, matching OpenH264's `pNeighAvail->iLeftAvail &&
   !IS_SKIP(iLeftType)`)."
  [eng ctxs left-coded? top-coded?]
  (let [ctx-inc (+ (if left-coded? 1 0) (if top-coded? 1 0))]
    (decode-decision! eng (nth ctxs (+ ctx-skip ctx-inc)))))

(defn read-mb-type-p!
  "P,SP-slice `mb_type` (§9.3.2.5/Table 9-37), ported bin-for-bin from
   OpenH264's `ParseMBTypePSliceCabac` (see namespace docstring's porting
   discipline) — a DIFFERENT binarization tree from I-slice's
   `read-mb-type-i!` even though both happen to share `ctx-skip`(11) as a
   base offset (P-slice's `mb_type`/`mb_skip_flag` are adjacent in
   Table 9-11's ctxIdxOffset numbering: skip=11..13, mb_type prefix=14..).
   Returns the RAW P-slice `mb_type` value, Table 7-13's own numbering —
   the SAME numbering `h264.decode/decode-macroblock-p!` already dispatches
   on for the CAVLC path (0=P_L0_16x16, 1..3=sub-partitioned inter — this
   binarization can never itself produce 4/P_8x8ref0, see this fn's
   development note below — 5=Intra_NxN, 6..29=Intra_16x16 (P-slice
   numbering, `intra_mb_type = mb_type - 5` per Table 7-13), 30=I_PCM) —
   so callers can reuse `decode-macroblock-p!`'s existing dispatch/throw
   structure unchanged.

   Note on value 4 (P_8x8ref0): OpenH264's P-slice mb_type CABAC
   binarization only ever produces 0/1/2/3 from its \"P MB\" branch (2
   bins after the P-vs-intra prefix) — value 4 is a CAVLC-only ue(v)
   codeNum distinction (P_8x8 vs P_8x8ref0 differ only in whether
   sub_mb_type's own ref_idx is force-zeroed, a distinction CABAC's
   binarization tree doesn't need a separate mb_type bin string for).
   Irrelevant to this repo's scope either way — both 3 (P_8x8) and 4
   (P_8x8ref0) throw downstream (sub-partitioned motion, out of scope,
   same discipline as CAVLC's `decode-macroblock-p!`)."
  [eng ctxs]
  (let [bin0 (decode-decision! eng (nth ctxs (+ ctx-skip 3)))] ;; ctx14: 0=P MB, 1=intra
    (if (zero? bin0)
      ;; --- P MB: 2 more bins distinguish 0/1/2/3 ---
      (let [b1 (decode-decision! eng (nth ctxs (+ ctx-skip 4)))] ;; ctx15
        (if (pos? b1)
          (let [b2 (decode-decision! eng (nth ctxs (+ ctx-skip 6)))] ;; ctx17
            (if (pos? b2) 1 2))
          (let [b2 (decode-decision! eng (nth ctxs (+ ctx-skip 5)))] ;; ctx16
            (if (pos? b2) 3 0))))
      ;; --- Intra MB: same overall shape as read-mb-type-i!, different ctx bank ---
      (let [b1 (decode-decision! eng (nth ctxs (+ ctx-skip 6)))] ;; ctx17: 0=Intra_NxN, 1=Intra_16x16
        (if (zero? b1)
          5
          (if (= 1 (decode-terminate! eng))
            30 ;; I_PCM (P-slice numbering)
            (let [b2 (decode-decision! eng (nth ctxs (+ ctx-skip 7))) ;; ctx18
                  mb-type (+ 6 (* 12 b2))
                  b3 (decode-decision! eng (nth ctxs (+ ctx-skip 8))) ;; ctx19
                  mb-type (if (pos? b3)
                            (let [b4 (decode-decision! eng (nth ctxs (+ ctx-skip 8)))] ;; ctx19 again
                              (+ mb-type 4 (* 4 b4)))
                            mb-type)
                  b5 (decode-decision! eng (nth ctxs (+ ctx-skip 9))) ;; ctx20
                  mb-type (+ mb-type (* 2 b5))
                  b6 (decode-decision! eng (nth ctxs (+ ctx-skip 9)))] ;; ctx20 again
              (+ mb-type b6))))))))

;; --- §9.3.3.1.1.4-ish coded_block_pattern for INTER macroblocks (§9.3.2.6
;;     binarization, Table 9-11 ctxIdxOffset 73) — a COMPLETELY DIFFERENT
;;     binarization from CAVLC's me(v)+`golomb-to-inter-cbp` table lookup
;;     (see `h264.decode/read-coded-block-pattern-inter!`), not merely an
;;     entropy-recoding of the same table: CABAC reads CodedBlockPatternLuma
;;     bit-by-bit (one ctx-coded bin per 8x8 luma quadrant, context derived
;;     from whether the SPATIALLY ADJACENT neighbor 8x8 block had ANY
;;     residual) then CodedBlockPatternChroma via 2 more context-coded bins.
;;     Ported from OpenH264's `ParseCbpInfoCabac`. UNUSED for Intra_16x16
;;     (CBP inferred from mb_type, same as CAVLC — see `h264.decode/i16x16-mb-info`). ---

(defn read-coded-block-pattern-inter-cabac!
  "`coded_block_pattern` for a CABAC-coded INTER (P_L0_16x16) macroblock.
   `left-cbp-luma`/`top-cbp-luma` are the NEIGHBOR macroblock's own 4-bit
   CodedBlockPatternLuma (nil if that neighbor is unavailable — picture
   edge; a P_Skip neighbor contributes 0, matching CAVLC's own convention
   that a skipped macroblock has no residual at all — see `h264.decode`'s
   CABAC P-slice macroblock-state shape); `left-cbp-chroma`/`top-cbp-chroma`
   likewise for CodedBlockPatternChroma (0..2, nil if unavailable). Returns
   {:cbp-luma (0..15) :cbp-chroma (0..2)}."
  [eng ctxs left-cbp-luma top-cbp-luma left-cbp-chroma top-cbp-chroma]
  (let [bit-zero? (fn [cbp bit] (zero? (bit-and (bit-shift-right cbp bit) 1)))
        top-avail? (some? top-cbp-luma)
        left-avail? (some? left-cbp-luma)
        b-top0 (and top-avail? (bit-zero? top-cbp-luma 2))
        b-top1 (and top-avail? (bit-zero? top-cbp-luma 3))
        a-left0 (and left-avail? (bit-zero? left-cbp-luma 1))
        a-left1 (and left-avail? (bit-zero? left-cbp-luma 3))
        b0 (decode-decision! eng (nth ctxs (+ ctx-cbp (if a-left0 1 0) (if b-top0 2 0))))
        b1 (decode-decision! eng (nth ctxs (+ ctx-cbp (if (zero? b0) 1 0) (if b-top1 2 0))))
        b2 (decode-decision! eng (nth ctxs (+ ctx-cbp (if a-left1 1 0) (if (zero? b0) 2 0))))
        b3 (decode-decision! eng (nth ctxs (+ ctx-cbp (if (zero? b2) 1 0) (if (zero? b1) 2 0))))
        cbp-luma (+ (if (pos? b0) 1 0) (if (pos? b1) 2 0) (if (pos? b2) 4 0) (if (pos? b3) 8 0))
        cb0-a? (and left-avail? (pos? left-cbp-chroma))
        cb0-b? (and top-avail? (pos? top-cbp-chroma))
        cbit0 (decode-decision! eng (nth ctxs (+ ctx-cbp 4 (if cb0-a? 1 0) (if cb0-b? 2 0))))
        cbp-chroma (if (zero? cbit0)
                     0
                     (let [cb1-a? (and left-avail? (= 2 left-cbp-chroma))
                           cb1-b? (and top-avail? (= 2 top-cbp-chroma))
                           cbit1 (decode-decision! eng (nth ctxs (+ ctx-cbp 8 (if cb1-a? 1 0) (if cb1-b? 2 0))))]
                       (if (zero? cbit1) 1 2)))]
    {:cbp-luma cbp-luma :cbp-chroma cbp-chroma}))

;; --- §9.3.2.3 coeff_abs_level_minus1's EGk bypass suffix + UEG "greater
;;     than 2" continuation, both ported literally from OpenH264's
;;     `DecodeExpBypassCabac`/`DecodeUEGLevelCabac` (see namespace
;;     docstring) rather than re-derived, since an off-by-one here silently
;;     produces a plausible-but-wrong coefficient magnitude. ---

(defn- decode-exp-golomb-bypass!
  "Order-`k0` Exp-Golomb, bypass-coded (§9.3.2.3's EGk, ported from
   `DecodeExpBypassCabac`): a unary prefix (each `1` bit doubles the implicit
   range and increments `k0`) terminated by a `0`, then `k0` more bypass
   bits read directly (MSB-first) as the suffix value.

   BUG FIX (multi-macroblock CABAC root-cause, see README \"Pixel decode:
   CABAC\" and ADR-2607122000 addendum): the suffix accumulation MUST use a
   SEPARATE accumulator from the prefix sum, the two ADDED together at the
   end — exactly OpenH264's own `DecodeExpBypassCabac` (`iSymTmp` for the
   prefix, a SEPARATE `iSymTmp2` for the suffix, `uiSymVal = iSymTmp +
   iSymTmp2`). The previous version here reused the prefix's `sym` as the
   suffix loop's OWN starting accumulator and OR'd suffix bits into it —
   which is a SILENT NO-OP for every suffix value, because a `count`-bit
   unary prefix always accumulates to exactly `2^count - 1` (ALL `count`
   low bits already 1), and the suffix then OR's `count` MORE bits into
   those SAME low bit positions, which can only ever leave them unchanged.
   This made `coeff_abs_level_minus1` silently truncate to the truncated-
   unary prefix's own value (`decode-ueg-level!`'s `code`) plus the wrong,
   suffix-blind EG0 term, for EVERY coefficient whose magnitude was large
   enough to saturate the cMax=13 truncated-unary bank in
   `decode-ueg-level!` (i.e. `coeff_abs_level_minus1 >= 14`) — invisible on
   `flat16-dc-only-cabac.h264`/`gradient16-ac-cabac.h264` (both single-MB,
   ≤1 small significant coefficient, never reaching this code path at all)
   but reliably wrong on real multi-macroblock/multi-coefficient content
   the moment any one block's decoded magnitude got large enough to need
   this suffix. Root-caused by an independent from-scratch Python
   re-implementation (arithmetic engine + context tables cross-checked
   programmatically against Cisco OpenH264's own `common_tables.cpp`, zero
   diffs across all 460 context-init entries and every ctxIdxOffset/block-
   category constant) that reproduced the IDENTICAL wrong bin sequence and
   coefficient values as this namespace on a real multi-macroblock Main-
   profile CABAC fixture — i.e. the entropy decode CONTROL FLOW (which
   bins get read, in what order, against which contexts) was already
   correct, only this one arithmetic combination step was wrong — then
   confirmed by hand-tracing the actual bin sequence for the fixture's
   affected DC block and finding the corrected value (`code + (prefix +
   suffix) + 1`) exactly matches an independently-CAVLC-encoded reference
   of near-identical content (`+29`/`+89` instead of the previous `+22`/
   `+78` at two of the block's four significant positions)."
  [eng k0]
  (loop [count k0 sym 0]
    (let [bit (decode-bypass! eng)]
      (if (= bit 1)
        (let [count' (inc count)]
          (when (= count' 16)
            (throw (ex-info "h264.cabac: Exp-Golomb bypass unary prefix exceeded 16 (corrupt bitstream)" {})))
          (recur count' (+ sym (bit-shift-left 1 count))))
        (loop [i count acc 0]
          (if (zero? i)
            (+ sym acc)
            (let [i' (dec i) b (decode-bypass! eng)]
              (recur i' (if (= b 1) (bit-or acc (bit-shift-left 1 i')) acc)))))))))

;; --- §9.3.2.3 mvd_l0/mvd_l1 UEG3 binarization (k0=3, signedValFlag=1) —
;;     ADR-2607122000 P-slice CABAC increment. Ported from OpenH264's
;;     `ParseMvdInfoCabac`/`DecodeUEGMvCabac` (`cabac_decoder.cpp`), reusing
;;     `decode-exp-golomb-bypass!` above (the SAME EGk bypass-suffix helper
;;     coeff_abs_level_minus1 uses, just called with k0=3 instead of k0=0 —
;;     see that fn's docstring for the multi-macroblock bug this namespace
;;     already fixed there once; this is the SAME fn, not a re-derivation,
;;     so that fix automatically covers mvd too). ---

(def ^:private mvd-bin-pos->ctx
  "OpenH264's `g_kMvdBinPos2Ctx` (`cabac_decoder.cpp`) — maps the mvd UEG3
   continuation's bin position (0..7) to a ctx-index OFFSET relative to the
   continuation's own base (`ctx-mvd + comp*7 + 3`, see `read-mvd!`):
   position 0 (the continuation's own first bin) uses offset 0, positions
   1/2 use offsets 1/2, and positions 3..7 all SHARE offset 3 (a single
   context reused for the truncated-unary tail) — a real, spec-mandated
   context-reuse pattern, not a porting shortcut."
  [0 1 2 3 3 3 3 3])

(defn- read-mvd-ueg3-continuation!
  "Literal port of `DecodeUEGMvCabac`: the mvd UEG3 continuation beyond
   `read-mvd!`'s own neighbor-context-coded first (outer) bin. `ctx-base`
   is this component's absolute mvd ctx base (`ctx-mvd + comp*7`) — the
   continuation's own contexts start at `ctx-base+3` (`g_kMvdBinPos2Ctx`
   indexes relative to THAT). Returns the value to ADD to 1 (the caller's
   outer bin already established `abs(mvd) >= 1`)."
  [eng ctxs ctx-base]
  (let [c3 (+ ctx-base 3)
        bin0 (decode-decision! eng (nth ctxs (+ c3 (nth mvd-bin-pos->ctx 0))))]
    (if (zero? bin0)
      0
      (loop [count 1 code 0]
        (let [ctx-idx (+ c3 (nth mvd-bin-pos->ctx count))
              b (decode-decision! eng (nth ctxs ctx-idx))
              code' (inc code)
              count' (inc count)]
          (if (and (not (zero? b)) (not= count' 8))
            (recur count' code')
            (if (not (zero? b))
              (+ code' (decode-exp-golomb-bypass! eng 3) 1)
              code')))))))

(defn read-mvd!
  "`mvd_l0` (or `mvd_l1`, unused — this repo's scope is single-list P-slice
   only) component binarization, §9.3.2.3 UEG3 (k0=3, signedValFlag=1),
   ported from OpenH264's `ParseMvdInfoCabac`. `comp` is 0 (horizontal) or 1
   (vertical) — `mvd_l0[0]`/`mvd_l0[1]` each get their OWN 7-context bank
   (`ctx-mvd` + `comp*7`, Table 9-11's `CTX_NUM_MVD`=7). `neighbor-abs-sum`
   is `|left-neighbor mvd comp| + |top-neighbor mvd comp|` for the SAME
   component — an unavailable OR non-inter (intra/P_Skip, which never
   carries an `mvd_l0` at all) neighbor contributes 0, see `h264.decode`'s
   `:mvd` neighbor-state tracking for the CABAC P-slice macroblock loop."
  [eng ctxs comp neighbor-abs-sum]
  (let [base (+ ctx-mvd (* comp 7))
        ctx-inc (cond (> neighbor-abs-sum 32) 2 (>= neighbor-abs-sum 3) 1 :else 0)
        outer-bin (decode-decision! eng (nth ctxs (+ base ctx-inc)))]
    (if (zero? outer-bin)
      0
      (let [mag (+ 1 (read-mvd-ueg3-continuation! eng ctxs base))
            sign (decode-bypass! eng)]
        (if (= sign 1) (- mag) mag)))))

(defn- decode-ueg-level!
  "The \"is this coefficient's absolute value greater than 2\" continuation
   (ported from `DecodeUEGLevelCabac`): a truncated-unary prefix (cMax=13,
   ALL bins on the SAME shared context `ctx`) then, if the prefix saturates
   at 13 without a natural `0` terminator, an EG0 bypass suffix
   (`decode-exp-golomb-bypass!` with k0=0). Returns the amount to ADD to the
   already-known base level of 2 (the caller has already decoded
   significance=1 and greater1=1, i.e. level>=2, before calling this)."
  [eng ctx]
  (if (zero? (decode-decision! eng ctx))
    0
    (loop [code 0 count 1]
      (let [bit (decode-decision! eng ctx)
            code (inc code)
            count (inc count)]
        (if (and (not (zero? bit)) (not= count 13))
          (recur code count)
          (if (not (zero? bit))
            (+ code (decode-exp-golomb-bypass! eng 0) 1)
            code))))))

;; --- §7.3.5.3.3/9.3.3.1.1.9 coded_block_flag + §9.3.3.1.2/9.3.2.3
;;     significant_coeff_flag/last_significant_coeff_flag/
;;     coeff_abs_level_minus1, combined into one per-block residual decode
;;     matching `h264.cavlc/residual-block!`'s OWN return shape (SCAN-order
;;     `:coeffs` + `:total-coeff`) so `h264.decode` can reuse the exact same
;;     entropy-independent unscan/dequant/transform pipeline for both. ---

(defn- read-significant-map!
  "§9.3.3.1.2/Table 9-39: `significant_coeff_flag`/`last_significant_coeff_flag`
   for one block, scan positions 0..(max-pos-1) each read a
   significant_coeff_flag (context = position index, no neighbor dependence)
   then, if significant, a last_significant_coeff_flag (same position-
   indexed context in the LAST table) — if that fires, all REMAINING
   positions are 0 and decode stops early. If the loop runs through position
   (max-pos-1) without an early stop, position max-pos (the final scan
   position) is IMPLICITLY significant (no bit read for it — §9.3.3.1.2's
   own note that the last coefficient position never gets its own
   significant_coeff_flag). Returns a `(inc max-pos)`-length (== max-num-
   coeff) vector of 0/1."
  [eng ctxs map-base last-base max-pos]
  (loop [i 0 sig (vec (repeat (inc max-pos) 0))]
    (if (>= i max-pos)
      (assoc sig max-pos 1)
      (let [s (decode-decision! eng (nth ctxs (+ map-base i)))]
        (if (zero? s)
          (recur (inc i) sig)
          (let [last? (decode-decision! eng (nth ctxs (+ last-base i)))]
            (if (zero? last?)
              (recur (inc i) (assoc sig i 1))
              (assoc sig i 1))))))))

(defn- read-coeff-levels!
  "§9.3.2.3/9.3.3.1.3 `coeff_abs_level_minus1` (+ its bypass sign bit),
   walking the already-decoded significance vector `sig` in REVERSE scan
   order (spec-mandated — c1/c2 adaptive-context state is threaded through
   this SAME reverse traversal, reset to c1=1/c2=0 once per block). Zero
   (non-significant) positions consume NO bits at all. Returns {:coeffs
   :total-coeff}, `:coeffs` in SCAN order (position 0..max-pos, signed
   dequantization-ready levels — same shape `h264.cavlc/residual-block!`'s
   `:coeffs` has)."
  [eng ctxs one-base abs-base max-c2 sig max-pos]
  (loop [i max-pos c1 1 c2 0 levels (vec (repeat (count sig) 0)) total 0]
    (if (< i 0)
      {:coeffs levels :total-coeff total}
      (if (zero? (nth sig i))
        (recur (dec i) c1 c2 levels total)
        (let [gt1 (decode-decision! eng (nth ctxs (+ one-base c1)))
              lvl (inc gt1)
              [lvl c1' c2']
              (if (= lvl 2)
                (let [extra (decode-ueg-level! eng (nth ctxs (+ abs-base c2)))]
                  [(+ lvl extra) 0 (min max-c2 (inc c2))])
                [lvl (if (pos? c1) (min 4 (inc c1)) c1) c2])
              sign (decode-bypass! eng)
              lvl (if (= sign 1) (- lvl) lvl)]
          (recur (dec i) c1' c2' (assoc levels i lvl) (inc total)))))))

(defn residual-block!
  "Decode one CABAC residual block (`cat` in `#{:luma-dc :luma-ac
   :chroma-dc :chroma-ac :luma-regular}` — see `cat-params`):
   `coded_block_flag` (always explicitly read in this repo's scope — no
   ChromaArrayType==3/8x8-transform `coded_block_flag`-inference shortcut
   applies, see namespace docstring) gates whether ANY further bits are
   read at all; if set, `significant_coeff_flag`/`last_significant_coeff_flag`
   map (`read-significant-map!`) then `coeff_abs_level_minus1`+sign
   (`read-coeff-levels!`). `cbf-nA`/`cbf-nB` are the already-derived (by
   `h264.decode`, per §9.3.3.1.1.9 — unavailable-neighbor default is
   `!!IS_INTRA(CURRENT macroblock)`, i.e. `true` for the intra callers
   (`decode-intra-macroblock-body-cabac!`), `false` for the inter caller
   (`decode-inter-16x16-macroblock-cabac!`, ADR-2607122000 CABAC+P-slice
   increment) — NOT a fixed value, see
   `h264.decode/decode-chroma-ac-blocks-cabac!`'s docstring for a real bug
   this distinction fixed) `coded_block_flag` neighbor booleans.
   Returns {:coeffs (SCAN-order vector, length = category's max-num-coeff)
   :total-coeff int} — the SAME shape `h264.cavlc/residual-block!` returns,
   so `h264.decode` can dequantize/unscan/transform identically regardless
   of entropy method."
  [eng ctxs cat cbf-nA cbf-nB]
  (let [{:keys [max-num-coeff max-pos max-c2 cbf-off map-off one-off]} (cat-params cat)
        cbf-ctx-inc (+ (if cbf-nA 1 0) (* 2 (if cbf-nB 1 0)))
        cbf (decode-decision! eng (nth ctxs (+ ctx-cbf cbf-off cbf-ctx-inc)))]
    (if (zero? cbf)
      {:coeffs (vec (repeat max-num-coeff 0)) :total-coeff 0}
      (let [sig (read-significant-map! eng ctxs (+ ctx-map map-off) (+ ctx-last map-off) max-pos)]
        (read-coeff-levels! eng ctxs (+ ctx-one one-off) (+ ctx-abs one-off) max-c2 sig max-pos)))))
