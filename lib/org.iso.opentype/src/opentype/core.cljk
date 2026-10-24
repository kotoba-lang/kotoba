(ns opentype.core
  "TrueType/OpenType (SFNT) decode — ISO/IEC 14496-22 Open Font Format.
   Offset-based, so a small hand parser over the table directory + the
   head/maxp/name tables. R0 extracts the table set, head (units-per-em,
   the fixed magicNumber for validation), glyph count and the family name.
   CFF/glyf outline parsing is a follow-up. Extracted from kotoba-lang/kasane
   (kasane.ttf, ADR-2606272100) as `org-iso-opentype`. Consumed by
   `org-w3-woff` (which reassembles a WOFF-wrapped SFNT and delegates here)."
  (:require [opentype.bytes :as b]))

(def ^:private head-magic 0x5F0F3CF5)

(defn- be [bv o n] (b/uint! (b/cursor (subvec bv o (+ o n))) n true))

(defn- name-family
  "Extract the font family (name ID 1) from the 'name' table. Prefers a
   Windows UTF-16BE record, falls back to Macintosh ASCII."
  [bv off]
  (let [count'  (be bv (+ off 2) 2)
        storage (+ off (be bv (+ off 4) 2))
        recs    (mapv (fn [i]
                        (let [r (+ off 6 (* i 12))]
                          {:platform (be bv r 2) :nameID (be bv (+ r 6) 2)
                           :length (be bv (+ r 8) 2) :soff (be bv (+ r 10) 2)}))
                      (range count'))
        fam     (filter #(= (:nameID %) 1) recs)
        win     (first (filter #(= (:platform %) 3) fam))
        mac     (first (filter #(= (:platform %) 1) fam))
        rec     (or win mac (first fam))]
    (when rec
      (let [bytes (subvec bv (+ storage (:soff rec)) (+ storage (:soff rec) (:length rec)))]
        (if (= (:platform rec) 3)
          (b/bytes->ascii (take-nth 2 (rest bytes)))           ; UTF-16BE → low bytes (ASCII BMP)
          (b/bytes->ascii bytes))))))

(defn parse
  "Parse SFNT `data` → {:sfnt-version :num-tables :tables :magic :magic-ok?
   :units-per-em :num-glyphs :family}."
  [data]
  (let [bv     (vec data)
        ver    (be bv 0 4)
        n      (be bv 4 2)
        tables (into {} (map (fn [i]
                               (let [o (+ 12 (* i 16))]
                                 [(b/bytes->ascii (subvec bv o (+ o 4)))
                                  {:offset (be bv (+ o 8) 4) :length (be bv (+ o 12) 4)}]))
                             (range n)))
        head   (:offset (tables "head"))
        maxp   (:offset (tables "maxp"))
        nm     (:offset (tables "name"))]
    {:sfnt-version ver
     :num-tables   n
     :tables       (set (keys tables))
     :magic        (when head (be bv (+ head 12) 4))
     :magic-ok?    (and head (= (be bv (+ head 12) 4) head-magic))
     :units-per-em (when head (be bv (+ head 18) 2))
     :num-glyphs   (when maxp (be bv (+ maxp 4) 2))
     :family       (when nm (name-family bv nm))
     ;; Kept so a caller can reach `opentype.cmap` without re-parsing the
     ;; directory. `:tables` is a SET of names and answers whether a table
     ;; exists; this answers where it is, which is the question anybody who
     ;; got a yes will ask next.
     :table-offsets (into {} (map (fn [[k v]] [k (:offset v)])) tables)}))
