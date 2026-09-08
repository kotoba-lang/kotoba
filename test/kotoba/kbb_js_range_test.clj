(ns kotoba.kbb-js-range-test
  "The RANGE form of wire 35 (:fs/app-data) on kbb --backend js
  (bin/kbb_js.cljs fs-read-range!), mirroring the native loader's
  fs_app_data_range_read_provider (amu, 2026-09-07): request
  \"<path>RANGE_SEP<offset>:<length>\" -> exactly that window of the file.

  Measured here on a 70,000-byte fixture (larger than one guest string, with
  U+2500 planted at byte 5000) through examples/kbb/probe_fs_range_via_env
  .kotoba, which writes the window it read back to disk so the BYTES are
  compared, not just the count: [0, 4096) and [66000, +4000) equal the
  fixture's slices; the receipt sequence is :read-range :ok then :write :ok.
  And through kbb.fs/read-range with i64 arguments, which builds the spec
  with kbb.fs/i64->text (the guest has no number->string builtin): the same
  window answers the same bytes, so the digits came out right.

  The refusals, each leaving the three marks kbb-js-providers-test defines
  (exit 1, :kbb-js/guest-failed naming :fs/app-data, a LAST receipt with
  :outcome :denied and :op :read-range): a window past EOF, a window that
  cuts the code point, a spec that is not <offset>:<length>, a length over
  the guest string limit, a second RANGE_SEP, and a path outside the scope.
  The whole-file read of the same fixture is still refused (that refusal is
  the reason the range form exists).

  Needs `nbb` on PATH and an amu checkout with node_modules (AMU_HOME, or the
  deps.edn pin under ~/.gitlibs); otherwise SKIPPED, and it says so."
  (:require [clojure.edn :as edn]
            [clojure.java.io :as io]
            [clojure.java.shell :as shell]
            [kotoba.lang.text :as str]
            [clojure.test :refer [deftest is testing]])
  (:import [java.nio.file Files]
           [java.nio.file.attribute FileAttribute]
           [java.nio.charset StandardCharsets]))

(def ^:private home (System/getProperty "user.dir"))

(defn- nbb-available? []
  (try (zero? (:exit (shell/sh "nbb" "--version"))) (catch Exception _ false)))

(defn- amu-available? []
  (let [amu-home (or (System/getenv "AMU_HOME")
                     (let [sha (second (re-find #"kotoba-lang/amu\s*\{[^}]*:git/sha\s+\"([0-9a-f]{40})\""
                                                (slurp (io/file home "deps.edn"))))]
                       (when sha (str (System/getProperty "user.home") "/.gitlibs/libs/io.github.kotoba-lang/amu/" sha))))]
    (and amu-home (.exists (io/file amu-home "node_modules" "nbb" "cli.js")))))

(def ^:private ready? (delay (and (nbb-available?) (amu-available?))))

