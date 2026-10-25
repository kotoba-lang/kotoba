(ns h264.intra-pred
  "H.264 Intra_16x16 luma prediction (§8.3.3) AND Intra_Chroma prediction
   (§8.3.4, ChromaArrayType 1 / 4:2:0 8x8 chroma blocks) modes.

   Luma (`predict-16x16`): modes 0 (Vertical), 1 (Horizontal), 2 (DC) —
   mode 3 (Plane) is NOT implemented (out of scope, see README/task scope
   notes).

   Intra_4x4 (`predict-4x4`, §8.3.1.2, mb_type I_NxN with
   transform_size_8x8_flag 0) IS implemented, all nine modes — see the
   bottom of this file. Intra_8x8 (§8.3.2, the OTHER thing mb_type I_NxN
   can mean) is NOT, and is deliberately not half-implemented: it needs the
   8x8 integer transform and the §8.3.2.2 reference-sample low-pass filter,
   and `h264.decode/reject-intra-8x8!` refuses it with a pinned reason
   rather than falling through to the 4x4 modes.

   NOTE there are now THREE separate prediction-mode numberings in this
   namespace and they are different permutations of each other: Intra_16x16
   (Table 8-4, 0=Vertical/1=Horizontal/2=DC/3=Plane), Intra_4x4 (Table 8-2,
   0=Vertical/1=Horizontal/2=DC/3=DDL/4=DDR/5=VR/6=HD/7=VL/8=HU) and
   Intra_Chroma (Table 8-5, 0=DC/1=Horizontal/2=Vertical/3=Plane). Only
   Horizontal (1) and DC (2) mean the same thing in all three.

   Chroma (`predict-chroma-8x8`): modes 0 (DC), 1 (Horizontal), 2
   (Vertical), 3 (Plane) — ALL FOUR §8.3.4 chroma modes are implemented
   (unlike luma, where Plane is out of scope) because real-world encoders
   select chroma Plane even for near-flat chroma content whenever both
   neighbors are available (observed empirically with real libx264 output
   while building this repo's chroma golden vectors — a real encoder chose
   Plane for constant Cb=Cr=128 content at a moderate QP, apparently as an
   RD tie-break, not because the content had any actual gradient) — so
   leaving it unimplemented would make chroma decode fail on ordinary
   multi-macroblock real streams, not just contrived ones. NOTE the chroma
   mode NUMBERING (Table 8-5: 0=DC/1=Horizontal/2=Vertical/3=Plane) is a
   DIFFERENT permutation than the luma Intra_16x16 mode numbering above
   (0=Vertical/1=Horizontal/2=DC) — this is a real, easy-to-miss spec
   quirk, not a typo; `h264.decode` reads the two mode syntax elements
   (`Intra16x16PredMode`/`intra_chroma_pred_mode`) into this SAME
   `predict-*` mode-number convention split deliberately to avoid silently
   swapping them.

   New implementation as part of the kotoba-lang reverse-domain
   media/graphics standards-substrate split (com-junkawasaki/root)."
  )

(defn- clip8 [v] (max 0 (min 255 v)))

