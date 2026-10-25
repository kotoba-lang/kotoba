(ns isobmff.box
  "Generic ISO Base Media File Format (ISO/IEC 14496-12) box-tree reader,
   shared by both the static-image path (AVIF/HEIC meta>iprp>ipco>ispe,
   see isobmff.meta) and the MP4 demux/mux path (moov>trak>...>stbl, see
   isobmff.demux/mux/remux).

   This unifies two previously independent, DUPLICATE box-tree
   implementations — kasane.isobmff (a flat walker tuned for AVIF/HEIC
   meta boxes) and utsushi.container (a nested-tree walker tuned for MP4
   moov boxes) — into one. The merge fixes a real gap: utsushi's walker
   didn't know `meta` is a FullBox (4-byte version+flags before its
   children), which kasane's walker handled correctly for the AVIF path;
   this version applies that fix generally.

   Extracted from kotoba-lang/kasane (kasane.isobmff, ADR-2606280010) and
   kotoba-lang/utsushi (utsushi.container, ADR-2606272200) as
   `org-iso-isobmff`. Pure cljc."
  (:require [isobmff.bytes :as b]))

;; Container box types that hold nested boxes and get recursed into.
;; Covers both the MP4 tree (moov/trak/mdia/minf/stbl/moof/traf/...) and
;; the AVIF/HEIC tree (meta/iprp/ipco/iref). `mdat` is deliberately absent —
;; it holds raw media data, never nested boxes.
(def container-box?
  #{"moov" "trak" "mdia" "minf" "stbl" "dinf" "edts"
    "udta" "mvex" "moof" "traf" "mfra" "meta" "ipro" "sinf"
    "iprp" "ipco" "iref"})

;; Boxes that are FullBoxes (4-byte version+flags prefix) even though they
;; also act as containers — children start after that prefix, not right
;; after the 8-byte box header. `meta` is the one case in this box set.
(def ^:private fullbox-container? #{"meta"})

(defn parse-boxes
  "byte-vector `buf`'s [start,end) span of boxes, oldest-first. Each box is
   {:type :start :size :header (:children)}. size==1 → 64-bit largesize
   (header 16) / size==0 → extends to EOF / container types recurse into
   :children (meta's FullBox version+flags prefix is skipped first)."
  ([buf] (parse-boxes buf 0 (count buf)))
  ([buf start end]
   (loop [pos start, acc []]
     (if (> (+ pos 8) end)
       acc
       (let [size32 (b/u32 buf pos)
             type   (b/ascii4 buf (+ pos 4))
             [hdr size] (cond
                          (= size32 1) [16 (b/u64 buf (+ pos 8))]
                          (= size32 0) [8  (- end pos)]
                          :else        [8  size32])
             box-end (+ pos size)
             body    (+ pos hdr (if (fullbox-container? type) 4 0))
             base    {:type type :start pos :size size :header hdr}
             box     (if (container-box? type)
                       (assoc base :children (parse-boxes buf body (min box-end end)))
                       base)]
         (if (or (< size 8) (> box-end end))
           (conj acc box)
           (recur box-end (conj acc box))))))))

(defn find-box
  "Depth-first first box matching `type` (nil if none)."
  [boxes type]
  (some (fn [{t :type ch :children :as box}]
          (cond (= t type) box
                ch          (find-box ch type)
                :else       nil))
        boxes))

(defn types
  "Flat vector of every box type in the tree, all depths, top-to-bottom
   depth-first order (matches kasane.isobmff's original flat-walk :boxes
   output shape)."
  [boxes]
  (vec (mapcat (fn [{t :type ch :children}] (cons t (when ch (types ch)))) boxes)))

(defn leaf-payload
  "box payload bytes (after the box header, before the box end) as a subvec.
   ISO FullBoxes have payload[0..3] = version(1)+flags(3)."
  [buf {:keys [start size header]}]
  (subvec buf (+ start header) (+ start size)))
