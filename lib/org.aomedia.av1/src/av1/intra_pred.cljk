(ns av1.intra-pred
  "AV1 intra prediction processes, transcribed from AV1 Bitstream & Decoding
   Process Specification section 7.11.2 (\"Intra prediction process\") --
   7.11.2.5 (\"DC intra prediction process\"), 7.11.2.4 (\"Directional
   intra prediction process\", V_PRED/H_PRED cases only), and 7.11.2.2
   (\"Basic intra prediction process\", PAETH_PRED) -- AOMediaCodec/av1-spec
   master, 08.decoding.process.md #Intra prediction process / #DC intra
   prediction process / #Directional intra prediction process / #Basic
   intra prediction process (fetched 2026-07-13, DC_PRED originally;
   V_PRED/H_PRED addition fetched again 2026-07-13 for the Phase 1
   mode-coverage extension below; PAETH_PRED addition fetched again
   2026-07-13 for the PAETH mode-coverage extension below, including the
   general \"Intra prediction process\" section's AboveRow[-1]/LeftCol[-1]
   (topleft corner sample) derivation that only PAETH_PRED (of this
   namespace's supported modes) needs).

   SCOPE (Phase 1 continuation, ADR-2607122000 Migration step 9 -- see
   av1.decode-block namespace docstring for the full scope statement):
   DC_PRED / V_PRED / H_PRED / PAETH_PRED / SMOOTH_PRED only (mode is not
   always a parameter here for dc-predict, which keeps its original narrow
   signature; v-predict/h-predict/paeth-predict/smooth-predict below are
   the other entry points -- av1.decode-block throws before calling this
   namespace for any other intra mode: D45/D135/D113/D157/D203/D67/
   SMOOTH_V_PRED/SMOOTH_H_PRED are all still out of scope). 8-bit only.
   Luma-only (plane is implicit -- caller passes the plane's own pixel
   buffer).

   PAETH_PRED (mode 12) is, per spec 08.decoding.process.md's general
   \"Intra prediction process\" mode dispatch, NOT routed through the
   directional intra prediction process at all (is_directional_mode(
   PAETH_PRED) is false -- PAETH_PRED is modes 1..8's odd one out among
   this namespace's four supported modes) -- it goes to its own \"basic
   intra prediction process\" (7.11.2.2). This has a real, useful
   consequence for av1.decode-block: intra_angle_info_y() is gated on
   is_directional_mode(YMode), so PAETH_PRED blocks read NO angle_delta_y
   bit at all (unlike V_PRED/H_PRED, which do -- see av1.decode-block/
   read-angle-delta-y's docstring for that bug history) -- av1.decode-block
   doesn't need any new angle-delta handling for this extension, only a
   wider intra_frame_y_mode decode restriction and this namespace's new
   paeth-predict.

   V_PRED (mode 1, Mode_To_Angle[V_PRED] == 90) and H_PRED (mode 2,
   Mode_To_Angle[H_PRED] == 180) are technically routed through the spec's
   general \"directional intra prediction process\" (7.11.2.4, since
   is_directional_mode(V_PRED) and is_directional_mode(H_PRED) are both
   true), not through a dedicated non-directional formula the way DC_PRED
   is -- but this repo only ever exercises them with AngleDeltaY forced to
   0. IMPORTANT (corrected 2026-07-13 after a real-data bit-exactness
   failure): `--enable-angle-delta=0` does NOT remove `angle_delta_y` from
   the bitstream -- intra_angle_info_y() is called UNCONDITIONALLY by
   intra_frame_mode_info() whenever is_directional_mode(YMode) is true,
   with no enable_angle_delta gate at all (that flag only biases the
   ENCODER's search to always choose the zero-offset symbol). An earlier
   revision of this namespace incorrectly assumed the read could be
   skipped entirely, which desynced every subsequent bit in a V_PRED/
   H_PRED block. `av1.decode-block/read-angle-delta-y` now performs the
   real symbol read (`TileAngleDeltaCdf[YMode-V_PRED]`) and *asserts*
   (throws if false) that the decoded AngleDeltaY is 0, rather than
   assuming it -- so the pAngle-exactly-90/180 derivation below is now a
   verified precondition, not an unread assumption. At pAngle exactly 90 or 180, 7.11.2.4's steps
   10/11 apply directly (`pred[i][j] = AboveRow[j]` / `pred[i][j] =
   LeftCol[i]`, no per-sample angle/base/shift math needed), AND -- proven
   by inspecting 7.11.2.4 step 4 together with 7.11.2.10's edge-upsample
   selection formula (`d = Abs(delta); if (d<=0 || d>=40) useUpsample=0`) --
   neither intra edge filtering (7.11.2.4 step 4's inner filter branch is
   gated on `pAngle != 90 && pAngle != 180`, so it never runs for our
   pAngle) nor intra edge upsampling (delta = pAngle-90 = 0 or pAngle-180 =
   0 in both calls, so d=0 forces useUpsample=0 regardless of
   enable_intra_edge_filter/filterType) ever modifies AboveRow/LeftCol for
   these two exact angles -- so v-predict/h-predict below can validly copy
   AboveRow[j]/LeftCol[i] unmodified, without needing to implement filter
   corner / intra filter type / intra edge filter / intra edge upsample at
   all. This is a structural guarantee for pAngle==90/180 specifically, not
   an approximation -- see the namespace's git history / ADR-2607122000
   Migration step 9 continuation notes for the derivation.

   SMOOTH_PRED (mode 9, added by the SMOOTH mode-coverage extension, fetched
   2026-07-13 for the general \"Smooth intra prediction process\" section,
   08.decoding.process.md, and its Sm_Weights_Tx_* weight tables,
   10.additional.tables.md -- see av1.tables namespace docstring's
   Sm-Weights section for the two-source cross-check discipline used for
   those tables): like PAETH_PRED, NOT a directional mode
   (is_directional_mode(SMOOTH_PRED) is false -- SMOOTH_PRED/SMOOTH_V_PRED/
   SMOOTH_H_PRED all go to the spec's own dedicated \"Smooth intra
   prediction process\", 7.11.2.6, never the directional process 7.11.2.4),
   so av1.decode-block's existing `(contains? #{V_PRED H_PRED} y-mode)`
   angle-delta gate already correctly excludes it with no code change
   needed (same reasoning as PAETH_PRED's docstring section above).
   SMOOTH_V_PRED/SMOOTH_H_PRED (the two 1D-blend simplifications of
   SMOOTH_PRED, 7.11.2.6's second/third bullets) are explicitly OUT of
   scope for this extension -- only the two-edge SMOOTH_PRED case is
   implemented, see `smooth-predict` below."
  (:require [av1.tables :as tables]))

(defn dc-predict
  "spec 7.11.2.5: DC intra prediction. `frame` is a row-major flat vector of
   the plane's *reconstructed-so-far* pixel buffer (width `frame-w`,
   `frame-h` rows -- CurrFrame per spec), `x`/`y` the top-left sample of the
   block to predict, `have-left?`/`have-above?` availability flags (spec's
   haveLeft/haveAbove -- this phase never constructs haveAboveRight/
   haveBelowLeft since the DC formula doesn't need them), `log2W`/`log2H`
   the block's log2 width/height, `bit-depth` (8 in this repo). Returns a
   flat row-major w*h vector of predicted samples.

   maxX/maxY (used to clip the AboveRow/LeftCol read positions per spec)
   are derived from `frame-w`/`frame-h` directly (this repo's plane buffer
   is always sized exactly (MiCols*4) x (MiRows*4), matching spec's
   `(MiCols*MI_SIZE)-1` / `(MiRows*MI_SIZE)-1` for plane 0 -- chroma's
   subsampled maxX/maxY is out of scope, this repo is monochrome/luma-only,
   see av1.decode-block)."
  [frame frame-w frame-h x y have-left? have-above? log2W log2H bit-depth]
  (let [w (bit-shift-left 1 log2W)
        h (bit-shift-left 1 log2H)
        max-x (dec frame-w)
        max-y (dec frame-h)
        px (fn [xx yy] (nth frame (+ (* yy frame-w) xx)))
        left-col (fn [k] (px (dec x) (min max-y (+ y k))))
        above-row (fn [k] (px (min max-x (+ x k)) (dec y)))
        clip1 (fn [v] (let [hi (dec (bit-shift-left 1 bit-depth))]
                        (cond (< v 0) 0 (> v hi) hi :else v)))
        dc-val
        (cond
          (and have-left? have-above?)
          (let [sum (+ (reduce + (map left-col (range h)))
                       (reduce + (map above-row (range w)))
                       (bit-shift-right (+ w h) 1))]
            (quot sum (+ w h)))

          have-left?
          (let [sum (reduce + (map left-col (range h)))]
            (clip1 (bit-shift-right (+ sum (bit-shift-right h 1)) log2H)))

          have-above?
          (let [sum (reduce + (map above-row (range w)))]
            (clip1 (bit-shift-right (+ sum (bit-shift-right w 1)) log2W)))

          :else
          (bit-shift-left 1 (dec bit-depth)))]
    (vec (repeat (* w h) dc-val))))

;; ---------------------------------------------------------------------
;; Shared AboveRow[k]/LeftCol[k] accessors (spec 7.11.2 general "Intra
;; prediction process", the AboveRow[i]/LeftCol[i] for i=0..w+h-1
;; derivations) -- used by v-predict/h-predict below. haveAboveRight and
;; haveBelowLeft are always false in this repo's scope (no multi-block
;; frame this phase validates ever constructs them -- see av1.decode-block
;; namespace docstring), which only affects aboveLimit/leftLimit's clamp
;; range; since v-predict/h-predict only ever read AboveRow[0..w-1]/
;; LeftCol[0..h-1] (never the extended w..w+h-1 range that
;; haveAboveRight/haveBelowLeft would extend), this simplification is
;; exact for these two modes regardless.

(defn- above-row-fn
  "Returns `(fn [k] AboveRow[k])` for k=0..w-1, per spec 7.11.2's AboveRow
   derivation (haveAboveRight forced false, see above)."
  [frame frame-w x y have-left? have-above? w bit-depth]
  (cond
    (and (not have-above?) have-left?)
    (let [v (nth frame (+ (* y frame-w) (dec x)))] (constantly v))

    (and (not have-above?) (not have-left?))
    (constantly (dec (bit-shift-left 1 (dec bit-depth))))

    :else
    (let [max-x (dec frame-w)
          above-limit (min max-x (+ x w -1))]
      (fn [k] (nth frame (+ (* (dec y) frame-w) (min above-limit (+ x k))))))))

(defn- left-col-fn
  "Returns `(fn [k] LeftCol[k])` for k=0..h-1, per spec 7.11.2's LeftCol
   derivation (haveBelowLeft forced false, see above)."
  [frame frame-w frame-h x y have-left? have-above? h bit-depth]
  (cond
    (and (not have-left?) have-above?)
    (let [v (nth frame (+ (* (dec y) frame-w) x))] (constantly v))

    (and (not have-left?) (not have-above?))
    (constantly (inc (bit-shift-left 1 (dec bit-depth))))

    :else
    (let [max-y (dec frame-h)
          left-limit (min max-y (+ y h -1))]
      (fn [k] (nth frame (+ (* (min left-limit (+ y k)) frame-w) (dec x)))))))

(defn v-predict
  "spec 7.11.2.4 step 10 (pAngle == 90): pred[i][j] = AboveRow[j] for all i
   -- valid for V_PRED given this namespace's scope (AngleDeltaY forced 0,
   see namespace docstring for why edge filter/upsample never apply here).
   Same parameter shape as `dc-predict`/`h-predict` (including the unused
   `_frame-h` -- V_PRED only ever reads AboveRow, which doesn't need
   frame-h's max-y clipping the way LeftCol does)."
  [frame frame-w _frame-h x y have-left? have-above? log2W log2H bit-depth]
  (let [w (bit-shift-left 1 log2W)
        h (bit-shift-left 1 log2H)
        ar (above-row-fn frame frame-w x y have-left? have-above? w bit-depth)
        row (mapv ar (range w))]
    (vec (mapcat (fn [_i] row) (range h)))))

(defn h-predict
  "spec 7.11.2.4 step 11 (pAngle == 180): pred[i][j] = LeftCol[i] for all j
   -- valid for H_PRED given this namespace's scope (AngleDeltaY forced 0,
   see namespace docstring). Same parameter shape as `dc-predict` above."
  [frame frame-w frame-h x y have-left? have-above? log2W log2H bit-depth]
  (let [w (bit-shift-left 1 log2W)
        h (bit-shift-left 1 log2H)
        lc (left-col-fn frame frame-w frame-h x y have-left? have-above? h bit-depth)]
    (vec (mapcat (fn [i] (repeat w (lc i))) (range h)))))

;; ---------------------------------------------------------------------
;; PAETH_PRED (spec 7.11.2.2 "Basic intra prediction process") -- the only
;; supported mode that needs AboveRow[-1]/LeftCol[-1] (the topleft corner
;; sample; LeftCol[-1] == AboveRow[-1] per spec, so only one accessor is
;; needed), per the general "Intra prediction process" section's (08.
;; decoding.process.md #Intra prediction process) four-case derivation:
;; haveAbove&&haveLeft -> CurrFrame[y-1][x-1]; haveAbove-only ->
;; CurrFrame[y-1][x]; haveLeft-only -> CurrFrame[y][x-1]; neither ->
;; 1<<(BitDepth-1). (Note this is a DIFFERENT formula than AboveRow[i]/
;; LeftCol[i]'s own have-only-one-neighbor fallback cases above -- those
;; broadcast a single real sample across the whole row/column, the corner
;; case here picks a specific single sample per its own case list -- so
;; above-row-corner below is its own function, not reducible to
;; above-row-fn/left-col-fn.)

(defn- above-row-corner
  "AboveRow[-1] (== LeftCol[-1]) per spec 7.11.2's general derivation."
  [frame frame-w x y have-left? have-above? bit-depth]
  (cond
    (and have-above? have-left?) (nth frame (+ (* (dec y) frame-w) (dec x)))
    have-above? (nth frame (+ (* (dec y) frame-w) x))
    have-left? (nth frame (+ (* y frame-w) (dec x)))
    :else (bit-shift-left 1 (dec bit-depth))))

(defn paeth-predict
  "spec 7.11.2.2 \"Basic intra prediction process\" (PAETH_PRED): for each
   i=0..h-1, j=0..w-1, base = AboveRow[j] + LeftCol[i] - AboveRow[-1]; pick
   whichever of LeftCol[i]/AboveRow[j]/AboveRow[-1] is closest to base
   (ties broken toward LeftCol, then AboveRow[j], per the spec's ordered
   step list -- transcribed exactly, not just 'closest wins' with an
   unspecified tiebreak). Same parameter shape as dc-predict/v-predict/
   h-predict above (including the shared above-row-fn/left-col-fn
   accessors, whose haveAboveRight/haveBelowLeft-forced-false
   simplification is exact here too: paeth-predict only ever reads
   AboveRow[0..w-1]/LeftCol[0..h-1], never the extended w..w+h-1 range, see
   those helpers' docstrings)."
  [frame frame-w frame-h x y have-left? have-above? log2W log2H bit-depth]
  (let [w (bit-shift-left 1 log2W)
        h (bit-shift-left 1 log2H)
        ar (above-row-fn frame frame-w x y have-left? have-above? w bit-depth)
        lc (left-col-fn frame frame-w frame-h x y have-left? have-above? h bit-depth)
        corner (above-row-corner frame frame-w x y have-left? have-above? bit-depth)]
    (vec (for [i (range h) j (range w)]
           (let [above (ar j)
                 left (lc i)
                 base (- (+ above left) corner)
                 p-left (abs (- base left))
                 p-top (abs (- base above))
                 p-topleft (abs (- base corner))]
             (cond
               (and (<= p-left p-top) (<= p-left p-topleft)) left
               (<= p-top p-topleft) above
               :else corner))))))

;; ---------------------------------------------------------------------
;; SMOOTH_PRED (spec 7.11.2.6 "Smooth intra prediction process", the
;; SMOOTH_PRED case of its three-way mode dispatch -- SMOOTH_V_PRED/
;; SMOOTH_H_PRED are out of scope, see namespace docstring's SMOOTH
;; section). Reuses the shared above-row-fn/left-col-fn accessors exactly
;; like paeth-predict does: smooth-predict only ever reads
;; AboveRow[0..w-1]/LeftCol[0..h-1] (plus AboveRow[w-1]/LeftCol[h-1],
;; already within that same 0..w-1/0..h-1 range -- no extended w..w+h-1
;; access is needed), so those helpers' haveAboveRight/haveBelowLeft-
;; forced-false simplification is exact here too.

(defn- sm-weights-for
  "tables/Sm-Weights-Tx-* selected by log2W/log2H, per spec 7.11.2.6 step
   1/2's dispatch table (log2 2/3/4/5/6 -> 4x4/8x8/16x16/32x32/64x64)."
  [log2]
  (case (long log2)
    2 tables/Sm-Weights-Tx-4x4
    3 tables/Sm-Weights-Tx-8x8
    4 tables/Sm-Weights-Tx-16x16
    5 tables/Sm-Weights-Tx-32x32
    6 tables/Sm-Weights-Tx-64x64))

(defn smooth-predict
  "spec 7.11.2.6 \"Smooth intra prediction process\", SMOOTH_PRED case: for
   each i=0..h-1, j=0..w-1,

     smoothPred = smWeightsY[i]*AboveRow[j] + (256-smWeightsY[i])*LeftCol[h-1]
                + smWeightsX[j]*LeftCol[i]  + (256-smWeightsX[j])*AboveRow[w-1]
     pred[i][j] = Round2(smoothPred, 9)

   where smWeightsX/smWeightsY are `sm-weights-for` of log2W/log2H
   respectively. Same parameter shape as dc-predict/v-predict/h-predict/
   paeth-predict above."
  [frame frame-w frame-h x y have-left? have-above? log2W log2H bit-depth]
  (let [w (bit-shift-left 1 log2W)
        h (bit-shift-left 1 log2H)
        ar (above-row-fn frame frame-w x y have-left? have-above? w bit-depth)
        lc (left-col-fn frame frame-w frame-h x y have-left? have-above? h bit-depth)
        sm-weights-x (sm-weights-for log2W)
        sm-weights-y (sm-weights-for log2H)
        above-right (ar (dec w))
        left-bottom (lc (dec h))
        round2-9 (fn [v] (bit-shift-right (+ v 256) 9))]
    (vec (for [i (range h) j (range w)]
           (let [above (ar j)
                 left (lc i)
                 wy (nth sm-weights-y i)
                 wx (nth sm-weights-x j)
                 smooth-pred (+ (* wy above)
                                (* (- 256 wy) left-bottom)
                                (* wx left)
                                (* (- 256 wx) above-right))]
             (round2-9 smooth-pred))))))
