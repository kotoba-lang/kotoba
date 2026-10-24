(ns mil1553.command
  "The Command Word's 16-bit payload:

  ```
  bit  1  2  3  4  5 | 6  | 7  8  9 10 11 | 12 13 14 15 16
       RT Address    |T/R | Subaddr/Mode  | Word Count / Mode Code
       (5 bits)      |(1) | (5 bits)      | (5 bits)
  ```

  RT Address 0..30 addresses one Remote Terminal; **31 is reserved for
  Broadcast** (all RTs act on the command; no RT is expected to respond
  with a Status Word for a broadcast, which is why `mil1553.message`
  treats broadcast specially rather than uniformly).

  T/R: 1 = the addressed RT is commanded to TRANSMIT (send data back to
  the bus); 0 = the addressed RT is commanded to RECEIVE (accept data
  words that follow).

  Subaddress/Mode: the values `0` (00000) and `31` (11111) are reserved
  to mean 'this Command Word is a MODE CODE command, not a data
  transfer' — the last 5-bit field is then a mode code (see
  `mil1553.mode`) instead of a word count. Every other value 1..30 is an
  ordinary subaddress, and the last field is a Word Count.

  Word Count: 1..31 mean that many data words; **the bit pattern 00000
  conventionally means 32 data words**, not zero — a Command Word can
  never actually request zero data words, so the all-zero bit pattern is
  reused for the one count value (32) that would not otherwise fit in 5
  bits. Decoding therefore maps a raw field value of 0 to a count of 32;
  encoding does the reverse. Get this backwards and every message with
  the maximum word count silently becomes a message with none.")

(def broadcast-rt-address 31)
(def mode-code-subaddress-values #{0 31})

(defn- mode-command?
  [subaddress-mode]
  (contains? mode-code-subaddress-values subaddress-mode))

(defn pack
  "`{:rt-address 0-31 :tr :receive/:transmit :subaddress-mode 0-31
  :word-count-or-mode 1-32-or-mode-code}` -> `[:ok payload]`, the 16-bit
  Command Word payload (before `mil1553.word/pack` adds Sync/Parity).

  When `:subaddress-mode` is 0 or 31, `:word-count-or-mode` is taken as a
  literal mode code 0..31 (see `mil1553.mode`). Otherwise it is a data
  word count 1..32, and 32 is encoded as the 00000 bit pattern."
  [{:keys [rt-address tr subaddress-mode word-count-or-mode]}]
  (cond
    (not (<= 0 rt-address 31)) [:error :mil1553/rt-address-out-of-range rt-address]
    (not (#{:receive :transmit} tr)) [:error :mil1553/bad-tr-bit tr]
    (not (<= 0 subaddress-mode 31)) [:error :mil1553/subaddress-out-of-range subaddress-mode]
    :else
    (let [mode? (mode-command? subaddress-mode)
          field-err (when-not mode?
                      (when-not (<= 1 word-count-or-mode 32)
                        [:error :mil1553/word-count-out-of-range word-count-or-mode]))
          mode-err (when mode?
                     (when-not (<= 0 word-count-or-mode 31)
                       [:error :mil1553/mode-code-out-of-range word-count-or-mode]))]
      (cond
        field-err field-err
        mode-err mode-err
        :else
        (let [last-field (if mode? word-count-or-mode
                              (if (= 32 word-count-or-mode) 0 word-count-or-mode))
              tr-bit (if (= tr :transmit) 1 0)]
          [:ok (bit-or (bit-shift-left rt-address 11)
                       (bit-shift-left tr-bit 10)
                       (bit-shift-left subaddress-mode 5)
                       last-field)])))))

(defn unpack
  "16-bit Command Word `payload` -> `[:ok {:rt-address :tr
  :subaddress-mode :mode-command? :word-count-or-mode}]`. `:tr` is
  `:receive`/`:transmit`. `:word-count-or-mode` is the mode code (0..31)
  when `:mode-command?` is true, otherwise the data word count with the
  00000 -> 32 remapping already applied."
  [payload]
  (if-not (<= 0 payload 0xFFFF)
    [:error :mil1553/payload-out-of-range payload]
    (let [rt-address (bit-and (unsigned-bit-shift-right payload 11) 0x1F)
          tr-bit (bit-and (unsigned-bit-shift-right payload 10) 0x1)
          subaddress-mode (bit-and (unsigned-bit-shift-right payload 5) 0x1F)
          last-field (bit-and payload 0x1F)
          mode? (mode-command? subaddress-mode)]
      [:ok {:rt-address rt-address
            :tr (if (= 1 tr-bit) :transmit :receive)
            :subaddress-mode subaddress-mode
            :mode-command? mode?
            :word-count-or-mode (if mode? last-field (if (zero? last-field) 32 last-field))}])))

(defn broadcast?
  [{:keys [rt-address]}]
  (= broadcast-rt-address rt-address))
