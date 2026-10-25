(ns h264.slice
  "H.264 slice header parsing (ITU-T H.264 / ISO/IEC 14496-10 §7.3.3
   slice_header). Scope: I-slices (this repo's original decode scope, see
   `h264.decode`) AND P-slices (ADR-2607122000 Migration step 7's first
   increment — single reference frame, no reference-list reordering, no
   weighted prediction, no adaptive/MMCO reference marking) —
   first_mb_in_slice, slice_type, pic_parameter_set_id, frame_num,
   idr_pic_id, POC fields (only for pic_order_cnt_type 0, the common case;
   type 1 throws — type 2 in particular derives POC directly from frame_num
   and needs no extra bits here, so it's actually already fully handled by
   NOT reading anything extra, but is called out explicitly since it's what
   this repo's own golden-vector fixtures use), redundant_pic_cnt (read-
   and-discarded when the PPS declares it present — needed for P-slices too,
   since it precedes the P-specific fields below),
   num_ref_idx_active_override_flag / num_ref_idx_l0_active_minus1 (P-slice
   only — this repo requires the ACTIVE count to resolve to exactly 1,
   i.e. a single reference frame, throwing otherwise),
   ref_pic_list_modification_flag_l0 (P-slice only — throws if set, since
   reference-list reordering implies >1 candidate reference, out of scope),
   pred_weight_table absence check (throws if PPS `weighted_pred?` is set,
   since explicit weighted prediction is out of scope), dec_ref_pic_marking
   (IDR's two flags for IDR pictures per the ORIGINAL scope, OR — new —
   non-IDR's adaptive_ref_pic_marking_mode_flag, throwing if set since MMCO
   reference-list editing is out of scope; only read at all when
   `nal-ref-idc` is nonzero, matching spec's `if (nal_ref_idc != 0)` gate),
   slice_qp_delta, and the deblocking_filter_control fields (read-and-
   discarded — SPS/PPS-controlled deblocking is out of scope for this
   decoder's R0.5 reference-decode phase; see README). ALSO (ADR-2607122000
   P-slice CABAC increment): `cabac_init_idc` (P-slice only, present only
   when the PPS declares `entropy_coding_mode_flag`==1 — selects one of 3
   P-slice-only CABAC context-init columns, see `h264.cabac/init-contexts`).

   `parse-header!` takes an already-positioned `h264.expgolomb` reader
   (created by the caller over the slice RBSP, NAL header byte included at
   index 0 per this repo's convention — see `h264.sps`/`h264.pps`) and
   ADVANCES it past the slice header, so the SAME reader can continue
   being used by `h264.decode` for macroblock_layer() parsing immediately
   afterward — unlike `h264.sps/parse`/`h264.pps/parse`, which each own a
   private reader, this can't be a black box because the caller needs the
   reader's post-header bit position.

   New implementation as part of the kotoba-lang reverse-domain
   media/graphics standards-substrate split (com-junkawasaki/root)."
  (:require [h264.expgolomb :as eg]))

(defn slice-type-class
  "Raw `slice_type` (0..9, §7.4.3) → a keyword per Table 7-6's mod-5
   collapse (`slice_type` and `slice_type + 5` — \"all slices in the
   picture have this type\" — mean the same thing): :p (0/5) :b (1/6)
   :i (2/7) :sp (3/8) :si (4/9)."
  [slice-type]
  (case (mod slice-type 5)
    0 :p 1 :b 2 :i 3 :sp 4 :si))

(defn parse-header!
  "Advance `r` (an `h264.expgolomb` reader already past the 1-byte NAL
   header) past the slice header, given the SPS map (`h264.sps/parse`
   result) and PPS map (`h264.pps/parse` result) it references. `nal-type`
   is the containing NAL's `nal-unit-type` (5 = IDR slice); `nal-ref-idc`
   is the containing NAL's `nal_ref_idc` (gates whether `dec_ref_pic_marking`
   is present at all, per spec — see namespace docstring).

   Returns {:first-mb-in-slice :slice-type :slice-type-class
   :pic-parameter-set-id :frame-num :idr-pic-id :slice-qp-delta :slice-qp}."
  [r {:keys [log2-max-frame-num-minus4 pic-order-cnt-type
             log2-max-pic-order-cnt-lsb-minus4]}
   {:keys [pic-init-qp deblocking-filter-control-present?
           num-ref-idx-l0-default-active weighted-pred?
           redundant-pic-cnt-present? entropy-coding-mode]}
   nal-type nal-ref-idc]
  (let [idr? (= nal-type 5)
        first-mb-in-slice (eg/ue! r)
        slice-type (eg/ue! r)
        slice-class (slice-type-class slice-type)
        pic-parameter-set-id (eg/ue! r)
        frame-num (eg/bits! r (+ log2-max-frame-num-minus4 4))
        idr-pic-id (when idr? (eg/ue! r))
        _ (case pic-order-cnt-type
            0 (do (eg/bits! r (+ log2-max-pic-order-cnt-lsb-minus4 4))
                  nil)
            2 nil ; POC derived directly from frame_num — no extra bits
            (throw (ex-info "h264.slice: only pic_order_cnt_type 0/2 supported"
                             {:pic-order-cnt-type pic-order-cnt-type})))
        _ (when redundant-pic-cnt-present?
            (eg/ue! r))
        ;; --- P-slice-only fields (§7.3.3), in spec syntax order ---
        num-ref-idx-l0-active
        (when (= slice-class :p)
          (if (= 1 (eg/flag! r))                      ; num_ref_idx_active_override_flag
            (inc (eg/ue! r))                           ; num_ref_idx_l0_active_minus1
            num-ref-idx-l0-default-active))
        _ (when (and (= slice-class :p) (not= 1 num-ref-idx-l0-active))
            (throw (ex-info "h264.slice: only a single active L0 reference (num_ref_idx_l0_active == 1) is supported"
                             {:num-ref-idx-l0-active num-ref-idx-l0-active})))
        _ (when (= slice-class :p)
            (when (= 1 (eg/flag! r))                   ; ref_pic_list_modification_flag_l0
              (throw (ex-info "h264.slice: ref_pic_list_modification (reference-list reordering) not supported"
                               {}))))
        _ (when (and (= slice-class :p) weighted-pred?)
            (throw (ex-info "h264.slice: weighted prediction (pred_weight_table) not supported" {})))
        ;; --- dec_ref_pic_marking(), only present when nal_ref_idc != 0 ---
        _ (when (not (zero? nal-ref-idc))
            (if idr?
              (do (eg/flag! r)    ; no_output_of_prior_pics_flag
                  (eg/flag! r))   ; long_term_reference_flag
              (when (= 1 (eg/flag! r))                 ; adaptive_ref_pic_marking_mode_flag
                (throw (ex-info "h264.slice: adaptive reference marking (MMCO) not supported" {})))))
        ;; --- cabac_init_idc (§7.3.3, ADR-2607122000 P-slice CABAC increment)
        ;;     — present ONLY when entropy_coding_mode_flag==1 AND slice_type
        ;;     is P/SP/B (never for I/SI, where it isn't even signaled — CABAC
        ;;     context init always uses the SINGLE I-slice column regardless,
        ;;     see `h264.cabac/init-contexts`). `ue(v)` (NOT a fixed 2-bit
        ;;     field — verified against FFmpeg's own `h264_slice.c`
        ;;     `get_ue_golomb_31`/`cabac_init_idc` after an initial WRONG
        ;;     `u(2)` read produced a real, immediately-caught desync: a real
        ;;     x264 CABAC P-slice's next 2 raw bits decoded to 3, an
        ;;     impossible `cabac_init_idc` value, before this fix), values
        ;;     0/1/2 select one of 3 P/B-only (m,n) context-init columns
        ;;     (`context-init-p0/p1/p2`) — a DIFFERENT mechanism from
        ;;     I-slice's fixed column, not merely an unused field for this
        ;;     repo's P-slice scope. Throws on a decoded value > 2 (matches
        ;;     FFmpeg's own overflow check) rather than silently misindexing.
        cabac-init-idc
        (when (and (= slice-class :p) (= entropy-coding-mode :cabac))
          (let [idc (eg/ue! r)]
            (when (> idc 2)
              (throw (ex-info "h264.slice: cabac_init_idc out of range (0..2)" {:cabac-init-idc idc})))
            idc))
        slice-qp-delta (eg/se! r)
        _ (when deblocking-filter-control-present?
            (let [idc (eg/ue! r)]
              (when (not= idc 1)
                (eg/se! r) (eg/se! r))))]
    {:first-mb-in-slice first-mb-in-slice
     :slice-type slice-type
     :slice-type-class slice-class
     :pic-parameter-set-id pic-parameter-set-id
     :frame-num frame-num
     :idr-pic-id idr-pic-id
     :slice-qp-delta slice-qp-delta
     :slice-qp (+ pic-init-qp slice-qp-delta)
     :cabac-init-idc cabac-init-idc}))

