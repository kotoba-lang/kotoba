(ns kotoba.process.read-bounded
  "read-bounded -- addressed on its own.

  Split out of kotoba.lang.process on 2026-09-09 (ADR-2609091200). The unit
  here is the DEFINITION, and this repo's deps.edn names exactly the
  definitions it reaches -- nothing else.
"
  #?(:cljs (:require ["child_process" :as cp]))
  #?(:clj
     (:import (java.io ByteArrayOutputStream InputStream)
              (java.nio.charset StandardCharsets)
              (java.util.concurrent TimeUnit))))

#?(:clj
   (defn read-bounded
     "Read `in` fully (bounded by `max-bytes`) as UTF-8. Twin of the helper in
     kotoba.lang.process-host's `sh` — duplicated here (not required) because
     process-host itself requires this namespace, so requiring the other way
     round would be circular."
     [^InputStream in max-bytes]
     (let [buf (byte-array 4096)
           out (ByteArrayOutputStream.)]
       (loop [total 0]
         (let [n (.read in buf)]
           (cond
             (neg? n) (.toString out StandardCharsets/UTF_8)
             (>= total max-bytes) (.toString out StandardCharsets/UTF_8)
             :else
             (let [take (min n (- max-bytes total))]
               (.write out buf 0 take)
               (recur (+ total take)))))))))
