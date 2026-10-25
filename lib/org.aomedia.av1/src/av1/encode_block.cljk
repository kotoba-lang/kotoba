(ns av1.encode-block
  "encode_block() -- the encode-side inverse of av1.decode-block/
   decode-block, for THIS repo's narrow single-keyframe encode scope only
   (2026-07 AV1 encode task, ADR-2607122000 Migration step 9 continuation):
   a single BLOCK_32X32/PARTITION_NONE leaf covering the whole (32x32)
   frame, DC_PRED (luma) + UV_DC_PRED (chroma, per the chroma encode
   extension below), TX_32X32/DCT_DCT (luma) + TX_16X16/DCT_DCT (chroma) --
   scoped even narrower than av1.decode-block's own scope (which also
   supports V_PRED/H_PRED/PAETH_PRED/SMOOTH_PRED, ADST/TX_4X4, and a
   zero-motion inter-frame extension -- none of which this encode pass
   produces).

   Every context-derivation helper this needs (get-coeff-base-ctx/
   get-coeff-br-ctx/get-dc-sign-ctx/get-txb-skip-ctx-chroma/record-above!/
   record-left!) is REUSED directly from av1.decode-block (made public
   there for exactly this reason -- a visibility-only change, no logic
   change) rather than re-transcribed here: those functions are pure
   (cdf-context math over an already-known coefficient/state map, no
   bitstream interaction), so reusing them structurally GUARANTEES this
   encoder's context derivation can never independently drift from the
   decoder's -- a real risk if the same ~40-line ctx formula were
   hand-copied a second time.

   `write-coeffs` mirrors av1.decode-block/read-coeffs's own three passes
   (all_zero -> transform_type -> eob -> level pass (c=eob-1 downto 0) ->
   sign+golomb pass (c=0..eob-1)) in the same order, over the SAME target
   `quant` array (already-quantized coefficients in raster position, from
   av1.transform/forward-transform-2d + quantize) -- so every ctx this
   encoder computes mid-write is computed from exactly the same
   partially-filled `quant` state read-coeffs would have decoded UP TO
   that point, guaranteeing the two sides can't desync on context.
   `write-coeffs` was ALREADY fully generalized over plane/tx-size via its
   `spec` argument (the SAME map shape av1.decode-block's `luma-spec-base`/
   `chroma-spec-base`/`u-spec`/`v-spec` use) before this chroma encode
   extension -- since chroma's TxType is DCT_DCT with a structural
   zero-bit guarantee for this scope (no `transform_type()` write needed
   for plane>0, exactly mirroring av1.decode-block/read-coeffs' own
   plane==0-only `read-transform-type` call), `write-coeffs` needed
   ZERO changes to serve chroma (TX_16X16, plane 1/2) in addition to luma
   (TX_32X32, plane 0) -- av1.encode's chroma extension only needed a new
   `write-uv-mode` (below) and new chroma `spec` maps at the call site (see
   av1.encode's own chroma section)."
  (:require [av1.bool-encoder :as be]
            [av1.tables :as tables]
            [av1.decode-block :as db]))

;; ---------------------------------------------------------------------
;; Generic per-context CDF get/put -- mirrors av1.decode-block's
;; get-cdf/put-cdf/read-cdf-symbol, but for the ENCODE side (writes a
;; caller-supplied `sym` instead of reading one).

(defn- get-cdf [state cdf-key ctx-key default]
  (get-in state [cdf-key ctx-key] default))

(defn- put-cdf [state cdf-key ctx-key cdf]
  (assoc-in state [cdf-key ctx-key] cdf))

(defn- write-cdf-symbol
  "Encode-side mirror of av1.decode-block's private read-cdf-symbol: write
   `sym` against the tile-persisted (or default) cdf at `[cdf-key
   ctx-key]`, adapting per `(:cdf-adapt? state)` via the SAME
   av1.bool-decoder/adapt-cdf both sides share (see its docstring).
   Returns state'."
  [state cdf-key ctx-key default sym]
  (let [cdf (get-cdf state cdf-key ctx-key default)
        adapt? (:cdf-adapt? state true)
        [cdf' enc'] (be/encode-symbol (:enc state) cdf sym adapt?)]
    (-> state (assoc :enc enc') (put-cdf cdf-key ctx-key cdf'))))

