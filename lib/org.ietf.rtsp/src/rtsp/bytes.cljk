(ns rtsp.bytes
  "The one conversion this codec needs between `vector<int 0..255>` — the
  byte-vector convention `modbus.pdu` and `rtp.header` already use in
  this workspace — and text.

  RTSP's own grammar (RFC 2326 §12, borrowed from HTTP/1.1's
  `TEXT = <any OCTET except CTLs>`) defines the start-line and headers as
  octets, not as any particular character encoding. Mapping byte value
  N to the Unicode code point N (Latin-1, not UTF-8) is therefore the
  *correct* transform for this specific 0..255 domain, not a shortcut —
  it is exact and its own inverse, because no byte in range ever needs
  more than one JS UTF-16 code unit or one JVM char to represent, so
  there is no surrogate-pair or multi-byte hazard to get backwards.

  **The code-point-extraction hazard is real, and this namespace hit it
  during development, not just \"elsewhere in the workspace\".**
  `org-modbus`'s README documents `(map int \"...\")` silently returning
  zeros under ClojureScript, because a JVM `(seq \"abc\")` yields
  `Character`s (where `int` is a code point) while a ClojureScript
  `(seq \"abc\")` yields one-character *strings* (where `int` on a
  string is not a code point at all — it coerces through `js/Number`,
  which parses `\"a\"` as NaN, truncated to 0). `str->bytes` below
  originally used exactly `(mapv int s)` and returned all zeros under
  `nbb` (confirmed: `(mapv int \"abc\")` => `[0 0 0]` in cljs, `[97 98
  99]` on the JVM) — caught only because this codec's own cljs test run
  is part of its conformance floor, not by inspection. The fix is the
  same one `kotoba.bytes/code-unit-at` uses: a reader-conditional
  accessor, `.charAt`/`(int)` on the JVM vs `.charCodeAt` in cljs."
)

(defn bytes->str
  "vector<int 0..255> -> string, one char per byte. `char` on an integer
  is the correct inverse on both platforms (no analogous hazard here —
  int->char, not char->int)."
  [bs]
  (apply str (map char bs)))

(defn- code-unit-at [s i] #?(:clj (int (.charAt s i)) :cljs (.charCodeAt s i)))

(defn str->bytes
  "string of chars 0..255 -> vector<int 0..255>. Any code point outside
  that range is a caller error (this codec's header grammar never
  produces one), not silently masked."
  [s]
  (mapv #(code-unit-at s %) (range (count s))))
