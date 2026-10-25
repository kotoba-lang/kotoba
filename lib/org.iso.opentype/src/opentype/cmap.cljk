(ns opentype.cmap
  "The `cmap` table — characters to glyph ids, and back.

  ## Why the reverse direction is the point

  Forwards is what a layout engine wants. Backwards is what anybody holding
  glyph ids and no characters wants, and that is a real and common position:
  a PDF composite font with `Identity-H` encoding puts GLYPH IDS in the
  content stream, so the text of the page is unreadable without the font
  that drew it. `/ToUnicode` is how a producer is supposed to say what those
  ids mean and plenty of producers do not ship one — measured at 3 of 30
  real documents, 550 runs in a single LaTeX-CJK paper.

  For an embedded subset font the `cmap` is right there in the file and says
  exactly this, backwards. So `gid->unicode` is not a heuristic; it is the
  font's own table read in the other direction.

  ## Which subtable, and why the order

  Format 12 first (full Unicode, so a document with anything outside the BMP
  keeps it), then format 4 (BMP, and what most fonts ship). A symbol-encoded
  (3,0) subtable is read too and marked, because its code points are in the
  0xF000 private-use block and mean nothing on their own — a caller that
  treated them as characters would produce private-use gibberish that looks
  like a font problem rather than a mapping problem.

  Formats 0, 2, 6, 13 and 14 are not read. They cover bitmap-era
  single-byte, legacy CJK, trimmed arrays, last-resort fonts and variation
  sequences; none has turned up in the measured corpus, and a parser for a
  format nobody can test is a parser nobody should trust."
  (:require [opentype.bytes :as b]))

(defn- be [bv o n]
  (when (<= (+ o n) (count bv))
    (b/uint! (b/cursor (subvec bv o (+ o n))) n true)))

(defn encodings
  "The `cmap` subtables, as `{:platform :encoding :offset :format}`.

  `offset` is absolute in the font, not relative to the table, so a caller
  never has to remember which."
  [bv cmap-off]
  (let [n (or (be bv (+ cmap-off 2) 2) 0)]
    (into []
          (keep (fn [i]
                  (let [r (+ cmap-off 4 (* i 8))
                        off (be bv (+ r 4) 4)]
                    (when off
                      (let [abs (+ cmap-off off)]
                        {:platform (be bv r 2)
                         :encoding (be bv (+ r 2) 2)
                         :offset abs
                         :format (be bv abs 2)})))))
          (range n))))

(defn- format-4
  "Segment mapping to delta values. The awkward one, and the awkward part is
  `idRangeOffset`: it is a byte offset *from its own address*, so the glyph
  index lives at `(address of idRangeOffset[i]) + idRangeOffset[i] +
  (c − start[i]) × 2`. Computing it from the start of the table instead —
  the obvious reading — lands in a different place for every segment but the
  first, which is why a font can look almost right."
  [bv off]
  (let [seg-x2 (or (be bv (+ off 6) 2) 0)
        segs (quot seg-x2 2)
        end-base (+ off 14)
        start-base (+ end-base seg-x2 2)
        delta-base (+ start-base seg-x2)
        range-base (+ delta-base seg-x2)]
    (persistent!
     (reduce
      (fn [acc i]
        (let [end (be bv (+ end-base (* i 2)) 2)
              start (be bv (+ start-base (* i 2)) 2)
              delta (be bv (+ delta-base (* i 2)) 2)
              range-off (be bv (+ range-base (* i 2)) 2)]
          (if (or (nil? end) (nil? start) (> start end) (= start 0xFFFF))
            acc
            (reduce
             (fn [acc c]
               (let [gid (if (zero? range-off)
                           (mod (+ c delta) 0x10000)
                           (let [at (+ range-base (* i 2) range-off
                                       (* 2 (- c start)))
                                 g (be bv at 2)]
                             (when (and g (pos? g)) (mod (+ g delta) 0x10000))))]
                 (if (and gid (pos? gid)) (assoc! acc c gid) acc)))
             acc
             (range start (inc end))))))
      (transient {})
      (range segs)))))

(defn- format-12
  "Segmented coverage. Groups are already ranges, so this is the simple one —
  except that a single group may be enormous, and a font that maps the whole
  of a plane would otherwise be expanded a code point at a time."
  [bv off]
  (let [n (or (be bv (+ off 12) 4) 0)]
    (persistent!
     (reduce
      (fn [acc i]
        (let [g (+ off 16 (* i 12))
              start (be bv g 4)
              end (be bv (+ g 4) 4)
              gid (be bv (+ g 8) 4)]
          (if (or (nil? start) (nil? end) (> start end)
                  ;; A group covering more than a plane is a corrupt length,
                  ;; not a font. Expanding it is how a parser turns a bad
                  ;; file into an out-of-memory error.
                  (> (- end start) 0x10FFFF))
            acc
            (reduce (fn [acc k] (assoc! acc (+ start k) (+ gid k)))
                    acc
                    (range 0 (inc (- end start)))))))
      (transient {})
      (range n)))))

(defn- subtable [bv {:keys [offset format]}]
  (case format
    4 (format-4 bv offset)
    12 (format-12 bv offset)
    nil))

(defn unicode->gid
  "The font's character-to-glyph map, or nil when it has no subtable this
  reads.

  `:symbol?` on the result says the code points are the (3,0) private-use
  kind — see the namespace docstring for why that has to be said rather
  than silently returned as characters."
  [bv cmap-off]
  (let [encs (encodings bv cmap-off)
        pick (fn [pred] (first (filter pred encs)))
        chosen (or (pick #(and (= 3 (:platform %)) (= 10 (:encoding %))
                               (= 12 (:format %))))
                   (pick #(= 12 (:format %)))
                   (pick #(and (= 3 (:platform %)) (= 1 (:encoding %))
                               (= 4 (:format %))))
                   (pick #(= 4 (:format %))))]
    (when-let [m (and chosen (subtable bv chosen))]
      (when (seq m)
        (with-meta m {:symbol? (and (= 3 (:platform chosen))
                                    (= 0 (:encoding chosen)))
                      :format (:format chosen)})))))

(defn gid->unicode
  "The reverse map: glyph id to code point.

  **The lowest code point wins a collision**, and collisions are normal — a
  font routinely points several characters at one glyph, and the interesting
  case is that it points both a letter and its private-use duplicate there.
  Taking the lowest is what keeps `A` from coming back as U+F041."
  [uni->gid]
  (persistent!
   (reduce (fn [acc [u g]]
             (let [prev (get acc g)]
               (if (and prev (<= prev u)) acc (assoc! acc g u))))
           (transient {})
           uni->gid)))
