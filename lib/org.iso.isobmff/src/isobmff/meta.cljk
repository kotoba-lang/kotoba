(ns isobmff.meta
  "AVIF/HEIC still-image metadata: brand (ftyp) + dimensions (ispe, nested
   inside meta>iprp>ipco). Pixel decode (AV1/HEVC) is out of scope — the
   caller carries the coded image as an opaque blob. Extracted from
   kotoba-lang/kasane (kasane.isobmff, ADR-2606280010) as part of
   `org-iso-isobmff`."
  (:require [isobmff.bytes :as b]
            [isobmff.box :as box]))

(defn parse
  "Parse AVIF/HEIC `data` → {:brand :width :height :boxes}. :boxes is a flat
   vector of every box type seen, all depths (see isobmff.box/types)."
  [data]
  (let [buf  (vec data)
        all  (box/parse-boxes buf)
        ftyp (box/find-box all "ftyp")
        ispe (box/find-box all "ispe")]
    {:brand  (when ftyp (b/ascii4 buf (+ (:start ftyp) (:header ftyp))))
     :width  (when ispe (b/u32 buf (+ (:start ispe) (:header ispe) 4)))    ; after 4-byte version/flags
     :height (when ispe (b/u32 buf (+ (:start ispe) (:header ispe) 8)))
     :boxes  (box/types all)}))
