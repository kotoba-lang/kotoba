;; Host-side helpers for the machine_ir port (BOOTSTRAP-REFERENCE: JVM host reading).
(ns mi
  (:require [clojure.string :as str] [clojure.edn] [clojure.walk]
            [kotoba.compiler.cli :as cli]))

(defonce cp-file (atom "/tmp/kotoba-route/cp-guest.txt"))
(def scratch "/tmp/kotoba-route")
(def kroot "/private/tmp/wt-K-kotoba-lang")

(defn source-paths
  "Source roots for a guest compile: EXTRA first, then the wall classpath's src roots,
  amu src and kotoba-lang compat."
  [extra]
  (let [cp (str/trim (slurp @cp-file))]
    (vec (concat extra
                 (filter #(str/ends-with? % "/src") (str/split cp #":"))
                 ["/private/tmp/wt-A-amu-measure/src" (str kroot "/lang/compat")]))))

(defn run-cli [& args]
  (let [code (atom 0)
        out (with-out-str
              (binding [*err* *out* *print-namespace-maps* false
                        cli/*exit* (fn [c] (reset! code c))]
                (apply cli/-main args)))]
    {:code @code :out out}))

(defn compile-guest
  "Compile GUEST (a module with an exported `main`) for aarch64-macos and extract `main`.
  Writes OUT.kexe, OUT.bin and returns the offset (or the refusal text)."
  [guest out extra-roots caps]
  (spit (str out ".policy.edn")
        (str "{:allow #{" (str/join " " (map #(str "[:cap/call " % "]") caps)) "}}"))
  (let [sp (mapcat (fn [p] ["--source-path" p]) (source-paths extra-roots))
        c (apply run-cli "compile" guest "--target" "aarch64-macos" "--unpinned"
                 "--policy" (str out ".policy.edn") "--output" (str out ".kexe") sp)]
    (if-not (re-find #":ok true" (:out c))
      {:refused (:out c)}
      ;; extract `main` without the CLI's bounded reader (200k nodes; a linked machine_ir guest is larger)
      (let [art (clojure.edn/read-string {:default (fn [_ v] v)} (slurp (str out ".kexe")))
            ex (get (:exports art) 'main)]
        (with-open [o (java.io.FileOutputStream. (str out ".bin"))]
          (.write o (byte-array (map unchecked-byte (:code art)))))
        {:offset (:offset ex) :bin (str out ".bin")}))))

;; ── recording host calls ─────────────────────────────────────────────────────
(require 'kotoba.compiler.core 'kotoba.native.machine-ir 'kotoba.native.aarch64)

(defonce recordings (atom {}))
(defonce originals (atom {}))

(defn wrap! [sym]
  (let [v (resolve sym)]
    (when-not (contains? @originals sym)
      (swap! originals assoc sym @v))
    (let [f (get @originals sym)]
      (alter-var-root v (constantly
                         (fn [& args]
                           (try (let [r (apply f args)]
                                  (swap! recordings update sym (fnil conj []) [(vec args) r])
                                  r)
                                (catch clojure.lang.ExceptionInfo e
                                  (swap! recordings update sym (fnil conj [])
                                         [(vec args) [:kotoba/error (:problem (ex-data e))]])
                                  (throw e)))))))))

(defn unwrap-all! []
  (doseq [[sym f] @originals] (alter-var-root (resolve sym) (constantly f)))
  (reset! originals {}))

(defn corpus-files []
  (let [roots ["/private/tmp/wt-A-amu-measure/examples"
               "/private/tmp/wt-A-amu-measure/test/nbb/fixtures"
               "/private/tmp/wt-A-amu-measure/resources/kotoba/lang-conformance"
               "/private/tmp/wt-A-amu-measure/bench"]]
    (sort (for [r roots
                f (file-seq (java.io.File. r))
                :when (str/ends-with? (.getName f) ".kotoba")]
            (.getPath f)))))

(defn compile-corpus!
  "Compile every corpus file for aarch64-macos on the host; returns {:ok n :refused n}."
  [files]
  (let [ok (atom 0) bad (atom 0)]
    (doseq [f files]
      (try (kotoba.compiler.core/compile-source (slurp f) :aarch64-macos-kotoba-v1)
           (swap! ok inc)
           (catch Throwable _ (swap! bad inc))))
    {:ok @ok :refused @bad}))

(defn edn-line [x]
  (binding [*print-namespace-maps* false *print-length* nil *print-level* nil]
    (pr-str x)))

(defn write-cases!
  "One line per recorded call of SYM: [args... expected], at most MAXB bytes a line, de-duplicated."
  [sym out maxb]
  (let [rows (distinct (map (fn [[args r]] (edn-line (conj args r))) (get @recordings sym)))
        kept (filter #(<= (count (.getBytes ^String % "UTF-8")) maxb) rows)]
    (spit out (str (str/join "\n" kept) "\n"))
    {:calls (count (get @recordings sym)) :distinct (count rows) :kept (count kept)}))

(require 'kotoba.sema 'kotoba.kir 'kotoba.compiler.project 'kotoba.compiler.project-files)
(defn guest-hir [guest]
  (let [graph (kotoba.compiler.project-files/load-closed-graph guest (source-paths []))
        linked (kotoba.compiler.project/link-source (:sources graph) (:root graph))]
    (kotoba.sema/analyze (:source linked) {:admit-linked-synthetics? true})))

(defn native-blockers [hir]
  (for [f (:functions hir)
        :when (not (kotoba.kir/only-native-word-typed-features? (assoc hir :functions [f])))]
    (:name f)))

(defn blockers-of [guest extra]
  (let [graph (kotoba.compiler.project-files/load-closed-graph guest (source-paths extra))
        linked (kotoba.compiler.project/link-source (:sources graph) (:root graph))
        h (kotoba.sema/analyze (:source linked) {:admit-linked-synthetics? true})]
    (doseq [n (native-blockers h)]
      (let [f (first (filter #(= n (:name %)) (:functions h)))]
        (binding [*print-length* 10 *print-level* 5 *print-namespace-maps* false]
          (println (str n " " (pr-str (:param-types f)) " " (pr-str (:result f)) " " (subs (pr-str (:body f)) 0 (min 400 (count (pr-str (:body f))))))))))))

(defn read-case
  "Read a recorded case line; keywords with a numeric name (vregs, labels) are not Clojure-readable."
  [text]
  (let [t (str/replace text #":([a-zA-Z][\w.\-]*)/(\d[\w\-]*)" ":$1/__num__$2")]
    (clojure.walk/postwalk
     (fn [x] (if (and (keyword? x) (str/starts-with? (name x) "__num__"))
               (keyword (namespace x) (subs (name x) 7))
               x))
     (binding [*read-eval* false] (read-string t)))))

(defn cut-cases
  "Prefixes of the first function's instructions of a recorded v3 MIR case, as case lines for SYM."
  [in out sym ks]
  (let [[p _] (read-case (slurp in))
        f (first (:mir/functions p)) ins (:mir/instructions f)
        g @(resolve sym)]
    (spit out (str (str/join "\n" (for [k ks]
                                    (let [q (assoc p :mir/functions [(assoc f :mir/instructions (vec (take k ins)))])]
                                      (str (name sym) " " (edn-line [q (g q)])))))
                   "\n"))))


(defn stage-cases
  "For one emit-program case line (KIR), the stage inputs on the host: lower-kir-module, compile-gmir, encode-mc-module lines."
  [in out]
  (let [[kir0 _] (read-case (str/replace-first (slurp in) #"^emit-program " ""))
        kir (-> kir0 kotoba.native.keyword-equality/rewrite-program kotoba.native.vector-region/rewrite-program
                (update :functions #(-> % kotoba.native.string-search/augment-functions
                                        kotoba.native.string-index/augment-functions
                                        kotoba.native.document/augment-functions))
                (#(if (:exports %) % (assoc % :exports (mapv :name (:functions %))))))
        g (kotoba.native.machine-ir/lower-kir-module kir)
        m (kotoba.native.machine-ir/compile-gmir :aarch64 g)
        prefixes (kotoba.native.machine-ir/entry-fuel-prefixes kir (constantly []))
        e (kotoba.native.machine-ir/encode-mc-module m prefixes (:exports kir))]
    (spit out (str "lower-kir-module " (edn-line [kir g]) "\n"
                   "compile-gmir " (edn-line [:aarch64 g m]) "\n"
                   "encode-mc-module " (edn-line [m prefixes (:exports kir) e]) "\n"))))

(defn callers-of [guest helper]
  (let [graph (kotoba.compiler.project-files/load-closed-graph guest (source-paths []))
        linked (kotoba.compiler.project/link-source (:sources graph) (:root graph))
        h (kotoba.sema/analyze (:source linked) {:admit-linked-synthetics? true})]
    (for [f (:functions h) :when (str/includes? (pr-str (:body f)) (str helper))]
      [(:name f) (:source-name f) (subs (pr-str (:body f)) 0 (min 300 (count (pr-str (:body f)))))])))

(defn gmir-stage-cases [in out]
  (let [[_ g _] (read-case (str/replace-first (second (str/split-lines (slurp in))) #"^compile-gmir " ""))
        sel (kotoba.mir/select-target :aarch64 g)
        h (kotoba.native.machine-ir/hoist-program-consumers sel)
        a (kotoba.mir/allocate-registers h)
        c (kotoba.native.machine-ir/coalesce-program-moves a)
        l (kotoba.native.machine-ir/lower-mc c)]
    (spit out (str "hoist-program-consumers " (edn-line [sel h]) "\n"
                   "coalesce-program-moves " (edn-line [a c]) "\n"
                   "lower-mc " (edn-line [c l]) "\n"))))

(defn aiueos-files []
  (let [roots ["/Users/junkawasaki/github/kotoba-lang/aiueos/os/aiueos/native"
               "/Users/junkawasaki/github/kotoba-lang/aiueos/os/aiueos/kotoba"
               "/Users/junkawasaki/github/kotoba-lang/aiueos/resources"]]
    (sort (for [r roots
                f (file-seq (java.io.File. r))
                :when (str/ends-with? (.getName f) ".kotoba")]
            (.getPath f)))))
