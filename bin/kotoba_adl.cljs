#!/usr/bin/env nbb
(ns kotoba-adl
  "`kotoba adl` -- mechanical conversion of EDN to Kotoba ADL.

   Runs on nbb, so it does not start a JVM. The codec it drives
   (kotoba.adl / kotoba.adl.reader) is portable .cljc; only this driver is
   nbb-specific, because it walks directories and renames files, and kbb's fs
   capability is a single request/response bounded at 65536 bytes with no
   directory listing. Remove this driver in favour of kbb when kbb grows a
   directory-walking capability -- the codec needs no change.

   Exit codes: 0 clean, 1 findings, 2 refused (could not measure)."
  (:require [kotoba.adl :as adl]
            [kotoba.adl.reader :as r]
            [clojure.string :as str]
            ["fs" :as fs]
            ["path" :as path]
            ["child_process" :as cp]))

;; Filenames an external tool owns. Renaming these breaks the toolchain and we
;; cannot fix it from here: the clojure CLI requires deps.edn, nbb requires
;; nbb.edn. These are origin-owned names, not ours to rename.
(def tool-owned
  #{"deps.edn" "nbb.edn" "bb.edn" "shadow-cljs.edn" "figwheel-main.edn"
    "lein-project.edn" "data_readers.edn" "config.edn.template"})

(def source-ext [".clj" ".cljs" ".cljc"])

