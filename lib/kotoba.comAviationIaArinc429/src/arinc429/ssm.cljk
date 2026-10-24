(ns arinc429.ssm
  "Sign/Status Matrix — word bits 30-31, a 2-bit field whose four codes
  mean DIFFERENT things depending on the data type carried in the same
  word (BNR, BCD, or Discrete). This is the field the ADR-style task brief
  for this library calls out by name: 'the SSM interpretation table per
  data type'.

  **Provenance / confidence note — this table is this library's weakest
  point, more so than the label reversal in `arinc429.label`.** The four
  meanings below are reconstructed from public ARINC 429 tutorials and are
  widely repeated across vendor application notes with this exact wording
  and this exact bit-code assignment, but different secondary sources are
  not perfectly consistent with each other about the BCD row in
  particular (whether 00/11 map to plus/minus or the reverse), and this
  library has not seen the paid AEEC 429 standard text to arbitrate. Treat
  the SSM *codes* (which 2-bit pattern is which data type's row) as far
  more solid than the exact sign polarity in the BCD row — if you are
  wiring this against a real system, verify against your ICD/interface
  document for that specific parameter, not against this table.

  Codes are the same 4 raw values (0-3) across data types; only the label
  attached to each value changes.")

(def bnr-table
  "BNR (Binary, i.e. two's-complement numeric) data. Also used, per common
  convention, for words whose data field is Discrete-per-bit but whose
  status semantics follow the BNR pattern rather than the Discrete one
  below — this library exposes both tables and lets the caller pick,
  rather than guessing from the label."
  {0 :failure-warning
   1 :no-computed-data
   2 :functional-test
   3 :normal-operation})

(def bcd-table
  "BCD (Binary-Coded Decimal) data. Codes 1 and 2 (no-computed-data,
  functional-test) mean the same as the BNR table; codes 0 and 3 carry the
  VALUE'S SIGN instead of a validity flag — this is the row flagged above
  as least confident."
  {0 :plus-north-east-right-to-above
   1 :no-computed-data
   2 :functional-test
   3 :minus-south-west-left-from-below})

(def discrete-table
  "Discrete data. Note this table's 0/3 codes are the OPPOSITE polarity
  from the BNR table above (0 = normal here, 3 = failure here; BNR has it
  reversed) — this asymmetry is exactly why SSM cannot be interpreted
  without knowing the word's data type, and is the reason this namespace
  takes an explicit `data-type` argument rather than one shared table."
  {0 :normal-operation
   1 :no-computed-data
   2 :functional-test
   3 :failure-warning})

(def ^:private tables
  {:bnr bnr-table :bcd bcd-table :discrete discrete-table})

(defn interpret
  "2-bit raw SSM code (0-3) + `data-type` (`:bnr` `:bcd` or `:discrete`)
  -> `[:ok keyword]` or `[:error :arinc429/unknown-data-type data-type]`
  or `[:error :arinc429/ssm-out-of-range code]`."
  [code data-type]
  (cond
    (not (<= 0 code 3)) [:error :arinc429/ssm-out-of-range code]
    (not (contains? tables data-type)) [:error :arinc429/unknown-data-type data-type]
    :else [:ok (get (tables data-type) code)]))

(defn code-for
  "The inverse of `interpret`: the status keyword + data-type -> the 2-bit
  raw code. `[:ok code]` or `[:error :arinc429/unknown-status kw]`."
  [status-kw data-type]
  (if-let [table (get tables data-type)]
    (if-let [code (first (keep (fn [[k v]] (when (= v status-kw) k)) table))]
      [:ok code]
      [:error :arinc429/unknown-status status-kw])
    [:error :arinc429/unknown-data-type data-type]))
