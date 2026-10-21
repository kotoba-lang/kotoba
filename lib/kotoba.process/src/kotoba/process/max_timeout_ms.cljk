(ns kotoba.process.max-timeout-ms
  "max-timeout-ms -- addressed on its own.

  Split out of kotoba.lang.process on 2026-09-09 (ADR-2609091200). The unit
  here is the DEFINITION, and this repo's deps.edn names exactly the
  definitions it reaches -- nothing else.
"
  #?(:cljs (:require ["child_process" :as cp]))
  #?(:clj
     (:import (java.io ByteArrayOutputStream InputStream)
              (java.nio.charset StandardCharsets)
              (java.util.concurrent TimeUnit))))

(def max-timeout-ms 600000)