(defn- source-path? [p] (some #(str/ends-with? p %) source-ext))

(defn- source-target [p]
  (str (subs p 0 (str/last-index-of p ".")) ".kotoba"))

(def skip-dirs #{".git" "node_modules" ".nbb" ".cpcache" "target" ".shadow-cljs"
                 ".projection-cache" "dist" "build" ".datalad"})

(defn- walk-edn [root out]
  (let [st (try (fs/statSync root) (catch :default _ nil))]
    (cond
      (nil? st) out
      (.isFile st) (if (or (str/ends-with? root ".edn") (source-path? root))
                     (conj out root) out)
      (.isDirectory st)
      (if (contains? skip-dirs (path/basename root))
        out
        (reduce (fn [acc e] (walk-edn (path/join root e) acc))
                out
                (sort (fs/readdirSync root))))
      :else out)))

(defn- dirty-set
  "Paths with uncommitted changes, per git.

   Converting one of these renames a file out from under an edit that is not in
   any commit. Measured 2026-09-10: wave 1 hit exactly this. A bot had appended
   one record to a metrics document; the rename landed upstream, the local edit
   then blocked the merge, and the record survived only because it was archived
   by hand first. --tracked-only guards files git does not know about; it says
   nothing about files git knows about and whose content has moved on."
  [root]
  (let [out (.toString (cp/execSync "git status --porcelain -z --"
                                    #js {:cwd root :maxBuffer 268435456}))]
    (->> (str/split out #"\u0000")
         (remove empty?)
         ;; porcelain -z: "XY <path>", and a rename adds a second NUL-separated
         ;; path which we do not need -- an entry without a status prefix is
         ;; that trailing path and is dropped by the length guard below.
         (keep (fn [e] (when (> (count e) 3) (subs e 3))))
         set)))

(defn- tracked-set
  "The set of git-tracked paths under root. Untracked files are another
   agent's in-flight work in this workspace; renaming them is destructive and
   invisible to review, so --tracked-only exists and the wave uses it."
  [root]
  (let [out (.toString (cp/execSync "git ls-files -z -- '*.edn' '*.clj' '*.cljs' '*.cljc'"
                                    #js {:cwd root :maxBuffer 268435456}))]
    (set (remove empty? (str/split out #"\u0000")))))

(def dirty-paths (delay (dirty-set (js/process.cwd))))

(defn- ns-of
  "The namespace a source file declares, or nil."
  [txt]
  (try
    (let [forms (r/forms (r/read-cst txt :source))]
      (some (fn [n]
              (when (and (= :coll (:t n)) (= :list (:kind n)))
                (let [fs (r/forms (:children n))]
                  (when (and (= "ns" (some-> (first fs) :v str))
                             (= :atom (:t (second fs))))
                    (str (:v (second fs)))))))
            forms))
    (catch :default _ nil)))

(def ^:private consumer-skip
  "Directories the consumer index does not walk by default. `orgs` is the west
   checkout of thousands of child repos; walking it per run is not feasible.
   It is REPORTED rather than skipped quietly -- a consumer scan that silently
   covered less than you thought is the same shape as the rename that started
   all this."
  (conj skip-dirs "orgs"))

(defn- code-index
  "Every Clojure-runtime source file under root, read once.

   Built once per run rather than per candidate: the guard asks the same
   question of the same corpus for every file, and walking the tree per file
   turned a superproject run into minutes."
  [root]
  (let [out (atom [])]
    ((fn walk [d]
       (doseq [e (fs/readdirSync d #js {:withFileTypes true})]
         (let [n (.-name e) pth (path/join d n)]
           (cond
             (.isDirectory e) (when-not (contains? consumer-skip n) (walk pth))
             (source-path? n)
             (swap! out conj [pth (try (fs/readFileSync pth "utf8") (catch :default _ ""))])))))
     root)
    @out))

(def code-corpus (delay (code-index (js/process.cwd))))

(def ^:private reference-ext
  [".edn" ".json" ".yml" ".yaml" ".toml" ".plist" ".sh" ".md" ".mjs" ".cjs" ".js"])

(defn- reference-index
  "Files that could name a source file BY PATH rather than require it as a
   namespace: gate tables, plists, package scripts, runbooks."
  [root]
  (let [out (atom [])]
    ((fn walk [d]
       (doseq [e (fs/readdirSync d #js {:withFileTypes true})]
         (let [n (.-name e) pth (path/join d n)]
           (cond
             (.isDirectory e) (when-not (contains? consumer-skip n) (walk pth))
             (some #(str/ends-with? n %) reference-ext)
             (swap! out conj [pth (try (fs/readFileSync pth "utf8") (catch :default _ ""))])))))
     root)
    @out))

(def reference-corpus (delay (reference-index (js/process.cwd))))

(defn- index-by
  "Inverts a corpus into token -> the files naming it.

   The direct form -- for each candidate, scan every file -- is
   O(candidates x corpus) and took minutes on this superproject. Each corpus is
   scanned once here instead, and the guard becomes a lookup."
  [corpus re]
  (let [m (atom {})]
    (doseq [[pth txt] corpus]
      ;; re-seq yields a STRING when the pattern has no capture group and a
      ;; vector when it has one. `first` on the string form silently yields a
      ;; character, every lookup misses, and the guard reports everything as
      ;; safe -- which is how this returned WOULD-CONVERT 74 for files it had
      ;; just refused.
      (doseq [tok (set (map #(if (string? %) % (first %)) (re-seq re txt)))]
        (swap! m update tok (fnil conj []) pth)))
    @m))

(def filename-index
  (delay (index-by @reference-corpus #"[A-Za-z0-9_.-]+\.clj[sc]?")))

(defn- dotted-prefixes
  "a.b.c -> #{a.b.c a.b}. The substring scan this index replaced matched a
   namespace inside a longer one -- looking for `gftd.score` found it in
   `gftd.score.core` -- and a token index does not. Measured 2026-09-10: that
   difference alone moved 13 files from refused to convertible, which is the
   wrong direction for a guard to drift."
  [tok]
  (let [parts (str/split tok #"\.")]
    (set (for [n (range 2 (inc (count parts)))]
           (str/join "." (take n parts))))))

(def ns-index
  (delay (let [raw (index-by @code-corpus #"[a-z][a-zA-Z0-9.*+!_?<>=-]*\.[a-zA-Z0-9.*+!_?<>=-]+")
               m (atom {})]
           (doseq [[tok files] raw
                   pre (dotted-prefixes tok)]
             (swap! m update pre (fnil into []) files))
           (into {} (map (fn [[k v]] [k (vec (distinct v))]) @m)))))

(defn- path-invokers
  "Files naming this source file by its filename.

   A namespace guard is not enough. A fleet gate is never required as a
   namespace -- scripts/fleet-ci/tick.cljs reads gates.edn and runs
   `gates/<file>.cljs` by path, under nbb, which cannot load .kotoba. Renaming
   one would leave gates.edn pointing at a file that no longer exists, and a
   rename does not fail. Measured 2026-09-10: 68 of the 75 gate scripts passed
   the namespace guard and would have been converted."
  [p]
  (let [base (path/basename p)
        self* (path/resolve p)]
    (vec (remove #(= (path/resolve %) self*) (get @filename-index base [])))))

(defn- clojure-consumers
  "Files still loaded by a Clojure runtime that name this namespace.

   Renaming a source file to .kotoba does not move its consumers, and the
   runtimes are not interchangeable: amu resolves .kotoba, nbb does not.
   Measured 2026-09-10 in this workspace -- kotoba-lang/datalog was renamed
   (commit d3c1caf, `Rename src to .kotoba`) while three nbb scripts still
   required datalog.core, and the datom query face has been dead since:
   `Could not find namespace: datalog.core`. Nothing reported it, because a
   rename does not fail."
  [ns-name self]
  (when ns-name
    (let [self* (path/resolve self)]
      (vec (remove #(= (path/resolve %) self*) (get @ns-index ns-name []))))))

(defn- annex-pointer? [txt] (str/starts-with? txt "/annex/objects"))

(defn- classify
  "Decides what can be done with one .edn path, and why. Never returns a
   generic 'skip' -- a skipped file and a converted file must be told apart in
   the output."
  [p]
  (let [base (path/basename p)]
    (cond
      (contains? tool-owned base)
      {:status :refused :reason :tool-owned-filename}

      (not (fs/existsSync p))
      {:status :refused :reason :absent-from-worktree}

      (contains? @dirty-paths (path/relative (js/process.cwd) (path/resolve p)))
      {:status :refused :reason :uncommitted-changes}

      (source-path? p)
      ;; A program, not a document. The data rewrite is meaning-preserving for
      ;; data and NOT for code: {:a 1} in source would become (map (:a 1)), an
      ;; application of `map`. 415 files in this tree contain a map literal
      ;; inside code. So source is RENAMED and never rewritten -- Kotoba source
      ;; is already Clojure-shaped, which is the whole reason the rename is the
      ;; conversion.
      (let [txt (fs/readFileSync p "utf8")]
        (cond
          (fs/existsSync (source-target p))
          {:status :refused :reason :target-exists}

          (nil? (try (r/read-cst txt :source) (catch :default _ nil)))
          {:status :refused :reason :unparseable-source}

          :else
          (let [consumers (clojure-consumers (ns-of txt) p)
                invokers (path-invokers p)]
            (cond
              (seq consumers)
              {:status :refused :reason :still-required-by-clojure-runtime
               :detail (str/join ", " (take 3 consumers))}
              (seq invokers)
              {:status :refused :reason :invoked-by-path
               :detail (str/join ", " (take 3 invokers))}
              :else {:status :ok :rename-only true}))))

      :else
      (let [txt (fs/readFileSync p "utf8")]
        (cond
          (annex-pointer? txt)
          {:status :refused :reason :git-annex-pointer}

          (fs/existsSync (str (subs p 0 (- (count p) 4)) ".kotoba"))
          {:status :refused :reason :target-exists}

          :else
          (let [adl (try (adl/edn->adl txt)
                         (catch :default e {::err (ex-message e)}))]
            (if (map? adl)
              {:status :refused :reason :unreadable :detail (::err adl)}
              ;; Verify BEFORE offering to write. An unverified conversion is
              ;; never written, so "converted" always means "round-tripped".
              (let [orig (try (r/read-cst txt) :ok (catch :default _ ::no))
                    back (try (adl/read-all adl) (catch :default e {::err (ex-message e)}))]
                (cond
                  (= orig ::no) {:status :refused :reason :unreadable}
                  (map? back) {:status :refused :reason :decode-failed :detail (::err back)}
                  :else {:status :ok :text adl})))))))))

(defn- target-path [p] (str (subs p 0 (- (count p) 4)) ".kotoba"))

(defn- filter-tracked [files tracked-only?]
  (if-not tracked-only?
    [files 0]
    (let [tracked (tracked-set (js/process.cwd))
          keep (vec (filter #(contains? tracked (path/relative (js/process.cwd) (path/resolve %))) files))]
      [keep (- (count files) (count keep))])))

(defn- run-convert [paths apply? tracked-only?]
  (let [all (reduce (fn [acc p] (walk-edn p acc)) [] paths)
        [files untracked] (filter-tracked all tracked-only?)
        tally (atom {:converted 0 :would-convert 0})
        refusals (atom {})]
    (doseq [p files]
      (let [{:keys [status reason text]} (classify p)]
        (if (= status :ok)
          (if apply?
            (do (if (source-path? p)
                  (fs/renameSync p (source-target p))
                  (do (fs/writeFileSync (target-path p) text)
                      (fs/unlinkSync p)))
                (swap! tally update :converted inc))
            (swap! tally update :would-convert inc))
          (swap! refusals update reason (fnil inc 0)))))
    (println (str "SCANNED\t" (count files)))
    (when (realized? code-corpus)
      (println (str "CONSUMER-SCAN\t" (count @code-corpus)
                    " Clojure-runtime files"
                    (when (realized? reference-corpus)
                      (str " + " (count @reference-corpus) " reference files"))
                    "; NOT walked: orgs/ (west children)")))
    (when (pos? untracked)
      (println (str "SKIPPED-UNTRACKED\t" untracked "\t(--tracked-only: not ours to rename)")))
    (println (str (if apply? "CONVERTED\t" "WOULD-CONVERT\t")
                  (if apply? (:converted @tally) (:would-convert @tally))))
    (doseq [[reason n] (sort-by (comp - val) @refusals)]
      (println (str "REFUSED\t" n "\t" (name reason))))
    (cond
      (zero? (count files))
      (do (println "Refusing to report a pass: scanned 0 files") 2)
      (seq @refusals) 1
      :else 0)))

(defn- run-verify [paths]
  (let [files (reduce (fn [acc p] (walk-edn p acc)) [] paths)
        ok (atom 0) refusals (atom {})]
    (doseq [p files]
      (let [{:keys [status reason]} (classify p)]
        (if (= status :ok) (swap! ok inc) (swap! refusals update reason (fnil inc 0)))))
    (println (str "SCANNED\t" (count files)))
    (println (str "ROUND-TRIPS\t" @ok))
    (doseq [[reason n] (sort-by (comp - val) @refusals)]
      (println (str "REFUSED\t" n "\t" (name reason))))
    (cond (zero? (count files)) (do (println "Refusing to report a pass: scanned 0 files") 2)
          (seq @refusals) 1
          :else 0)))

(defn -main [& args]
  (let [[cmd & rest*] args
        apply? (boolean (some #{"--apply"} rest*))
        paths (vec (remove #(str/starts-with? % "--") rest*))]
    (js/process.exit
     (case cmd
       "encode" (do (println (adl/edn->adl (fs/readFileSync (first paths) "utf8"))) 0)
       "decode" (do (println (pr-str (adl/read-string (fs/readFileSync (first paths) "utf8")))) 0)
       "verify" (run-verify paths)
       "convert" (run-convert paths apply? (boolean (some #{"--tracked-only"} rest*)))
       (do (println "usage: kotoba adl <encode|decode|verify|convert> <paths...> [--apply]") 2)))))

(apply -main *command-line-args*)
