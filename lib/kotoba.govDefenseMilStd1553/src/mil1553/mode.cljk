(ns mil1553.mode
  "The 5-bit Mode Code table: what a Command Word's Word Count/Mode Code
  field means when its Subaddress/Mode field is 0 or 31 (see
  `mil1553.command`).

  **Confidence note.** Codes 0-8 and 16-21 below are the specific mode
  codes named, with this exact numbering, across multiple independent
  public sources (Wikipedia's MIL-STD-1553 article, DDC/aerospace bus
  application notes, unclassified DoD/NASA training slide decks) closely
  enough that this implementation is reasonably confident in them —
  substantially more confident than `com-aviation-ia-arinc-664`'s
  `afdx.vl` MAC convention, for instance, though still not a citation of
  the paid standard text. Codes 9-15 and 22-31 are marked `:reserved`
  here — **not** because this library knows they carry no meaning (some
  are used by vendor-specific extensions in real systems), but because
  this implementation does not have a confident, sourced meaning to
  assign them, and inventing one would be exactly the kind of fabricated
  spec vector this library's README warns against. `:reserved` in this
  table means 'not enumerated with confidence', not 'guaranteed unused'.

  `:data-word` on each entry: `:none` (no data word transfers with this
  mode code), `:bc-to-rt` (the BC sends one data word right after the
  Command Word), `:rt-to-bc` (the RT sends one data word, after its
  Status Word), or `:unknown` for the reserved codes, where this library
  is not confident enough to assert either way — a caller building a
  message with a `:unknown` mode code gets an explicit
  `:mil1553/mode-code-data-word-unknown` error from `mil1553.message`
  rather than a silent guess.")

(def table
  {0 {:name "Dynamic Bus Control" :data-word :none}
   1 {:name "Synchronize" :data-word :none}
   2 {:name "Transmit Status Word" :data-word :none}
   3 {:name "Initiate Self-Test" :data-word :none}
   4 {:name "Transmitter Shutdown" :data-word :none}
   5 {:name "Override Transmitter Shutdown" :data-word :none}
   6 {:name "Inhibit Terminal Flag Bit" :data-word :none}
   7 {:name "Override Inhibit Terminal Flag Bit" :data-word :none}
   8 {:name "Reset Remote Terminal" :data-word :none}
   9 {:name "Reserved" :data-word :unknown}
   10 {:name "Reserved" :data-word :unknown}
   11 {:name "Reserved" :data-word :unknown}
   12 {:name "Reserved" :data-word :unknown}
   13 {:name "Reserved" :data-word :unknown}
   14 {:name "Reserved" :data-word :unknown}
   15 {:name "Reserved" :data-word :unknown}
   16 {:name "Transmit Vector Word" :data-word :rt-to-bc}
   17 {:name "Synchronize (with data word)" :data-word :bc-to-rt}
   18 {:name "Transmit Last Command" :data-word :rt-to-bc}
   19 {:name "Transmit BIT Word" :data-word :rt-to-bc}
   20 {:name "Selected Transmitter Shutdown" :data-word :bc-to-rt}
   21 {:name "Override Selected Transmitter Shutdown" :data-word :bc-to-rt}
   22 {:name "Reserved" :data-word :unknown}
   23 {:name "Reserved" :data-word :unknown}
   24 {:name "Reserved" :data-word :unknown}
   25 {:name "Reserved" :data-word :unknown}
   26 {:name "Reserved" :data-word :unknown}
   27 {:name "Reserved" :data-word :unknown}
   28 {:name "Reserved" :data-word :unknown}
   29 {:name "Reserved" :data-word :unknown}
   30 {:name "Reserved" :data-word :unknown}
   31 {:name "Reserved" :data-word :unknown}})

(defn lookup
  "5-bit mode code (0..31) -> `[:ok {:name :data-word}]`, or `[:error
  :mil1553/mode-code-out-of-range n]`."
  [code]
  (if-let [entry (get table code)]
    [:ok entry]
    [:error :mil1553/mode-code-out-of-range code]))

(defn data-word-direction
  "5-bit mode code -> `[:ok :none/:bc-to-rt/:rt-to-bc]`, or `[:error
  :mil1553/mode-code-data-word-unknown code]` for the codes this table
  marks `:reserved`/`:unknown` — see the namespace docstring for why
  that is a distinct outcome from `:none`, not folded into it."
  [code]
  (let [[status entry] (lookup code)]
    (cond
      (= :error status) [status entry]
      (= :unknown (:data-word entry)) [:error :mil1553/mode-code-data-word-unknown code]
      :else [:ok (:data-word entry)])))
