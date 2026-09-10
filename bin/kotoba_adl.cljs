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

(def ^:private project-files ["deps.edn" "nbb.edn" "bb.edn" "shadow-cljs.edn"])

;; The set of paths this pass is converting, as resolved absolutes.
;;
;; Both consumer guards below used to ask "does a consumer exist?" when the
;; question they are FOR is "will a Clojure consumer REMAIN?". Converting a
;; whole source root file-by-file, every file blocks every other: A requires B
;; so B is refused, and A is refused for its own requirer, so a tree that is
;; entirely self-consistent converts nothing. Measured 2026-09-10 across eight
;; real target repositories: 56 scanned, 0 convertible.
;;
;; Set-awareness does not weaken either guard. A consumer that is itself
;; converting in this pass is not a Clojure consumer afterwards, and a source
;; root that converts ENTIRELY leaves no Clojure namespace for a build to
;; resolve by extension. What still refuses -- and must -- is a PARTIAL
;; conversion of a source root, and any consumer outside the set.
(def ^:dynamic *convert-set* #{})

(defn- declared-source-paths
  "Source paths a Clojure project file declares, as absolute directories."
  [root]
  (->> project-files
       (mapcat (fn [pf]
                 (let [f (path/join root pf)]
                   (when (fs/existsSync f)
                     (let [txt (try (fs/readFileSync f "utf8") (catch :default _ ""))]
                       ;; :paths / :source-paths string vectors, read as text --
                       ;; enough to know which directories the build compiles.
                       (->> (re-seq #"\"([^\"]{1,120})\"" txt)
                            (map second)
                            (filter #(and (not (str/includes? % " "))
                                          (fs/existsSync (path/join root %))
                                          (.isDirectory (fs/statSync (path/join root %)))))))))))
       (map #(path/resolve root %))
       distinct
       vec))

(defn- walk-source
  "Every Clojure source file under DIR. Separate from walk-edn because the
   build guard asks about source only -- an .edn under the root is not resolved
   by extension from :paths."
  [root out]
  (let [st (try (fs/statSync root) (catch :default _ nil))]
    (cond
      (nil? st) out
      (.isFile st) (if (source-path? root) (conj out root) out)
      (.isDirectory st)
      (if (contains? skip-dirs (path/basename root))
        out
        (reduce (fn [acc e] (walk-source (path/join root e) acc))
                out (sort (fs/readdirSync root))))
      :else out)))

(defn- build-consumes?
  "True when a build config compiles this file BY EXTENSION.

   The third way a consumer names a file, and the one neither other guard sees.
   shadow-cljs compiles src/**/*.cljs; nbb and the clojure CLI resolve a
   namespace from :paths by extension. None of them names the file, so renaming
   it to .kotoba makes it invisible to the build and nothing reports an error --
   which is exactly how kotoba-lang/datalog took the datom query face down.

   This is why Q9 treats source migration as a whole-component build change and
   not a rename: the file cannot move until its BUILD moves."
  [p]
  (let [abs (path/resolve p)]
    (loop [d (path/dirname abs)]
      (cond
        (or (= d "/") (str/blank? d)) false
        (some #(fs/existsSync (path/join d %)) project-files)
        (let [owning (first (filter #(str/starts-with? abs (str % path/sep))
                                    (declared-source-paths d)))]
          (if (nil? owning)
            false
            ;; The hazard is a file going invisible to a build that still
            ;; expects it. If the WHOLE declared source root is converting,
            ;; no Clojure namespace remains under it for any runtime to
            ;; resolve by extension, and a consumer that still needs one is
            ;; caught by the external-consumer guard rather than this one.
            ;; A PARTIAL conversion is still refused, which is the case the
            ;; kotoba-lang/datalog incident actually was.
            (boolean (some (fn [f] (not (contains? *convert-set* (path/resolve f))))
                           (walk-source owning [])))))
        :else (recur (path/dirname d))))))

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

(def extra-code-roots (atom []))

(defn- scan-roots [] (cons (js/process.cwd) @extra-code-roots))

(def code-corpus
  (delay (vec (mapcat code-index (scan-roots)))))

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

(def reference-corpus
  (delay (vec (mapcat reference-index (scan-roots)))))

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
  ;; .edn belongs here too. Without it the index held only Clojure filenames,
  ;; so the name guard could never fire for a document -- and a guard that
  ;; cannot fire reports exactly what a guard with nothing to find reports.
  (delay (index-by @reference-corpus #"[A-Za-z0-9_.-]+\.(?:clj[sc]?|cljc|edn|kotoba)")))

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

(def needed-bare-names
  "Single-segment namespace names among the candidates of THIS run.

   A bare name cannot live in the dotted-token index, and scanning the corpus
   once per such candidate is what made a superproject run take ten minutes.
   Collecting the names first turns it back into one filtered pass."
  (atom #{}))

(def bare-index
  (delay
    (let [needed @needed-bare-names
          m (atom {})]
      (when (seq needed)
        (doseq [[pth txt] @code-corpus]
          (doseq [tok (set (map #(if (string? %) % (first %))
                                (re-seq #"[a-zA-Z][a-zA-Z0-9*+!_?<>=-]*" txt)))]
            (when (contains? needed tok)
              (swap! m update tok (fnil conj []) pth)))))
      @m)))

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
    (let [self* (path/resolve self)
          hits (if (str/includes? ns-name ".")
                 (get @ns-index ns-name [])
                 ;; A single-segment namespace -- (ns gate) -- has no dot, and
                 ;; the dotted-token index cannot hold it at all. Measured
                 ;; 2026-09-10: that absence alone left 13 files reported as
                 ;; convertible that the scan had refused. These are a minority,
                 ;; so they get the scan; the index carries the rest.
                 (get @bare-index ns-name []))]
      ;; A consumer inside this pass stops being a Clojure consumer when the
      ;; pass lands, so it is not evidence against converting this file.
      (vec (remove #(let [r (path/resolve %)]
                      (or (= r self*) (contains? *convert-set* r)))
                   hits)))))

(defn- code-outside-strings
  "TXT with string literals and line comments blanked out, so a scan for
   dispatch tags cannot be fooled by one quoted inside a docstring. Character
   literals are left alone deliberately -- \\\" is a character, not a string
   opener, and treating it as one silently swallows the rest of the file."
  [txt]
  (let [n (count txt)]
    (loop [i 0 out [] state :code]
      (if (>= i n)
        (apply str out)
        (let [c (nth txt i)
              c2 (when (< (inc i) n) (nth txt (inc i)))]
          (case state
            :code (cond
                    (and (= c \\) c2) (recur (+ i 2) (conj out \space \space) :code)
                    ;; A regex literal opens with #" and its body is scanned as
                    ;; a string. Measured 2026-09-10: without this arm the `"`
                    ;; was taken as an ordinary string opener and blanked, so
                    ;; the `#"` the scanner is looking for never survived into
                    ;; the sanitized text and every regex was ADMITTED. The
                    ;; marker is emitted so the body can still be blanked.
                    (and (= c \#) (= c2 \"))
                    (recur (+ i 2) (into out (seq "#REGEX")) :string)
                    (= c \") (recur (inc i) (conj out \space) :string)
                    (= c \;) (recur (inc i) (conj out \space) :comment)
                    :else (recur (inc i) (conj out c) :code))
            :string (cond
                      (and (= c \\) c2) (recur (+ i 2) (conj out \space \space) :string)
                      (= c \") (recur (inc i) (conj out \space) :code)
                      :else (recur (inc i) (conj out \space) :string))
            :comment (if (= c \newline)
                       (recur (inc i) (conj out c) :code)
                       (recur (inc i) (conj out \space) :comment))))))))

(def ^:private unsupported-dispatch
  "Dispatch forms amu's SOURCE reader refuses. Measured 2026-09-10 by bisecting
   real files down to the offending line, not by reading a grammar."
  [["#REGEX" :regex-literal] ["#js" :js-literal] ["#inst" :inst-literal]
   ["#uuid" :uuid-literal] ["#object" :object-literal]])

(defn- source-inadmissible
  "Why amu's source reader will refuse this file, or nil.

   The converter's own reader is NOT this check. Measured 2026-09-10:
   `kotoba.adl.reader/read-cst` ACCEPTS all four shapes below, so
   :unparseable-source never fires for them and the file is renamed into a
   state where `amu check` answers `source reader rejected input` -- with NO
   span in six of seven cases, which is an error a reader cannot act on.

   Refusing here is conservative: the cost of a false refusal is a file that
   did not move, and the cost of a false admission is a file that moved and
   stopped being readable. Those are not symmetric."
  [txt]
  (let [code (code-outside-strings txt)
        first-line (first (remove str/blank? (str/split-lines txt)))]
    (cond
      (str/starts-with? txt "#!")
      :executable-script
      (and first-line (str/starts-with? (str/trim first-line) "//"))
      :not-clojure-source
      :else
      (when-let [hit (first (filter (fn [[lit _]] (str/includes? code lit))
                                    unsupported-dispatch))]
        (second hit)))))

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

          ;; Our reader is more permissive than the compiler's. Refusing with
          ;; the specific construct beats renaming into a spanless failure.
          (some? (source-inadmissible txt))
          {:status :refused :reason (source-inadmissible txt)}

          (build-consumes? p)
          {:status :refused :reason :compiled-by-build-config}

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

          ;; A document is read by name too, and until now only SOURCE was
          ;; guarded against that. A child repo's README.edn is read by the
          ;; superproject (scripts/repo-search.cljs reads READMEs); converting
          ;; it would break that with nothing reporting an error -- the same
          ;; shape as every other failure this design is built around.
          (seq (path-invokers p))
          {:status :refused :reason :referenced-by-name
           :detail (str/join ", " (take 3 (path-invokers p)))}

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

(defn- collect-bare-names! [files]
  (reset! needed-bare-names
          (into #{}
                (keep (fn [p]
                        (when (and (source-path? p) (fs/existsSync p))
                          (let [n (ns-of (fs/readFileSync p "utf8"))]
                            (when (and n (not (str/includes? n "."))) n))))
                      files))))

(defn- run-convert [paths apply? tracked-only?]
  (let [all (reduce (fn [acc p] (walk-edn p acc)) [] paths)
        [files untracked] (filter-tracked all tracked-only?)
        _ (collect-bare-names! files)
        ;; Whether a file may convert depends on which OTHER files convert, so
        ;; the answer is a fixpoint rather than a single pass. Start optimistic
        ;; -- assume everything requested converts -- classify, drop whatever
        ;; was refused, and repeat. The set only ever shrinks, so this
        ;; terminates; the bound is belt-and-braces and is REPORTED rather than
        ;; hidden, because a run that stopped early is not the same answer as a
        ;; run that settled.
        ;; The reason a file is refused must be the reason it FIRST dropped out,
        ;; not the reason it fails once everything else has dropped too.
        ;; Measured 2026-09-10: without this, a file refused in iteration 1 for
        ;; its own reason was reported as `compiled-by-build-config`, because by
        ;; the final pass the converting set was empty and the build guard
        ;; refuses every file against an empty set. The cascade reason is true
        ;; and useless -- it points at the consequence, not the cause.
        first-reason (atom {})
        [settled iters converged?]
        (loop [s (set (map #(path/resolve %) files)) i 0]
          (let [ok (set (for [p files
                              :let [c (binding [*convert-set* s] (classify p))]
                              :when (do (when (and (not= :ok (:status c))
                                                   (not (contains? @first-reason (path/resolve p))))
                                          (swap! first-reason assoc (path/resolve p) (:reason c)))
                                        (= :ok (:status c)))]
                          (path/resolve p)))]
            (cond
              (= ok s) [ok i true]
              (>= i 8) [ok i false]
              :else (recur ok (inc i)))))
        tally (atom {:converted 0 :would-convert 0})
        refusals (atom {})]
    (when-not converged?
      (println "REFUSED\tfixpoint did not settle in 8 iterations -- not reporting a pass")
      (.exit js/process 2))
    (doseq [p files]
      (let [{:keys [status text]} (binding [*convert-set* settled] (classify p))
            reason (get @first-reason (path/resolve p))]
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
    (println (str "FIXPOINT\t" iters " iteration(s) to settle, " (count settled) " in the converting set"))
    (when (realized? code-corpus)
      (println (str "CONSUMER-SCAN\t" (count @code-corpus)
                    " Clojure-runtime files"
                    (when (realized? reference-corpus)
                      (str " + " (count @reference-corpus) " reference files"))
                    " across " (count (scan-roots)) " root(s)"
                    (when (empty? @extra-code-roots)
                      "; NOT walked: anything outside this repo (pass --code)")
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
        _ (collect-bare-names! files)
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
        code-roots (->> (map vector rest* (rest rest*))
                        (keep (fn [[a b]] (when (= a "--code") b)))
                        vec)
        flag-values (set code-roots)
        paths (vec (remove #(or (str/starts-with? % "--") (contains? flag-values %)) rest*))]
    (reset! extra-code-roots code-roots)
    (js/process.exit
     (case cmd
       "encode" (do (println (adl/edn->adl (fs/readFileSync (first paths) "utf8"))) 0)
       "decode" (do (println (pr-str (adl/read-string (fs/readFileSync (first paths) "utf8")))) 0)
       "verify" (run-verify paths)
       "convert" (run-convert paths apply? (boolean (some #{"--tracked-only"} rest*)))
       (do (println "usage: kotoba adl <encode|decode|verify|convert> <paths...> [--apply]") 2)))))

(apply -main *command-line-args*)
