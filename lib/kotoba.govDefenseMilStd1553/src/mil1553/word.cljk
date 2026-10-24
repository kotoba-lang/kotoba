(ns mil1553.word
  "The 20-bit MIL-STD-1553B word, common to all three word types (Command,
  Data, Status): a 3-bit Sync field, a 16-bit payload, and one odd Parity
  bit.

  ```
  | Sync (3) | payload (16, MSB first) | Parity (1, odd) |
  ```

  **Sync is a software abstraction of a physical-layer encoding
  violation, not a claim about wire bit values.** On the actual bus, the
  Sync field is not Manchester-encoded data at all — it is 3 bit-times of
  a deliberate Manchester bi-phase VIOLATION: a contiguous high level for
  Command/Status words, a contiguous low level for Data words. That has
  no natural representation as 3 NRZ data bits (a real Manchester
  encoder/decoder distinguishes it by the absence of the expected
  mid-bit transition, not by reading '0' or '1' values). This namespace
  assigns two arbitrary-but-fixed 3-bit codes, `sync-command-status` and
  `sync-data`, purely so the field exists as a normal fixed-width slot in
  a packed integer alongside payload and parity — **do not read these
  specific numeric values as an electrical/physical fact about the bus.**
  This is this library's clearest instance of 'a codec, not a bus
  controller, no hardware, no timing' from the README.

  MIL-STD-1553B is a US Department of Defense standard; the field widths
  and odd-parity rule here are widely and consistently documented in
  public material (its Wikipedia article, DDC/Data Device Corporation and
  similar bus-analyser vendor application notes, numerous unclassified
  DoD/NASA training materials) — this is the most confidently-sourced of
  this task's three libraries, per its own brief, but this implementation
  has still not read the paid SAE/DoD standard text itself.")

(def sync-command-status
  "Software tag for the Command/Status sync pattern (contiguous HIGH for
  3 bit-times on the real bus — see the namespace docstring)."
  2r110)

(def sync-data
  "Software tag for the Data-word sync pattern (contiguous LOW for 3
  bit-times on the real bus)."
  2r001)

(defn- popcount
  "Count set bits among `x`'s low `width` bits. Parameterised on width
  rather than fixed at 16 on purpose: `pack` needs to count exactly the
  16 payload bits, but `parity-ok?` needs to count 17 (payload + parity
  together) — using a 16-bit-fixed counter for both was this namespace's
  own first bug, caught by the exhaustive word round-trip test: a fixed
  popcount16 silently dropped bit 16 (the payload's own MSB) from the
  parity check, so any payload with its top bit set failed parity
  verification on a word this same code had just correctly packed."
  [x width]
  (loop [n x i 0 c 0]
    (if (= i width) c (recur (unsigned-bit-shift-right n 1) (inc i) (+ c (bit-and n 1))))))

(defn pack
  "`sync` (`sync-command-status` or `sync-data`, or any 0..7 tag) +
  `payload` (0..0xFFFF) -> `[:ok word]`, a 20-bit unsigned integer
  (comfortably inside the 31-bit range every runtime's bitwise operators
  agree on, unlike `com-aviation-ia-arinc-429`'s full 32-bit word — no
  `u32`-style canonicalisation is needed here).

  `[:error :mil1553/sync-out-of-range n]` or `[:error
  :mil1553/payload-out-of-range n]`."
  [sync payload]
  (cond
    (not (<= 0 sync 7)) [:error :mil1553/sync-out-of-range sync]
    (not (<= 0 payload 0xFFFF)) [:error :mil1553/payload-out-of-range payload]
    :else
    (let [ones (popcount payload 16)
          parity (bit-and 1 (inc ones))] ;; odd parity over the 16 payload bits
      [:ok (bit-or (bit-shift-left sync 17) (bit-shift-left payload 1) parity)])))

(defn parity-ok?
  "True when the word's 17 bits (payload + parity) contain an odd number
  of 1-bits — MIL-STD-1553B uses odd parity per word (unlike ARINC 429,
  which uses odd parity over the whole 32-bit word; 1553's parity bit
  covers only Sync-through-payload's 16 data bits, not Sync itself, per
  the widely repeated description of the standard)."
  [word]
  (odd? (popcount (bit-and word 0x1FFFF) 17)))

(defn unpack
  "20-bit `word` -> `[:ok {:sync :payload}]`, or `[:error
  :mil1553/parity-mismatch word]`."
  [word]
  (if-not (parity-ok? word)
    [:error :mil1553/parity-mismatch word]
    [:ok {:sync (bit-and (unsigned-bit-shift-right word 17) 0x7)
          :payload (bit-and (unsigned-bit-shift-right word 1) 0xFFFF)}]))
