(ns afdx.sequence
  "The AFDX Sequence Number: a 1-octet counter appended to every frame
  on a Virtual Link, whose defining trap this library's task brief names
  directly — it wraps 255 -> 1, SKIPPING 0, not 255 -> 0 -> 1 the way a
  naive `(mod (inc sn) 256)` would.

  0 is reserved: by common description across public AFDX material, an
  End System's very first frame on a VL after activation carries SN 1,
  and 0 is used only as a receiver-side 'no frame received yet' sentinel
  — it is never itself transmitted as a real frame's SN. That reserved
  status is why the live cycle has period 255 (values 1..255), not 256,
  which matters for `steps-forward` below: naive modulo-256 wrap-distance
  arithmetic is wrong here for the same reason naive modulo-256 `next-sn`
  is wrong.

  Confidence: this wrap rule (255 -> 1, 0 reserved/never transmitted) is
  repeated consistently and specifically across multiple independent
  public AFDX descriptions — more consistently than the BCD SSM polarity
  question in `com-aviation-ia-arinc-429` or the MAC-address convention
  in `afdx.vl` — but is still reconstructed from secondary sources, not
  the paid ARINC 664 P7 text.")

(defn valid-sn?
  "Any single octet, 0..255, is a syntactically valid SN field — `sn`
  being 0 specifically means 'sentinel, not a transmitted frame' rather
  than being itself invalid; callers that care about that distinction
  use `initial?` separately."
  [sn]
  (<= 0 sn 255))

(defn initial?
  "True for the reserved sentinel value: no frame received/sent yet on
  this VL."
  [sn]
  (zero? sn))

(defn next-sn
  "The SN that follows `sn` on the wire. `next-sn(255)` is 1 — NOT 0 —
  and `next-sn(0)` (the initial sentinel) is 1, the first real SN a VL
  ever transmits. Every other value simply increments."
  [sn]
  (let [n (inc sn)]
    (if (> n 255) 1 n)))

(defn steps-forward
  "How many `next-sn` applications it takes to reach `to` starting from
  `from`, both in the live 1..255 cycle (period 255, NOT 256 — see the
  namespace docstring for why 0's reserved status matters here). 0 if
  `from` = `to`. `[:error :afdx/sn-out-of-range n]` if either argument is
  the reserved sentinel 0 or otherwise out of 1..255."
  [from to]
  (if (or (not (<= 1 from 255)) (not (<= 1 to 255)))
    [:error :afdx/sn-out-of-range (if (<= 1 from 255) to from)]
    [:ok (mod (- to from) 255)]))
