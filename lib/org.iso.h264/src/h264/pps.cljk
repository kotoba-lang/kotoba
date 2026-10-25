(ns h264.pps
  "H.264 Picture Parameter Set (PPS, NAL type 8) parsing — H.264 §7.3.2.2
   pic_parameter_set_rbsp. Reads the *unescaped* RBSP (see h264.rbsp) via
   Exp-Golomb (see h264.expgolomb), same pattern as h264.sps.

   Covers the common case (num_slice_groups_minus1 == 0, i.e. no FMO —
   Flexible Macroblock Ordering is a rarely-used H.264 feature essentially
   absent from real-world encoders); slice_group_map_type and its
   type-specific data are not implemented, since parsing them correctly
   requires the picture's macroblock count from the referenced SPS (an
   extra cross-reference this repo's per-NAL parse functions don't thread
   through). Fields defined only when more_rbsp_data() is true (High
   Profile's transform_8x8_mode_flag / pic_scaling_matrix_present_flag /
   second_chroma_qp_index_offset) also aren't parsed — detecting
   more_rbsp_data precisely needs the RBSP's exact trailing-bit position,
   which this reader doesn't track. Both gaps are documented limitations,
   not silent wrong answers: parse throws on num_slice_groups_minus1 > 0
   rather than guessing."
  (:require [h264.expgolomb :as eg]))

(defn parse
  "Parse a PPS RBSP (already emulation-unescaped, header byte INCLUDED at
   index 0 — see h264.rbsp/unescape) → {:pic-parameter-set-id
   :seq-parameter-set-id :entropy-coding-mode :num-ref-idx-l0-default-active
   :num-ref-idx-l1-default-active :weighted-pred? :weighted-bipred-idc
   :pic-init-qp :pic-init-qs :chroma-qp-index-offset
   :deblocking-filter-control-present? :constrained-intra-pred?
   :redundant-pic-cnt-present?}."
  [rbsp]
  (let [r (eg/reader rbsp)
        _ (eg/bits! r 8)                                   ; NAL header byte
        pps-id (eg/ue! r)
        sps-id (eg/ue! r)
        entropy-coding-mode (eg/flag! r)                    ; 0=CAVLC 1=CABAC
        _bottom-field-poc (eg/flag! r)
        num-slice-groups-minus1 (eg/ue! r)
        _ (when (pos? num-slice-groups-minus1)
            (throw (ex-info "h264.pps: FMO (num_slice_groups_minus1 > 0) not supported"
                            {:num-slice-groups-minus1 num-slice-groups-minus1})))
        num-ref-idx-l0 (eg/ue! r)
        num-ref-idx-l1 (eg/ue! r)
        weighted-pred? (= 1 (eg/flag! r))
        weighted-bipred-idc (eg/bits! r 2)
        pic-init-qp (+ 26 (eg/se! r))
        pic-init-qs (+ 26 (eg/se! r))
        chroma-qp-index-offset (eg/se! r)
        deblocking-present? (= 1 (eg/flag! r))
        constrained-intra-pred? (= 1 (eg/flag! r))
        redundant-pic-cnt-present? (= 1 (eg/flag! r))]
    {:pic-parameter-set-id pps-id
     :seq-parameter-set-id sps-id
     :entropy-coding-mode (if (= entropy-coding-mode 1) :cabac :cavlc)
     :num-ref-idx-l0-default-active (inc num-ref-idx-l0)
     :num-ref-idx-l1-default-active (inc num-ref-idx-l1)
     :weighted-pred? weighted-pred?
     :weighted-bipred-idc weighted-bipred-idc
     :pic-init-qp pic-init-qp
     :pic-init-qs pic-init-qs
     :chroma-qp-index-offset chroma-qp-index-offset
     :deblocking-filter-control-present? deblocking-present?
     :constrained-intra-pred? constrained-intra-pred?
     :redundant-pic-cnt-present? redundant-pic-cnt-present?}))

;; --- encode side (Wave 2 addition, kotoba-lang/root ADR-2607121400) ---

(defn encode
  "Encode a minimal PPS RBSP (NAL header byte included at index 0, matching
   `parse`'s convention). Always writes `num_slice_groups_minus1` = 0 (no
   FMO, matching `parse`'s own coverage). Accepts the same keys `parse`
   returns; missing keys default to a minimal all-CAVLC,
   no-weighted-prediction baseline PPS.
   Round-trip verified against `parse` in pps_test.clj."
  [{:keys [pic-parameter-set-id seq-parameter-set-id entropy-coding-mode
           num-ref-idx-l0-default-active num-ref-idx-l1-default-active
           weighted-pred? weighted-bipred-idc pic-init-qp pic-init-qs
           chroma-qp-index-offset deblocking-filter-control-present?
           constrained-intra-pred? redundant-pic-cnt-present?]
    :or {pic-parameter-set-id 0 seq-parameter-set-id 0
         entropy-coding-mode :cavlc
         num-ref-idx-l0-default-active 1 num-ref-idx-l1-default-active 1
         weighted-pred? false weighted-bipred-idc 0
         pic-init-qp 26 pic-init-qs 26 chroma-qp-index-offset 0
         deblocking-filter-control-present? true
         constrained-intra-pred? false redundant-pic-cnt-present? false}}]
  (let [w (eg/writer)
        nal-header (bit-or (bit-shift-left 3 5) 8)]           ; nal_ref_idc=3, nal_unit_type=8 (PPS)
    (eg/write-bits! w 8 nal-header)
    (eg/write-ue! w pic-parameter-set-id)
    (eg/write-ue! w seq-parameter-set-id)
    (eg/write-flag! w (= entropy-coding-mode :cabac))
    (eg/write-flag! w false)                                  ; bottom_field_pic_order_in_frame_present_flag
    (eg/write-ue! w 0)                                        ; num_slice_groups_minus1 (no FMO)
    (eg/write-ue! w (dec num-ref-idx-l0-default-active))
    (eg/write-ue! w (dec num-ref-idx-l1-default-active))
    (eg/write-flag! w weighted-pred?)
    (eg/write-bits! w 2 weighted-bipred-idc)
    (eg/write-se! w (- pic-init-qp 26))
    (eg/write-se! w (- pic-init-qs 26))
    (eg/write-se! w chroma-qp-index-offset)
    (eg/write-flag! w deblocking-filter-control-present?)
    (eg/write-flag! w constrained-intra-pred?)
    (eg/write-flag! w redundant-pic-cnt-present?)
    (eg/rbsp-trailing-bits! w)
    (eg/bytes! w)))
