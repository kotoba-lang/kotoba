(ns kotoba.crypto.jvm-digest
  "jvm-digest -- addressed on its own.

  Split out of kotoba.lang.crypto on 2026-09-09 (ADR-2609091200). The unit
  here is the DEFINITION, and this repo's deps.edn names exactly the
  definitions it reaches -- nothing else.
"
  )

(defn jvm-digest [algo data]
  #?(:clj  (let [md (java.security.MessageDigest/getInstance algo)]
             (.digest md (byte-array data)))
     :cljs (throw (ex-info "crypto: WASM/CLJS digest needs host-injected fn" {:algo algo}))))
