(ns mil1553.data
  "The Data Word's 16-bit payload: raw, uninterpreted data — MIL-STD-1553B
  does not itself define what a Data Word's bits mean; that is entirely
  up to the two subsystems exchanging it (a real system layers something
  like MIL-STD-1553's own related standards, or a project-specific ICD,
  on top). This namespace exists mainly to give Data Words the same
  `pack`/`unpack` shape as `mil1553.command`/`mil1553.status`, plus the
  one genuinely 1553-specific rule that DOES apply generically: a value
  is a valid 16-bit payload, full stop.")

(defn pack
  "16-bit value 0..0xFFFF -> `[:ok payload]` (payload IS the value —
  provided for symmetry with `mil1553.command`/`mil1553.status`, and so
  a caller can treat all three word kinds uniformly before handing the
  payload to `mil1553.word/pack`)."
  [value]
  (if (<= 0 value 0xFFFF)
    [:ok value]
    [:error :mil1553/payload-out-of-range value]))

(defn unpack
  [payload]
  (if (<= 0 payload 0xFFFF)
    [:ok payload]
    [:error :mil1553/payload-out-of-range payload]))
