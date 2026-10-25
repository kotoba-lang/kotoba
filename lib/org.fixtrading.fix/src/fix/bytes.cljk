(ns fix.bytes
  "Byte<->string primitives shared by the rest of this library, and the low
  level SOH-delimited field splitter/parser.

  FIX's wire format is officially ASCII outside a few free-text fields
  (Text(58) and friends, which FIX 5.0 SP2 Volume 1 allows to carry
  ISO 8859-1/UTF-8 depending on session-level encoding negotiation this
  library does not implement). This library treats every field value as
  Latin-1 — one byte in 0..255 maps to exactly one character and back —
  which round-trips byte-exact for the ASCII subset this library's own
  dictionary and tests use. A caller who needs to push real multi-byte UTF-8
  free text through a field is responsible for their own encode/decode of
  that field's value; this library does not do implicit UTF-8 transcoding
  anywhere, on purpose, because that is exactly the seam where a byte-level
  protocol quietly stops being byte-level.")

(def soh
  "0x01 — the field delimiter framing every FIX field. It is not a
  printable character on purpose: any byte a real field value needs to
  carry is either not this one, or (RawData(96), which this library does
  not implement) preceded by an explicit length so an embedded 0x01 is
  never mistaken for a delimiter."
  1)

(defn char-code
  "Codepoint of `s`'s `i`-th char.

  Deliberately not `(int (nth s i))`. Under ClojureScript, `nth` on a
  string returns a one-character JS string, and `int` applied to *that* is
  not the codepoint-extraction operator it is on the JVM (where `.charAt`
  already gives you a primitive `char` and `int` widens it). `.charCodeAt`
  is the primitive that actually agrees with the JVM's
  `(int (.charAt s i))` for every codepoint in the Basic Multilingual
  Plane, which is all this library's Latin-1 byte mapping ever produces.
  This is the same idiom org-modbus's README names as having produced a
  wrong-and-plausible answer three times in one day elsewhere in this
  workspace — `(map int \"123456789\")` silently becoming nine zero bytes
  under ClojureScript while looking correct on the JVM."
  [s i]
  #?(:clj (int (.charAt ^String s i))
     :cljs (.charCodeAt s i)))

(defn byte->char
  "The inverse of `char-code`: the character whose codepoint is `b`
  (0..255). `char` on the JVM and `String.fromCharCode` under
  ClojureScript agree for this range; neither is used on the other
  runtime, again on purpose."
  [b]
  #?(:clj (char (bit-and b 0xFF))
     :cljs (js/String.fromCharCode (bit-and b 0xFF))))

(defn str->bytes
  "`s` as a vector of byte values 0..255, one per character, via
  `char-code`+`bit-and 0xFF` — never `.getBytes`/`TextEncoder`, so this
  function is exactly and only the inverse of `bytes->str` below, with no
  UTF-8 multi-byte expansion in either direction."
  [s]
  (mapv #(bit-and (char-code s %) 0xFF) (range (count s))))

(defn bytes->str
  "The inverse of `str->bytes`."
  [bs]
  (apply str (map byte->char bs)))

(defn parse-uint
  "`s` as a non-negative base-10 integer, or `nil` if `s` is empty or
  contains any non-digit character.

  Deliberately not `js/parseInt` alone under ClojureScript: `js/parseInt`
  parses a leading numeric prefix and silently ignores trailing garbage
  (`(js/parseInt \"12x\" 10)` => `12`), which would let a corrupt
  BodyLength or CheckSum field pass validation instead of failing it. The
  regex match is the actual validation; the runtime-specific integer
  parse only runs once the whole string is known to be digits."
  [s]
  (when (and (string? s) (re-matches #"[0-9]+" s))
    #?(:clj (Long/parseLong s)
       :cljs (js/parseInt s 10))))

(defn split-soh
  "`bs` (a seq of byte values) split on `soh`, as a vector of byte-value
  vectors (SOH itself is dropped, the way tag=value pairs are conventionally
  written without their delimiter). `:trailing?` is true when the input
  ends mid-field — i.e. the last byte was not a SOH — which means the frame
  is incomplete and the trailing partial field is dropped from `:fields`
  rather than treated as a real one."
  [bs]
  (loop [remaining (seq bs) cur [] out []]
    (if (empty? remaining)
      {:fields out :trailing? (boolean (seq cur))}
      (let [b (first remaining)]
        (if (= b soh)
          (recur (rest remaining) [] (conj out cur))
          (recur (rest remaining) (conj cur b) out))))))

(defn parse-field
  "One field's byte vector (no SOH, no leading/trailing separators) -> a
  `[tag value-string]` pair, or `nil` if there is no `=` (0x3D) or the part
  before it isn't a valid non-negative integer tag."
  [field-bytes]
  (let [eq-idx (first (keep-indexed (fn [i b] (when (= b 61) i)) field-bytes))]
    (when eq-idx
      (let [tag-bytes (subvec (vec field-bytes) 0 eq-idx)
            val-bytes (subvec (vec field-bytes) (inc eq-idx) (count field-bytes))
            tag (parse-uint (bytes->str tag-bytes))]
        (when tag
          [tag (bytes->str val-bytes)])))))
