(ns quickjs.binary
  "QuickJS WASM binary loading contract.

   Split out of kotoba-lang/browser (ADR-2607051140) — the only file under
   browser.compat.quickjs* with zero coupling to browser's own domain model
   (audit/dom-bridge/net/origin/profile/runtime/storage/event-loop). The
   other quickjs.* adapter/binding/execution namespaces stay in browser: they
   describe how a QuickJS engine wires into *that specific browser's*
   capability/session model, not a generic reusable contract."
  #?(:clj (:import [java.nio.file Files Path]
                   [java.security MessageDigest])))

(def wasm-magic [0 97 115 109])

(defn wasm-bytes?
  [bytes]
  (let [xs (take 4 (seq bytes))]
    (= wasm-magic (mapv #(bit-and 0xff %) xs))))

#?(:clj
   (defn sha256-hex
     [bytes]
     (let [digest (.digest (MessageDigest/getInstance "SHA-256") bytes)]
       (apply str (map #(format "%02x" (bit-and 0xff %)) digest)))))

#?(:cljs
   (defn- byte->hex
     [b]
     (let [hex (.toString (bit-and b 0xff) 16)]
       (if (= 1 (.-length hex)) (str "0" hex) hex))))

#?(:cljs
   (defn- array-buffer->hex
     "Lowercase hex digest string from a digest `ArrayBuffer`, byte-for-byte
      identical in format to :clj's `sha256-hex` (`format \"%02x\"` per byte,
      concatenated) so a hash computed here for the same bytes matches the
      JVM-computed hash exactly."
     [buf]
     (let [bytes (js/Uint8Array. buf)
           n (.-length bytes)]
       (loop [i 0 acc (transient [])]
         (if (< i n)
           (recur (inc i) (conj! acc (byte->hex (aget bytes i))))
           (apply str (persistent! acc)))))))

#?(:cljs
   (defn sha256-hex
     "Async counterpart to :clj's `sha256-hex`: computes a real SHA-256 over
      `bytes` (a `js/Uint8Array`) via the Web Crypto API and returns a
      Promise resolving to the same lowercase hex digest format `:clj`
      produces. There is no synchronous digest API in browsers, so unlike
      :clj this cannot be a plain function returning a string -- callers
      (`load-url`) must `.then` it before building a `descriptor`.

      Fails loudly (rejects) rather than degrading silently when
      `js/crypto.subtle` is unavailable (e.g. a non-secure context that
      isn't https/localhost) -- returning a descriptor with a nil/skipped
      hash in that case would silently defeat the integrity check
      `attach-binary`/`verify-integrity` exist for, which is the exact bug
      this function fixes."
     [bytes]
     (if (and (exists? js/crypto) (exists? js/crypto.subtle))
       (-> (.digest js/crypto.subtle "SHA-256" bytes)
           (.then array-buffer->hex))
       (js/Promise.reject
        (js/Error. "quickjs.binary/sha256-hex: js/crypto.subtle unavailable (requires a secure context, e.g. https or localhost)")))))

(defn descriptor
  "`bytes` is a JVM byte array on :clj (`count` works directly) but a
   `js/Uint8Array` on :cljs (`load-url`'s `fetch().arrayBuffer()` result) --
   `js/Uint8Array` doesn't implement ClojureScript's `ICounted`, so plain
   `count` throws `No protocol method ICounted.-count defined` on every
   real :cljs call (confirmed via the real ClojureScript/Node compiler,
   never caught before since this repo has no :cljs test toolchain checked
   in). `.-length` is the correct, direct way to size a typed array."
  [{:keys [bytes path sha256] :as opts}]
  (let [size #?(:clj (count bytes) :cljs (.-length bytes))]
    {:quickjs.binary/path path
     :quickjs.binary/sha256 #?(:clj (or sha256 (sha256-hex bytes))
                               :cljs sha256)
     :quickjs.binary/size size
     :quickjs.binary/wasm? (wasm-bytes? bytes)
     :quickjs.binary/bytes bytes
     :quickjs.binary/meta (dissoc opts :bytes :path :sha256)}))

(defn verify-integrity
  [binary expected-sha256]
  (let [actual (:quickjs.binary/sha256 binary)]
    {:quickjs.binary/integrity-ok? (= expected-sha256 actual)
     :quickjs.binary/expected-sha256 expected-sha256
     :quickjs.binary/actual-sha256 actual}))

#?(:clj
   (defn load-wasm-file
     [path]
     (let [p (Path/of (str path) (make-array String 0))
           bytes (Files/readAllBytes p)]
       (descriptor {:path (str path) :bytes bytes}))))

#?(:cljs
   (defn load-url
     "Fetches `url`, then computes a real SHA-256 over the response bytes
      (via `sha256-hex`'s Web Crypto digest, an additional async step
      after `.arrayBuffer()`) BEFORE building the descriptor, passing the
      computed hex string in as `:sha256`. This keeps `descriptor` itself
      synchronous and unchanged in shape -- `descriptor`'s :cljs branch
      already just passes through whatever `:sha256` it's given, so no
      change to `descriptor` was needed, only to what `load-url` gives it."
     ([url]
      (load-url url {}))
     ([url {:keys [signal]}]
      (let [opts #js {}]
        (when signal
          (aset opts "signal" signal))
     (-> (js/fetch url opts)
         (.then #(.arrayBuffer %))
         (.then (fn [buf]
                  (let [bytes (js/Uint8Array. buf)]
                    (-> (sha256-hex bytes)
                        (.then (fn [hex]
                                 (descriptor {:path url :bytes bytes :sha256 hex}))))))))))))

(defn attach-binary
  ([binding binary]
   (attach-binary binding binary {}))
  ([binding binary {:keys [expected-sha256]}]
  (if (and (:quickjs.binary/wasm? binary)
           (or (nil? expected-sha256)
               (:quickjs.binary/integrity-ok? (verify-integrity binary expected-sha256))))
    (assoc binding :quickjs/binary (dissoc binary :quickjs.binary/bytes))
    (assoc binding :quickjs/error {:reason (if (:quickjs.binary/wasm? binary)
                                             :quickjs/integrity-check-failed
                                             :quickjs/invalid-wasm-binary)
                                   :path (:quickjs.binary/path binary)
                                   :integrity (when expected-sha256
                                                (verify-integrity binary expected-sha256))}))))