(defmacro when-ready [& body]
  `(if @ready?
     (do ~@body)
     (println "SKIPPED kotoba.kbb-js-range-test: nbb or an amu checkout with node_modules is not available (set AMU_HOME)")))

(defn- kbb-js [extra-env & argv]
  (let [env (-> (into {} (System/getenv)) (merge extra-env) (assoc "KBB_HOME" home))
        {:keys [exit out err]} (apply shell/sh "nbb" "bin/kbb_js.cljs" (concat argv [:env env]))
        receipt (try (edn/read-string (last (remove str/blank? (str/split-lines out))))
                     (catch Exception _ nil))]
    (when-not (map? receipt)
      (throw (ex-info "kbb_js printed no receipt" {:exit exit :out out :err err})))
    (assoc receipt :exit exit)))

(defn- receipts
  "The :fs/app-data receipts of a run; the probe's three :env/read receipts
  precede them and are not what these tests measure."
  [r]
  (filterv #(= :fs/app-data (:capability %)) (get-in r [:kotoba.cli/data :kotoba.kbb/receipts])))

(defn- refused! [r]
  (is (not (:kotoba.cli/ok? r)) (pr-str r))
  (is (= 1 (:exit r)))
  (is (= :kbb-js/guest-failed (:kotoba.cli/code r)))
  (is (= :fs/app-data (get-in r [:kotoba.cli/data :kotoba.kbb/capability])) (pr-str r))
  (let [last-receipt (last (receipts r))]
    (is (= :denied (:outcome last-receipt)) (pr-str (receipts r)))
    last-receipt))

(defn- temp-dir [] (str (Files/createTempDirectory "kbb-js-range" (make-array FileAttribute 0))))

(defn- delete-tree! [dir]
  (doseq [^java.io.File f (reverse (file-seq (io/file dir)))] (.delete f)))

(defn- fixture-bytes
  "70,000 bytes: 5,000 ASCII, U+2500 (3 bytes), then ASCII to the end."
  []
  (let [pattern "0123456789abcdef\n"
        ascii (fn [n] (subs (apply str (repeat (inc (quot n (count pattern))) pattern)) 0 n))]
    (.getBytes (str (ascii 5000) "─" (ascii (- 70000 5003))) StandardCharsets/UTF_8)))

(defn- write-policy! [dir scope]
  (let [f (io/file dir "policy.edn")]
    (spit f (pr-str {:kotoba.policy/capabilities #{:env/read :fs/app-data}
                     :kotoba.policy/forbid-wildcard true
                     :kotoba.policy/capability-resources
                     {:env/read #{"KBB_PROBE_FILE" "KBB_PROBE_SPEC" "KBB_PROBE_OUT"}
                      :fs/app-data #{scope}}}))
    (.getPath f)))

(deftest range-read-answers-exact-windows
  (when-ready
   (let [tmp (temp-dir)
         bytes (fixture-bytes)
         big (io/file tmp "big.txt")
         out (io/file tmp "out.bin")
         policy (write-policy! tmp tmp)
         run (fn [spec] (kbb-js {"KBB_PROBE_FILE" (.getPath big) "KBB_PROBE_SPEC" spec "KBB_PROBE_OUT" (.getPath out)}
                                "examples/kbb/probe_fs_range_via_env.kotoba" "--policy" policy "--source-path" "lib"))
         slice (fn [off len] (java.util.Arrays/copyOfRange ^bytes bytes (int off) (int (+ off len))))]
     (try
       (io/copy bytes big)
       (is (= 70000 (alength bytes)))
       (testing "[0, 4096): the bytes on disk are the fixture's first 4096 bytes"
         (let [r (run "0:4096")]
           (is (:kotoba.cli/ok? r) (pr-str r))
           (is (= 4096 (get-in r [:kotoba.cli/data :kotoba.kbb/result])))
           (is (= [:read-range :write] (mapv :op (receipts r))) (pr-str (receipts r)))
           (is (= {:capability :fs/app-data :op :read-range :request (.getPath big) :offset 0 :length 4096 :outcome :ok :bytes 4096}
                  (first (receipts r))))
           (is (java.util.Arrays/equals ^bytes (slice 0 4096) ^bytes (Files/readAllBytes (.toPath out))))))
       (testing "[66000, +4000): a tail window, byte-exact"
         (let [r (run "66000:4000")]
           (is (:kotoba.cli/ok? r) (pr-str r))
           (is (= 4000 (get-in r [:kotoba.cli/data :kotoba.kbb/result])))
           (is (java.util.Arrays/equals ^bytes (slice 66000 4000) ^bytes (Files/readAllBytes (.toPath out))))))
       (testing "[4990, +20) straddles the code point on both sides and is fine"
         (let [r (run "4990:20")]
           (is (:kotoba.cli/ok? r) (pr-str r))
           (is (java.util.Arrays/equals ^bytes (slice 4990 20) ^bytes (Files/readAllBytes (.toPath out))))))
       (testing "kbb.fs/read-range with i64 arguments builds the same spec through i64->text"
         (let [script (io/file tmp "range_i64.kotoba")
                 pol (io/file tmp "range_i64_policy.edn")]
           (spit script (str "(ns probe.range-i64 (:require [kbb.fs :as fs]) (:export [main]))\n"
                             "(defn main [] :i64 (fs/write-bytes-count \"" (.getPath out) "\" (fs/read-range \"" (.getPath big) "\" 66000 4000)))\n"))
           (spit pol (pr-str {:kotoba.policy/capabilities #{:fs/app-data} :kotoba.policy/forbid-wildcard true
                              :kotoba.policy/capability-resources {:fs/app-data #{tmp}}}))
           (.delete out)
           (let [r (kbb-js {} (.getPath script) "--policy" (.getPath pol) "--source-path" "lib")]
             (is (:kotoba.cli/ok? r) (pr-str r))
             (is (= 4000 (get-in r [:kotoba.cli/data :kotoba.kbb/result])))
             (is (= {:offset 66000 :length 4000} (select-keys (first (receipts r)) [:offset :length])) (pr-str (receipts r)))
             (is (java.util.Arrays/equals ^bytes (slice 66000 4000) ^bytes (Files/readAllBytes (.toPath out)))))))
       (finally (delete-tree! tmp))))))

(deftest range-read-refuses-by-name
  (when-ready
   (let [tmp (temp-dir)
         outside (temp-dir)
         bytes (fixture-bytes)
         big (io/file tmp "big.txt")
         out (io/file tmp "out.bin")
         policy (write-policy! tmp tmp)
         run (fn [file spec] (kbb-js {"KBB_PROBE_FILE" file "KBB_PROBE_SPEC" spec "KBB_PROBE_OUT" (.getPath out)}
                                     "examples/kbb/probe_fs_range_via_env.kotoba" "--policy" policy "--source-path" "lib"))
         denied (fn [r] (get-in r [:kotoba.cli/data :kotoba.kbb/denied]))]
     (try
       (io/copy bytes big)
       (io/copy bytes (io/file outside "big.txt"))
       (testing "a window past EOF is refused, not shortened"
         (let [r (run (.getPath big) "69500:1000")]
           (is (= {:offset 69500 :length 1000 :bytes 70000} (select-keys (refused! r) [:offset :length :bytes])))
           (is (= "range [69500, 70500) lies outside the file (70000 bytes)" (denied r)))))
       (testing "a window that cuts U+2500 is refused"
         (let [r (run (.getPath big) "5001:4")]
           (is (= :read-range (:op (refused! r))))
           (is (= "range does not fall on UTF-8 code-point boundaries" (denied r)))))
       (testing "a spec that is not <offset>:<length> is refused"
         (let [r (run (.getPath big) "abc")]
           (refused! r)
           (is (= "range spec must be <offset>:<length> in decimal" (denied r)))))
       (testing "a length over the guest string limit is refused before any read"
         (let [r (run (.getPath big) "0:70000")]
           (is (= {:length 70000 :limit 65536} (select-keys (refused! r) [:length :limit])))
           (is (= "range length exceeds the guest string limit" (denied r)))))
       (testing "a second RANGE_SEP in the request is refused"
         (let [r (run (.getPath big) "0:4RANGE_SEP")]
           (refused! r)
           (is (= "request contains the RANGE_SEP token twice" (denied r)))))
       (testing "a path outside the :fs/app-data scope is refused"
         (let [r (run (.getPath (io/file outside "big.txt")) "0:16")]
           (refused! r)
           (is (= "path outside the granted :fs/app-data scope" (denied r)))))
       (testing "the whole-file read of the fixture is still refused (why the range form exists)"
         (let [script (io/file tmp "whole.kotoba")
               pol (io/file tmp "whole_policy.edn")]
           (spit script (str "(ns probe.whole (:require [kbb.fs :as fs]) (:export [main]))\n"
                             "(defn main [] :i64 (fs/read-bytes-count \"" (.getPath big) "\"))\n"))
           (spit pol (pr-str {:kotoba.policy/capabilities #{:fs/app-data} :kotoba.policy/forbid-wildcard true
                              :kotoba.policy/capability-resources {:fs/app-data #{tmp}}}))
           (let [r (kbb-js {} (.getPath script) "--policy" (.getPath pol) "--source-path" "lib")]
             (is (= "file exceeds the guest string limit (70000 > 65536 bytes)" (denied r))))))
       (finally (delete-tree! tmp) (delete-tree! outside))))))
