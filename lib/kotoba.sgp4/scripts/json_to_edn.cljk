(ns json-to-edn
  "Oracle JSON -> the EDN fixtures under test/sgp4/.

  Keys are kebab-cased, with `jdsatepochF` spelled out as `:jdsatepoch-frac`
  rather than left to the generic rule: the generic rule turns it into
  `:jdsatepoch-f`, which is a key no test reads. On ClojureScript a missing
  key is nil and `(+ 2451723.5 nil)` is 2451723.5 -- so the assertion that
  should have compared two epochs compared one against itself and passed.
  That happened. Hence the explicit case, and the `number?` guard in
  sgp4.core-test."
  (:require ["fs" :as fs] [kotoba.lang.text :as str]))

(def header
  {"golden.edn"
   (str ";; SGP4 golden vectors -- GENERATED, do not hand-edit.\n"
        ";; Oracle: python `sgp4` 2.27 (Vallado C++ port). No shared code.\n"
        ";; Regenerate: scripts/regenerate-golden.md\n")
   "frames_golden.edn"
   (str ";; Frame-conversion golden -- GENERATED, do not hand-edit.\n"
        ";; Oracles: sgp4.propagation/gstime; pyproj 3.7.2 / PROJ 9.5.1.\n"
        ";; Regenerate: scripts/regenerate-golden.md\n")})

(defn kebab [k]
  (if (= k "jdsatepochF")
    "jdsatepoch-frac"
    (-> k (str/replace #"([a-z0-9])([A-Z])" "$1-$2") (str/replace "_" "-") str/lower)))

(defn ->edn [v indent]
  (let [sp (apply str (repeat indent "  "))
        sp1 (str sp "  ")]
    (cond
      ;; Keys are SORTED. `js->clj` hands back an unordered map above eight
      ;; entries, so without this the same input regenerates to a different
      ;; byte sequence each run and every regeneration looks like a change.
      (map? v) (str "{\n"
                    (str/join "\n" (map (fn [[k val]]
                                          (str sp1 ":" k " "
                                               (str/triml (->edn val (inc indent)))))
                                        (sort-by key (into (sorted-map)
                                                           (map (fn [[k val]] [(kebab (name k)) val]) v)))))
                    "\n" sp "}")
      (vector? v) (if (map? (first v))
                    (str "[\n" (str/join "\n" (map #(str sp1 (str/triml (->edn % (inc indent)))) v))
                         "\n" sp "]")
                    (str "[" (str/join " " (map #(->edn % 0) v)) "]"))
      (nil? v) "nil"
      (string? v) (pr-str v)
      :else (pr-str v))))

(let [argv (js->clj js/process.argv)
      ;; nbb's argv carries [node, nbb_main.js, this-script, ...user args],
      ;; and the count of leading entries differs between invocations. Taking
      ;; the last two is stable; taking (drop 2) read this file as the input.
      [in out] (take-last 2 argv)
      data (js->clj (js/JSON.parse (fs/readFileSync in "utf8")))
      base (last (str/split out #"/"))]
  (when-not (and in out) (println "usage: json_to_edn.cljs <in.json> <out.edn>") (js/process.exit 2))
  (fs/writeFileSync out (str (get header base "") (->edn data 0) "\n"))
  (println "wrote" out))