(defn- write-literal-bits
  "Encode-side mirror of av1.bool-decoder/read-literal (via repeated
   av1.decode-block-style raw-bit reads, `bd/read-literal` on the decode
   side / `be/encode-literal` here) -- used for eob's raw extra bits and
   the sign+golomb pass's non-DC sign bit / golomb suffix bits, all of
   which av1.decode-block reads via `bd/read-literal state 1` one bit at a
   time (not through a cdf at all)."
  [state n value]
  (assoc state :enc (be/encode-literal (:enc state) n value)))

;; ---------------------------------------------------------------------
;; read_skip()'s encode-side inverse.

(defn write-skip [state row col avail-u? avail-l? skip]
  (let [ctx (+ (if avail-u? (get (:skips state) [(dec row) col] 0) 0)
               (if avail-l? (get (:skips state) [row (dec col)] 0) 0))]
    (write-cdf-symbol state :skip-cdfs ctx (nth tables/Default-Skip-Cdf ctx) skip)))

;; ---------------------------------------------------------------------
;; intra_frame_y_mode's encode-side inverse -- see av1.decode-block/
;; read-y-mode's docstring for the ctx derivation and the (0,0)-only
;; scope restriction (this repo's only supported ctx pair). `y-mode` must
;; be DC_PRED for this namespace's scope (throws otherwise, matching
;; read-y-mode's own restriction to a small mode set, narrowed further
;; here to only DC_PRED since that's all this encode pass produces).

(defn write-y-mode [state row col avail-u? avail-l? y-mode]
  (when (not= y-mode db/DC_PRED)
    (throw (ex-info "av1.encode-block: out of scope: only DC_PRED is supported by this encode pass"
                     {:reason :unsupported-y-mode :y-mode y-mode})))
  (let [neighbor-mode (fn [avail? r c] (if avail? (get (:y-modes state) [r c] db/DC_PRED) db/DC_PRED))
        ctx-of (fn [m] (nth tables/Intra-Mode-Context m))
        abovemode (ctx-of (neighbor-mode avail-u? (dec row) col))
        leftmode (ctx-of (neighbor-mode avail-l? row (dec col)))
        ctx [abovemode leftmode]]
    (when (not= [0 0] ctx)
      (throw (ex-info "av1.encode-block: out of scope: intra_frame_y_mode ctx != (0,0)"
                       {:reason :unsupported-y-mode-ctx :ctx ctx})))
    (write-cdf-symbol state :y-mode-cdf [0 0] tables/Default-Intra-Frame-Y-Mode-Cdf-0-0 y-mode)))

;; ---------------------------------------------------------------------
;; uv_mode's encode-side inverse -- chroma (Cb/Cr) encode extension
;; (ADR-2607122000 Migration step 9 continuation, mirroring
;; av1.decode-block's own chroma-decode extension). See av1.decode-block/
;; read-uv-mode's docstring for the ctx derivation (the block's own already-
;; decoded YMode, NOT a neighbor lookup) and the restriction to
;; {DC_PRED,V_PRED,H_PRED} y-modes (chroma+PAETH_PRED/SMOOTH_PRED luma has
;; no transcribed TileUVModeCflAllowedCdf row, out of scope for both encode
;; and decode). `uv-mode` must be UV_DC_PRED for this encode pass's scope
;; (throws otherwise, matching this namespace's `write-y-mode`'s own
;; DC_PRED-only restriction)."

(defn write-uv-mode [state y-mode uv-mode]
  (when (not (contains? #{db/DC_PRED db/V_PRED db/H_PRED} y-mode))
    (throw (ex-info "av1.encode-block: out of scope: uv_mode ctx (YMode) not in {DC_PRED,V_PRED,H_PRED}"
                     {:reason :unsupported-y-mode-for-uv-mode-ctx :y-mode y-mode})))
  (when (not= uv-mode db/UV_DC_PRED)
    (throw (ex-info "av1.encode-block: out of scope: only UV_DC_PRED is supported by this encode pass"
                     {:reason :unsupported-uv-mode :uv-mode uv-mode})))
  (write-cdf-symbol state :uv-mode-cdf y-mode
                     (nth tables/Default-Uv-Mode-Cfl-Allowed-Cdf-Dc-V-H y-mode) uv-mode))

;; ---------------------------------------------------------------------
;; eob's encode-side inverse -- see av1.decode-block/read-eob's docstring
;; for the eob_pt/eob0/eob-shift/eob_extra/raw-extra-bits derivation this
;; inverts. `eob0-for-pt`/`bucket-size-for-pt` below are the same
;; closed-form eob0/bucket-size read-eob computes inline, factored out
;; here since write-eob needs both the forward (pt -> eob0) direction (to
;; search for the right pt) AND, once found, the remaining/eob-extra/
;; raw-bits decomposition read-eob's OWN inverse needs.

(defn- eob0-for-pt [pt] (if (< pt 2) pt (inc (bit-shift-left 1 (- pt 2)))))
(defn- bucket-size-for-pt [pt] (if (< pt 3) 1 (bit-shift-left 1 (- pt 2))))

(defn- pt-for-eob
  "Find the eob_pt bucket (1-indexed, matching read-eob's `eob-pt`) whose
   `[eob0, eob0+bucket-size)` range contains `target-eob`."
  [target-eob]
  (loop [pt 1]
    (when (> pt 32)
      (throw (ex-info "av1.encode-block: internal: no eob_pt bucket found (target-eob too large)"
                       {:target-eob target-eob})))
    (let [e0 (eob0-for-pt pt) size (bucket-size-for-pt pt)]
      (if (and (>= target-eob e0) (< target-eob (+ e0 size)))
        pt
        (recur (inc pt))))))

(defn- write-eob
  [state q-idx target-eob eob-pt-cdf-key eob-pt-table eob-extra-cdf-key eob-extra-table]
  (let [pt (pt-for-eob target-eob)
        eob-pt-sym (dec pt)
        state1 (write-cdf-symbol state eob-pt-cdf-key [] (nth eob-pt-table q-idx) eob-pt-sym)
        eob-shift (max -1 (- pt 3))]
    (if (>= eob-shift 0)
      (let [e0 (eob0-for-pt pt)
            remaining (- target-eob e0)
            eob-extra-bit (bit-and (bit-shift-right remaining eob-shift) 1)
            state2 (write-cdf-symbol state1 eob-extra-cdf-key eob-shift
                                     (get-in eob-extra-table [q-idx eob-shift]) eob-extra-bit)
            n (max 0 (- pt 2))]
        (reduce (fn [s i]
                  (let [shift (- n 1 i)
                        bit (bit-and (bit-shift-right remaining shift) 1)]
                    (write-literal-bits s 1 bit)))
                state2 (range 1 n)))
      state1)))

;; ---------------------------------------------------------------------
;; golomb's encode-side inverse -- see av1.decode-block/read-golomb's
;; docstring: a standard Exp-Golomb code, `(L-1)` zero bits + a 1-bit
;; terminator + `(L-1)` raw suffix bits, `L = FloorLog2(x)+1` (x>=1, the
;; number of bits needed to represent `x`).

(defn- br-floor-log2 [x]
  (loop [s 0, x' x] (if (<= x' 1) s (recur (inc s) (quot x' 2)))))

(defn- write-golomb [state x]
  (when (< x 1)
    (throw (ex-info "av1.encode-block: internal: write-golomb requires x >= 1" {:x x})))
  (let [l (inc (br-floor-log2 x))]
    (-> state
        (write-literal-bits (dec l) 0)   ;; (l-1) zero bits
        (write-literal-bits 1 1)         ;; terminator
        (write-literal-bits (dec l) (bit-and x (dec (bit-shift-left 1 (dec l))))))))  ;; (l-1) suffix bits

;; ---------------------------------------------------------------------
;; coeffs()'s encode-side inverse -- `spec` is av1.decode-block's own
;; `luma-spec-base` (merged with this frame's delta-q-dc/delta-q-ac, see
;; av1.encode's orchestration) -- reused as-is (same map shape
;; read-coeffs/decode-transform-block already consume) rather than a
;; parallel encode-only spec map, so there is exactly one place that
;; defines \"which cdf-key/table goes with TX_32X32 luma\".
;;
;; `quant` is the target flat row-major (already-quantized, from
;; av1.transform/forward-transform-2d+quantize) coefficient array for this
;; transform block. Returns [eob state'] -- `eob` is threaded back to the
;; caller (av1.encode) so it can decide the luma-result bookkeeping the
;; same shape av1.decode-block's decode-transform-block returns.

(defn write-coeffs
  [state q-idx row col mi-cols mi-rows txb-skip-ctx spec quant]
  (let [{:keys [plane bwl w scan
                txb-skip-cdf-key txb-skip-table
                eob-pt-cdf-key eob-pt-table eob-extra-cdf-key eob-extra-table
                coeff-base-eob-cdf-key coeff-base-eob-table
                coeff-base-cdf-key coeff-base-table
                coeff-br-cdf-key coeff-br-table
                dc-sign-cdf-key dc-sign-table]} spec
        w4 (bit-shift-right w 2) h4 w4
        ;; eob = 1 + (last scan-order index c whose scan[c] position is
        ;; nonzero in `quant`), or 0 if every position is 0 (all_zero=1) --
        ;; the encode-side derivation of what read-coeffs' `eob` return
        ;; value already tells the DECODE side (this is the one value this
        ;; fn computes from `quant` rather than mirroring a bitstream
        ;; read, since `quant` is the encoder's own already-chosen target).
        seg-eob (count scan)
        eob (inc (or (last (keep-indexed (fn [c pos] (when (not= 0 (nth quant pos)) c)) scan)) -1))
        all-zero (if (zero? eob) 1 0)
        state1 (write-cdf-symbol state txb-skip-cdf-key txb-skip-ctx
                                  (get-in txb-skip-table [q-idx txb-skip-ctx]) all-zero)]
    (if (pos? all-zero)
      [0 (-> state1 (db/record-above! plane col w4 0 0) (db/record-left! plane row h4 0 0))]
      (let [dc-sign-ctx (db/get-dc-sign-ctx state1 plane col row w4 h4 mi-cols mi-rows)
            ;; transform_type(): for TX_32X32/is_inter==0, get_tx_set()
            ;; structurally forces TX_SET_DCTONLY (zero bits) -- see
            ;; av1.decode-block/read-transform-type's docstring. This
            ;; encode pass's scope (TX_32X32/DCT_DCT only) never needs the
            ;; real cdf-write branch that a smaller/inter tx size would.
            state1b state1
            state2 (write-eob state1b q-idx eob eob-pt-cdf-key eob-pt-table eob-extra-cdf-key eob-extra-table)
            ;; level pass: c = eob-1 downto 0, writing coeff_base_eob (at
            ;; c=eob-1) or coeff_base (elsewhere) + coeff_br continuation,
            ;; exactly mirroring read-coeffs' own loop. CRITICAL: unlike
            ;; the rest of this fn, `get-coeff-base-ctx`/`get-coeff-br-ctx`
            ;; must NOT see `quant` (the fully-known target array) --
            ;; av1.decode-block's read-coeffs computes ctx from
            ;; `quant1`-IN-PROGRESS (starts all-zero, only positions with
            ;; HIGHER scan-index than the one currently being processed are
            ;; populated, since it's built by the SAME c=eob-1-downto-0
            ;; pass this mirrors) -- a not-yet-decoded neighbor reads as 0
            ;; on the real decoder regardless of what its own eventual
            ;; value will be. Using the full target `quant` here instead
            ;; would let a not-yet-\"decoded\" neighbor's real (nonzero)
            ;; value leak into ctx, picking a DIFFERENT symbol than the
            ;; real decoder (which only ever sees 0 for that neighbor at
            ;; this point) would decode it as -- a genuine desync bug, not
            ;; a cosmetic one. So this reduce threads its own `quant-so-far`
            ;; (all-zero to start, UNSIGNED and capped exactly the way
            ;; read-coeffs' own `level2` is: `min(abs(target), 15)` --
            ;; values >14 are only representable via the sign-pass's
            ;; golomb escape, so the level pass itself never stores more
            ;; than 15, matching read-coeffs' own quant1 exactly) instead
            ;; of reading `quant` (the true, unsigned-magnitude-unbounded
            ;; target) for context.
            [_quant-so-far state3]
            (reduce
             (fn [[qsf s] c]
               (let [pos (nth scan c)
                     eob? (= c (dec eob))
                     level (abs (long (nth quant pos)))
                     capped-level (min level 15)
                     ctx (if eob?
                           (+ (- (db/get-coeff-base-ctx qsf pos c true bwl w) tables/SIG_COEF_CONTEXTS)
                              tables/SIG_COEF_CONTEXTS_EOB)
                           (db/get-coeff-base-ctx qsf pos c false bwl w))
                     ;; base-level: what the coeff_base_eob/coeff_base
                     ;; symbol itself can directly represent (capped at 3
                     ;; -- av1.decode-block's `level`/`level2` before/after
                     ;; the br-loop refinement below). `level` (this fn's
                     ;; `level` binding) is >=1 at the eob position by
                     ;; construction (eob is defined as the last nonzero
                     ;; scan position + 1, see `eob` above).
                     base-level (min level 3)
                     s2 (if eob?
                          (write-cdf-symbol s coeff-base-eob-cdf-key ctx (get-in coeff-base-eob-table [q-idx ctx])
                                            (dec base-level))
                          (write-cdf-symbol s coeff-base-cdf-key ctx (get-in coeff-base-table [q-idx ctx]) base-level))]
                 (if (> level tables/NUM_BASE_LEVELS)
                   (let [max-iters (quot tables/COEFF_BASE_RANGE (dec tables/BR_CDF_SIZE))]
                     (loop [idx 0, remaining (- capped-level base-level), s s2]
                       (if (>= idx max-iters)
                         [(assoc qsf pos capped-level) s]
                         (let [br-ctx (db/get-coeff-br-ctx qsf pos bwl w)
                               br (min remaining (dec tables/BR_CDF_SIZE))
                               s' (write-cdf-symbol s coeff-br-cdf-key br-ctx (get-in coeff-br-table [q-idx br-ctx]) br)]
                           (if (< br (dec tables/BR_CDF_SIZE))
                             [(assoc qsf pos capped-level) s']
                             (recur (inc idx) (- remaining br) s'))))))
                   [(assoc qsf pos capped-level) s2])))
             [(vec (repeat seg-eob 0)) state2] (range (dec eob) -1 -1))
            ;; sign + golomb pass: c = 0..eob-1 forward.
            [dc-category cul-level state4]
            (reduce
             (fn [[dc-cat cul s] c]
               (let [pos (nth scan c)
                     qv (nth quant pos)]
                 (if (zero? qv)
                   [dc-cat cul s]
                   (let [sign (if (neg? qv) 1 0)
                         abs-qv (abs (long qv))
                         s2 (if (zero? c)
                              (write-cdf-symbol s dc-sign-cdf-key dc-sign-ctx (get-in dc-sign-table [q-idx dc-sign-ctx]) sign)
                              (write-literal-bits s 1 sign))
                         over-threshold? (> abs-qv (+ tables/NUM_BASE_LEVELS tables/COEFF_BASE_RANGE))
                         s3 (if over-threshold?
                              (write-golomb s2 (- abs-qv tables/COEFF_BASE_RANGE tables/NUM_BASE_LEVELS))
                              s2)
                         dc-cat' (if (and (zero? pos) (pos? abs-qv)) (if (pos? sign) 1 2) dc-cat)
                         qv3 (bit-and abs-qv 0xFFFFF)
                         cul' (+ cul qv3)]
                     [dc-cat' cul' s3]))))
             [0 0 state3]
             (range eob))
            cul-level (min 63 cul-level)
            state5 (-> state4 (db/record-above! plane col w4 dc-category cul-level) (db/record-left! plane row h4 dc-category cul-level))]
        [eob state5]))))
