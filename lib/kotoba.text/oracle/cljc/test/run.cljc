(ns text-oracle-run
  "Oracle case runner for the kotoba.lang.text twin. Same output
  contract as the json/edn twin runners (one line per case plus a
  fixed-order summary; values print solely on failure).

  `:cmap-keys` cases carry escape maps with string keys; the runner
  normalizes each key with `first`, which answers the seq-element type
  of the running host (Character on bb, one-char string elsewhere).

  Usage (from the directory holding this file):
    bb -cp <oracle-src>:<this-dir> run.cljc
    nbb -cp <oracle-src>:<this-dir> run.cljc
    basilisp run -p <oracle-src> -p <this-dir> run.cljc"
  (:require [kotoba.lang.text :as t]
            [text-oracle-cases :as cases]
            [clojure.string :as str])
  #?(:lpy (:import sys)))

(defn- char-code [ch]
  #?(:lpy (ord (str ch))
     :clj (int (.charAt (str ch) 0))
     :cljs (.charCodeAt (str ch) 0)))

(defn- normalize-args [c]
  (if (:cmap-keys c)
    (mapv (fn [a] (if (map? a) (into {} (map (fn [[k v]] [(first (str k)) v]) a)) a))
            (:args c))
    (:args c)))

(defn- outcome [c]
  (try
    (let [got (apply (case (:op c)
                       :split t/split :join t/join :split-lines t/split-lines
                       :trim t/trim :triml t/triml :trimr t/trimr
                       :trim-newline t/trim-newline
                       :upper t/upper :lower t/lower :ascii-lower t/ascii-lower
                       :capitalize t/capitalize
                       :starts-with? t/starts-with? :ends-with? t/ends-with?
                       :includes? t/includes?
                       :index-of t/index-of :last-index-of t/last-index-of
                       :blank? t/blank?
                       :replace t/replace :replace-first t/replace-first
                       :reverse t/reverse :truncate t/truncate
                       :pad-left t/pad-left :pad-right t/pad-right
                       :escape t/escape :re-quote t/re-quote
                       :re-find t/re-find :re-matches t/re-matches :re-seq t/re-seq
                       :format t/format
                       :codepoints t/codepoints :from-codepoints t/from-codepoints
                       :from-codepoints-codes (fn [& cps] (t/codepoints (apply t/from-codepoints cps)))
                       :segment-text t/segment-text :pad-center-text t/pad-center-text
                       :trim-text t/trim-text :blank-text? t/blank-text?)
                     (normalize-args c))]
      (cond
        (:expect-codes c)
        (let [codes (mapv char-code (str got))]
          {:pass (= codes (:expect-codes c)) :got codes :want (:expect-codes c)})
        (contains? c :error)
        {:pass false :got got :want-error (:error c)}
        :else
        {:pass (= (if (seq? got) (vec got) got) (:expect c)) :got got :want (:expect c)}))
    (catch #?(:lpy python/Exception :clj Exception :cljs :default) e
      (if-let [want (:error c)]
        {:pass (str/includes? (str (ex-message e)) want)
         :got (str "ERROR: " (ex-message e)) :want-error want}
        {:pass false :got (str "ERROR: " (ex-message e)) :want (:expect c)}))))

(defn -main [& _]
  (let [all (concat cases/cases cases/must-fail-cases)
        results (mapv (fn [c]
                        (let [r (outcome c)
                              pass? (if (:must-fail c) (not (:pass r)) (:pass r))]
                          (assoc c :result (assoc r :pass pass?))))
                      all)
        fails (filterv (comp not :pass :result) results)]
    (doseq [r results]
      (println (str (:id r) (if (:pass (:result r)) " ok" " FAIL"))))
    (doseq [f fails]
      (println "GOT:" (pr-str (:got (:result f)))
               "WANT:" (pr-str (select-keys f [:expect :expect-codes :error]))))
    (println "cases:" (count results) "pass:" (- (count results) (count fails))
             "fail:" (mapv :id fails))
    (let [code (if (seq fails) 1 0)]
      #?(:lpy (.exit sys code)
         :clj (System/exit code)
         :cljs (.exit js/process code)))))

(-main)
