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

(def skip-dirs #{".git" "node_modules" ".nbb" ".cpcache" "target" ".shadow-cljs"
                 ".projection-cache" "dist" "build" ".datalad"})

(defn- walk-edn [root out]
  (let [st (try (fs/statSync root) (catch :default _ nil))]
    (cond
      (nil? st) out
      (.isFile st) (if (str/ends-with? root ".edn") (conj out root) out)
      (.isDirectory st)
      (if (contains? skip-dirs (path/basename root))
        out
        (reduce (fn [acc e] (walk-edn (path/join root e) acc))
                out
                (sort (fs/readdirSync root))))
      :else out)))

(defn- tracked-set
  "The set of git-tracked paths under root. Untracked files are another
   agent's in-flight work in this workspace; renaming them is destructive and
   invisible to review, so --tracked-only exists and the wave uses it."
  [root]
  (let [out (.toString (cp/execSync "git ls-files -z -- '*.edn'"
                                    #js {:cwd root :maxBuffer 268435456}))]
    (set (remove empty? (str/split out #"\u0000")))))

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
            (do (fs/writeFileSync (target-path p) text)
                (fs/unlinkSync p)
                (swap! tally update :converted inc))
            (swap! tally update :would-convert inc))
          (swap! refusals update reason (fnil inc 0)))))
    (println (str "SCANNED\t" (count files)))
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
