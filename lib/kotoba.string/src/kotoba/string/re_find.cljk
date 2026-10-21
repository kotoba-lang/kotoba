(ns kotoba.string.re-find
  "re-find -- one definition, addressed on its own.

  Split out of kotoba.lang.text on 2026-09-09. The unit here is the
  DEFINITION, not the library: this repo holds re-find and names, in its
  deps.edn, exactly the definitions re-find reaches. Nothing else."
  (:refer-clojure :exclude [re-find])
  )

(defn re-find    [re s] (#?(:clj clojure.core/re-find :cljs cljs.core/re-find) re s))
