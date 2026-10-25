(ns usd.usdc-bridge
  "Binary .usdc (and .usdz) support for usd.core (ADR-2607101525 M3), via
  the real Pixar oracle (tools/usd_oracle.py, `pip install usd-core`)
  rather than a from-scratch crate-format implementation — exactly what
  D1 always intended once a concrete need for binary showed up (\"バイナ
  リが必要な場面は、実オラクル … に変換を委譲すればよい … 自前でバイナリ
  パーサを書く必要はない\").

  JVM-only (`.clj`, not `.cljc`, like `usd.oracle-test`): shells out to
  Python via clojure.java.shell, which has no cljs equivalent. usd.core
  itself stays a portable, zero-dependency ASCII-text parser/emitter —
  this namespace is a thin, separate bridge on top of it, never required
  by usd.core or kotoba.usd.

  read-usdc/write-usdc round-trip through usd.core's own EDN prim-tree
  shape (`{:opts {...} :prims [...]}` / `(apply usda opts prims)`), so
  callers work with the same data shape regardless of whether the file on
  disk is ASCII or binary."
  (:require [clojure.java.io :as io]
            [clojure.java.shell :as shell]
            [usd.core :as usd]))

(defn- oracle-python []
  (or (System/getenv "USD_ORACLE_PYTHON") "python3"))

(defn- driver-path []
  (str (io/file "tools" "usd_oracle.py")))

(defn oracle-available?
  "True if `python3` (or $USD_ORACLE_PYTHON) has `pxr` importable. Not
  memoized (unlike usd.oracle-test's `delay`) since this is a public,
  occasionally-rechecked entry point, not a hot test-suite path."
  []
  (try
    (= 0 (:exit (shell/sh (oracle-python) "-c" "import pxr")))
    (catch Exception _ false)))

(defn- run-convert [in-path out-path]
  (let [{:keys [exit err]} (shell/sh (oracle-python) (driver-path) "convert" in-path out-path)]
    (when-not (zero? exit)
      (throw (ex-info (str "usd_oracle.py convert failed: " err)
                       {:in in-path :out out-path :exit exit :err err})))))

(defn- with-temp-file [suffix f]
  (let [tmp (java.io.File/createTempFile "usd-usdc-bridge-" suffix)]
    (try (f tmp) (finally (.delete tmp)))))

(defn read-usdc
  "Read a binary .usdc (or .usdz) file at `path` into the same
  `{:opts {...} :prims [...]}` shape `usd.core/parse` returns for ASCII
  text — via the oracle (Usd.Stage export to a temp .usda, then
  usd.core's own real parser on that text)."
  [path]
  (with-temp-file ".usda"
    (fn [tmp]
      (run-convert path (.getAbsolutePath tmp))
      (usd/parse (slurp tmp)))))

(defn write-usdc!
  "Write `opts`/`prims` (the same arguments `usd.core/usda` takes) to a
  binary .usdc file at `out-path`, via usd.core's own real emitter
  (to a temp .usda) followed by an oracle conversion to binary. `out-path`
  determines the binary sub-format (.usdc crate / .usdz package) the same
  way it would for `usdcat -o`."
  [opts prims out-path]
  (with-temp-file ".usda"
    (fn [tmp]
      (spit tmp (apply usd/usda opts prims))
      (run-convert (.getAbsolutePath tmp) out-path))))
