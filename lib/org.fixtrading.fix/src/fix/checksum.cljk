(ns fix.checksum
  "BodyLength(9) and CheckSum(10) — the two arithmetic fields in the FIX
  standard header/trailer, and the classic place a from-scratch
  implementation gets subtly wrong (FIX.5.0 SP2 Volume 1, 'Message
  Header'/'Message Trailer').

  **BodyLength** is the byte count starting at the first byte of the
  MsgType(35) field and running through — and including — the SOH that
  terminates the last body field, i.e. up to but not including the '1' of
  '10=' that starts CheckSum. It does **not** include BeginString(8) or
  BodyLength(9) itself, and it **does** include that final trailing SOH.
  Off by one on either boundary doesn't corrupt the message it's computed
  for — a receiver reads exactly `BodyLength` bytes after the '9=NNN' field
  to go looking for '10=', so an implementation that miscounts either end
  produces a frame that *parses as itself* (its own CheckSum will even
  verify, if CheckSum is computed the same wrong way) and only fails on
  whatever comes next: the following message's BeginString gets read as
  though it were still inside this one, or the last byte or two of this
  message's own last field get treated as this message's CheckSum tag.

  **CheckSum** is the sum, mod 256, of every byte from the very first byte
  of the message (BeginString's '8') through that same trailing SOH
  BodyLength's count ends on — i.e. BodyLength's own byte range, plus the
  '8=...' and '9=...' fields in front of it — rendered as **exactly three**
  ASCII digits, zero-padded ('7' is wrong; the wire value is '007'). Two
  independent boundary mistakes are possible here: forgetting the trailing
  SOH before '10=' (same bug as BodyLength, one byte short), and rendering
  the sum without zero-padding (a receiver comparing strings, not integers,
  rejects '62' even though the arithmetic was correct)."
  (:require [fix.bytes :as b]))

(defn format-checksum
  "`n` (already reduced mod 256 by the caller) as exactly three ASCII
  digits, zero-padded. Not `String/format`/`goog.string.format` — neither
  is guaranteed present on every runtime this `.cljc` targets, and the
  padding logic is three lines without it."
  [n]
  (let [s (str (bit-and n 0xFF))]
    (str (case (count s) 1 "00" 2 "0" "") s)))

(defn checksum
  "The FIX CheckSum of `bs` (a seq of byte values): sum mod 256, formatted
  as three digits. `bit-and % 0xFF` on each byte is defensive (callers are
  expected to already be passing 0..255 values out of `fix.bytes`); summing
  with plain `+` rather than folding `bit-and` into the running total
  avoids relying on 32-bit-wraparound `bit-and` semantics for the
  intermediate sum, which ClojureScript's `bit-and` truncates to a signed
  Int32 — irrelevant for any message this library will ever see, but wrong
  to rely on regardless."
  [bs]
  (format-checksum (mod (reduce + 0 (map #(bit-and % 0xFF) bs)) 256)))

(defn body-length
  "The BodyLength of a byte seq that already starts at MsgType(35) and ends
  at the SOH terminating the last body field (i.e. exactly the slice the
  docstring above describes) — just its count. Exists mostly so the
  'what BodyLength counts' definition lives in one place instead of being
  re-derived at each call site as `(count ...)`."
  [bs]
  (count bs))
