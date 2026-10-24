(ns kotobase.engine.completion
  "Minimal host-neutral composition for an immediate value, JVM CompletionStage,
  or JavaScript Promise."
  #?(:clj (:import [java.util.concurrent CompletionStage]
                   [java.util.function Function])))

(defn completion? [x]
  #?(:clj (instance? CompletionStage x)
     :cljs (and (some? x) (fn? (.-then x)))))

(defn then-result [x f]
  #?(:clj (if (completion? x)
            (.thenApply ^CompletionStage x
                        (reify Function
                          (apply [_ value] (f value))))
            (f x))
     :cljs (if (completion? x) (.then x f) (f x))))
