(ns kotobase.blockcodec.fixtures
  "Payloads the suite frames, shared so the two runtimes cannot drift apart in
  what they think they are testing.

  `ascii` is here for a reason worth keeping: the first draft of these
  fixtures used `(map int s)`, which is the character's code point on the JVM
  and — because ClojureScript seqs a string into single-character strings and
  `int` is `(bit-or x 0)` — **zero** for every letter on ClojureScript.
  The ClojureScript suite passed anyway: both sides of every round-trip used
  the same broken fixture, so it was self-consistently testing a payload of
  mostly zeros. Only `golden-test`, which compares against literal bytes
  produced on the other runtime, could see it.")

(defn ascii
  "ASCII string → vector of byte values, on either runtime."
  [s]
  #?(:clj (mapv int s)
     :cljs (mapv #(.charCodeAt ^js % 0) s)))

(defn quad-payload
  "Shaped like the DAG-CBOR of a `{\"quads\" [...]}` tx payload: a map header,
  then subject/predicate strings that repeat the way real kotobase quads
  repeat. That repetition is the entire reason this format pays."
  [n]
  (into [0xA1 0x65]
        (mapcat (fn [i]
                  (ascii (str "did:web:kotobase.net:entity:" (mod i 500)
                              "|kind|value-" i)))
                (range n))))

(defn incompressible
  "Deterministic but structureless — a linear congruential walk. Stands in for
  the AEAD ciphertext `arrangement.core/index-root` actually stores in a leaf,
  which measures at ratio 1.003: it *grows* under DEFLATE."
  [n]
  (loop [i 0 s 12345 acc [0xA1]]
    (if (= i n)
      acc
      (let [s' (mod (+ (* s 1103515245) 12345) 2147483648)]
        (recur (inc i) s' (conj acc (mod (quot s' 65536) 256)))))))

(defn golden-input
  "The payload `golden-test` pins the framed bytes of."
  []
  (into [0xA1 0x66 0x71 0x75 0x61 0x64 0x73]
        (mapcat (fn [i] (ascii (str "did:web:kotobase.net:e" (mod i 7) "|p|v" i)))
                (range 60))))
