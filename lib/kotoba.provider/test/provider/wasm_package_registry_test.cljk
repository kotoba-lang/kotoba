(ns provider.wasm-package-registry-test
  "Every row of wasm-packages-v1.edn, not the eight the other suites name.

  The registry is what `verify-wasm-package-digest`, `grant-binding` and
  `production-claim-blockers` read: a row's `:sha256` is the content address a
  grant is bound to. Before this namespace only the 8 pure-allowlist rows were
  checked against their bytes (`kit-package-test/pure-allowlist-real-wasm`);
  the other 134 -- including all 112 compiler-AOT rows -- could claim a digest
  no test compared to anything.

  What this does NOT check: that the shipped `.wasm` is what the declared
  `:source-kotoba` compiles to. That needs the compiler and a recorded builder
  commit, and the registry records neither -- `:builder :kotoba-compiler/v1`
  names a tool, not a version. Measured 2026-08-12 against the fleet's compiler
  pin 806f5ce: of the 71 `:wasm-module` rows with a declared source, 35
  reproduce byte-identically, 29 differ, and 7 no longer compile. So the
  source-to-artifact direction stays unguarded here on purpose rather than by
  omission."
  (:require [clojure.java.io :as io]
            [kotoba.lang.text :as str]
            [clojure.test :refer [deftest is]]
            [provider.kit-package :as kit]))

(def ^:private packages (:packages (kit/load-wasm-packages-table)))

(deftest registry-is-not-empty
  (is (<= 142 (count packages))
      "row count only grows; a shrunk registry means rows were dropped"))

(deftest every-row-digest-matches-its-bytes
  (doseq [entry packages]
    (let [bytes (kit/load-wasm-package-bytes (:resource entry))]
      (is (kit/verify-wasm-package-digest entry bytes)
          (str (:name entry) " :sha256 does not match " (:resource entry)))
      (is (= [0x00 0x61 0x73 0x6d]
             (mapv #(bit-and % 0xff) (take 4 bytes)))
          (str (:name entry) " is not a wasm binary")))))

(deftest every-declared-source-kotoba-exists
  (let [declared (filter #(get-in % [:source :source-kotoba]) packages)]
    (is (<= 112 (count declared))
        "rows declaring a kotoba source only grow")
    (doseq [entry declared]
      (let [path (get-in entry [:source :source-kotoba])]
        ;; Registry paths are repo-relative; the classpath root is the repo root
        ;; for `resources/`, so strip that prefix to reach the same file.
        (is (some? (io/resource (str/replace path #"^resources/" "")))
            (str (:name entry) " declares a missing source: " path))))))

(deftest compiler-built-rows-declare-a-source
  ;; A row that names the compiler as its builder but no source is a claim with
  ;; nothing behind it -- there is no file to point at when asked what it is.
  (doseq [entry packages]
    (when (= :kotoba-compiler/v1 (get-in entry [:source :builder]))
      (is (some? (get-in entry [:source :source-kotoba]))
          (str (:name entry) " is compiler-built with no :source-kotoba")))))