(defn predict-16x16
  "Predict a 16x16 luma macroblock per §8.3.3. `mode` is 0 (Vertical), 1
   (Horizontal), or 2 (DC). `top-row`/`left-col` are 16-element pixel
   vectors from the already-reconstructed neighbor macroblocks (ignored /
   may be nil when the corresponding availability flag is false).

   Per spec, Vertical requires `top-available?` and Horizontal requires
   `left-available?` (a conformant encoder never selects them otherwise);
   this throws rather than silently guessing if that's violated. DC mode
   is defined for all four availability combinations (§8.3.3.1): both
   available → rounded average of both; only one available → that one's
   average; neither → 128 (the flat default used when this MB has no
   reconstructed neighbors at all, e.g. the top-left MB of a frame)."
  [mode {:keys [top-available? left-available? top-row left-col]}]
  (case mode
    0 (if top-available?
        (vec (repeat 16 top-row))
        (throw (ex-info "h264.intra-pred: Vertical mode requires an available top neighbor" {})))
    1 (if left-available?
        (mapv #(vec (repeat 16 %)) left-col)
        (throw (ex-info "h264.intra-pred: Horizontal mode requires an available left neighbor" {})))
    2 (let [dc (cond
                 (and top-available? left-available?)
                 (quot (+ (reduce + top-row) (reduce + left-col) 16) 32)
                 top-available? (quot (+ (reduce + top-row) 8) 16)
                 left-available? (quot (+ (reduce + left-col) 8) 16)
                 :else 128)]
        (vec (repeat 16 (vec (repeat 16 dc)))))
    (throw (ex-info "h264.intra-pred: unsupported Intra_16x16 pred mode (only 0/1/2 implemented)"
                     {:mode mode}))))

(defn- chroma-dc-quadrants
  "The 4 scalar DC values for the top-left/top-right/bottom-left/bottom-
   right 4x4 quadrants of an 8x8 Intra_Chroma_DC-predicted block (§8.3.4.1).
   Ported 1:1 (including which raw SUM feeds the bottom-right quadrant —
   it's `(sum-top-right + sum-bottom-left)`, NOT an average of the two
   already-rounded quadrant DC values) from ffmpeg's `pred8x8_dc_c`/
   `pred8x8_left_dc_c`/`pred8x8_top_dc_c` (`libavcodec/h264pred_template.c`)."
  [top-available? left-available? top-row left-col]
  (cond
    (and top-available? left-available?)
    (let [sum-t04 (reduce + (subvec top-row 0 4))
          sum-t48 (reduce + (subvec top-row 4 8))
          sum-l04 (reduce + (subvec left-col 0 4))
          sum-l48 (reduce + (subvec left-col 4 8))]
      [(quot (+ sum-t04 sum-l04 4) 8)   ; top-left: both neighbors, 8 samples
       (quot (+ sum-t48 2) 4)           ; top-right: top only, 4 samples
       (quot (+ sum-l48 2) 4)           ; bottom-left: left only, 4 samples
       (quot (+ sum-t48 sum-l48 4) 8)]) ; bottom-right: top-right + bottom-left RAW sums, 8 samples
    top-available?
    (let [dc-l (quot (+ (reduce + (subvec top-row 0 4)) 2) 4)
          dc-r (quot (+ (reduce + (subvec top-row 4 8)) 2) 4)]
      [dc-l dc-r dc-l dc-r])
    left-available?
    (let [dc-top (quot (+ (reduce + (subvec left-col 0 4)) 2) 4)
          dc-bot (quot (+ (reduce + (subvec left-col 4 8)) 2) 4)]
      [dc-top dc-top dc-bot dc-bot])
    :else
    [128 128 128 128]))

(defn- assemble-chroma-dc-grid
  [[dc-tl dc-tr dc-bl dc-br]]
  (vec (for [row (range 8)]
         (vec (for [col (range 8)]
                (cond (and (< row 4) (< col 4)) dc-tl
                      (< row 4) dc-tr
                      (< col 4) dc-bl
                      :else dc-br))))))

(defn- chroma-plane-grid
  "8x8 Intra_Chroma_Plane prediction (§8.3.4.4). `top-row`/`left-col` are
   8-element pixel vectors (this block's own top/left neighbor samples,
   indices 0..7); `corner` is the single diagonal top-left sample p[-1,-1]
   (the top-left MB's bottom-right chroma pixel — always available
   whenever BOTH `top-row`/`left-col` are, in single-slice raster-scan
   decode order, since that MB was necessarily already reconstructed; see
   `h264.decode/decode-macroblock!`'s `topleft-mb` derivation). Ported 1:1
   (including the exact H/V weighted-difference formula and the `a`
   integer-plane-origin term) from ffmpeg's `pred8x8_plane_c`
   (`libavcodec/h264pred_template.c`)."
  [top-row left-col corner]
  (let [top #(nth top-row %) left #(nth left-col %)
        h-raw (+ (- (top 4) (top 2))
                  (* 2 (- (top 5) (top 1)))
                  (* 3 (- (top 6) (top 0)))
                  (* 4 (- (top 7) corner)))
        v-raw (+ (- (left 4) (left 2))
                  (* 2 (- (left 5) (left 1)))
                  (* 3 (- (left 6) (left 0)))
                  (* 4 (- (left 7) corner)))
        H (bit-shift-right (+ (* 17 h-raw) 16) 5)
        V (bit-shift-right (+ (* 17 v-raw) 16) 5)
        a (- (* 16 (+ (left 7) (top 7) 1)) (* 3 (+ V H)))]
    (vec (for [row (range 8)]
           (let [a-row (+ a (* row V))]
             (vec (for [col (range 8)]
                    (clip8 (bit-shift-right (+ a-row (* col H)) 5)))))))))

(defn predict-chroma-8x8
  "Predict an 8x8 Intra_Chroma block (one component, Cb or Cr) per §8.3.4.
   `mode` is 0 (DC), 1 (Horizontal), 2 (Vertical), or 3 (Plane) — NOTE this
   numbering is Table 8-5's chroma numbering, a DIFFERENT permutation than
   `predict-16x16`'s luma mode numbers (see namespace docstring).
   `top-row`/`left-col` are 8-element pixel vectors from the already-
   reconstructed neighbor macroblock's SAME chroma component (ignored/may
   be nil when the corresponding availability flag is false); `corner` (Plane
   only) is the diagonal top-left MB's bottom-right sample of this SAME
   component."
  [mode {:keys [top-available? left-available? top-row left-col corner]}]
  (case mode
    2 (if top-available?
        (vec (repeat 8 top-row))
        (throw (ex-info "h264.intra-pred: chroma Vertical mode requires an available top neighbor" {})))
    1 (if left-available?
        (mapv #(vec (repeat 8 %)) left-col)
        (throw (ex-info "h264.intra-pred: chroma Horizontal mode requires an available left neighbor" {})))
    0 (assemble-chroma-dc-grid (chroma-dc-quadrants top-available? left-available? top-row left-col))
    3 (if (and top-available? left-available?)
        (chroma-plane-grid top-row left-col corner)
        (throw (ex-info "h264.intra-pred: chroma Plane mode requires both top and left neighbors" {})))
    (throw (ex-info "h264.intra-pred: unsupported Intra_Chroma pred mode (only 0/1/2/3 implemented)"
                     {:mode mode}))))

;; --- Intra_4x4 luma prediction (§8.3.1.2.1-9) — added by the Intra_4x4
;;     increment. Intra_8x8 (§8.3.2, mb_type I_NxN with
;;     transform_size_8x8_flag == 1, needing the separate 8x8 transform AND
;;     the §8.3.2.2 reference-sample low-pass filter) is DELIBERATELY NOT
;;     here and is NOT half-implemented: `h264.decode` rejects it with a
;;     pinned reason literal rather than falling through to these 4x4
;;     modes, which would silently mis-predict. ---

(defn- i4x4-neighbour-samples
  "Assemble the 13 §8.3.1.2 neighbouring samples for ONE 4x4 luma block into
   two flat accessors: `pt` (8 elements = p[0..7,-1], top then top-right)
   and `pl` (4 elements = p[-1,0..3]), plus the scalar `ptl` = p[-1,-1].

   The ONE substitution the spec mandates here (§8.3.1.2, and it is easy to
   miss because it is stated in the sample-derivation clause rather than in
   any individual mode's clause): when p[x,-1] for x = 4..7 are marked NOT
   available for Intra_4x4 prediction but p[3,-1] IS available, p[4..7,-1]
   are SUBSTITUTED with the value of p[3,-1]. This is not an optional
   optimization — Diagonal_Down_Left (mode 3) and Vertical_Left (mode 7)
   read p[4..7,-1] unconditionally and a real encoder DOES select them for
   blocks whose above-right neighbour is unavailable (5 of the 16 4x4 block
   positions per macroblock always have an unavailable above-right — the
   {3,7,11,13,15} set, see `h264.decode/i4x4-topright-source`), relying on
   the decoder performing exactly this substitution.

   Returns nil for `pt` when the top neighbour itself is unavailable (in
   which case no top-reading mode is legal and `predict-4x4` throws)."
  [{:keys [top-available? top-right-available? top top-right left topleft]}]
  {:pt (when top-available?
         (into (vec top)
               (if top-right-available? (vec top-right) (vec (repeat 4 (nth top 3))))))
   :pl (when left (vec left))
   :ptl topleft})

(defn predict-4x4
  "Predict ONE 4x4 luma block per §8.3.1.2.1-9. `mode` is Intra4x4PredMode
   (0 Vertical, 1 Horizontal, 2 DC, 3 Diagonal_Down_Left, 4
   Diagonal_Down_Right, 5 Vertical_Right, 6 Horizontal_Down, 7
   Vertical_Left, 8 Horizontal_Up — Table 8-2's numbering, which is a THIRD
   numbering distinct from both `predict-16x16`'s Intra_16x16 numbering and
   `predict-chroma-8x8`'s Table 8-5 chroma numbering; only mode 1
   (Horizontal) and mode 2 (DC) happen to coincide across all three).

   Neighbour samples arrive as `{:top-available? :top-right-available?
   :left-available? :topleft-available? :top :top-right :left :topleft}`
   where `:top` is the 4-vector p[0..3,-1], `:top-right` the 4-vector
   p[4..7,-1] (may be nil — see `i4x4-neighbour-samples`' substitution),
   `:left` the 4-vector p[-1,0..3], `:topleft` the scalar p[-1,-1].
   Availability is per-BLOCK, not per-macroblock: the 16 4x4 blocks of one
   macroblock have five distinct availability patterns and the block at
   grid position [0,0] of the top-left macroblock of a picture has none of
   them (only DC is then legal). Returns a 4x4 row-major vector-of-vectors.

   Every mode except DC has a mandatory availability precondition (§8.3.1.2.x
   'this mode shall be used only when ... are marked as available'); a
   conformant encoder never selects one otherwise, so this THROWS rather
   than substituting a guess — the same choice `predict-16x16` makes, and
   the reason a real desync surfaces as an exception instead of as
   plausible-looking wrong pixels."
  [mode {:keys [top-available? left-available? topleft-available?] :as nb}]
  (let [{:keys [pt pl ptl]} (i4x4-neighbour-samples nb)
        need! (fn [ok? what]
                (when-not ok?
                  (throw (ex-info (str "h264.intra-pred: Intra_4x4 mode " mode
                                       " requires available " what " neighbour samples")
                                  {:mode mode :missing what}))))
        t #(nth pt %)
        l #(nth pl %)
        ;; §8.3.1.2's sample grid is p[x,y] with x from -1 and y from -1, so
        ;; index -1 on EITHER axis is the single corner sample p[-1,-1] — it
        ;; is not out of range, it is the same pixel reached two ways. Modes
        ;; 4/5/6 all index into the top row or the left column with an
        ;; expression that reaches -1 for the blocks nearest the corner
        ;; (Diagonal_Down_Right at x-y == 1, Vertical_Right at zVR == -2,
        ;; Horizontal_Down at zHD == -2), so they go through `px`/`py`
        ;; instead of `t`/`l`. Using `t`/`l` there does not mis-predict
        ;; quietly — it throws IndexOutOfBounds — but only for content that
        ;; actually selects those modes at those positions, which no flat
        ;; fixture ever does.
        px (fn [i] (if (neg? i) ptl (nth pt i)))
        py (fn [i] (if (neg? i) ptl (nth pl i)))
        grid (fn [f] (vec (for [y (range 4)] (vec (for [x (range 4)] (f x y))))))
        avg2 (fn [a b] (bit-shift-right (+ a b 1) 1))
        avg3 (fn [a b c] (bit-shift-right (+ a (* 2 b) c 2) 2))]
    (case mode
      ;; §8.3.1.2.1 Intra_4x4_Vertical
      0 (do (need! top-available? "top") (grid (fn [x _] (t x))))
      ;; §8.3.1.2.2 Intra_4x4_Horizontal
      1 (do (need! left-available? "left") (grid (fn [_ y] (l y))))
      ;; §8.3.1.2.3 Intra_4x4_DC — the ONLY mode with no precondition.
      2 (let [dc (cond
                   (and top-available? left-available?)
                   (bit-shift-right (+ (reduce + (subvec pt 0 4)) (reduce + pl) 4) 3)
                   left-available? (bit-shift-right (+ (reduce + pl) 2) 2)
                   top-available? (bit-shift-right (+ (reduce + (subvec pt 0 4)) 2) 2)
                   :else 128)]
          (grid (fn [_ _] dc)))
      ;; §8.3.1.2.4 Intra_4x4_Diagonal_Down_Left — reads p[0..7,-1], i.e.
      ;; the top-right samples (possibly substituted, see above).
      3 (do (need! top-available? "top")
            (grid (fn [x y]
                    (if (and (= x 3) (= y 3))
                      (bit-shift-right (+ (t 6) (* 3 (t 7)) 2) 2)
                      (avg3 (t (+ x y)) (t (+ x y 1)) (t (+ x y 2)))))))
      ;; §8.3.1.2.5 Intra_4x4_Diagonal_Down_Right
      4 (do (need! (and top-available? left-available? topleft-available?) "top+left+top-left")
            (grid (fn [x y]
                    (cond
                      (> x y) (avg3 (px (- x y 2)) (px (- x y 1)) (px (- x y)))
                      (< x y) (avg3 (py (- y x 2)) (py (- y x 1)) (py (- y x)))
                      :else (avg3 (t 0) ptl (l 0))))))
      ;; §8.3.1.2.6 Intra_4x4_Vertical_Right
      5 (do (need! (and top-available? left-available? topleft-available?) "top+left+top-left")
            (grid (fn [x y]
                    (let [z (- (* 2 x) y)
                          h (bit-shift-right y 1)]
                      (cond
                        (contains? #{0 2 4 6} z) (avg2 (px (- x h 1)) (px (- x h)))
                        (contains? #{1 3 5} z) (avg3 (px (- x h 2)) (px (- x h 1)) (px (- x h)))
                        (= z -1) (avg3 (l 0) ptl (t 0))
                        :else (avg3 (py (- y 1)) (py (- y 2)) (py (- y 3))))))))
      ;; §8.3.1.2.7 Intra_4x4_Horizontal_Down
      6 (do (need! (and top-available? left-available? topleft-available?) "top+left+top-left")
            (grid (fn [x y]
                    (let [z (- (* 2 y) x)
                          h (bit-shift-right x 1)]
                      (cond
                        (contains? #{0 2 4 6} z) (avg2 (py (- y h 1)) (py (- y h)))
                        (contains? #{1 3 5} z) (avg3 (py (- y h 2)) (py (- y h 1)) (py (- y h)))
                        (= z -1) (avg3 (l 0) ptl (t 0))
                        :else (avg3 (px (- x 1)) (px (- x 2)) (px (- x 3))))))))
      ;; §8.3.1.2.8 Intra_4x4_Vertical_Left — also reads p[4..7,-1].
      7 (do (need! top-available? "top")
            (grid (fn [x y]
                    (let [h (bit-shift-right y 1)]
                      (if (even? y)
                        (avg2 (t (+ x h)) (t (+ x h 1)))
                        (avg3 (t (+ x h)) (t (+ x h 1)) (t (+ x h 2))))))))
      ;; §8.3.1.2.9 Intra_4x4_Horizontal_Up
      8 (do (need! left-available? "left")
            (grid (fn [x y]
                    (let [z (+ x (* 2 y))
                          h (bit-shift-right x 1)]
                      (cond
                        (contains? #{0 2 4} z) (avg2 (l (+ y h)) (l (+ y h 1)))
                        (contains? #{1 3} z) (avg3 (l (+ y h)) (l (+ y h 1)) (l (+ y h 2)))
                        (= z 5) (bit-shift-right (+ (l 2) (* 3 (l 3)) 2) 2)
                        :else (l 3))))))
      (throw (ex-info "h264.intra-pred: unsupported Intra_4x4 pred mode (Table 8-2 defines 0..8 only)"
                      {:mode mode})))))