;; --- encode side (ADR-2607122000 Migration step 8) ---

(defn encode-header!
  "Write a slice_header (§7.3.3) to `w` (an `h264.expgolomb` WRITER, NOT
   the reader `parse-header!` uses — this repo's encode path builds the
   whole slice NAL, including the macroblock data that follows, into a
   single writer, mirroring `parse-header!`'s \"continue with the same
   reader\" design but for writing). Scope: single-slice-per-picture IDR
   I-slice only (mirrors `parse-header!`'s own decode scope, and
   `h264.encode`'s encoder scope) — `slice-type` is fixed to 7 (all-I,
   the encoder-preferred all-slices-I-type value, decodable exactly like
   plain I (2) by `h264.decode`, which accepts both), `first-mb-in-slice`
   fixed to 0, `pic-order-cnt-type` fixed to 0 (matching `h264.sps/encode`'s
   own fixed choice) so only `log2-max-pic-order-cnt-lsb-minus4` bits (all
   zero, per that fixed SPS choice) are written, and IDR-only
   dec_ref_pic_marking flags (both written false — no long-term reference,
   no prior-pics discard needed for a single-frame stream).

   `sps`/`pps` are the maps this repo's OWN `h264.sps/encode`/`h264.pps/encode`
   were called with (NOT `parse`'s output — same shape, but the caller
   already has these since it built the SPS/PPS NALs). `slice-qp` is the
   ABSOLUTE QP this slice codes at (this fn derives
   `slice_qp_delta = slice-qp - pic-init-qp` from the PPS's own
   `pic-init-qp`, so it can't drift from what the referenced PPS declares).
   `idr-pic-id` should be a small non-negative int (this repo only ever
   encodes a single IDR frame per stream, so 0 is fine)."
  [w {:keys [log2-max-frame-num-minus4]}
   {:keys [pic-init-qp deblocking-filter-control-present?]}
   {:keys [frame-num idr-pic-id slice-qp]}]
  (eg/write-ue! w 0)                                        ; first_mb_in_slice
  (eg/write-ue! w 7)                                        ; slice_type = 7 (all I)
  (eg/write-ue! w 0)                                        ; pic_parameter_set_id
  (eg/write-bits! w (+ log2-max-frame-num-minus4 4) frame-num)
  (eg/write-ue! w idr-pic-id)                               ; idr_pic_id (nal_unit_type=5 always for this encoder)
  ;; pic_order_cnt_type is always 0 (h264.sps/encode's own fixed choice) —
  ;; log2_max_pic_order_cnt_lsb_minus4 is always 0 there too, so exactly 4
  ;; bits of pic_order_cnt_lsb are written (all zero — this repo only
  ;; encodes a single picture, so POC value is immaterial).
  (eg/write-bits! w 4 0)
  (eg/write-flag! w false)                                  ; no_output_of_prior_pics_flag
  (eg/write-flag! w false)                                  ; long_term_reference_flag
  (eg/write-se! w (- slice-qp pic-init-qp))                 ; slice_qp_delta
  ;; MUST mirror whatever the referenced PPS actually declared for
  ;; deblocking_filter_control_present_flag (`h264.pps/encode`'s DEFAULT is
  ;; true — omitting this field when the PPS says it's present would desync
  ;; the bit reader on every subsequent syntax element, including the whole
  ;; macroblock layer). When present, write disable_deblocking_filter_idc=1
  ;; (fully disabled — matches this encoder's own no-deblocking-filter
  ;; scope, so no slice_alpha_c0_offset_div2/slice_beta_offset_div2 follow).
  (when deblocking-filter-control-present?
    (eg/write-ue! w 1))
  nil)

(defn encode-p-header!
  "Write a P-slice slice_header (§7.3.3) to `w` — the P-slice counterpart of
   `encode-header!` (which is I-slice only), ADR-2607122000 P-slice encode
   increment (`h264.encode`'s P_Skip/P_L0_16x16 encoder). Scope mirrors
   `parse-header!`'s own P-slice decode scope exactly (single reference
   frame, no reordering, no weighted prediction — see that fn's docstring):
   `first_mb_in_slice` fixed to 0, `slice_type` fixed to 5 (the encoder-
   preferred all-slices-P-type value, Table 7-6 — decodable exactly like
   plain P (0) by `h264.slice/slice-type-class`, which collapses both to
   `:p`), `pic_order_cnt_type` fixed to 0 (matching `h264.sps/encode`'s own
   fixed choice, so only `log2_max_pic_order_cnt_lsb_minus4` — always 0 —
   bits are written, all zero), `num_ref_idx_active_override_flag` always
   written false (uses the PPS's own default active count — this repo's
   `h264.pps/encode` DEFAULTS `num-ref-idx-l0-default-active` to 1, exactly
   the single-reference-frame requirement `parse-header!` enforces, so no
   override is ever needed), `ref_pic_list_modification_flag_l0` always
   written false (no reference reordering), no `pred_weight_table` (PPS
   `weighted_pred?` must be false, matching `pps/encode`'s default — this fn
   doesn't check, since it can't write nonexistent bits; passing a
   weighted-prediction PPS here would silently produce a stream
   `parse-header!` throws on).

   `nal-ref-idc` (an opts key, default 0) MUST equal the containing NAL
   header's actual 3-bit `nal_ref_idc` value the caller writes — this gates
   whether `adaptive_ref_pic_marking_mode_flag` is written at all (mirrors
   `parse-header!`'s `(when (not (zero? nal-ref-idc)) ...)` read gate
   exactly); when written (nonzero `nal-ref-idc`), it's always `false` (no
   MMCO/adaptive reference marking — this repo's single-reference-frame,
   no-DPB scope has nothing to mark)."
  [w {:keys [log2-max-frame-num-minus4]}
   {:keys [pic-init-qp deblocking-filter-control-present? redundant-pic-cnt-present?]}
   {:keys [frame-num slice-qp nal-ref-idc]
    :or {nal-ref-idc 0}}]
  (eg/write-ue! w 0)                                        ; first_mb_in_slice
  (eg/write-ue! w 5)                                        ; slice_type = 5 (all P)
  (eg/write-ue! w 0)                                        ; pic_parameter_set_id
  (eg/write-bits! w (+ log2-max-frame-num-minus4 4) frame-num)
  ;; no idr_pic_id (this is a non-IDR slice, nal_unit_type=1 — see
  ;; `parse-header!`'s `idr?` gate, which is false here).
  ;; pic_order_cnt_type is always 0 (h264.sps/encode's own fixed choice) —
  ;; log2_max_pic_order_cnt_lsb_minus4 is always 0 there too, so exactly 4
  ;; bits of pic_order_cnt_lsb are written (all zero — POC value is
  ;; immaterial for this repo's single-slice-per-picture scope).
  (eg/write-bits! w 4 0)
  (when redundant-pic-cnt-present?
    (eg/write-ue! w 0))
  (eg/write-flag! w false)                                  ; num_ref_idx_active_override_flag
  (eg/write-flag! w false)                                  ; ref_pic_list_modification_flag_l0
  (when (not (zero? nal-ref-idc))
    (eg/write-flag! w false))                                ; adaptive_ref_pic_marking_mode_flag
  (eg/write-se! w (- slice-qp pic-init-qp))                 ; slice_qp_delta
  (when deblocking-filter-control-present?
    (eg/write-ue! w 1))
  nil)
