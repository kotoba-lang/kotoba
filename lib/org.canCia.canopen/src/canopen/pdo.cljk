(ns canopen.pdo
  "PDO (Process Data Object) mapping-entry encoding and the contiguous
  bit-packing PDO data uses, CiA 301 §7.4 / §7.5.

  **Mapping entry** — each of the (up to 8, one per byte of a PDO's DLC)
  mapped Object Dictionary entries in a PDO Mapping Parameter object
  (0x1600..0x1603 for RPDOs, 0x1A00..0x1A03 for TPDOs) is itself a single
  32-bit value, packed:

    31..16  Index          the mapped object's OD index
    15..8   Subindex       the mapped object's OD subindex
     7..0   Length (bits)  how many bits of the PDO this entry occupies

  Note this is **big-endian field order within the u32** (index in the
  high 16 bits) even though the u32 itself, like every other CANopen
  multi-byte field, rides the wire little-endian byte-first — the same
  'field order in the value vs. byte order on the wire are different
  questions' distinction EtherCAT's working-counter and PROFINET's
  data-status byte each have their own version of.

  **PDO data packing** (the actual process-data bytes, up to 8 per PDO)
  is *not* one-value-per-byte: values are packed as a contiguous bit
  stream, LSB-first, starting at bit 0 of byte 0 of the PDO — a 3-bit
  value followed by a 13-bit value followed by a 4-bit value occupies
  exactly 20 bits (2.5 bytes), with the 13-bit value straddling a byte
  boundary. `pack-fields`/`unpack-fields` below implement this generically
  from a list of field widths, independent of what OD entries they came
  from.

  Source: the mapping-entry bit layout and 'packed bit stream, not
  byte-aligned fields' packing rule are reproduced identically across
  CANopenNode (`301/CO_PDO.c`, `OD_getObjectDictionaryEntry`-style mapping
  unpack) and python-canopen (`canopen/pdo/base.py`, `Variable.offset`/
  `length` bit arithmetic); CiA 301 §7.4/7.5 themselves are paywalled and
  not quoted here from memory.")

;; ── mapping entry, CiA 301 §7.4.5 ────────────────────────────────────────

(defn pack-mapping-entry
  "`{:index :subindex :length-bits}` -> `[:ok u32]`.

  Ends with `unsigned-bit-shift-right ... 0`, not just `bit-or`: this is a
  genuine 32-bit value, and whenever `:index` has its own top bit set
  (`:index` >= 0x8000, so the packed word's bit 31 ends up set too),
  plain `bit-or`/`bit-shift-left` — 32-bit SIGNED on ClojureScript's JS
  host — would return a NEGATIVE host number for a value that is not
  negative on the wire. No effect on the JVM, where this expression
  already produces a nonnegative Long."
  [{:keys [index subindex length-bits]}]
  (cond
    (not (<= 0 index 0xFFFF)) [:error :canopen/index-out-of-range index]
    (not (<= 0 subindex 0xFF)) [:error :canopen/subindex-out-of-range subindex]
    (not (<= 0 length-bits 0xFF)) [:error :canopen/length-bits-out-of-range length-bits]
    :else
    [:ok (unsigned-bit-shift-right
          (bit-or (bit-shift-left (bit-and index 0xFFFF) 16)
                  (bit-shift-left (bit-and subindex 0xFF) 8)
                  (bit-and length-bits 0xFF))
          0)]))

(defn unpack-mapping-entry
  "u32 -> `[:ok {:index :subindex :length-bits}]`. Normalises `entry`
  with `unsigned-bit-shift-right ... 0` before the range check — on
  ClojureScript a value with bit 31 set can arrive as a negative host
  number (see `pack-mapping-entry`'s docstring) even though it is a
  perfectly valid 32-bit mapping entry, and rejecting it on sign alone
  would be wrong."
  [entry]
  (let [entry (unsigned-bit-shift-right entry 0)]
    (if-not (<= 0 entry 0xFFFFFFFF)
      [:error :canopen/mapping-entry-out-of-range entry]
      [:ok {:index (bit-and (unsigned-bit-shift-right entry 16) 0xFFFF)
            :subindex (bit-and (unsigned-bit-shift-right entry 8) 0xFF)
            :length-bits (bit-and entry 0xFF)}])))

;; ── contiguous LSB-first bit packing of PDO data ────────────────────────

(defn pack-fields
  "`widths` (bit widths, in mapping order) + `values` (matching ints) ->
  `[:ok bytes]`, the PDO data bytes. Values are packed LSB-first into a
  contiguous bit stream starting at bit 0 of byte 0 — the CANopen PDO
  convention, distinct from byte-aligned struct packing."
  [widths values]
  (cond
    (not= (count widths) (count values))
    [:error :canopen/pdo-mapping-value-count-mismatch
     {:widths (count widths) :values (count values)}]

    (some (fn [[w v]] (not (<= 0 v (dec (bit-shift-left 1 w))))) (map vector widths values))
    [:error :canopen/pdo-value-does-not-fit-width
     (first (filter (fn [[w v]] (not (<= 0 v (dec (bit-shift-left 1 w)))))
                     (map vector widths values)))]

    (> (reduce + widths) 64)
    [:error :canopen/pdo-mapping-exceeds-frame {:total-bits (reduce + widths)}]

    :else
    (let [total-bits (reduce + widths)
          nbytes (quot (+ total-bits 7) 8)]
      (loop [ws widths vs values bit-pos 0 out (vec (repeat nbytes 0))]
        (if (empty? ws)
          [:ok out]
          (let [w (first ws) v (first vs)]
            (recur (rest ws) (rest vs) (+ bit-pos w)
                   (loop [i 0 out out]
                     (if (= i w)
                       out
                       (let [bit (bit-and (unsigned-bit-shift-right v i) 1)
                             abs-bit (+ bit-pos i)
                             byte-idx (quot abs-bit 8)
                             bit-idx (mod abs-bit 8)]
                         (recur (inc i)
                                (update out byte-idx
                                        #(bit-or % (bit-shift-left bit bit-idx))))))))))))))

(defn unpack-fields
  "`widths` + PDO data `bytes` -> `[:ok values]`, the inverse of
  `pack-fields`."
  [widths bytes]
  (let [bs (vec bytes)
        total-bits (reduce + widths)]
    (cond
      (> total-bits (* 8 (count bs)))
      [:error :canopen/pdo-data-too-short {:need-bits total-bits :have-bytes (count bs)}]

      :else
      (loop [ws widths bit-pos 0 out []]
        (if (empty? ws)
          [:ok out]
          (let [w (first ws)
                v (loop [i 0 v 0]
                    (if (= i w)
                      v
                      (let [abs-bit (+ bit-pos i)
                            byte-idx (quot abs-bit 8)
                            bit-idx (mod abs-bit 8)
                            bit (bit-and (unsigned-bit-shift-right (nth bs byte-idx) bit-idx) 1)]
                        (recur (inc i) (bit-or v (bit-shift-left bit i))))))]
            (recur (rest ws) (+ bit-pos w) (conj out v))))))))
