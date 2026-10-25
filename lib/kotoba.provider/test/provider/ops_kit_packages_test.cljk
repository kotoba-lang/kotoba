(ns provider.ops-kit-packages-test
  "W6 ops kit packages: EDN surface + honest qualification claims."
  (:require [clojure.edn :as edn]
            [clojure.java.io :as io]
            [kotoba.lang.text :as str]
            [clojure.test :refer [deftest is testing]]))

(def ops-kits
  [{:name :secret :resource "kotoba/lang/capability-kits/secret-v1.edn" :id 21}
   {:name :process :resource "kotoba/lang/capability-kits/process-v1.edn" :id 20}
   {:name :scoped-fs :resource "kotoba/lang/capability-kits/scoped-fs-v1.edn" :id 19}
   {:name :git :resource "kotoba/lang/capability-kits/git-v1.edn" :id 22}
   {:name :entropy :resource "kotoba/lang/capability-kits/entropy-v1.edn" :id 23}])

(defn- load-kit [resource]
  (edn/read-string (slurp (io/resource resource))))

(deftest ops-kit-packages-load
  (doseq [{:keys [name resource id]} ops-kits]
    (testing (str name)
      (let [kit (load-kit resource)
            q (:qualification kit)
            cap (:capability kit)]
        (is (= name (:kotoba.capability-kit/name kit)))
        (is (= 1 (:kotoba.capability-kit/version kit)))
        (is (= id (:id cap)))
        (is (= :implemented (:reference q)))
        ;; Component pilots (secret 0166, entropy 0167): wasm-aot partial + signed ready.
        (let [component-pilot? (contains? #{:secret :entropy :process :scoped-fs :git} name)]
          (is (contains? (if component-pilot? #{:partial} #{:pending})
                         (:wasm-aot q))
              (str name " wasm-aot honesty"))
          (is (contains? (if component-pilot? #{:ready} #{:pending})
                         (:signed-content-addressed-package q))
              (str name " signed package honesty")))
        (is (some? (:request kit)))
        (is (some? (:result kit)))))))
(deftest provider-conformance-lists-ops-kits
  (let [conf (edn/read-string
              (slurp (io/resource "kotoba/lang/provider-conformance-v1.edn")))
        names (set (map :name (:kits conf)))]
    (is (contains? names :http) "pre-existing network kit")
    (doseq [n [:secret :process :scoped-fs :git :entropy]]
      (is (contains? names n) (str "ops kit registered: " n)))))

(deftest http-kit-still-honest-about-aot
  (let [http (load-kit "kotoba/lang/capability-kits/http-v1.edn")]
    (is (= :implemented (get-in http [:qualification :reference])))
    ;; ADR 0162/0165: Component enables signed package ready; wasm-aot stays partial
    ;; (thin host re-export, not compiler-AOT kit body).
    (is (= :partial (get-in http [:qualification :wasm-aot]))
        "ops Component pilot may mark wasm-aot partial (not full compiler AOT)")
    (is (= :ready (get-in http [:qualification :signed-content-addressed-package]))
        "ADR 0165 content-addressed Component package path ready")))

(deftest secret-kit-still-honest-about-aot
  (let [secret (load-kit "kotoba/lang/capability-kits/secret-v1.edn")]
    (is (= :implemented (get-in secret [:qualification :reference])))
    ;; ADR 0163/0166: Component enables signed package ready; wasm-aot stays partial
    ;; (embedded name policy, not compiler-AOT kit body / host fetch).
    (is (= :partial (get-in secret [:qualification :wasm-aot]))
        "ops Component pilot may mark wasm-aot partial (not full compiler AOT)")
    (is (= :ready (get-in secret [:qualification :signed-content-addressed-package]))
        "ADR 0166 content-addressed Component package path ready")))

(deftest entropy-kit-still-honest-about-aot
  (let [entropy (load-kit "kotoba/lang/capability-kits/entropy-v1.edn")]
    (is (= :implemented (get-in entropy [:qualification :reference])))
    (is (= :partial (get-in entropy [:qualification :wasm-aot]))
        "ADR 0167 draw-size Component: wasm-aot partial (host CSPRNG remains authority)")
    (is (= :ready (get-in entropy [:qualification :signed-content-addressed-package]))
        "ADR 0167 content-addressed Component package path ready")))

(deftest process-kit-still-honest-about-aot
  (let [process (load-kit "kotoba/lang/capability-kits/process-v1.edn")]
    (is (= :implemented (get-in process [:qualification :reference])))
    (is (= :partial (get-in process [:qualification :wasm-aot]))
        "ops Component pilot may mark wasm-aot partial (not full compiler AOT)")
    (is (= :ready (get-in process [:qualification :signed-content-addressed-package]))
        "ADR 0168 content-addressed Component package path ready")))

(deftest scoped-fs-kit-still-honest-about-aot
  (let [fs (load-kit "kotoba/lang/capability-kits/scoped-fs-v1.edn")]
    (is (= :implemented (get-in fs [:qualification :reference])))
    (is (= :partial (get-in fs [:qualification :wasm-aot])))
    (is (= :ready (get-in fs [:qualification :signed-content-addressed-package])))))

(deftest git-kit-still-honest-about-aot
  (let [git (load-kit "kotoba/lang/capability-kits/git-v1.edn")]
    (is (= :implemented (get-in git [:qualification :reference])))
    (is (= :partial (get-in git [:qualification :wasm-aot]))
        "ops Component pilot may mark wasm-aot partial (not full compiler AOT)")
    (is (= :ready (get-in git [:qualification :signed-content-addressed-package]))
        "ADR 0170 content-addressed Component package path ready")))

(deftest http-compiler-aot-bounds-package-registered
  (let [table (edn/read-string
               (slurp (io/resource "kotoba/lang/wasm-packages/wasm-packages-v1.edn")))
        by-name (into {} (map (juxt :name identity) (:packages table)))
        mod (get by-name :http-post-bounds)
        comp (get by-name :http-post-bounds-component)
        mod-bytes (-> (io/resource (:resource mod))
                      io/input-stream
                      .readAllBytes)
        comp-bytes (-> (io/resource (:resource comp))
                       io/input-stream
                       .readAllBytes)
        sha (fn [^bytes b]
              (let [md (java.security.MessageDigest/getInstance "SHA-256")]
                (.update md b)
                (apply str (map #(format "%02x" %) (.digest md)))))]
    (is (= :wasm-module (:artifact-kind mod)))
    (is (= :wasm-component (:artifact-kind comp)))
    (is (false? (:fixture? mod)))
    (is (false? (:fixture? comp)))
    (is (= :ops-network (:class mod)))
    (is (= :kotoba-compiler/v1 (get-in mod [:source :builder])))
    (is (= :kotoba-compiler/v1 (get-in comp [:source :builder])))
    (is (= (:sha256 mod) (sha mod-bytes)))
    (is (= (:sha256 comp) (sha comp-bytes)))
    (is (contains? (:exports mod) "http_post_bounds_ok"))
    ;; source.kotoba present on classpath
    (is (some? (io/resource "kotoba/lang/wasm-packages/src/http_post_bounds.kotoba")))))

(deftest http-compiler-aot-bounds-live-behavior
  (let [bytes (-> (io/resource "kotoba/lang/wasm-packages/http-post-bounds-v1.wasm")
                  io/input-stream
                  .readAllBytes)
        ;; Chicory if available, else skip with note — use java wasm via process node
        ]
    ;; Prefer Node WebAssembly for zero extra deps (matches pure i64 ABI).
    (let [tmp (java.io.File/createTempFile "http-bounds" ".wasm")
          _ (java.nio.file.Files/write (.toPath tmp) bytes
                                       (into-array java.nio.file.OpenOption []))
          script (str "const b=require('fs').readFileSync(" (pr-str (.getAbsolutePath tmp)) ");"
                      "WebAssembly.instantiate(b).then(({instance})=>{"
                      "const f=instance.exports.http_post_bounds_ok;"
                      "const out=["
                      "Number(f(100n,1n,10n,1000n)),"
                      "Number(f(0n,1n,10n,1000n)),"
                      "Number(f(5000n,1n,10n,1000n)),"
                      "Number(f(100n,40n,10n,1000n)),"
                      "Number(f(100n,1n,70000n,1000n)),"
                      "Number(f(100n,1n,10n,0n)),"
                      "Number(f(100n,1n,10n,40000n))"
                      "];"
                      "console.log(JSON.stringify(out));"
                      "}).catch(e=>{console.error(e); process.exit(1);});")
          pb (ProcessBuilder. ["node" "-e" script])
          p (.start pb)
          out (slurp (.getInputStream p))
          err (slurp (.getErrorStream p))
          code (.waitFor p)]
      (.delete tmp)
      (is (zero? code) (str "node failed: " err out))
      (is (= [0 -1 -1 -2 -3 -4 -4] (edn/read-string out))))))

(deftest compiler-aot-numeric-bounds-packages-registered
  "ADR 0172: process/entropy/git compiler-AOT pure bounds packages."
  (let [table (edn/read-string
               (slurp (io/resource "kotoba/lang/wasm-packages/wasm-packages-v1.edn")))
        by-name (into {} (map (juxt :name identity) (:packages table)))
        sha (fn [^bytes b]
              (let [md (java.security.MessageDigest/getInstance "SHA-256")]
                (.update md b)
                (apply str (map #(format "%02x" %) (.digest md)))))
        check (fn [mod-name comp-name export]
                (let [mod (get by-name mod-name)
                      comp (get by-name comp-name)
                      mod-bytes (-> (io/resource (:resource mod)) io/input-stream .readAllBytes)
                      comp-bytes (-> (io/resource (:resource comp)) io/input-stream .readAllBytes)]
                  (is (= :wasm-module (:artifact-kind mod)))
                  (is (= :wasm-component (:artifact-kind comp)))
                  (is (false? (:fixture? mod)))
                  (is (= :kotoba-compiler/v1 (get-in mod [:source :builder])))
                  (is (= (:sha256 mod) (sha mod-bytes)))
                  (is (= (:sha256 comp) (sha comp-bytes)))
                  (is (contains? (:exports mod) export))))]
    (check :process-spawn-bounds :process-spawn-bounds-component "process_spawn_bounds_ok")
    (check :entropy-draw-bounds :entropy-draw-bounds-component "entropy_draw_ok")
    (check :git-run-bounds :git-run-bounds-component "git_run_bounds_ok")
    (is (some? (io/resource "kotoba/lang/wasm-packages/src/process_spawn_bounds.kotoba")))
    (is (some? (io/resource "kotoba/lang/wasm-packages/src/entropy_draw_bounds.kotoba")))
    (is (some? (io/resource "kotoba/lang/wasm-packages/src/git_run_bounds.kotoba")))))

(deftest compiler-aot-numeric-bounds-live-behavior
  (let [run (fn [resource export cases]
              (let [bytes (-> (io/resource resource) io/input-stream .readAllBytes)
                    tmp (java.io.File/createTempFile "bounds" ".wasm")
                    _ (java.nio.file.Files/write (.toPath tmp) bytes
                                                 (into-array java.nio.file.OpenOption []))
                    args-js (str/join ","
                              (map (fn [args]
                                     (str "Number(f("
                                          (str/join "," (map #(str % "n") args))
                                          "))"))
                                   cases))
                    script (str "const b=require('fs').readFileSync(" (pr-str (.getAbsolutePath tmp)) ");"
                                "WebAssembly.instantiate(b).then(({instance})=>{"
                                "const f=instance.exports." export ";"
                                "console.log(JSON.stringify([" args-js "]));"
                                "}).catch(e=>{console.error(e); process.exit(1);});")
                    pb (ProcessBuilder. ["node" "-e" script])
                    p (.start pb)
                    out (slurp (.getInputStream p))
                    err (slurp (.getErrorStream p))
                    code (.waitFor p)]
                (.delete tmp)
                (is (zero? code) (str resource " node failed: " err out))
                (edn/read-string out)))]
    (is (= [0 -1 -2 -3 -3 -4 -4]
           (run "kotoba/lang/wasm-packages/process-spawn-bounds-v1.wasm"
                "process_spawn_bounds_ok"
                [[1 100 1000] [0 100 1000] [40 100 1000]
                 [1 0 1000] [1 70000 1000] [1 100 0] [1 100 700000]])))
    (is (= [0 0 0 -1 -1 -1]
           (run "kotoba/lang/wasm-packages/entropy-draw-bounds-v1.wasm"
                "entropy_draw_ok"
                [[1] [32] [64] [0] [65] [-1]])))
    (is (= [0 -1 -2 -3 -3 -4 -4]
           (run "kotoba/lang/wasm-packages/git-run-bounds-v1.wasm"
                "git_run_bounds_ok"
                [[1 100 1000] [0 100 1000] [80 100 1000]
                 [1 0 1000] [1 70000 1000] [1 100 0] [1 100 700000]])))))

(deftest secret-compiler-aot-name-len-package-registered
  (let [table (edn/read-string
               (slurp (io/resource "kotoba/lang/wasm-packages/wasm-packages-v1.edn")))
        by-name (into {} (map (juxt :name identity) (:packages table)))
        mod (get by-name :secret-name-len)
        comp (get by-name :secret-name-len-component)
        mod-bytes (-> (io/resource (:resource mod)) io/input-stream .readAllBytes)
        comp-bytes (-> (io/resource (:resource comp)) io/input-stream .readAllBytes)
        sha (fn [^bytes b]
              (let [md (java.security.MessageDigest/getInstance "SHA-256")]
                (.update md b)
                (apply str (map #(format "%02x" %) (.digest md)))))]
    (is (= :wasm-module (:artifact-kind mod)))
    (is (= :wasm-component (:artifact-kind comp)))
    (is (false? (:fixture? mod)))
    (is (= :ops-network (:class mod)))
    (is (= :kotoba-compiler/v1 (get-in mod [:source :builder])))
    (is (= (:sha256 mod) (sha mod-bytes)))
    (is (= (:sha256 comp) (sha comp-bytes)))
    (is (contains? (:exports mod) "secret_name_len_ok"))
    (is (some? (io/resource "kotoba/lang/wasm-packages/src/secret_name_len.kotoba")))))

(deftest secret-compiler-aot-name-len-live-behavior
  (let [bytes (-> (io/resource "kotoba/lang/wasm-packages/secret-name-len-v1.wasm")
                  io/input-stream .readAllBytes)
        tmp (java.io.File/createTempFile "secret-len" ".wasm")
        _ (java.nio.file.Files/write (.toPath tmp) bytes
                                     (into-array java.nio.file.OpenOption []))
        script (str "const b=require('fs').readFileSync(" (pr-str (.getAbsolutePath tmp)) ");"
                    "WebAssembly.instantiate(b).then(({instance})=>{"
                    "const f=instance.exports.secret_name_len_ok;"
                    "const out=[Number(f(0n)),Number(f(1n)),Number(f(128n)),Number(f(129n))];"
                    "console.log(JSON.stringify(out));"
                    "}).catch(e=>{console.error(e); process.exit(1);});")
        p (.start (ProcessBuilder. ["node" "-e" script]))
        out (slurp (.getInputStream p))
        err (slurp (.getErrorStream p))
        code (.waitFor p)]
    (.delete tmp)
    (is (zero? code) (str "node failed: " err out))
    (is (= [-1 0 0 -2] (edn/read-string out)))))

(deftest scoped-fs-compiler-aot-path-len-package-registered
  (let [table (edn/read-string
               (slurp (io/resource "kotoba/lang/wasm-packages/wasm-packages-v1.edn")))
        by-name (into {} (map (juxt :name identity) (:packages table)))
        mod (get by-name :fs-path-len)
        comp (get by-name :fs-path-len-component)
        mod-bytes (-> (io/resource (:resource mod)) io/input-stream .readAllBytes)
        comp-bytes (-> (io/resource (:resource comp)) io/input-stream .readAllBytes)
        sha (fn [^bytes b]
              (let [md (java.security.MessageDigest/getInstance "SHA-256")]
                (.update md b)
                (apply str (map #(format "%02x" %) (.digest md)))))]
    (is (= :wasm-module (:artifact-kind mod)))
    (is (= :wasm-component (:artifact-kind comp)))
    (is (false? (:fixture? mod)))
    (is (= :ops (:class mod)))
    (is (= :kotoba-compiler/v1 (get-in mod [:source :builder])))
    (is (= (:sha256 mod) (sha mod-bytes)))
    (is (= (:sha256 comp) (sha comp-bytes)))
    (is (contains? (:exports mod) "fs_path_len_ok"))
    (is (some? (io/resource "kotoba/lang/wasm-packages/src/fs_path_len.kotoba")))))

(deftest scoped-fs-compiler-aot-path-len-live-behavior
  (let [bytes (-> (io/resource "kotoba/lang/wasm-packages/fs-path-len-v1.wasm")
                  io/input-stream .readAllBytes)
        tmp (java.io.File/createTempFile "fs-path-len" ".wasm")
        _ (java.nio.file.Files/write (.toPath tmp) bytes
                                     (into-array java.nio.file.OpenOption []))
        script (str "const b=require('fs').readFileSync(" (pr-str (.getAbsolutePath tmp)) ");"
                    "WebAssembly.instantiate(b).then(({instance})=>{"
                    "const f=instance.exports.fs_path_len_ok;"
                    "const out=[Number(f(0n)),Number(f(1n)),Number(f(1024n)),Number(f(1025n))];"
                    "console.log(JSON.stringify(out));"
                    "}).catch(e=>{console.error(e); process.exit(1);});")
        p (.start (ProcessBuilder. ["node" "-e" script]))
        out (slurp (.getInputStream p))
        err (slurp (.getErrorStream p))
        code (.waitFor p)]
    (.delete tmp)
    (is (zero? code) (str "node failed: " err out))
    (is (= [-1 0 0 -2] (edn/read-string out)))))

(deftest compiler-aot-value-length-packages
  "ADR 0175: secret/fs value-length pure bounds."
  (let [table (edn/read-string
               (slurp (io/resource "kotoba/lang/wasm-packages/wasm-packages-v1.edn")))
        by-name (into {} (map (juxt :name identity) (:packages table)))
        sha (fn [^bytes b]
              (let [md (java.security.MessageDigest/getInstance "SHA-256")]
                (.update md b)
                (apply str (map #(format "%02x" %) (.digest md)))))
        check (fn [mod-name comp-name export]
                (let [mod (get by-name mod-name)
                      comp (get by-name comp-name)
                      mod-bytes (-> (io/resource (:resource mod)) io/input-stream .readAllBytes)
                      comp-bytes (-> (io/resource (:resource comp)) io/input-stream .readAllBytes)]
                  (is (some? mod) (str mod-name))
                  (is (= :kotoba-compiler/v1 (get-in mod [:source :builder])))
                  (is (= (:sha256 mod) (sha mod-bytes)))
                  (is (= (:sha256 comp) (sha comp-bytes)))
                  (is (contains? (:exports mod) export))))]
    (check :secret-value-len :secret-value-len-component "secret_value_len_ok")
    (check :fs-value-len :fs-value-len-component "fs_value_len_ok")))

(deftest compiler-aot-value-length-live
  (let [run (fn [resource export cases]
              (let [bytes (-> (io/resource resource) io/input-stream .readAllBytes)
                    tmp (java.io.File/createTempFile "vlen" ".wasm")
                    _ (java.nio.file.Files/write (.toPath tmp) bytes
                                                 (into-array java.nio.file.OpenOption []))
                    args-js (str/join ","
                              (map (fn [args]
                                     (str "Number(f("
                                          (str/join "," (map #(str % "n") args))
                                          "))"))
                                   cases))
                    script (str "const b=require('fs').readFileSync(" (pr-str (.getAbsolutePath tmp)) ");"
                                "WebAssembly.instantiate(b).then(({instance})=>{"
                                "const f=instance.exports." export ";"
                                "console.log(JSON.stringify([" args-js "]));"
                                "}).catch(e=>{console.error(e); process.exit(1);});")
                    pb (ProcessBuilder. ["node" "-e" script])
                    p (.start pb)
                    out (slurp (.getInputStream p))
                    err (slurp (.getErrorStream p))
                    code (.waitFor p)]
                (.delete tmp)
                (is (zero? code) (str err out))
                (edn/read-string out)))]
    (is (= [0 0 -2 -1]
           (run "kotoba/lang/wasm-packages/secret-value-len-v1.wasm"
                "secret_value_len_ok" [[0] [8192] [8193] [-1]])))
    (is (= [0 0 -2 -1]
           (run "kotoba/lang/wasm-packages/fs-value-len-v1.wasm"
                "fs_value_len_ok" [[0] [65536] [65537] [-1]])))))

(deftest secret-compiler-aot-char-class-package-registered
  (let [table (edn/read-string
               (slurp (io/resource "kotoba/lang/wasm-packages/wasm-packages-v1.edn")))
        by-name (into {} (map (juxt :name identity) (:packages table)))
        mod (get by-name :secret-name-char)
        comp (get by-name :secret-name-char-component)
        mod-bytes (-> (io/resource (:resource mod)) io/input-stream .readAllBytes)
        comp-bytes (-> (io/resource (:resource comp)) io/input-stream .readAllBytes)
        sha (fn [^bytes b]
              (let [md (java.security.MessageDigest/getInstance "SHA-256")]
                (.update md b)
                (apply str (map #(format "%02x" %) (.digest md)))))]
    (is (= :wasm-module (:artifact-kind mod)))
    (is (= :wasm-component (:artifact-kind comp)))
    (is (false? (:fixture? mod)))
    (is (= :ops-network (:class mod)))
    (is (= :kotoba-compiler/v1 (get-in mod [:source :builder])))
    (is (= (:sha256 mod) (sha mod-bytes)))
    (is (= (:sha256 comp) (sha comp-bytes)))
    (is (contains? (:exports mod) "secret_name_char_ok"))
    (is (some? (io/resource "kotoba/lang/wasm-packages/src/secret_name_char.kotoba")))))

(deftest secret-compiler-aot-char-class-live-behavior
  (let [bytes (-> (io/resource "kotoba/lang/wasm-packages/secret-name-char-v1.wasm")
                  io/input-stream .readAllBytes)
        tmp (java.io.File/createTempFile "secret-char" ".wasm")
        _ (java.nio.file.Files/write (.toPath tmp) bytes
                                     (into-array java.nio.file.OpenOption []))
        script (str "const b=require('fs').readFileSync(" (pr-str (.getAbsolutePath tmp)) ");"
                    "WebAssembly.instantiate(b).then(({instance})=>{"
                    "const f=instance.exports.secret_name_char_ok;"
                    "const codes=[65,0,9,10,32,42,47,63,92,97];"
                    "const out=codes.map(c=>Number(f(BigInt(c))));"
                    "console.log(JSON.stringify(out));"
                    "}).catch(e=>{console.error(e); process.exit(1);});")
        p (.start (ProcessBuilder. ["node" "-e" script]))
        out (slurp (.getInputStream p))
        err (slurp (.getErrorStream p))
        code (.waitFor p)]
    (.delete tmp)
    (is (zero? code) (str "node failed: " err out))
    (is (= [0 -3 -3 -3 -3 -3 -3 -3 -3 0] (edn/read-string out)))))

(deftest compiler-aot-fs-path-gate-packages
  "ADR 0177: pure scoped-fs path state-machine gates."
  (let [table (edn/read-string
               (slurp (io/resource "kotoba/lang/wasm-packages/wasm-packages-v1.edn")))
        by-name (into {} (map (juxt :name identity) (:packages table)))
        sha (fn [^bytes b]
              (let [md (java.security.MessageDigest/getInstance "SHA-256")]
                (.update md b)
                (apply str (map #(format "%02x" %) (.digest md)))))
        mod (get by-name :fs-path-gate)
        comp (get by-name :fs-path-gate-component)
        mod-bytes (-> (io/resource (:resource mod)) io/input-stream .readAllBytes)
        comp-bytes (-> (io/resource (:resource comp)) io/input-stream .readAllBytes)]
    (is (some? mod))
    (is (= :kotoba-compiler/v1 (get-in mod [:source :builder])))
    (is (= (:sha256 mod) (sha mod-bytes)))
    (is (= (:sha256 comp) (sha comp-bytes)))
    (doseq [e ["fs_path_first_ok" "fs_path_step" "fs_path_finish"]]
      (is (contains? (:exports mod) e)))
    (is (some? (io/resource "kotoba/lang/wasm-packages/src/fs_path_gate.kotoba")))))

(deftest compiler-aot-fs-path-gate-live
  (let [bytes (-> (io/resource "kotoba/lang/wasm-packages/fs-path-gate-v1.wasm")
                  io/input-stream .readAllBytes)
        tmp (java.io.File/createTempFile "fsgate" ".wasm")
        _ (java.nio.file.Files/write (.toPath tmp) bytes
                                     (into-array java.nio.file.OpenOption []))
        script (str
                "const b=require('fs').readFileSync(" (pr-str (.getAbsolutePath tmp)) ");"
                "WebAssembly.instantiate(b).then(({instance})=>{"
                "const first=instance.exports.fs_path_first_ok;"
                "const step=instance.exports.fs_path_step;"
                "const finish=instance.exports.fs_path_finish;"
                "const N=x=>Number(x);"
                "const walk=s=>{const bytes=[...Buffer.from(s)];"
                "const f=N(first(BigInt(bytes[0]))); if(f!==0) return f;"
                "let st=4n; for(const c of bytes){st=step(st,BigInt(c)); if(N(st)<0) return N(st);} return N(finish(st));};"
                "console.log(JSON.stringify(["
                "N(first(47n)),N(first(126n)),N(first(97n)),"
                "walk('a'),walk('a/b'),walk('a\\0b'),walk('a\\\\b'),"
                "walk('.'),walk('..'),walk('a/../b'),walk('a/b/c')"
                "]));"
                "}).catch(e=>{console.error(e); process.exit(1);});")
        pb (ProcessBuilder. ["node" "-e" script])
        p (.start pb)
        out (slurp (.getInputStream p))
        err (slurp (.getErrorStream p))
        code (.waitFor p)]
    (.delete tmp)
    (is (zero? code) (str err out))
    (is (= [-5 -6 0 0 0 -3 -4 -7 -7 -7 0] (edn/read-string out)))))

(deftest secret-typed-string-name-ok-package-registered
  (let [table (edn/read-string
               (slurp (io/resource "kotoba/lang/wasm-packages/wasm-packages-v1.edn")))
        by-name (into {} (map (juxt :name identity) (:packages table)))
        mod (get by-name :secret-name-ok)
        mod-bytes (-> (io/resource (:resource mod)) io/input-stream .readAllBytes)
        sha (fn [^bytes b]
              (let [md (java.security.MessageDigest/getInstance "SHA-256")]
                (.update md b)
                (apply str (map #(format "%02x" %) (.digest md)))))]
    (is (= :wasm-module (:artifact-kind mod)))
    (is (false? (:fixture? mod)))
    (is (= :ops-network (:class mod)))
    (is (= :kotoba-compiler/v1 (get-in mod [:source :builder])))
    (is (= :kotoba.typed (get-in mod [:source :typed-host])))
    (is (= (:sha256 mod) (sha mod-bytes)))
    (is (contains? (:exports mod) "secret_name_ok"))
    (is (contains? (:exports mod) "main"))
    (is (contains? (:imports mod) "kotoba:typed"))
    (is (some? (io/resource "kotoba/lang/wasm-packages/src/secret_name_ok.kotoba")))))

(deftest secret-typed-string-name-ok-live-browser-host-optional
  (let [host (or (System/getenv "KOTOBA_BROWSER_HOST")
                 ;; sibling monorepo layout /tmp worktree may not have it
                 (let [cand (io/file ".." "compiler" "runtime" "browser-host.mjs")]
                   (when (.exists cand) (.getAbsolutePath cand))))
        wasm (.getAbsolutePath
              (io/file "resources/kotoba/lang/wasm-packages/secret-name-ok-v1.wasm"))]
    (if-not (and host (.exists (io/file host)) (.exists (io/file wasm)))
      (is true "skip typed live when browser-host unavailable")
      (let [script (str "import { readFileSync } from 'fs';"
                        "import { instantiateKotoba } from "
                        (pr-str (str "file://" host))
                        ";"
                        "const h=await instantiateKotoba(readFileSync(" (pr-str wasm) "));"
                        "const v=h.instance.exports.main();"
                        "if(v!==-130n){console.error('got',v); process.exit(2);}"
                        "console.log(JSON.stringify([-130]));")
            pb (doto (ProcessBuilder. ["node" "--input-type=module" "-e" script])
                 (.redirectErrorStream true))
            p (.start pb)
            out (slurp (.getInputStream p))
            code (.waitFor p)]
        (is (zero? code) (str "browser-host live failed: " out))
        (is (= [-130] (edn/read-string out)))))))

(deftest compiler-aot-secret-name-walk-packages
  "ADR 0179: pure multi-step secret name walk."
  (let [table (edn/read-string
               (slurp (io/resource "kotoba/lang/wasm-packages/wasm-packages-v1.edn")))
        by-name (into {} (map (juxt :name identity) (:packages table)))
        sha (fn [^bytes b]
              (let [md (java.security.MessageDigest/getInstance "SHA-256")]
                (.update md b)
                (apply str (map #(format "%02x" %) (.digest md)))))
        mod (get by-name :secret-name-walk)
        comp (get by-name :secret-name-walk-component)
        mod-bytes (-> (io/resource (:resource mod)) io/input-stream .readAllBytes)
        comp-bytes (-> (io/resource (:resource comp)) io/input-stream .readAllBytes)]
    (is (some? mod))
    (is (= :kotoba-compiler/v1 (get-in mod [:source :builder])))
    (is (= (:sha256 mod) (sha mod-bytes)))
    (is (= (:sha256 comp) (sha comp-bytes)))
    (doseq [e ["secret_name_begin" "secret_name_next" "secret_name_end"]]
      (is (contains? (:exports mod) e)))
    (is (some? (io/resource "kotoba/lang/wasm-packages/src/secret_name_walk.kotoba")))))

(deftest compiler-aot-secret-name-walk-live
  (let [bytes (-> (io/resource "kotoba/lang/wasm-packages/secret-name-walk-v1.wasm")
                  io/input-stream .readAllBytes)
        tmp (java.io.File/createTempFile "snwalk" ".wasm")
        _ (java.nio.file.Files/write (.toPath tmp) bytes
                                     (into-array java.nio.file.OpenOption []))
        script (str
                "const b=require('fs').readFileSync(" (pr-str (.getAbsolutePath tmp)) ");"
                "WebAssembly.instantiate(b).then(({instance})=>{"
                "const begin=instance.exports.secret_name_begin;"
                "const next=instance.exports.secret_name_next;"
                "const end=instance.exports.secret_name_end;"
                "const N=x=>Number(x);"
                "const walk=s=>{let st=begin(BigInt(Buffer.byteLength(s))); if(N(st)<0) return N(st);"
                "for(const c of Buffer.from(s)){st=next(st,BigInt(c)); if(N(st)<0) return N(st);} return N(end(st));};"
                "console.log(JSON.stringify([walk(''),walk('api-key'),walk('x'.repeat(129)),walk('a/b'),walk('a*b')]));"
                "}).catch(e=>{console.error(e); process.exit(1);});")
        pb (ProcessBuilder. ["node" "-e" script])
        p (.start pb)
        out (slurp (.getInputStream p))
        err (slurp (.getErrorStream p))
        code (.waitFor p)]
    (.delete tmp)
    (is (zero? code) (str err out))
    (is (= [-1 0 -2 -3 -3] (edn/read-string out)))))

(deftest fs-typed-string-path-ok-package-registered
  (let [table (edn/read-string
               (slurp (io/resource "kotoba/lang/wasm-packages/wasm-packages-v1.edn")))
        by-name (into {} (map (juxt :name identity) (:packages table)))
        mod (get by-name :fs-path-ok)
        mod-bytes (-> (io/resource (:resource mod)) io/input-stream .readAllBytes)
        sha (fn [^bytes b]
              (let [md (java.security.MessageDigest/getInstance "SHA-256")]
                (.update md b)
                (apply str (map #(format "%02x" %) (.digest md)))))]
    (is (some? mod))
    (is (= :wasm-module (:artifact-kind mod)))
    (is (false? (:fixture? mod)))
    (is (= :ops-network (:class mod)))
    (is (= :kotoba-compiler/v1 (get-in mod [:source :builder])))
    (is (= :kotoba.typed (get-in mod [:source :typed-host])))
    (is (= (:sha256 mod) (sha mod-bytes)))
    (is (contains? (:exports mod) "fs_path_ok"))
    (is (contains? (:exports mod) "main"))
    (is (contains? (:imports mod) "kotoba:typed"))
    (is (some? (io/resource "kotoba/lang/wasm-packages/src/fs_path_ok.kotoba")))))

(deftest fs-typed-string-path-ok-live-browser-host-optional
  (let [host (or (System/getenv "KOTOBA_BROWSER_HOST")
                 (let [cand (io/file ".." "compiler" "runtime" "browser-host.mjs")]
                   (when (.exists cand) (.getAbsolutePath cand)))
                 (let [cand (io/file "/Users/junkawasaki/github/com-junkawasaki/orgs/kotoba-lang/compiler/runtime/browser-host.mjs")]
                   (when (.exists cand) (.getAbsolutePath cand))))
        wasm (.getAbsolutePath
              (io/file "resources/kotoba/lang/wasm-packages/fs-path-ok-v1.wasm"))]
    (if-not (and host (.exists (io/file host)) (.exists (io/file wasm)))
      (is true "skip typed live when browser-host unavailable")
      (let [script (str "import { readFileSync } from 'fs';"
                        "import { instantiateKotoba } from "
                        (pr-str (str "file://" host))
                        ";"
                        "const h=await instantiateKotoba(readFileSync(" (pr-str wasm) "));"
                        "const v=h.instance.exports.main();"
                        "if(v!==-15470n){console.error('got',v); process.exit(2);}"
                        "console.log(JSON.stringify([-15470]));")
            pb (doto (ProcessBuilder. ["node" "--input-type=module" "-e" script])
                 (.redirectErrorStream true))
            p (.start pb)
            out (slurp (.getInputStream p))
            code (.waitFor p)]
        (is (zero? code) (str "browser-host live failed: " out))
        (is (= [-15470] (edn/read-string out)))))))

(deftest scoped-fs-multistep-walk-package-registered
  (let [table (edn/read-string
               (slurp (io/resource "kotoba/lang/wasm-packages/wasm-packages-v1.edn")))
        by-name (into {} (map (juxt :name identity) (:packages table)))
        mod (get by-name :fs-path-walk)
        comp (get by-name :fs-path-walk-component)
        mod-bytes (-> (io/resource (:resource mod)) io/input-stream .readAllBytes)
        comp-bytes (-> (io/resource (:resource comp)) io/input-stream .readAllBytes)
        sha (fn [^bytes b]
              (let [md (java.security.MessageDigest/getInstance "SHA-256")]
                (.update md b)
                (apply str (map #(format "%02x" %) (.digest md)))))]
    (is (= :wasm-module (:artifact-kind mod)))
    (is (= :wasm-component (:artifact-kind comp)))
    (is (false? (:fixture? mod)))
    (is (= :ops-network (:class mod)))
    (is (= :kotoba-compiler/v1 (get-in mod [:source :builder])))
    (is (= (:sha256 mod) (sha mod-bytes)))
    (is (= (:sha256 comp) (sha comp-bytes)))
    (is (contains? (:exports mod) "fs_path_begin"))
    (is (contains? (:exports mod) "fs_path_next"))
    (is (contains? (:exports mod) "fs_path_end"))
    (is (some? (io/resource "kotoba/lang/wasm-packages/src/fs_path_walk.kotoba")))))

(deftest scoped-fs-multistep-walk-live-behavior
  (let [bytes (-> (io/resource "kotoba/lang/wasm-packages/fs-path-walk-v1.wasm")
                  io/input-stream .readAllBytes)
        tmp (java.io.File/createTempFile "fs-walk" ".wasm")
        _ (java.nio.file.Files/write (.toPath tmp) bytes
                                     (into-array java.nio.file.OpenOption []))
        script (str
                "const b=require('fs').readFileSync(" (pr-str (.getAbsolutePath tmp)) ");"
                "WebAssembly.instantiate(b).then(({instance})=>{"
                "const {fs_path_begin,fs_path_next,fs_path_end}=instance.exports;"
                "const N=x=>Number(x);"
                "function walk(s){"
                "  let st=N(fs_path_begin(BigInt(s.length)));"
                "  if(st<0) return st;"
                "  for(const ch of s){"
                "    st=N(fs_path_next(BigInt(st), BigInt(ch.charCodeAt(0))));"
                "    if(st<0) return st;"
                "  }"
                "  return N(fs_path_end(BigInt(st)));"
                "}"
                "const cases=['','a','a/b','../x','/a','~a','a\\\\b','ok/path','a/..'];"
                "const out=cases.map(walk);"
                "console.log(JSON.stringify(out));"
                "}).catch(e=>{console.error(e); process.exit(1);});")
        p (.start (ProcessBuilder. ["node" "-e" script]))
        out (slurp (.getInputStream p))
        err (slurp (.getErrorStream p))
        code (.waitFor p)]
    (.delete tmp)
    (is (zero? code) (str "node failed: " err out))
    (is (= [-1 0 0 -7 -5 -6 -4 0 -7] (edn/read-string out)))))

(deftest http-typed-string-url-ok-package-registered
  (let [table (edn/read-string
               (slurp (io/resource "kotoba/lang/wasm-packages/wasm-packages-v1.edn")))
        by-name (into {} (map (juxt :name identity) (:packages table)))
        mod (get by-name :http-url-ok)
        mod-bytes (-> (io/resource (:resource mod)) io/input-stream .readAllBytes)
        sha (fn [^bytes b]
              (let [md (java.security.MessageDigest/getInstance "SHA-256")]
                (.update md b)
                (apply str (map #(format "%02x" %) (.digest md)))))]
    (is (some? mod))
    (is (= :wasm-module (:artifact-kind mod)))
    (is (= :kotoba-compiler/v1 (get-in mod [:source :builder])))
    (is (= :kotoba.typed (get-in mod [:source :typed-host])))
    (is (= (:sha256 mod) (sha mod-bytes)))
    (is (contains? (:exports mod) "http_url_ok"))
    (is (contains? (:exports mod) "main"))
    (is (contains? (:imports mod) "kotoba:typed"))
    (is (some? (io/resource "kotoba/lang/wasm-packages/src/http_url_ok.kotoba")))))

(deftest http-typed-string-url-ok-live-browser-host-optional
  (let [host (or (System/getenv "KOTOBA_BROWSER_HOST")
                 (let [cand (io/file ".." "compiler" "runtime" "browser-host.mjs")]
                   (when (.exists cand) (.getAbsolutePath cand)))
                 (let [cand (io/file "/Users/junkawasaki/github/com-junkawasaki/orgs/kotoba-lang/compiler/runtime/browser-host.mjs")]
                   (when (.exists cand) (.getAbsolutePath cand))))
        wasm (.getAbsolutePath
              (io/file "resources/kotoba/lang/wasm-packages/http-url-ok-v1.wasm"))]
    (if-not (and host (.exists (io/file host)) (.exists (io/file wasm)))
      (is true "skip typed live when browser-host unavailable")
      (let [script (str "import { readFileSync } from 'fs';"
                        "import { instantiateKotoba } from "
                        (pr-str (str "file://" host))
                        ";"
                        "const h=await instantiateKotoba(readFileSync(" (pr-str wasm) "));"
                        "const v=h.instance.exports.main();"
                        "if(v!==-130n){console.error('got',v); process.exit(2);}"
                        "console.log(JSON.stringify([-130]));")
            pb (doto (ProcessBuilder. ["node" "--input-type=module" "-e" script])
                 (.redirectErrorStream true))
            p (.start pb)
            out (slurp (.getInputStream p))
            code (.waitFor p)]
        (is (zero? code) (str "browser-host live failed: " out))
        (is (= [-130] (edn/read-string out)))))))

(deftest process-multistep-walk-package-registered
  (let [table (edn/read-string
               (slurp (io/resource "kotoba/lang/wasm-packages/wasm-packages-v1.edn")))
        by-name (into {} (map (juxt :name identity) (:packages table)))
        mod (get by-name :process-spawn-walk)
        comp (get by-name :process-spawn-walk-component)
        mod-bytes (-> (io/resource (:resource mod)) io/input-stream .readAllBytes)
        comp-bytes (-> (io/resource (:resource comp)) io/input-stream .readAllBytes)
        sha (fn [^bytes b]
              (let [md (java.security.MessageDigest/getInstance "SHA-256")]
                (.update md b)
                (apply str (map #(format "%02x" %) (.digest md)))))]
    (is (= :wasm-module (:artifact-kind mod)))
    (is (= :wasm-component (:artifact-kind comp)))
    (is (false? (:fixture? mod)))
    (is (= :ops-network (:class mod)))
    (is (= :kotoba-compiler/v1 (get-in mod [:source :builder])))
    (is (= (:sha256 mod) (sha mod-bytes)))
    (is (= (:sha256 comp) (sha comp-bytes)))
    (is (contains? (:exports mod) "process_spawn_begin"))
    (is (contains? (:exports mod) "process_spawn_arg"))
    (is (contains? (:exports mod) "process_spawn_end"))
    (is (some? (io/resource "kotoba/lang/wasm-packages/src/process_spawn_walk.kotoba")))))

(deftest process-multistep-walk-live-behavior
  (let [bytes (-> (io/resource "kotoba/lang/wasm-packages/process-spawn-walk-v1.wasm")
                  io/input-stream .readAllBytes)
        tmp (java.io.File/createTempFile "proc-walk" ".wasm")
        _ (java.nio.file.Files/write (.toPath tmp) bytes
                                     (into-array java.nio.file.OpenOption []))
        script (str
                "const b=require('fs').readFileSync(" (pr-str (.getAbsolutePath tmp)) ");"
                "WebAssembly.instantiate(b).then(({instance})=>{"
                "const {process_spawn_begin,process_spawn_arg,process_spawn_end}=instance.exports;"
                "const N=x=>Number(x);"
                "function walk(argc,lens,mo,to){"
                "  let st=N(process_spawn_begin(BigInt(argc)));"
                "  if(st<0) return st;"
                "  for(const L of lens){"
                "    st=N(process_spawn_arg(BigInt(st), BigInt(L)));"
                "    if(st<0) return st;"
                "  }"
                "  return N(process_spawn_end(BigInt(st), BigInt(mo), BigInt(to)));"
                "}"
                "const out=["
                "  walk(3,[1,2,3],100,1000),"
                "  walk(0,[],100,1000),"
                "  walk(33,Array(33).fill(1),100,1000),"
                "  walk(1,[5000],100,1000),"
                "  walk(2,[1],100,1000),"
                "  walk(1,[1,1],100,1000),"
                "  walk(1,[1],100,0),"
                "  walk(1,[1],0,1000)"
                "];"
                "console.log(JSON.stringify(out));"
                "}).catch(e=>{console.error(e); process.exit(1);});")
        p (.start (ProcessBuilder. ["node" "-e" script]))
        out (slurp (.getInputStream p))
        err (slurp (.getErrorStream p))
        code (.waitFor p)]
    (.delete tmp)
    (is (zero? code) (str "node failed: " err out))
    (is (= [0 -1 -2 -6 -7 -5 -4 -3] (edn/read-string out)))))

(deftest compiler-aot-git-run-walk-packages
  "ADR 0184: pure multi-step git run walk."
  (let [table (edn/read-string
               (slurp (io/resource "kotoba/lang/wasm-packages/wasm-packages-v1.edn")))
        by-name (into {} (map (juxt :name identity) (:packages table)))
        sha (fn [^bytes b]
              (let [md (java.security.MessageDigest/getInstance "SHA-256")]
                (.update md b)
                (apply str (map #(format "%02x" %) (.digest md)))))
        mod (get by-name :git-run-walk)
        comp (get by-name :git-run-walk-component)
        mod-bytes (-> (io/resource (:resource mod)) io/input-stream .readAllBytes)
        comp-bytes (-> (io/resource (:resource comp)) io/input-stream .readAllBytes)]
    (is (some? mod))
    (is (= :kotoba-compiler/v1 (get-in mod [:source :builder])))
    (is (= (:sha256 mod) (sha mod-bytes)))
    (is (= (:sha256 comp) (sha comp-bytes)))
    (doseq [e ["git_run_begin" "git_run_arg" "git_run_end"]]
      (is (contains? (:exports mod) e)))
    (is (some? (io/resource "kotoba/lang/wasm-packages/src/git_run_walk.kotoba")))))

(deftest compiler-aot-git-run-walk-live
  (let [bytes (-> (io/resource "kotoba/lang/wasm-packages/git-run-walk-v1.wasm")
                  io/input-stream .readAllBytes)
        tmp (java.io.File/createTempFile "gwalk" ".wasm")
        _ (java.nio.file.Files/write (.toPath tmp) bytes
                                     (into-array java.nio.file.OpenOption []))
        script (str
                "const b=require('fs').readFileSync(" (pr-str (.getAbsolutePath tmp)) ");"
                "WebAssembly.instantiate(b).then(({instance})=>{"
                "const begin=instance.exports.git_run_begin;"
                "const arg=instance.exports.git_run_arg;"
                "const end=instance.exports.git_run_end;"
                "const N=x=>Number(x);"
                "const walk=(argc,lens,mo,to)=>{let st=begin(BigInt(argc)); if(N(st)<0) return N(st);"
                "for(const L of lens){st=arg(st,BigInt(L)); if(N(st)<0) return N(st);} return N(end(st,BigInt(mo),BigInt(to)));};"
                "let st=begin(1n); st=arg(st,3n); const extra=N(arg(st,3n));"
                "console.log(JSON.stringify([walk(2,[3,4],100,1000),walk(0,[],100,1000),walk(65,[1],100,1000),"
                "walk(1,[5000],100,1000),walk(2,[3],100,1000),extra,walk(1,[1],0,1000),walk(1,[1],100,0)]));"
                "}).catch(e=>{console.error(e); process.exit(1);});")
        pb (ProcessBuilder. ["node" "-e" script])
        p (.start pb)
        out (slurp (.getInputStream p))
        err (slurp (.getErrorStream p))
        code (.waitFor p)]
    (.delete tmp)
    (is (zero? code) (str err out))
    (is (= [0 -1 -2 -6 -7 -5 -3 -4] (edn/read-string out)))))

(deftest http-multistep-walk-package-registered
  (let [table (edn/read-string
               (slurp (io/resource "kotoba/lang/wasm-packages/wasm-packages-v1.edn")))
        by-name (into {} (map (juxt :name identity) (:packages table)))
        mod (get by-name :http-post-walk)
        comp (get by-name :http-post-walk-component)
        mod-bytes (-> (io/resource (:resource mod)) io/input-stream .readAllBytes)
        comp-bytes (-> (io/resource (:resource comp)) io/input-stream .readAllBytes)
        sha (fn [^bytes b]
              (let [md (java.security.MessageDigest/getInstance "SHA-256")]
                (.update md b)
                (apply str (map #(format "%02x" %) (.digest md)))))]
    (is (= :wasm-module (:artifact-kind mod)))
    (is (= :wasm-component (:artifact-kind comp)))
    (is (false? (:fixture? mod)))
    (is (= :ops-network (:class mod)))
    (is (= :kotoba-compiler/v1 (get-in mod [:source :builder])))
    (is (= (:sha256 mod) (sha mod-bytes)))
    (is (= (:sha256 comp) (sha comp-bytes)))
    (doseq [x ["http_post_begin" "http_post_url" "http_post_headers"
                "http_post_body" "http_post_end"]]
      (is (contains? (:exports mod) x)))
    (is (some? (io/resource "kotoba/lang/wasm-packages/src/http_post_walk.kotoba")))))

(deftest http-multistep-walk-live-behavior
  (let [bytes (-> (io/resource "kotoba/lang/wasm-packages/http-post-walk-v1.wasm")
                  io/input-stream .readAllBytes)
        tmp (java.io.File/createTempFile "http-walk" ".wasm")
        _ (java.nio.file.Files/write (.toPath tmp) bytes
                                     (into-array java.nio.file.OpenOption []))
        script (str
                "const b=require('fs').readFileSync(" (pr-str (.getAbsolutePath tmp)) ");"
                "WebAssembly.instantiate(b).then(({instance})=>{"
                "const e=instance.exports; const N=x=>Number(x);"
                "function walk(u,h,b,t){"
                "  let s=N(e.http_post_begin());"
                "  s=N(e.http_post_url(BigInt(s),BigInt(u))); if(s<0) return s;"
                "  s=N(e.http_post_headers(BigInt(s),BigInt(h))); if(s<0) return s;"
                "  s=N(e.http_post_body(BigInt(s),BigInt(b))); if(s<0) return s;"
                "  return N(e.http_post_end(BigInt(s),BigInt(t)));"
                "}"
                "const out=[walk(10,2,100,1000),walk(0,0,0,1000),walk(10,40,0,1000),"
                "walk(10,0,70000,1000),walk(10,0,0,0),N(e.http_post_end(0n,1000n))];"
                "console.log(JSON.stringify(out));"
                "}).catch(e=>{console.error(e); process.exit(1);});")
        p (.start (ProcessBuilder. ["node" "-e" script]))
        out (slurp (.getInputStream p))
        err (slurp (.getErrorStream p))
        code (.waitFor p)]
    (.delete tmp)
    (is (zero? code) (str "node failed: " err out))
    (is (= [0 -1 -2 -3 -4 -5] (edn/read-string out)))))

(deftest http-typed-string-request-ok-package-registered
  (let [table (edn/read-string
               (slurp (io/resource "kotoba/lang/wasm-packages/wasm-packages-v1.edn")))
        by-name (into {} (map (juxt :name identity) (:packages table)))
        mod (get by-name :http-post-request-ok)
        mod-bytes (-> (io/resource (:resource mod)) io/input-stream .readAllBytes)
        sha (fn [^bytes b]
              (let [md (java.security.MessageDigest/getInstance "SHA-256")]
                (.update md b)
                (apply str (map #(format "%02x" %) (.digest md)))))]
    (is (some? mod))
    (is (= :wasm-module (:artifact-kind mod)))
    (is (= :kotoba-compiler/v1 (get-in mod [:source :builder])))
    (is (= :kotoba.typed (get-in mod [:source :typed-host])))
    (is (= (:sha256 mod) (sha mod-bytes)))
    (is (contains? (:exports mod) "http_post_request_ok"))
    (is (contains? (:exports mod) "main"))
    (is (contains? (:imports mod) "kotoba:typed"))
    (is (some? (io/resource "kotoba/lang/wasm-packages/src/http_post_request_ok.kotoba")))))

(deftest http-typed-string-request-ok-live-browser-host-optional
  (let [host (or (System/getenv "KOTOBA_BROWSER_HOST")
                 (let [cand (io/file ".." "compiler" "runtime" "browser-host.mjs")]
                   (when (.exists cand) (.getAbsolutePath cand)))
                 (let [cand (io/file "/Users/junkawasaki/github/com-junkawasaki/orgs/kotoba-lang/compiler/runtime/browser-host.mjs")]
                   (when (.exists cand) (.getAbsolutePath cand))))
        wasm (.getAbsolutePath
              (io/file "resources/kotoba/lang/wasm-packages/http-post-request-ok-v1.wasm"))]
    (if-not (and host (.exists (io/file host)) (.exists (io/file wasm)))
      (is true "skip typed live when browser-host unavailable")
      (let [script (str "import { readFileSync } from 'fs';"
                        "import { instantiateKotoba } from "
                        (pr-str (str "file://" host))
                        ";"
                        "const h=await instantiateKotoba(readFileSync(" (pr-str wasm) "));"
                        "const v=h.instance.exports.main();"
                        "if(v!==-13406n){console.error('got',v); process.exit(2);}"
                        "console.log(JSON.stringify([-13406]));")
            pb (doto (ProcessBuilder. ["node" "--input-type=module" "-e" script])
                 (.redirectErrorStream true))
            p (.start pb)
            out (slurp (.getInputStream p))
            code (.waitFor p)]
        (is (zero? code) (str "browser-host live failed: " out))
        (is (= [-13406] (edn/read-string out)))))))

(deftest http-typed-string-header-name-ok-package-registered
  (let [table (edn/read-string
               (slurp (io/resource "kotoba/lang/wasm-packages/wasm-packages-v1.edn")))
        by-name (into {} (map (juxt :name identity) (:packages table)))
        mod (get by-name :http-header-name-ok)
        mod-bytes (-> (io/resource (:resource mod)) io/input-stream .readAllBytes)
        sha (fn [^bytes b]
              (let [md (java.security.MessageDigest/getInstance "SHA-256")]
                (.update md b)
                (apply str (map #(format "%02x" %) (.digest md)))))]
    (is (some? mod))
    (is (= :wasm-module (:artifact-kind mod)))
    (is (= :kotoba-compiler/v1 (get-in mod [:source :builder])))
    (is (= :kotoba.typed (get-in mod [:source :typed-host])))
    (is (= (:sha256 mod) (sha mod-bytes)))
    (is (contains? (:exports mod) "http_header_name_ok"))
    (is (contains? (:exports mod) "main"))
    (is (contains? (:imports mod) "kotoba:typed"))
    (is (some? (io/resource "kotoba/lang/wasm-packages/src/http_header_name_ok.kotoba")))))

(deftest http-typed-string-header-name-ok-live-browser-host-optional
  (let [host (or (System/getenv "KOTOBA_BROWSER_HOST")
                 (let [cand (io/file ".." "compiler" "runtime" "browser-host.mjs")]
                   (when (.exists cand) (.getAbsolutePath cand)))
                 (let [cand (io/file "/Users/junkawasaki/github/com-junkawasaki/orgs/kotoba-lang/compiler/runtime/browser-host.mjs")]
                   (when (.exists cand) (.getAbsolutePath cand))))
        wasm (.getAbsolutePath
              (io/file "resources/kotoba/lang/wasm-packages/http-header-name-ok-v1.wasm"))]
    (if-not (and host (.exists (io/file host)) (.exists (io/file wasm)))
      (is true "skip typed live when browser-host unavailable")
      (let [script (str "import { readFileSync } from 'fs';"
                        "import { instantiateKotoba } from "
                        (pr-str (str "file://" host))
                        ";"
                        "const h=await instantiateKotoba(readFileSync(" (pr-str wasm) "));"
                        "const v=h.instance.exports.main();"
                        "if(v!==-130n){console.error('got',v); process.exit(2);}"
                        "console.log(JSON.stringify([-130]));")
            pb (doto (ProcessBuilder. ["node" "--input-type=module" "-e" script])
                 (.redirectErrorStream true))
            p (.start pb)
            out (slurp (.getInputStream p))
            code (.waitFor p)]
        (is (zero? code) (str "browser-host live failed: " out))
        (is (= [-130] (edn/read-string out)))))))

(deftest http-typed-string-header-value-ok-package-registered
  (let [table (edn/read-string
               (slurp (io/resource "kotoba/lang/wasm-packages/wasm-packages-v1.edn")))
        by-name (into {} (map (juxt :name identity) (:packages table)))
        mod (get by-name :http-header-value-ok)
        mod-bytes (-> (io/resource (:resource mod)) io/input-stream .readAllBytes)
        sha (fn [^bytes b]
              (let [md (java.security.MessageDigest/getInstance "SHA-256")]
                (.update md b)
                (apply str (map #(format "%02x" %) (.digest md)))))]
    (is (some? mod))
    (is (= :wasm-module (:artifact-kind mod)))
    (is (= :kotoba-compiler/v1 (get-in mod [:source :builder])))
    (is (= :kotoba.typed (get-in mod [:source :typed-host])))
    (is (= (:sha256 mod) (sha mod-bytes)))
    (doseq [e ["http_header_value_ok" "http_header_pair_ok" "main"]]
      (is (contains? (:exports mod) e)))
    (is (contains? (:imports mod) "kotoba:typed"))
    (is (some? (io/resource "kotoba/lang/wasm-packages/src/http_header_value_ok.kotoba")))))

(deftest http-typed-string-header-value-ok-live-browser-host-optional
  (let [host (or (System/getenv "KOTOBA_BROWSER_HOST")
                 (let [cand (io/file ".." "compiler" "runtime" "browser-host.mjs")]
                   (when (.exists cand) (.getAbsolutePath cand)))
                 (let [cand (io/file "/Users/junkawasaki/github/com-junkawasaki/orgs/kotoba-lang/compiler/runtime/browser-host.mjs")]
                   (when (.exists cand) (.getAbsolutePath cand))))
        wasm (.getAbsolutePath
              (io/file "resources/kotoba/lang/wasm-packages/http-header-value-ok-v1.wasm"))]
    (if-not (and host (.exists (io/file host)) (.exists (io/file wasm)))
      (is true "skip typed live when browser-host unavailable")
      (let [script (str "import { readFileSync } from 'fs';"
                        "import { instantiateKotoba } from "
                        (pr-str (str "file://" host))
                        ";"
                        "const h=await instantiateKotoba(readFileSync(" (pr-str wasm) "));"
                        "const v=h.instance.exports.main();"
                        "if(v!==-3036n){console.error('got',v); process.exit(2);}"
                        "console.log(JSON.stringify([-3036]));")
            pb (doto (ProcessBuilder. ["node" "--input-type=module" "-e" script])
                 (.redirectErrorStream true))
            p (.start pb)
            out (slurp (.getInputStream p))
            code (.waitFor p)]
        (is (zero? code) (str "browser-host live failed: " out))
        (is (= [-3036] (edn/read-string out)))))))

(deftest http-typed-string-headers-set-ok-package-registered
  (let [table (edn/read-string
               (slurp (io/resource "kotoba/lang/wasm-packages/wasm-packages-v1.edn")))
        by-name (into {} (map (juxt :name identity) (:packages table)))
        mod (get by-name :http-headers-set-ok)
        mod-bytes (-> (io/resource (:resource mod)) io/input-stream .readAllBytes)
        sha (fn [^bytes b]
              (let [md (java.security.MessageDigest/getInstance "SHA-256")]
                (.update md b)
                (apply str (map #(format "%02x" %) (.digest md)))))]
    (is (some? mod))
    (is (= :wasm-module (:artifact-kind mod)))
    (is (= :kotoba-compiler/v1 (get-in mod [:source :builder])))
    (is (= :kotoba.typed (get-in mod [:source :typed-host])))
    (is (= (:sha256 mod) (sha mod-bytes)))
    (doseq [e ["http_headers_begin" "http_headers_pair" "http_headers_end" "main"]]
      (is (contains? (:exports mod) e)))
    (is (contains? (:imports mod) "kotoba:typed"))
    (is (some? (io/resource "kotoba/lang/wasm-packages/src/http_headers_set_ok.kotoba")))))

(deftest http-headers-name-set-true-uniqueness-package-registered
  "T8.3 ADR 0223/0279: true name uniqueness in nominal HeaderNameSet."
  (let [table (edn/read-string
               (slurp (io/resource "kotoba/lang/wasm-packages/wasm-packages-v1.edn")))
        by-name (into {} (map (juxt :name identity) (:packages table)))
        mod (get by-name :http-headers-name-set)
        mod-bytes (-> (io/resource (:resource mod)) io/input-stream .readAllBytes)
        sha (fn [^bytes b]
              (let [md (java.security.MessageDigest/getInstance "SHA-256")]
                (.update md b)
                (apply str (map #(format "%02x" %) (.digest md)))))]
    (is (some? mod))
    (is (= :wasm-module (:artifact-kind mod)))
    (is (= :kotoba-compiler/v1 (get-in mod [:source :builder])))
    (is (= :kotoba.typed (get-in mod [:source :typed-host])))
    (is (= "85dd13bda2c801753d88025dce913bac4a2d5c3e80acf4648130ea2a022200d2"
           (:sha256 mod) (sha mod-bytes)))
    (doseq [e ["http_headers_names_begin" "http_headers_names_add"
               "http_headers_names_pair" "http_headers_names_code"
               "http_headers_names_count" "main"]]
      (is (contains? (:exports mod) e)))
    (is (contains? (:imports mod) "kotoba:typed"))
    (let [source-resource (io/resource "kotoba/lang/wasm-packages/src/http_headers_name_set.kotoba")
          source (slurp source-resource)]
      (is (some? source-resource))
      (is (str/includes? source "(defrecord HeaderNameSet"))
      (doseq [raw-surface ["(record-new" "(record-get" "(:schemas"]]
        (is (not (str/includes? source raw-surface)))))))

(deftest http-headers-edn-append-set-true-uniqueness-package-registered
  "T8.3 ADR 0224/0280: nominal EDN accumulator with true set uniqueness."
  (let [table (edn/read-string
               (slurp (io/resource "kotoba/lang/wasm-packages/wasm-packages-v1.edn")))
        by-name (into {} (map (juxt :name identity) (:packages table)))
        mod (get by-name :http-headers-edn-append-set)
        mod-bytes (-> (io/resource (:resource mod)) io/input-stream .readAllBytes)
        sha (fn [^bytes b]
              (let [md (java.security.MessageDigest/getInstance "SHA-256")]
                (.update md b)
                (apply str (map #(format "%02x" %) (.digest md)))))]
    (is (some? mod))
    (is (= :wasm-module (:artifact-kind mod)))
    (is (= :kotoba-compiler/v1 (get-in mod [:source :builder])))
    (is (= :kotoba.typed (get-in mod [:source :typed-host])))
    (is (= "5bf99a51ee63e6922c5c40dac91500fb54569f542469643ff51a09f38b63c494"
           (:sha256 mod) (sha mod-bytes)))
    (doseq [e ["http_headers_edn_set_begin" "http_headers_edn_set_append"
               "http_headers_edn_set_edn" "http_headers_edn_set_code"
               "http_headers_edn_set_count" "main"]]
      (is (contains? (:exports mod) e)))
    (is (contains? (:imports mod) "kotoba:typed"))
    (let [source-resource (io/resource "kotoba/lang/wasm-packages/src/http_headers_edn_append_set.kotoba")
          source (slurp source-resource)]
      (is (some? source-resource))
      (is (str/includes? source "(defrecord HeaderEdnAccumulator"))
      (doseq [raw-surface ["(record-new" "(record-get" "(:schemas"]]
        (is (not (str/includes? source raw-surface)))))))


(deftest http-edn-set-package-true-set-multi-export-registered
  "T8.3 ADR 0229/0279: EDN kit body in nominal accumulator."
  (let [table (edn/read-string
               (slurp (io/resource "kotoba/lang/wasm-packages/wasm-packages-v1.edn")))
        by-name (into {} (map (juxt :name identity) (:packages table)))
        mod (get by-name :http-edn-set-package)
        sha (fn [bs]
              (let [md (java.security.MessageDigest/getInstance "SHA-256")]
                (.update md bs)
                (format "%064x" (BigInteger. 1 (.digest md)))))]
    (is (some? mod))
    (is (= :wasm-module (:artifact-kind mod)))
    (is (= :kotoba-compiler/v1 (get-in mod [:source :builder])))
    (is (= :kotoba.typed (get-in mod [:source :typed-host])))
    (is (= "366a0ee5e2a34150ddf213e1bf073ed60485ba95d5266f1881fa6f1517cae906"
           (:sha256 mod)))
    (is (= (:sha256 mod)
           (sha (-> (io/resource (:resource mod)) io/input-stream .readAllBytes))))
    (doseq [e ["http_headers_edn_set_begin" "http_headers_edn_set_append"
               "http_headers_edn_set_edn" "http_headers_edn_set_code"
               "http_headers_edn_set_count" "http_request_edn_set"
               "http_result_ok_edn" "http_result_err_edn" "main"]]
      (is (contains? (:exports mod) e)))
    (let [source-resource (io/resource "kotoba/lang/wasm-packages/src/http_edn_set_package.kotoba")
          source (slurp source-resource)]
      (is (some? source-resource))
      (is (str/includes? source "(defrecord HeaderEdnAccumulator"))
      (doseq [raw-surface ["(record-new" "(record-get" "(:schemas"]]
        (is (not (str/includes? source raw-surface)))))))


(deftest http-request-set-record-kit-shaped-package-registered
  "T8.3 ADR 0231/0278: request nominal records + name-set uniqueness."
  (let [table (edn/read-string
               (slurp (io/resource "kotoba/lang/wasm-packages/wasm-packages-v1.edn")))
        by-name (into {} (map (juxt :name identity) (:packages table)))
        mod (get by-name :http-request-set-record)
        sha (fn [bs]
              (let [md (java.security.MessageDigest/getInstance "SHA-256")]
                (.update md bs)
                (format "%064x" (BigInteger. 1 (.digest md)))))]
    (is (some? mod))
    (is (= :wasm-module (:artifact-kind mod)))
    (is (= :kotoba-compiler/v1 (get-in mod [:source :builder])))
    (is (= :kotoba.typed (get-in mod [:source :typed-host])))
    (is (= "ba9b54f779cc60b1b381b56fe20033eec99e7880edd7854649d5ea444f946cbb"
           (:sha256 mod)))
    (is (= (:sha256 mod)
           (sha (-> (io/resource (:resource mod)) io/input-stream .readAllBytes))))
    (doseq [e ["http_req_begin" "http_req_add_header" "http_req_code"
               "http_req_count" "http_req_edn" "main"]]
      (is (contains? (:exports mod) e)))
    (let [source-resource (io/resource "kotoba/lang/wasm-packages/src/http_request_set_record.kotoba")
          source (slurp source-resource)]
      (is (some? source-resource))
      (doseq [declaration ["(defrecord Header" "(defrecord HttpRequest"]]
        (is (str/includes? source declaration)))
      (doseq [raw-surface ["(record-new" "(record-get" "(:schemas"]]
        (is (not (str/includes? source raw-surface)))))))


(deftest http-headers-edn-set-fold-package-registered
  "T8.3 ADR 0233/0279: full headers EDN over nominal records."
  (let [table (edn/read-string
               (slurp (io/resource "kotoba/lang/wasm-packages/wasm-packages-v1.edn")))
        by-name (into {} (map (juxt :name identity) (:packages table)))
        mod (get by-name :http-headers-edn-set-fold)
        sha (fn [bs]
              (let [md (java.security.MessageDigest/getInstance "SHA-256")]
                (.update md bs)
                (format "%064x" (BigInteger. 1 (.digest md)))))]
    (is (some? mod))
    (is (= :wasm-module (:artifact-kind mod)))
    (is (= "83e436b0674ceec5a85cd0a771e42b52d5b4e2a2286d708deee723afdceb8e98" (:sha256 mod)))
    (is (= (:sha256 mod)
           (sha (-> (io/resource (:resource mod)) io/input-stream .readAllBytes))))
    (doseq [e ["http_hdr_begin" "http_hdr_add" "http_hdr_code"
               "http_hdr_count" "http_hdr_edn" "main"]]
      (is (contains? (:exports mod) e)))
    (let [source-resource (io/resource "kotoba/lang/wasm-packages/src/http_headers_edn_set_fold.kotoba")
          source (slurp source-resource)]
      (is (some? source-resource))
      (doseq [declaration ["(defrecord Header" "(defrecord HeaderBag"]]
        (is (str/includes? source declaration)))
      (doseq [raw-surface ["(record-new" "(record-get" "(:schemas"]]
        (is (not (str/includes? source raw-surface)))))))


(deftest http-request-edn-set-record-package-registered
  "T8.3 ADR 0234/0277: full request EDN from nominal records + headers fold."
  (let [table (edn/read-string
               (slurp (io/resource "kotoba/lang/wasm-packages/wasm-packages-v1.edn")))
        by-name (into {} (map (juxt :name identity) (:packages table)))
        mod (get by-name :http-request-edn-set-record)
        sha (fn [bs]
              (let [md (java.security.MessageDigest/getInstance "SHA-256")]
                (.update md bs)
                (format "%064x" (BigInteger. 1 (.digest md)))))]
    (is (some? mod))
    (is (= :wasm-module (:artifact-kind mod)))
    (is (= "ad45dbea1d41849fc5b7301ae51925326ecc365c4fe39d359552c250f8f0d304" (:sha256 mod)))
    (is (= (:sha256 mod)
           (sha (-> (io/resource (:resource mod)) io/input-stream .readAllBytes))))
    (doseq [e ["http_req_begin" "http_req_add_header" "http_req_code"
               "http_req_count" "http_req_edn" "main"]]
      (is (contains? (:exports mod) e)))
    (let [source-resource (io/resource "kotoba/lang/wasm-packages/src/http_request_edn_set_record.kotoba")
          source (slurp source-resource)]
      (is (some? source-resource))
      (doseq [declaration ["(defrecord Header" "(defrecord HttpRequest"]]
        (is (str/includes? source declaration)))
      (doseq [raw-surface ["(record-new" "(record-get" "(:schemas"]]
        (is (not (str/includes? source raw-surface)))))))


(deftest http-result-edn-set-record-package-registered
  "T8.3 ADR 0235/0278: result EDN on nominal records, ok+err."
  (let [table (edn/read-string
               (slurp (io/resource "kotoba/lang/wasm-packages/wasm-packages-v1.edn")))
        by-name (into {} (map (juxt :name identity) (:packages table)))
        mod (get by-name :http-result-edn-set-record)
        sha (fn [bs]
              (let [md (java.security.MessageDigest/getInstance "SHA-256")]
                (.update md bs)
                (format "%064x" (BigInteger. 1 (.digest md)))))]
    (is (some? mod))
    (is (= :wasm-module (:artifact-kind mod)))
    (is (= "4962953a64acd40856e648bddae6e7c64ee017822938edefb65cc9c34219ffe0" (:sha256 mod)))
    (is (= (:sha256 mod)
           (sha (-> (io/resource (:resource mod)) io/input-stream .readAllBytes))))
    (doseq [e ["http_res_ok_begin" "http_res_ok_add_header" "http_res_ok_code"
               "http_res_ok_count" "http_res_ok_edn" "http_res_err_edn" "main"]]
      (is (contains? (:exports mod) e)))
    (let [source-resource (io/resource "kotoba/lang/wasm-packages/src/http_result_edn_set_record.kotoba")
          source (slurp source-resource)]
      (is (some? source-resource))
      (doseq [declaration ["(defrecord Header" "(defrecord HttpResponse"]]
        (is (str/includes? source declaration)))
      (doseq [raw-surface ["(record-new" "(record-get" "(:schemas"]]
        (is (not (str/includes? source raw-surface)))))))


(deftest process-edn-package-registered
  "T8.3 ADR 0238/0239/0280: process EDN on nominal ProcessRequest."
  (let [table (edn/read-string
               (slurp (io/resource "kotoba/lang/wasm-packages/wasm-packages-v1.edn")))
        by-name (into {} (map (juxt :name identity) (:packages table)))
        mod (get by-name :process-edn-package)
        sha (fn [bs]
              (let [md (java.security.MessageDigest/getInstance "SHA-256")]
                (.update md bs)
                (format "%064x" (BigInteger. 1 (.digest md)))))]
    (is (some? mod))
    (is (= :wasm-module (:artifact-kind mod)))
    (is (= "92c971e5d6b59d51c448091d45bf925ee0a87ea7808e9fa78cc697846c7d5917" (:sha256 mod)))
    (is (= (:sha256 mod)
           (sha (-> (io/resource (:resource mod)) io/input-stream .readAllBytes))))
    (doseq [e ["process_req_begin" "process_req_arg" "process_req_code"
               "process_req_argc" "process_req_edn"
               "process_reply_ok_edn" "process_reply_error_edn" "main"]]
      (is (contains? (:exports mod) e)))
    (let [source-resource (io/resource "kotoba/lang/wasm-packages/src/process_edn_package.kotoba")
          source (slurp source-resource)]
      (is (some? source-resource))
      (is (str/includes? source "(defrecord ProcessRequest"))
      (doseq [raw-surface ["(record-new" "(record-get" "(:schemas"]]
        (is (not (str/includes? source raw-surface)))))))


(deftest git-edn-package-registered
  "T8.3 ADR 0240/0241/0280: git EDN on nominal GitRequest."
  (let [table (edn/read-string
               (slurp (io/resource "kotoba/lang/wasm-packages/wasm-packages-v1.edn")))
        by-name (into {} (map (juxt :name identity) (:packages table)))
        mod (get by-name :git-edn-package)
        sha (fn [bs]
              (let [md (java.security.MessageDigest/getInstance "SHA-256")]
                (.update md bs)
                (format "%064x" (BigInteger. 1 (.digest md)))))]
    (is (some? mod))
    (is (= :wasm-module (:artifact-kind mod)))
    (is (= "b0c8e8581f2d82b9f87beb0781708e6304f3bb91741eff70568f4e4104ef4445" (:sha256 mod)))
    (is (= (:sha256 mod)
           (sha (-> (io/resource (:resource mod)) io/input-stream .readAllBytes))))
    (doseq [e ["git_req_begin" "git_req_arg" "git_req_code"
               "git_req_argc" "git_req_edn"
               "git_reply_ok_edn" "git_reply_error_edn" "main"]]
      (is (contains? (:exports mod) e)))
    (let [source-resource (io/resource "kotoba/lang/wasm-packages/src/git_edn_package.kotoba")
          source (slurp source-resource)]
      (is (some? source-resource))
      (is (str/includes? source "(defrecord GitRequest"))
      (doseq [raw-surface ["(record-new" "(record-get" "(:schemas"]]
        (is (not (str/includes? source raw-surface)))))))


(deftest scoped-fs-edn-package-registered
  "T8.3 ADR 0243: scoped-fs kit fixed-depth EDN request+reply package."
  (let [table (edn/read-string
               (slurp (io/resource "kotoba/lang/wasm-packages/wasm-packages-v1.edn")))
        by-name (into {} (map (juxt :name identity) (:packages table)))
        mod (get by-name :scoped-fs-edn-package)
        sha (fn [bs]
              (let [md (java.security.MessageDigest/getInstance "SHA-256")]
                (.update md bs)
                (format "%064x" (BigInteger. 1 (.digest md)))))]
    (is (some? mod))
    (is (= :wasm-module (:artifact-kind mod)))
    (is (= "c5a52bd3a62c53b21d3411bc09125a2c4355f7a0338e01b0dadd8ae3d1156274" (:sha256 mod)))
    (is (= (:sha256 mod)
           (sha (-> (io/resource (:resource mod)) io/input-stream .readAllBytes))))
    (doseq [e ["fs_req_read_edn" "fs_req_write_edn"
               "fs_reply_content_edn" "fs_reply_written_edn" "fs_reply_error_edn" "main"]]
      (is (contains? (:exports mod) e)))
    (is (some? (io/resource "kotoba/lang/wasm-packages/src/scoped_fs_edn_package.kotoba")))))

(deftest http-headers-names-add-component-true-set-registered
  "T8.3 ADR 0225: Component twin true-set name list (element-bound equality)."
  (let [table (edn/read-string
               (slurp (io/resource "kotoba/lang/wasm-packages/wasm-packages-v1.edn")))
        by-name (into {} (map (juxt :name identity) (:packages table)))
        comp (get by-name :http-headers-names-add-component)
        comp-bytes (-> (io/resource (:resource comp)) io/input-stream .readAllBytes)
        sha (fn [^bytes b]
              (let [md (java.security.MessageDigest/getInstance "SHA-256")]
                (.update md b)
                (apply str (map #(format "%02x" %) (.digest md)))))]
    (is (some? comp))
    (is (= :wasm-component (:artifact-kind comp)))
    (is (= :kotoba-component/headers-names-add
           (get-in comp [:source :component-lowering])))
    (is (= "939b4bfdff19bd17290a8a6b6e4d123baf727a9306c45625af50756e167c24fd"
           (:sha256 comp) (sha comp-bytes)))
    (is (contains? (:exports comp) "headers-names-add"))
    (is (some? (io/resource "kotoba/lang/wasm-packages/src/http_headers_names_add.kotoba")))))

(deftest http-typed-string-headers-set-ok-live-browser-host-optional
  (let [host (or (System/getenv "KOTOBA_BROWSER_HOST")
                 (let [cand (io/file ".." "compiler" "runtime" "browser-host.mjs")]
                   (when (.exists cand) (.getAbsolutePath cand)))
                 (let [cand (io/file "/Users/junkawasaki/github/com-junkawasaki/orgs/kotoba-lang/compiler/runtime/browser-host.mjs")]
                   (when (.exists cand) (.getAbsolutePath cand))))
        wasm (.getAbsolutePath
              (io/file "resources/kotoba/lang/wasm-packages/http-headers-set-ok-v1.wasm"))]
    (if-not (and host (.exists (io/file host)) (.exists (io/file wasm)))
      (is true "skip typed live when browser-host unavailable")
      (let [script (str "import { readFileSync } from 'fs';"
                        "import { instantiateKotoba } from "
                        (pr-str (str "file://" host))
                        ";"
                        "const h=await instantiateKotoba(readFileSync(" (pr-str wasm) "));"
                        "const v=h.instance.exports.main();"
                        "if(v!==-3647n){console.error('got',v); process.exit(2);}"
                        "console.log(JSON.stringify([-3647]));")
            pb (doto (ProcessBuilder. ["node" "--input-type=module" "-e" script])
                 (.redirectErrorStream true))
            p (.start pb)
            out (slurp (.getInputStream p))
            code (.waitFor p)]
        (is (zero? code) (str "browser-host live failed: " out))
        (is (= [-3647] (edn/read-string out)))))))

(deftest http-typed-string-response-ok-package-registered
  (let [table (edn/read-string
               (slurp (io/resource "kotoba/lang/wasm-packages/wasm-packages-v1.edn")))
        by-name (into {} (map (juxt :name identity) (:packages table)))
        mod (get by-name :http-response-ok)
        mod-bytes (-> (io/resource (:resource mod)) io/input-stream .readAllBytes)
        sha (fn [^bytes b]
              (let [md (java.security.MessageDigest/getInstance "SHA-256")]
                (.update md b)
                (apply str (map #(format "%02x" %) (.digest md)))))]
    (is (some? mod))
    (is (= :wasm-module (:artifact-kind mod)))
    (is (= :kotoba-compiler/v1 (get-in mod [:source :builder])))
    (is (= :kotoba.typed (get-in mod [:source :typed-host])))
    (is (= (:sha256 mod) (sha mod-bytes)))
    (doseq [e ["http_status_ok" "http_response_ok" "main"]]
      (is (contains? (:exports mod) e)))
    (is (contains? (:imports mod) "kotoba:typed"))
    (is (some? (io/resource "kotoba/lang/wasm-packages/src/http_response_ok.kotoba")))))

(deftest http-typed-string-response-ok-live-browser-host-optional
  (let [host (or (System/getenv "KOTOBA_BROWSER_HOST")
                 (let [cand (io/file ".." "compiler" "runtime" "browser-host.mjs")]
                   (when (.exists cand) (.getAbsolutePath cand)))
                 (let [cand (io/file "/Users/junkawasaki/github/com-junkawasaki/orgs/kotoba-lang/compiler/runtime/browser-host.mjs")]
                   (when (.exists cand) (.getAbsolutePath cand))))
        wasm (.getAbsolutePath
              (io/file "resources/kotoba/lang/wasm-packages/http-response-ok-v1.wasm"))]
    (if-not (and host (.exists (io/file host)) (.exists (io/file wasm)))
      (is true "skip typed live when browser-host unavailable")
      (let [script (str "import { readFileSync } from 'fs';"
                        "import { instantiateKotoba } from "
                        (pr-str (str "file://" host))
                        ";"
                        "const h=await instantiateKotoba(readFileSync(" (pr-str wasm) "));"
                        "const v=h.instance.exports.main();"
                        "if(v!==-1012n){console.error('got',v); process.exit(2);}"
                        "console.log(JSON.stringify([-1012]));")
            pb (doto (ProcessBuilder. ["node" "--input-type=module" "-e" script])
                 (.redirectErrorStream true))
            p (.start pb)
            out (slurp (.getInputStream p))
            code (.waitFor p)]
        (is (zero? code) (str "browser-host live failed: " out))
        (is (= [-1012] (edn/read-string out)))))))

(deftest http-typed-string-error-result-ok-package-registered
  (let [table (edn/read-string
               (slurp (io/resource "kotoba/lang/wasm-packages/wasm-packages-v1.edn")))
        by-name (into {} (map (juxt :name identity) (:packages table)))
        mod (get by-name :http-error-result-ok)
        mod-bytes (-> (io/resource (:resource mod)) io/input-stream .readAllBytes)
        sha (fn [^bytes b]
              (let [md (java.security.MessageDigest/getInstance "SHA-256")]
                (.update md b)
                (apply str (map #(format "%02x" %) (.digest md)))))]
    (is (some? mod))
    (is (= :wasm-module (:artifact-kind mod)))
    (is (= :kotoba-compiler/v1 (get-in mod [:source :builder])))
    (is (= :kotoba.typed (get-in mod [:source :typed-host])))
    (is (= (:sha256 mod) (sha mod-bytes)))
    (doseq [e ["http_error_ok" "http_result_arm_ok" "main"]]
      (is (contains? (:exports mod) e)))
    (is (contains? (:imports mod) "kotoba:typed"))
    (is (some? (io/resource "kotoba/lang/wasm-packages/src/http_error_result_ok.kotoba")))))

(deftest http-typed-string-error-result-ok-live-browser-host-optional
  (let [host (or (System/getenv "KOTOBA_BROWSER_HOST")
                 (let [cand (io/file ".." "compiler" "runtime" "browser-host.mjs")]
                   (when (.exists cand) (.getAbsolutePath cand)))
                 (let [cand (io/file "/Users/junkawasaki/github/com-junkawasaki/orgs/kotoba-lang/compiler/runtime/browser-host.mjs")]
                   (when (.exists cand) (.getAbsolutePath cand))))
        wasm (.getAbsolutePath
              (io/file "resources/kotoba/lang/wasm-packages/http-error-result-ok-v1.wasm"))]
    (if-not (and host (.exists (io/file host)) (.exists (io/file wasm)))
      (is true "skip typed live when browser-host unavailable")
      (let [script (str "import { readFileSync } from 'fs';"
                        "import { instantiateKotoba } from "
                        (pr-str (str "file://" host))
                        ";"
                        "const h=await instantiateKotoba(readFileSync(" (pr-str wasm) "));"
                        "const v=h.instance.exports.main();"
                        "if(v!==-13501n){console.error('got',v); process.exit(2);}"
                        "console.log(JSON.stringify([-13501]));")
            pb (doto (ProcessBuilder. ["node" "--input-type=module" "-e" script])
                 (.redirectErrorStream true))
            p (.start pb)
            out (slurp (.getInputStream p))
            code (.waitFor p)]
        (is (zero? code) (str "browser-host live failed: " out))
        (is (= [-13501] (edn/read-string out)))))))

(deftest http-typed-packages-pure-component-reemit-registered
  "ADR 0199: pure Canonical Components for url/request/response/error packages.
  Twins of typed-host wasm modules; no kotoba:typed import."
  (let [table (edn/read-string
               (slurp (io/resource "kotoba/lang/wasm-packages/wasm-packages-v1.edn")))
        by-name (into {} (map (juxt :name identity) (:packages table)))
        sha (fn [^bytes b]
              (let [md (java.security.MessageDigest/getInstance "SHA-256")]
                (.update md b)
                (apply str (map #(format "%02x" %) (.digest md)))))
        check
        (fn [mod-name comp-name]
          (let [mod (get by-name mod-name)
                comp (get by-name comp-name)
                mod-bytes (-> (io/resource (:resource mod)) io/input-stream .readAllBytes)
                comp-bytes (-> (io/resource (:resource comp)) io/input-stream .readAllBytes)]
            (is (some? mod) (str mod-name))
            (is (some? comp) (str comp-name))
            (is (= :wasm-module (:artifact-kind mod)))
            (is (= :wasm-component (:artifact-kind comp)))
            (is (= :kotoba-compiler/v1 (get-in mod [:source :builder])))
            (is (= :kotoba-compiler/v1 (get-in comp [:source :builder])))
            (is (= :kotoba.typed (get-in mod [:source :typed-host])))
            (is (nil? (get-in comp [:source :typed-host])))
            (is (= :kotoba-component/canonical
                   (get-in comp [:source :component-lowering])))
            (is (contains? (:imports mod) "kotoba:typed"))
            (is (nil? (:imports comp)))
            (is (= (:sha256 mod) (sha mod-bytes)))
            (is (= (:sha256 comp) (sha comp-bytes)))))]
    (check :http-url-ok :http-url-ok-component)
    (check :http-post-request-ok :http-post-request-ok-component)
    (check :http-response-ok :http-response-ok-component)
    (check :http-error-result-ok :http-error-result-ok-component)
    (check :http-header-name-ok :http-header-name-ok-component)
    (check :http-header-value-ok :http-header-value-ok-component)
    (check :http-headers-set-ok :http-headers-set-ok-component)
    (check :http-request-pack :http-request-pack-component)
    (check :http-result-pack :http-result-pack-component)
    (check :secret-name-ok :secret-name-ok-component)
    (check :fs-path-ok :fs-path-ok-component)))

(deftest http-typed-packages-pure-component-live-main
  "ADR 0199–0207: wasmtime Component live vectors for main() on pure re-emits."
  (let [run (fn [resource expected]
              (let [path (.getAbsolutePath
                          (io/file "resources" resource))
                    pb (ProcessBuilder. ["wasmtime" "run" "--invoke" "main()" path])
                    p (.start pb)
                    out (str/trim (slurp (.getInputStream p)))
                    err (slurp (.getErrorStream p))
                    code (.waitFor p)]
                (is (zero? code) (str resource " wasmtime failed: " err out))
                (is (= expected out) (str resource " main vector"))))]
    (run "kotoba/lang/wasm-packages/http-url-ok-v1.component.wasm" "-130")
    (run "kotoba/lang/wasm-packages/http-post-request-ok-v1.component.wasm" "-13406")
    (run "kotoba/lang/wasm-packages/http-response-ok-v1.component.wasm" "-1012")
    (run "kotoba/lang/wasm-packages/http-error-result-ok-v1.component.wasm" "-13501")
    (run "kotoba/lang/wasm-packages/http-header-name-ok-v1.component.wasm" "-130")
    (run "kotoba/lang/wasm-packages/http-header-value-ok-v1.component.wasm" "-3036")
    (run "kotoba/lang/wasm-packages/http-headers-set-ok-v1.component.wasm" "-3647")
    (run "kotoba/lang/wasm-packages/http-request-pack-v1.component.wasm" "-13467")
    (run "kotoba/lang/wasm-packages/http-result-pack-v1.component.wasm" "-12061")
    (run "kotoba/lang/wasm-packages/secret-name-ok-v1.component.wasm" "-130")
    (run "kotoba/lang/wasm-packages/fs-path-ok-v1.component.wasm" "-15470")))

(deftest http-typed-string-result-pack-package-registered
  (let [table (edn/read-string
               (slurp (io/resource "kotoba/lang/wasm-packages/wasm-packages-v1.edn")))
        by-name (into {} (map (juxt :name identity) (:packages table)))
        mod (get by-name :http-result-pack)
        mod-bytes (-> (io/resource (:resource mod)) io/input-stream .readAllBytes)
        sha (fn [^bytes b]
              (let [md (java.security.MessageDigest/getInstance "SHA-256")]
                (.update md b)
                (apply str (map #(format "%02x" %) (.digest md)))))]
    (is (some? mod))
    (is (= :wasm-module (:artifact-kind mod)))
    (is (= :kotoba-compiler/v1 (get-in mod [:source :builder])))
    (is (= :kotoba.typed (get-in mod [:source :typed-host])))
    (is (= (:sha256 mod) (sha mod-bytes)))
    (doseq [e ["http_result_begin" "http_result_status" "http_result_headers"
               "http_result_body" "http_result_code" "http_result_message"
               "http_result_retryable" "http_result_end" "main"]]
      (is (contains? (:exports mod) e)))
    (is (contains? (:imports mod) "kotoba:typed"))
    (is (some? (io/resource "kotoba/lang/wasm-packages/src/http_result_pack.kotoba")))))

(deftest http-typed-string-result-pack-live-browser-host-optional
  (let [host (or (System/getenv "KOTOBA_BROWSER_HOST")
                 (let [cand (io/file ".." "compiler" "runtime" "browser-host.mjs")]
                   (when (.exists cand) (.getAbsolutePath cand)))
                 (let [cand (io/file "/Users/junkawasaki/github/com-junkawasaki/orgs/kotoba-lang/compiler/runtime/browser-host.mjs")]
                   (when (.exists cand) (.getAbsolutePath cand))))
        wasm (.getAbsolutePath
              (io/file "resources/kotoba/lang/wasm-packages/http-result-pack-v1.wasm"))]
    (if-not (and host (.exists (io/file host)) (.exists (io/file wasm)))
      (is true "skip typed live when browser-host unavailable")
      (let [script (str "import { readFileSync } from 'fs';"
                        "import { instantiateKotoba } from "
                        (pr-str (str "file://" host))
                        ";"
                        "const h=await instantiateKotoba(readFileSync(" (pr-str wasm) "));"
                        "const v=h.instance.exports.main();"
                        "if(v!==-12061n){console.error('got',v); process.exit(2);}"
                        "console.log(JSON.stringify([-12061]));")
            pb (doto (ProcessBuilder. ["node" "--input-type=module" "-e" script])
                 (.redirectErrorStream true))
            p (.start pb)
            out (slurp (.getInputStream p))
            code (.waitFor p)]
        (is (zero? code) (str "browser-host live failed: " out))
        (is (= [-12061] (edn/read-string out)))))))

(deftest http-typed-string-request-pack-package-registered
  (let [table (edn/read-string
               (slurp (io/resource "kotoba/lang/wasm-packages/wasm-packages-v1.edn")))
        by-name (into {} (map (juxt :name identity) (:packages table)))
        mod (get by-name :http-request-pack)
        mod-bytes (-> (io/resource (:resource mod)) io/input-stream .readAllBytes)
        sha (fn [^bytes b]
              (let [md (java.security.MessageDigest/getInstance "SHA-256")]
                (.update md b)
                (apply str (map #(format "%02x" %) (.digest md)))))]
    (is (some? mod))
    (is (= :wasm-module (:artifact-kind mod)))
    (is (= :kotoba-compiler/v1 (get-in mod [:source :builder])))
    (is (= :kotoba.typed (get-in mod [:source :typed-host])))
    (is (= (:sha256 mod) (sha mod-bytes)))
    (doseq [e ["http_request_begin" "http_request_url" "http_request_headers"
               "http_request_body" "http_request_end" "main"]]
      (is (contains? (:exports mod) e)))
    (is (contains? (:imports mod) "kotoba:typed"))
    (is (some? (io/resource "kotoba/lang/wasm-packages/src/http_request_pack.kotoba")))))


(deftest http-request-edn-package-registered
  (let [table (edn/read-string
               (slurp (io/resource "kotoba/lang/wasm-packages/wasm-packages-v1.edn")))
        by-name (into {} (map (juxt :name identity) (:packages table)))
        mod (get by-name :http-request-edn)
        mod-bytes (-> (io/resource (:resource mod)) io/input-stream .readAllBytes)
        sha (fn [^bytes b]
              (let [md (java.security.MessageDigest/getInstance "SHA-256")]
                (.update md b)
                (apply str (map #(format "%02x" %) (.digest md)))))]
    (is (some? mod))
    (is (= :wasm-module (:artifact-kind mod)))
    (is (= :kotoba-compiler/v1 (get-in mod [:source :builder])))
    (is (nil? (get-in mod [:source :typed-host])))
    (is (= (:sha256 mod) (sha mod-bytes)))
    (doseq [e ["edn_quoted" "http_header_edn" "headers_edn_empty" "headers_edn_append"
               "headers_edn_has_name"
               "http_request_edn0" "http_request_edn"
               "http_result_ok_edn" "http_result_err_edn" "main"]]
      (is (contains? (:exports mod) e)))
    (is (some? (io/resource "kotoba/lang/wasm-packages/src/http_request_edn.kotoba")))))


(deftest http-headers-edn-empty-component-registered
  (let [table (edn/read-string
               (slurp (io/resource "kotoba/lang/wasm-packages/wasm-packages-v1.edn")))
        by-name (into {} (map (juxt :name identity) (:packages table)))
        mod (get by-name :http-headers-edn-empty)
        comp (get by-name :http-headers-edn-empty-component)
        sha (fn [^bytes b]
              (let [md (java.security.MessageDigest/getInstance "SHA-256")]
                (.update md b)
                (apply str (map #(format "%02x" %) (.digest md)))))]
    (is (some? mod))
    (is (some? comp))
    (is (= :wasm-module (:artifact-kind mod)))
    (is (= :wasm-component (:artifact-kind comp)))
    (is (= :kotoba-component/string-expression (get-in comp [:source :component-lowering])))
    (is (= (:sha256 mod) (sha (-> (io/resource (:resource mod)) io/input-stream .readAllBytes))))
    (is (= (:sha256 comp) (sha (-> (io/resource (:resource comp)) io/input-stream .readAllBytes))))
    (is (contains? (:exports mod) "headers_edn_empty"))
    (is (contains? (:exports comp) "headers-edn-empty"))))

(deftest http-header-edn-trust-component-registered
  (let [table (edn/read-string
               (slurp (io/resource "kotoba/lang/wasm-packages/wasm-packages-v1.edn")))
        by-name (into {} (map (juxt :name identity) (:packages table)))
        mod (get by-name :http-header-edn-trust)
        comp (get by-name :http-header-edn-trust-component)
        sha (fn [^bytes b]
              (let [md (java.security.MessageDigest/getInstance "SHA-256")]
                (.update md b)
                (apply str (map #(format "%02x" %) (.digest md)))))]
    (is (some? mod))
    (is (some? comp))
    (is (= :wasm-component (:artifact-kind comp)))
    (is (= :kotoba-component/string-expression (get-in comp [:source :component-lowering])))
    (is (= (:sha256 mod) (sha (-> (io/resource (:resource mod)) io/input-stream .readAllBytes))))
    (is (= (:sha256 comp) (sha (-> (io/resource (:resource comp)) io/input-stream .readAllBytes))))
    (is (contains? (:exports mod) "http_header_edn_trust"))
    (is (contains? (:exports comp) "http-header-edn-trust"))))

(deftest http-edn-trust-package-component-registered
  "T8.3 ADR 0213: multi-export string-expression-package EDN trust path."
  (let [table (edn/read-string
               (slurp (io/resource "kotoba/lang/wasm-packages/wasm-packages-v1.edn")))
        by-name (into {} (map (juxt :name identity) (:packages table)))
        mod (get by-name :http-edn-trust-package)
        comp (get by-name :http-edn-trust-package-component)
        sha (fn [^bytes b]
              (let [md (java.security.MessageDigest/getInstance "SHA-256")]
                (.update md b)
                (apply str (map #(format "%02x" %) (.digest md)))))]
    (is (some? mod))
    (is (some? comp))
    (is (= :wasm-module (:artifact-kind mod)))
    (is (= :wasm-component (:artifact-kind comp)))
    (is (= :kotoba-component/string-expression-package
           (get-in comp [:source :component-lowering])))
    (is (= (:sha256 mod) (sha (-> (io/resource (:resource mod)) io/input-stream .readAllBytes))))
    (is (= (:sha256 comp) (sha (-> (io/resource (:resource comp)) io/input-stream .readAllBytes))))
    (doseq [e ["headers_edn_empty" "http_header_edn_trust" "headers_edn_one"
               "http_request_edn_trust" "http_result_ok_edn_trust"
               "http_result_err_edn_trust"]]
      (is (contains? (:exports mod) e)))
    (doseq [e ["headers-edn-empty" "http-header-edn-trust" "headers-edn-one"
               "http-request-edn-trust" "http-result-ok-edn-trust"
               "http-result-err-edn-trust"]]
      (is (contains? (:exports comp) e)))
    (is (some? (io/resource "kotoba/lang/wasm-packages/src/http_edn_trust_package.kotoba")))))

(deftest http-edn-quoted-component-registered
  "T8.3 ADR 0214: reject-path edn_quoted Component first slice."
  (let [table (edn/read-string
               (slurp (io/resource "kotoba/lang/wasm-packages/wasm-packages-v1.edn")))
        by-name (into {} (map (juxt :name identity) (:packages table)))
        mod (get by-name :http-edn-quoted)
        comp (get by-name :http-edn-quoted-component)
        sha (fn [^bytes b]
              (let [md (java.security.MessageDigest/getInstance "SHA-256")]
                (.update md b)
                (apply str (map #(format "%02x" %) (.digest md)))))]
    (is (some? mod))
    (is (some? comp))
    (is (= :wasm-module (:artifact-kind mod)))
    (is (= :wasm-component (:artifact-kind comp)))
    (is (= :kotoba-component/edn-quoted
           (get-in comp [:source :component-lowering])))
    (is (= (:sha256 mod) (sha (-> (io/resource (:resource mod)) io/input-stream .readAllBytes))))
    (is (= (:sha256 comp) (sha (-> (io/resource (:resource comp)) io/input-stream .readAllBytes))))
    (is (contains? (:exports mod) "edn_quoted"))
    (is (contains? (:exports comp) "edn-quoted"))
    (is (some? (io/resource "kotoba/lang/wasm-packages/src/http_edn_quoted.kotoba")))))

(deftest http-header-edn-component-registered
  "T8.3 ADR 0215: reject-path http_header_edn composition on edn_quoted."
  (let [table (edn/read-string
               (slurp (io/resource "kotoba/lang/wasm-packages/wasm-packages-v1.edn")))
        by-name (into {} (map (juxt :name identity) (:packages table)))
        mod (get by-name :http-header-edn)
        comp (get by-name :http-header-edn-component)
        sha (fn [^bytes b]
              (let [md (java.security.MessageDigest/getInstance "SHA-256")]
                (.update md b)
                (apply str (map #(format "%02x" %) (.digest md)))))]
    (is (some? mod))
    (is (some? comp))
    (is (= :wasm-module (:artifact-kind mod)))
    (is (= :wasm-component (:artifact-kind comp)))
    (is (= :kotoba-component/http-header-edn
           (get-in comp [:source :component-lowering])))
    (is (= (:sha256 mod) (sha (-> (io/resource (:resource mod)) io/input-stream .readAllBytes))))
    (is (= (:sha256 comp) (sha (-> (io/resource (:resource comp)) io/input-stream .readAllBytes))))
    (is (contains? (:exports mod) "http_header_edn"))
    (is (contains? (:exports comp) "http-header-edn"))
    (is (some? (io/resource "kotoba/lang/wasm-packages/src/http_header_edn.kotoba")))))

(deftest http-headers-edn-append-component-registered
  "T8.3 ADR 0216/0227: multi-header append + map-element-bound name uniqueness."
  (let [table (edn/read-string
               (slurp (io/resource "kotoba/lang/wasm-packages/wasm-packages-v1.edn")))
        by-name (into {} (map (juxt :name identity) (:packages table)))
        mod (get by-name :http-headers-edn-append)
        comp (get by-name :http-headers-edn-append-component)
        sha (fn [^bytes b]
              (let [md (java.security.MessageDigest/getInstance "SHA-256")]
                (.update md b)
                (apply str (map #(format "%02x" %) (.digest md)))))]
    (is (some? mod))
    (is (some? comp))
    (is (= :wasm-module (:artifact-kind mod)))
    (is (= :wasm-component (:artifact-kind comp)))
    (is (= :kotoba-component/headers-edn-append
           (get-in comp [:source :component-lowering])))
    (is (= (:sha256 mod) (sha (-> (io/resource (:resource mod)) io/input-stream .readAllBytes))))
    (is (= (:sha256 comp) (sha (-> (io/resource (:resource comp)) io/input-stream .readAllBytes))))
    (is (= "ed8d6a1f39dca9d090a2fecb8c912776d2fb3ee03109967c9c1b0d9cb20b5833"
           (:sha256 comp)))
    (is (contains? (:exports mod) "headers_edn_append"))
    (is (contains? (:exports comp) "headers-edn-append"))
    (is (some? (io/resource "kotoba/lang/wasm-packages/src/http_headers_edn_append.kotoba")))))

(deftest http-result-err-edn-component-registered
  "T8.3 ADR 0217: result error arm reject-path on edn_quoted."
  (let [table (edn/read-string
               (slurp (io/resource "kotoba/lang/wasm-packages/wasm-packages-v1.edn")))
        by-name (into {} (map (juxt :name identity) (:packages table)))
        mod (get by-name :http-result-err-edn)
        comp (get by-name :http-result-err-edn-component)
        sha (fn [^bytes b]
              (let [md (java.security.MessageDigest/getInstance "SHA-256")]
                (.update md b)
                (apply str (map #(format "%02x" %) (.digest md)))))]
    (is (some? mod))
    (is (some? comp))
    (is (= :wasm-module (:artifact-kind mod)))
    (is (= :wasm-component (:artifact-kind comp)))
    (is (= :kotoba-component/http-result-err-edn
           (get-in comp [:source :component-lowering])))
    (is (= (:sha256 mod) (sha (-> (io/resource (:resource mod)) io/input-stream .readAllBytes))))
    (is (= (:sha256 comp) (sha (-> (io/resource (:resource comp)) io/input-stream .readAllBytes))))
    (is (contains? (:exports mod) "http_result_err_edn"))
    (is (contains? (:exports comp) "http-result-err-edn"))
    (is (some? (io/resource "kotoba/lang/wasm-packages/src/http_result_err_edn.kotoba")))))

(deftest http-result-ok-edn-component-registered
  "T8.3 ADR 0218: result ok arm reject-path on edn_quoted."
  (let [table (edn/read-string
               (slurp (io/resource "kotoba/lang/wasm-packages/wasm-packages-v1.edn")))
        by-name (into {} (map (juxt :name identity) (:packages table)))
        mod (get by-name :http-result-ok-edn)
        comp (get by-name :http-result-ok-edn-component)
        sha (fn [^bytes b]
              (let [md (java.security.MessageDigest/getInstance "SHA-256")]
                (.update md b)
                (apply str (map #(format "%02x" %) (.digest md)))))]
    (is (some? mod))
    (is (some? comp))
    (is (= :wasm-module (:artifact-kind mod)))
    (is (= :wasm-component (:artifact-kind comp)))
    (is (= :kotoba-component/http-result-ok-edn
           (get-in comp [:source :component-lowering])))
    (is (= (:sha256 mod) (sha (-> (io/resource (:resource mod)) io/input-stream .readAllBytes))))
    (is (= (:sha256 comp) (sha (-> (io/resource (:resource comp)) io/input-stream .readAllBytes))))
    (is (contains? (:exports mod) "http_result_ok_edn"))
    (is (contains? (:exports comp) "http-result-ok-edn"))
    (is (some? (io/resource "kotoba/lang/wasm-packages/src/http_result_ok_edn.kotoba")))))

(deftest http-request-edn0-component-registered
  "T8.3 ADR 0219: 0-header request EDN reject-path on edn_quoted."
  (let [table (edn/read-string
               (slurp (io/resource "kotoba/lang/wasm-packages/wasm-packages-v1.edn")))
        by-name (into {} (map (juxt :name identity) (:packages table)))
        mod (get by-name :http-request-edn0)
        comp (get by-name :http-request-edn0-component)
        sha (fn [^bytes b]
              (let [md (java.security.MessageDigest/getInstance "SHA-256")]
                (.update md b)
                (apply str (map #(format "%02x" %) (.digest md)))))]
    (is (some? mod))
    (is (some? comp))
    (is (= :wasm-module (:artifact-kind mod)))
    (is (= :wasm-component (:artifact-kind comp)))
    (is (= :kotoba-component/http-request-edn0
           (get-in comp [:source :component-lowering])))
    (is (= (:sha256 mod) (sha (-> (io/resource (:resource mod)) io/input-stream .readAllBytes))))
    (is (= (:sha256 comp) (sha (-> (io/resource (:resource comp)) io/input-stream .readAllBytes))))
    (is (contains? (:exports mod) "http_request_edn0"))
    (is (contains? (:exports comp) "http-request-edn0"))
    (is (some? (io/resource "kotoba/lang/wasm-packages/src/http_request_edn0.kotoba")))))


(deftest http-request-edn-reject-component-registered
  "T8.3 ADR 0220: multi-header request EDN reject-path Component."
  (let [table (edn/read-string
               (slurp (io/resource "kotoba/lang/wasm-packages/wasm-packages-v1.edn")))
        by-name (into {} (map (juxt :name identity) (:packages table)))
        mod (get by-name :http-request-edn-reject)
        comp (get by-name :http-request-edn-reject-component)
        sha (fn [^bytes b]
              (let [md (java.security.MessageDigest/getInstance "SHA-256")]
                (.update md b)
                (apply str (map #(format "%02x" %) (.digest md)))))]
    (is (some? mod))
    (is (some? comp))
    (is (= :wasm-module (:artifact-kind mod)))
    (is (= :wasm-component (:artifact-kind comp)))
    (is (= :kotoba-component/http-request-edn
           (get-in comp [:source :component-lowering])))
    (is (= (:sha256 mod) (sha (-> (io/resource (:resource mod)) io/input-stream .readAllBytes))))
    (is (= (:sha256 comp) (sha (-> (io/resource (:resource comp)) io/input-stream .readAllBytes))))
    (is (contains? (:exports mod) "http_request_edn"))
    (is (contains? (:exports comp) "http-request-edn"))
    (is (some? (io/resource "kotoba/lang/wasm-packages/src/http_request_edn_only.kotoba")))))

(deftest http-edn-reject-package-component-registered
  "T8.3 ADR 0221/0226/0227/0230: multi-export reject kit multi-ns + element-bound + names-add."
  (let [table (edn/read-string
               (slurp (io/resource "kotoba/lang/wasm-packages/wasm-packages-v1.edn")))
        by-name (into {} (map (juxt :name identity) (:packages table)))
        mod (get by-name :http-edn-reject-package)
        comp (get by-name :http-edn-reject-package-component)
        sha (fn [^bytes b]
              (let [md (java.security.MessageDigest/getInstance "SHA-256")]
                (.update md b)
                (apply str (map #(format "%02x" %) (.digest md)))))]
    (is (some? mod))
    (is (some? comp))
    (is (= :wasm-module (:artifact-kind mod)))
    (is (= :wasm-component (:artifact-kind comp)))
    (is (= :kotoba-component/http-edn-reject-package
           (get-in comp [:source :component-lowering])))
    (is (= (:sha256 mod) (sha (-> (io/resource (:resource mod)) io/input-stream .readAllBytes))))
    (is (= (:sha256 comp) (sha (-> (io/resource (:resource comp)) io/input-stream .readAllBytes))))
    (is (= "a11a96f6cc2d13d93c3089a0b88381888b5344db4ba91dcddb810d251630456b"
           (:sha256 comp)))
    (doseq [e ["headers_edn_empty" "headers_edn_append" "headers_names_add" "http_request_edn"
               "http_result_ok_edn" "http_result_err_edn"]]
      (is (contains? (:exports mod) e)))
    (doseq [e ["headers-edn-empty" "headers-edn-append" "headers-names-add"
               "http-request-edn" "http-result-ok-edn" "http-result-err-edn"]]
      (is (contains? (:exports comp) e)))
    (is (some? (io/resource "kotoba/lang/wasm-packages/src/http_edn_reject_package.kotoba")))))

(deftest http-typed-string-request-pack-live-browser-host-optional
  (let [host (or (System/getenv "KOTOBA_BROWSER_HOST")
                 (let [cand (io/file ".." "compiler" "runtime" "browser-host.mjs")]
                   (when (.exists cand) (.getAbsolutePath cand)))
                 (let [cand (io/file "/Users/junkawasaki/github/com-junkawasaki/orgs/kotoba-lang/compiler/runtime/browser-host.mjs")]
                   (when (.exists cand) (.getAbsolutePath cand))))
        wasm (.getAbsolutePath
              (io/file "resources/kotoba/lang/wasm-packages/http-request-pack-v1.wasm"))]
    (if-not (and host (.exists (io/file host)) (.exists (io/file wasm)))
      (is true "skip typed live when browser-host unavailable")
      (let [script (str "import { readFileSync } from 'fs';"
                        "import { instantiateKotoba } from "
                        (pr-str (str "file://" host))
                        ";"
                        "const h=await instantiateKotoba(readFileSync(" (pr-str wasm) "));"
                        "const v=h.instance.exports.main();"
                        "if(v!==-13467n){console.error('got',v); process.exit(2);}"
                        "console.log(JSON.stringify([-13467]));")
            pb (doto (ProcessBuilder. ["node" "--input-type=module" "-e" script])
                 (.redirectErrorStream true))
            p (.start pb)
            out (slurp (.getInputStream p))
            code (.waitFor p)]
        (is (zero? code) (str "browser-host live failed: " out))
        (is (= [-13467] (edn/read-string out)))))))

(deftest http-pure-memory-scan-package-registered
  "ADR 0194: pure hand-WAT memory-scan one-shot + Component."
  (let [table (edn/read-string
               (slurp (io/resource "kotoba/lang/wasm-packages/wasm-packages-v1.edn")))
        by-name (into {} (map (juxt :name identity) (:packages table)))
        mod (get by-name :http-memory-scan)
        comp (get by-name :http-memory-scan-component)
        mod-bytes (-> (io/resource (:resource mod)) io/input-stream .readAllBytes)
        comp-bytes (-> (io/resource (:resource comp)) io/input-stream .readAllBytes)
        sha (fn [^bytes b]
              (let [md (java.security.MessageDigest/getInstance "SHA-256")]
                (.update md b)
                (apply str (map #(format "%02x" %) (.digest md)))))]
    (is (some? mod))
    (is (some? comp))
    (is (= :wasm-module (:artifact-kind mod)))
    (is (= :wasm-component (:artifact-kind comp)))
    (is (= :hand-wat/v1 (get-in mod [:source :builder])))
    (is (nil? (get-in mod [:source :typed-host])))
    (is (= (:sha256 mod) (sha mod-bytes)))
    (is (= (:sha256 comp) (sha comp-bytes)))
    (doseq [e ["http_request_scan" "http_response_scan" "http_error_scan" "http_result_arm_ok"]]
      (is (contains? (:exports mod) e)))
    (is (some? (io/resource "kotoba/lang/wasm-packages/src/http_memory_scan.wat")))))

(deftest http-pure-memory-scan-live-behavior
  (let [bytes (-> (io/resource "kotoba/lang/wasm-packages/http-memory-scan-v1.wasm")
                  io/input-stream .readAllBytes)
        tmp (java.io.File/createTempFile "http-memscan" ".wasm")
        _ (java.nio.file.Files/write (.toPath tmp) bytes
                                     (into-array java.nio.file.OpenOption []))
        script (str
                "const b=require('fs').readFileSync(" (pr-str (.getAbsolutePath tmp)) ");"
                "WebAssembly.instantiate(b).then(({instance})=>{"
                "const mem=new Uint8Array(instance.exports.memory.buffer);"
                "const enc=new TextEncoder();"
                "function put(s,off){const u=enc.encode(s); mem.set(u,off); return u.length;}"
                "const req=instance.exports.http_request_scan;"
                "const resp=instance.exports.http_response_scan;"
                "const err=instance.exports.http_error_scan;"
                "const arm=instance.exports.http_result_arm_ok;"
                "const u1=put('https://x',0);"
                "const a=req(0,u1,1,2,1000);"
                "const u2=put('http://x',32);"
                "const b1=req(32,u2,1,2,1000);"
                "const c=req(0,0,1,2,1000);"
                "const d=resp(200,1,10);"
                "const e=resp(42,1,10);"
                "const cl=put('http/transport',64);"
                "const f=err(64,cl,6,0);"
                "const g=err(64,0,6,0);"
                "const bad=put('bad name',128);"
                "const h=err(128,bad,1,0);"
                "const i=arm(1);"
                "const j=arm(3);"
                "console.log(JSON.stringify([a,b1,c,d,e,f,g,h,i,j]));"
                "}).catch(e=>{console.error(e); process.exit(1);});")
        pb (ProcessBuilder. ["node" "-e" script])
        p (.start pb)
        out (slurp (.getInputStream p))
        err (slurp (.getErrorStream p))
        code (.waitFor p)]
    (.delete tmp)
    (is (zero? code) (str "node failed: " err out))
    ;; request ok, not-https, empty; response ok/bad; error ok/empty/bad-char; arm ok/bad
    (is (= [0 -3 -1 0 -1 0 -1 -3 0 -1] (edn/read-string out)))))

(deftest http-pure-header-memory-scan-package-registered
  "ADR 0195: pure hand-WAT header name/value/pair memory-scan + Component."
  (let [table (edn/read-string
               (slurp (io/resource "kotoba/lang/wasm-packages/wasm-packages-v1.edn")))
        by-name (into {} (map (juxt :name identity) (:packages table)))
        mod (get by-name :http-header-memory-scan)
        comp (get by-name :http-header-memory-scan-component)
        mod-bytes (-> (io/resource (:resource mod)) io/input-stream .readAllBytes)
        comp-bytes (-> (io/resource (:resource comp)) io/input-stream .readAllBytes)
        sha (fn [^bytes b]
              (let [md (java.security.MessageDigest/getInstance "SHA-256")]
                (.update md b)
                (apply str (map #(format "%02x" %) (.digest md)))))]
    (is (some? mod))
    (is (some? comp))
    (is (= :wasm-module (:artifact-kind mod)))
    (is (= :wasm-component (:artifact-kind comp)))
    (is (= :hand-wat/v1 (get-in mod [:source :builder])))
    (is (= (:sha256 mod) (sha mod-bytes)))
    (is (= (:sha256 comp) (sha comp-bytes)))
    (doseq [e ["http_header_name_scan" "http_header_value_scan" "http_header_pair_scan"]]
      (is (contains? (:exports mod) e)))
    (is (some? (io/resource "kotoba/lang/wasm-packages/src/http_header_memory_scan.wat")))))

(deftest http-pure-header-memory-scan-live-behavior
  (let [bytes (-> (io/resource "kotoba/lang/wasm-packages/http-header-memory-scan-v1.wasm")
                  io/input-stream .readAllBytes)
        tmp (java.io.File/createTempFile "http-hdr-scan" ".wasm")
        _ (java.nio.file.Files/write (.toPath tmp) bytes
                                     (into-array java.nio.file.OpenOption []))
        script (str
                "const b=require('fs').readFileSync(" (pr-str (.getAbsolutePath tmp)) ");"
                "WebAssembly.instantiate(b).then(({instance})=>{"
                "const mem=new Uint8Array(instance.exports.memory.buffer);"
                "const enc=new TextEncoder();"
                "function put(s,off){const u=enc.encode(s); mem.set(u,off); return u.length;}"
                "const name=instance.exports.http_header_name_scan;"
                "const val=instance.exports.http_header_value_scan;"
                "const pair=instance.exports.http_header_pair_scan;"
                "const n1=put('Content-Type',0);"
                "const a=name(0,n1);"
                "const b1=name(0,0);"
                "const bad=put('Bad Name',32);"
                "const c=name(32,bad);"
                "const v1=put('yes',64);"
                "const d=val(64,v1);"
                "const vbad=put('x'+String.fromCharCode(10)+'y',80);"
                "const e=val(80,vbad);"
                "const f=pair(0,n1,64,v1);"
                "const g=pair(32,bad,64,v1);"
                "const h=pair(0,n1,80,vbad);"
                "console.log(JSON.stringify([a,b1,c,d,e,f,g,h]));"
                "}).catch(e=>{console.error(e); process.exit(1);});")
        pb (ProcessBuilder. ["node" "-e" script])
        p (.start pb)
        out (slurp (.getInputStream p))
        err (slurp (.getErrorStream p))
        code (.waitFor p)]
    (.delete tmp)
    (is (zero? code) (str "node failed: " err out))
    (is (= [0 -1 -3 0 -3 0 -3 -6] (edn/read-string out)))))

(deftest http-pure-headers-set-scan-package-registered
  "ADR 0196: pure hand-WAT header set packing memory-scan + Component."
  (let [table (edn/read-string
               (slurp (io/resource "kotoba/lang/wasm-packages/wasm-packages-v1.edn")))
        by-name (into {} (map (juxt :name identity) (:packages table)))
        mod (get by-name :http-headers-set-scan)
        comp (get by-name :http-headers-set-scan-component)
        mod-bytes (-> (io/resource (:resource mod)) io/input-stream .readAllBytes)
        comp-bytes (-> (io/resource (:resource comp)) io/input-stream .readAllBytes)
        sha (fn [^bytes b]
              (let [md (java.security.MessageDigest/getInstance "SHA-256")]
                (.update md b)
                (apply str (map #(format "%02x" %) (.digest md)))))]
    (is (some? mod))
    (is (some? comp))
    (is (= :wasm-module (:artifact-kind mod)))
    (is (= :wasm-component (:artifact-kind comp)))
    (is (= :hand-wat/v1 (get-in mod [:source :builder])))
    (is (= (:sha256 mod) (sha mod-bytes)))
    (is (= (:sha256 comp) (sha comp-bytes)))
    (is (contains? (:exports mod) "http_headers_set_scan"))
    (is (some? (io/resource "kotoba/lang/wasm-packages/src/http_headers_set_scan.wat")))))

(deftest http-pure-headers-set-scan-live-behavior
  (let [bytes (-> (io/resource "kotoba/lang/wasm-packages/http-headers-set-scan-v1.wasm")
                  io/input-stream .readAllBytes)
        tmp (java.io.File/createTempFile "http-hdr-set" ".wasm")
        _ (java.nio.file.Files/write (.toPath tmp) bytes
                                     (into-array java.nio.file.OpenOption []))
        script (str
                "const b=require('fs').readFileSync(" (pr-str (.getAbsolutePath tmp)) ");"
                "WebAssembly.instantiate(b).then(({instance})=>{"
                "const mem=new Uint8Array(instance.exports.memory.buffer);"
                "const view=new DataView(instance.exports.memory.buffer);"
                "const enc=new TextEncoder();"
                "function put(s,off){const u=enc.encode(s); mem.set(u,off); return {off,len:u.length};}"
                "function writeRec(tableOff,i,nptr,nlen,vptr,vlen){"
                "  const base=tableOff+i*16;"
                "  view.setUint32(base,nptr,true); view.setUint32(base+4,nlen,true);"
                "  view.setUint32(base+8,vptr,true); view.setUint32(base+12,vlen,true);}"
                "const scan=instance.exports.http_headers_set_scan;"
                "const a=scan(0,0);"
                "const nm=put('X-Ok',256); const vl=put('yes',280);"
                "writeRec(0,0,nm.off,nm.len,vl.off,vl.len);"
                "const b1=scan(1,0);"
                "const bad=put('Bad Name',300);"
                "writeRec(0,0,bad.off,bad.len,vl.off,vl.len);"
                "const c=scan(1,0);"
                "const vbad=put('x'+String.fromCharCode(10)+'y',320);"
                "writeRec(0,0,nm.off,nm.len,vbad.off,vbad.len);"
                "const d=scan(1,0);"
                "const e=scan(40,0);"
                "console.log(JSON.stringify([a,b1,c,d,e]));"
                "}).catch(e=>{console.error(e); process.exit(1);});")
        pb (ProcessBuilder. ["node" "-e" script])
        p (.start pb)
        out (slurp (.getInputStream p))
        err (slurp (.getErrorStream p))
        code (.waitFor p)]
    (.delete tmp)
    (is (zero? code) (str "node failed: " err out))
    (is (= [0 0 -3 -6 -4] (edn/read-string out)))))

(deftest http-pure-request-full-scan-package-registered
  "ADR 0197: pure hand-WAT full request memory-scan + Component."
  (let [table (edn/read-string
               (slurp (io/resource "kotoba/lang/wasm-packages/wasm-packages-v1.edn")))
        by-name (into {} (map (juxt :name identity) (:packages table)))
        mod (get by-name :http-request-full-scan)
        comp (get by-name :http-request-full-scan-component)
        mod-bytes (-> (io/resource (:resource mod)) io/input-stream .readAllBytes)
        comp-bytes (-> (io/resource (:resource comp)) io/input-stream .readAllBytes)
        sha (fn [^bytes b]
              (let [md (java.security.MessageDigest/getInstance "SHA-256")]
                (.update md b)
                (apply str (map #(format "%02x" %) (.digest md)))))]
    (is (some? mod))
    (is (some? comp))
    (is (= :wasm-module (:artifact-kind mod)))
    (is (= :wasm-component (:artifact-kind comp)))
    (is (= :hand-wat/v1 (get-in mod [:source :builder])))
    (is (= (:sha256 mod) (sha mod-bytes)))
    (is (= (:sha256 comp) (sha comp-bytes)))
    (is (contains? (:exports mod) "http_request_full_scan"))
    (is (some? (io/resource "kotoba/lang/wasm-packages/src/http_request_full_scan.wat")))))

(deftest http-pure-request-full-scan-live-behavior
  (let [bytes (-> (io/resource "kotoba/lang/wasm-packages/http-request-full-scan-v1.wasm")
                  io/input-stream .readAllBytes)
        tmp (java.io.File/createTempFile "http-full-scan" ".wasm")
        _ (java.nio.file.Files/write (.toPath tmp) bytes
                                     (into-array java.nio.file.OpenOption []))
        script (str
                "const b=require('fs').readFileSync(" (pr-str (.getAbsolutePath tmp)) ");"
                "WebAssembly.instantiate(b).then(({instance})=>{"
                "const mem=new Uint8Array(instance.exports.memory.buffer);"
                "const view=new DataView(instance.exports.memory.buffer);"
                "const enc=new TextEncoder();"
                "function put(s,off){const u=enc.encode(s); mem.set(u,off); return {off,len:u.length};}"
                "function writeRec(tableOff,i,nptr,nlen,vptr,vlen){"
                "  const base=tableOff+i*16;"
                "  view.setUint32(base,nptr,true); view.setUint32(base+4,nlen,true);"
                "  view.setUint32(base+8,vptr,true); view.setUint32(base+12,vlen,true);}"
                "const scan=instance.exports.http_request_full_scan;"
                "const url=put('https://x',400);"
                "const nm=put('X-Ok',256); const vl=put('yes',280);"
                "writeRec(0,0,nm.off,nm.len,vl.off,vl.len);"
                "const a=scan(url.off,url.len,1,0,2,1000);"
                "const badu=put('http://x',450);"
                "const b1=scan(badu.off,badu.len,0,0,0,1000);"
                "const badn=put('Bad Name',500);"
                "writeRec(0,0,badn.off,badn.len,vl.off,vl.len);"
                "const c=scan(url.off,url.len,1,0,0,1000);"
                "const d=scan(url.off,url.len,40,0,0,1000);"
                "writeRec(0,0,nm.off,nm.len,vl.off,vl.len);"
                "const e=scan(url.off,url.len,1,0,0,0);"
                "console.log(JSON.stringify([a,b1,c,d,e]));"
                "}).catch(e=>{console.error(e); process.exit(1);});")
        pb (ProcessBuilder. ["node" "-e" script])
        p (.start pb)
        out (slurp (.getInputStream p))
        err (slurp (.getErrorStream p))
        code (.waitFor p)]
    (.delete tmp)
    (is (zero? code) (str "node failed: " err out))
    (is (= [0 -3 -13 -4 -6] (edn/read-string out)))))

(deftest http-pure-result-full-scan-package-registered
  "ADR 0198: pure hand-WAT full result memory-scan + Component."
  (let [table (edn/read-string
               (slurp (io/resource "kotoba/lang/wasm-packages/wasm-packages-v1.edn")))
        by-name (into {} (map (juxt :name identity) (:packages table)))
        mod (get by-name :http-result-full-scan)
        comp (get by-name :http-result-full-scan-component)
        mod-bytes (-> (io/resource (:resource mod)) io/input-stream .readAllBytes)
        comp-bytes (-> (io/resource (:resource comp)) io/input-stream .readAllBytes)
        sha (fn [^bytes b]
              (let [md (java.security.MessageDigest/getInstance "SHA-256")]
                (.update md b)
                (apply str (map #(format "%02x" %) (.digest md)))))]
    (is (some? mod))
    (is (some? comp))
    (is (= :wasm-module (:artifact-kind mod)))
    (is (= :wasm-component (:artifact-kind comp)))
    (is (= :hand-wat/v1 (get-in mod [:source :builder])))
    (is (= (:sha256 mod) (sha mod-bytes)))
    (is (= (:sha256 comp) (sha comp-bytes)))
    (is (contains? (:exports mod) "http_result_full_scan"))
    (is (some? (io/resource "kotoba/lang/wasm-packages/src/http_result_full_scan.wat")))))

(deftest http-pure-result-full-scan-live-behavior
  (let [bytes (-> (io/resource "kotoba/lang/wasm-packages/http-result-full-scan-v1.wasm")
                  io/input-stream .readAllBytes)
        tmp (java.io.File/createTempFile "http-result-full" ".wasm")
        _ (java.nio.file.Files/write (.toPath tmp) bytes
                                     (into-array java.nio.file.OpenOption []))
        script (str
                "const b=require('fs').readFileSync(" (pr-str (.getAbsolutePath tmp)) ");"
                "WebAssembly.instantiate(b).then(({instance})=>{"
                "const mem=new Uint8Array(instance.exports.memory.buffer);"
                "const view=new DataView(instance.exports.memory.buffer);"
                "const enc=new TextEncoder();"
                "function put(s,off){const u=enc.encode(s); mem.set(u,off); return {off,len:u.length};}"
                "function writeRec(tableOff,i,nptr,nlen,vptr,vlen){"
                "  const base=tableOff+i*16;"
                "  view.setUint32(base,nptr,true); view.setUint32(base+4,nlen,true);"
                "  view.setUint32(base+8,vptr,true); view.setUint32(base+12,vlen,true);}"
                "const scan=instance.exports.http_result_full_scan;"
                "const nm=put('X-Ok',256); const vl=put('yes',280);"
                "writeRec(0,0,nm.off,nm.len,vl.off,vl.len);"
                "const a=scan(0,200,1,0,2, 0,0,0,0);"
                "const b1=scan(0,42,0,0,0, 0,0,0,0);"
                "const cd=put('http/transport',400);"
                "const c=scan(1,0,0,0,0, cd.off,cd.len,6,0);"
                "const d=scan(1,0,0,0,0, 0,0,0,0);"
                "const e=scan(3,0,0,0,0, 0,0,0,0);"
                "console.log(JSON.stringify([a,b1,c,d,e]));"
                "}).catch(e=>{console.error(e); process.exit(1);});")
        pb (ProcessBuilder. ["node" "-e" script])
        p (.start pb)
        out (slurp (.getInputStream p))
        err (slurp (.getErrorStream p))
        code (.waitFor p)]
    (.delete tmp)
    (is (zero? code) (str "node failed: " err out))
    (is (= [0 -2 0 -21 -1] (edn/read-string out)))))

(deftest secret-reply-edn-package-registered
  "T8.3 ADR 0232: fixed-depth secret reply value/error EDN encode."
  (let [table (edn/read-string
               (slurp (io/resource "kotoba/lang/wasm-packages/wasm-packages-v1.edn")))
        by-name (into {} (map (juxt :name identity) (:packages table)))
        mod (get by-name :secret-reply-edn)
        sha (fn [^bytes b]
              (let [md (java.security.MessageDigest/getInstance "SHA-256")]
                (.update md b)
                (apply str (map #(format "%02x" %) (.digest md)))))]
    (is (some? mod))
    (is (= :wasm-module (:artifact-kind mod)))
    (is (= "5b7be77363b8bc41580297f2a857bd5d6dba0a1c4092e72ad0562ad9e8358181"
           (:sha256 mod)))
    (is (= (:sha256 mod) (sha (-> (io/resource (:resource mod)) io/input-stream .readAllBytes))))
    (is (contains? (:exports mod) "secret_reply_value_edn"))
    (is (contains? (:exports mod) "secret_reply_error_edn"))
    (is (contains? (:exports mod) "main"))
    (is (some? (io/resource "kotoba/lang/wasm-packages/src/secret_reply_edn.kotoba")))))

(deftest secret-request-edn-package-registered
  "T8.3 ADR 0236: fixed-depth secret get-request EDN."
  (let [table (edn/read-string
               (slurp (io/resource "kotoba/lang/wasm-packages/wasm-packages-v1.edn")))
        by-name (into {} (map (juxt :name identity) (:packages table)))
        mod (get by-name :secret-request-edn)
        sha (fn [^bytes b]
              (let [md (java.security.MessageDigest/getInstance "SHA-256")]
                (.update md b)
                (apply str (map #(format "%02x" %) (.digest md)))))]
    (is (some? mod))
    (is (= :wasm-module (:artifact-kind mod)))
    (is (= "fde508bfc9ba3af0c60258d5fb6d4f749308187cbee936975e095d6b5f9fb747"
           (:sha256 mod)))
    (is (= (:sha256 mod) (sha (-> (io/resource (:resource mod)) io/input-stream .readAllBytes))))
    (is (contains? (:exports mod) "secret_request_edn"))
    (is (contains? (:exports mod) "main"))))

(deftest secret-edn-package-registered
  "T8.3 ADR 0237: multi-export secret request+reply EDN package."
  (let [table (edn/read-string
               (slurp (io/resource "kotoba/lang/wasm-packages/wasm-packages-v1.edn")))
        by-name (into {} (map (juxt :name identity) (:packages table)))
        mod (get by-name :secret-edn-package)
        sha (fn [^bytes b]
              (let [md (java.security.MessageDigest/getInstance "SHA-256")]
                (.update md b)
                (apply str (map #(format "%02x" %) (.digest md)))))]
    (is (some? mod))
    (is (= :wasm-module (:artifact-kind mod)))
    (is (= "14c3a61df0ae6e75e5852d9eb0b1f891fcc76f467a2384fe8424f17c01dddae3"
           (:sha256 mod)))
    (is (= (:sha256 mod) (sha (-> (io/resource (:resource mod)) io/input-stream .readAllBytes))))
    (doseq [e ["secret_request_edn" "secret_reply_value_edn" "secret_reply_error_edn" "main"]]
      (is (contains? (:exports mod) e)))))


(deftest http-kit-edn-package-registered
  "T8.3 ADR 0242/0276: HTTP kit EDN uses the nominal Kotoba record surface."
  (let [table (edn/read-string
               (slurp (io/resource "kotoba/lang/wasm-packages/wasm-packages-v1.edn")))
        by-name (into {} (map (juxt :name identity) (:packages table)))
        mod (get by-name :http-kit-edn-package)
        sha (fn [bs]
              (let [md (java.security.MessageDigest/getInstance "SHA-256")]
                (.update md bs)
                (format "%064x" (BigInteger. 1 (.digest md)))))]
    (is (some? mod))
    (is (= :wasm-module (:artifact-kind mod)))
    (is (= "05e0ffaea4d3df1ed63842ce52755d6c154e65ef78232a24f442ad783c36ede9" (:sha256 mod)))
    (is (= (:sha256 mod)
           (sha (-> (io/resource (:resource mod)) io/input-stream .readAllBytes))))
    (doseq [e ["http_req_begin" "http_req_add_header" "http_req_code"
               "http_req_count" "http_req_edn"
               "http_res_ok_begin" "http_res_ok_add_header" "http_res_ok_code"
               "http_res_ok_count" "http_res_ok_edn" "http_res_err_edn" "main"]]
      (is (contains? (:exports mod) e)))
    (let [source-resource (io/resource "kotoba/lang/wasm-packages/src/http_kit_edn_package.kotoba")
          source (slurp source-resource)]
      (is (some? source-resource))
      (doseq [declaration ["(defrecord Header" "(defrecord HttpRequest"
                           "(defrecord HttpResponse"]]
        (is (str/includes? source declaration)))
      (doseq [raw-surface ["(record-new" "(record-get" "(:schemas"]]
        (is (not (str/includes? source raw-surface)))))))


(deftest entropy-edn-package-registered
  "T8.3 ADR 0244: entropy kit fixed-depth request/reply EDN package."
  (let [table (edn/read-string
               (slurp (io/resource "kotoba/lang/wasm-packages/wasm-packages-v1.edn")))
        by-name (into {} (map (juxt :name identity) (:packages table)))
        mod (get by-name :entropy-edn-package)
        sha (fn [bs]
              (let [md (java.security.MessageDigest/getInstance "SHA-256")]
                (.update md bs)
                (format "%064x" (BigInteger. 1 (.digest md)))))]
    (is (some? mod))
    (is (= :wasm-module (:artifact-kind mod)))
    (is (= "aa2d8c8ebdab2e36f1701bbf148e410c7e50de57a4b2fefc05f385de7b8c5437" (:sha256 mod)))
    (is (= (:sha256 mod)
           (sha (-> (io/resource (:resource mod)) io/input-stream .readAllBytes))))
    (doseq [e ["entropy_req_edn" "entropy_reply_hex_edn" "entropy_reply_error_edn" "main"]]
      (is (contains? (:exports mod) e)))
    (is (some? (io/resource "kotoba/lang/wasm-packages/src/entropy_edn_package.kotoba")))))

(deftest recursive-headers-edn-package-registered
  "T8.3 ADR 0246: W4 recursive nested EDN ADT for header lists."
  (let [table (edn/read-string
               (slurp (io/resource "kotoba/lang/wasm-packages/wasm-packages-v1.edn")))
        by-name (into {} (map (juxt :name identity) (:packages table)))
        mod (get by-name :recursive-headers-edn)
        sha (fn [bs]
              (let [md (java.security.MessageDigest/getInstance "SHA-256")]
                (.update md bs)
                (format "%064x" (BigInteger. 1 (.digest md)))))]
    (is (some? mod))
    (is (= :wasm-module (:artifact-kind mod)))
    (is (= "7b074e203bc400c6a391119701051222ace431080768cb3f07bc3a38dbb4c1a1" (:sha256 mod)))
    (is (= (:sha256 mod)
           (sha (-> (io/resource (:resource mod)) io/input-stream .readAllBytes))))
    (doseq [e ["edn_atom" "edn_pair" "edn_print" "headers_list_edn" "main"]]
      (is (contains? (:exports mod) e)))
    (is (some? (io/resource "kotoba/lang/wasm-packages/src/recursive_headers_edn.kotoba")))))

(deftest recursive-http-edn-package-registered
  "T8.3 ADR 0247: W4 recursive HTTP request/result EDN ADT."
  (let [table (edn/read-string
               (slurp (io/resource "kotoba/lang/wasm-packages/wasm-packages-v1.edn")))
        by-name (into {} (map (juxt :name identity) (:packages table)))
        mod (get by-name :recursive-http-edn)
        sha (fn [bs]
              (let [md (java.security.MessageDigest/getInstance "SHA-256")]
                (.update md bs)
                (format "%064x" (BigInteger. 1 (.digest md)))))]
    (is (some? mod))
    (is (= :wasm-module (:artifact-kind mod)))
    (is (= "d2a07804f5cd798d2b8e7342ea8a345648964e8fc4131bd8ce656fdefd9627cd" (:sha256 mod)))
    (is (= (:sha256 mod)
           (sha (-> (io/resource (:resource mod)) io/input-stream .readAllBytes))))
    (doseq [e ["edn_atom" "edn_pair" "edn_print" "headers_list_edn"
               "request_tree_edn" "result_ok_tree_edn" "result_err_tree_edn" "main"]]
      (is (contains? (:exports mod) e)))
    (is (some? (io/resource "kotoba/lang/wasm-packages/src/recursive_http_edn.kotoba")))))

(deftest recursive-kv-edn-package-registered
  "T8.3 ADR 0248: W4 true nested pair(k,v) map EDN (≤3 fields)."
  (let [table (edn/read-string
               (slurp (io/resource "kotoba/lang/wasm-packages/wasm-packages-v1.edn")))
        by-name (into {} (map (juxt :name identity) (:packages table)))
        mod (get by-name :recursive-kv-edn)
        sha (fn [bs]
              (let [md (java.security.MessageDigest/getInstance "SHA-256")]
                (.update md bs)
                (format "%064x" (BigInteger. 1 (.digest md)))))]
    (is (some? mod))
    (is (= :wasm-module (:artifact-kind mod)))
    (is (= "540e939d4838ce3d89669f4839da6ac64194961502cb9b6435478f35506f1861" (:sha256 mod)))
    (is (= (:sha256 mod)
           (sha (-> (io/resource (:resource mod)) io/input-stream .readAllBytes))))
    (doseq [e ["edn_atom" "edn_pair" "edn_print" "header_kv_edn" "headers_list_edn"
               "request_kv_edn" "result_ok_kv_edn" "result_err_kv_edn" "main"]]
      (is (contains? (:exports mod) e)))
    (is (some? (io/resource "kotoba/lang/wasm-packages/src/recursive_kv_edn.kotoba")))))

(deftest recursive-kv4-edn-package-registered
  "T8.3 ADR 0249: W4 true-kv 4-field maps under ADT depth 12."
  (let [table (edn/read-string
               (slurp (io/resource "kotoba/lang/wasm-packages/wasm-packages-v1.edn")))
        by-name (into {} (map (juxt :name identity) (:packages table)))
        mod (get by-name :recursive-kv4-edn)
        sha (fn [bs]
              (let [md (java.security.MessageDigest/getInstance "SHA-256")]
                (.update md bs)
                (format "%064x" (BigInteger. 1 (.digest md)))))]
    (is (some? mod))
    (is (= :wasm-module (:artifact-kind mod)))
    (is (= "8e69b0867d3ad6fe31eda555ac4716d2b4694160e611e22663834d96246cb138" (:sha256 mod)))
    (is (= (:sha256 mod)
           (sha (-> (io/resource (:resource mod)) io/input-stream .readAllBytes))))
    (doseq [e ["edn_atom" "edn_pair" "edn_print" "header_kv_edn" "headers_list_edn"
               "request_kv4_edn" "result_ok_kv4_edn" "result_err_kv4_edn" "main"]]
      (is (contains? (:exports mod) e)))
    (is (some? (io/resource "kotoba/lang/wasm-packages/src/recursive_kv4_edn.kotoba")))))

(deftest recursive-record-kv-edn-package-registered
  "T8.3 ADR 0250: W4 record-typed kv entries in recursive EDN ADT."
  (let [table (edn/read-string
               (slurp (io/resource "kotoba/lang/wasm-packages/wasm-packages-v1.edn")))
        by-name (into {} (map (juxt :name identity) (:packages table)))
        mod (get by-name :recursive-record-kv-edn)
        sha (fn [bs]
              (let [md (java.security.MessageDigest/getInstance "SHA-256")]
                (.update md bs)
                (format "%064x" (BigInteger. 1 (.digest md)))))]
    (is (some? mod))
    (is (= :wasm-module (:artifact-kind mod)))
    (is (= "a6e24260014d50b8012c70706417a5341a49a65ebb42c31d31d660cc3bfb8143" (:sha256 mod)))
    (is (= (:sha256 mod)
           (sha (-> (io/resource (:resource mod)) io/input-stream .readAllBytes))))
    (doseq [e ["edn_atom" "edn_entry" "edn_pair" "edn_print" "header_rec_kv_edn"
               "headers_list_edn" "request_rec_kv_edn" "result_ok_rec_kv_edn"
               "result_err_rec_kv_edn" "main"]]
      (is (contains? (:exports mod) e)))
    (is (some? (io/resource "kotoba/lang/wasm-packages/src/recursive_record_kv_edn.kotoba")))))

(deftest secret-record-kv-edn-package-registered
  "T8.3 ADR 0251: secret kit W4 record-kv request/reply EDN."
  (let [table (edn/read-string
               (slurp (io/resource "kotoba/lang/wasm-packages/wasm-packages-v1.edn")))
        by-name (into {} (map (juxt :name identity) (:packages table)))
        mod (get by-name :secret-record-kv-edn)
        sha (fn [bs]
              (let [md (java.security.MessageDigest/getInstance "SHA-256")]
                (.update md bs)
                (format "%064x" (BigInteger. 1 (.digest md)))))]
    (is (some? mod))
    (is (= :wasm-module (:artifact-kind mod)))
    (is (= "5fc25c7169a1f1fb58e9e8c010b21063fab0f4f753d4caf1c0ae0bc4498a9897" (:sha256 mod)))
    (is (= (:sha256 mod)
           (sha (-> (io/resource (:resource mod)) io/input-stream .readAllBytes))))
    (doseq [e ["edn_atom" "edn_entry" "edn_pair" "edn_print"
               "secret_request_rec_kv_edn" "secret_reply_value_rec_kv_edn"
               "secret_reply_error_rec_kv_edn" "main"]]
      (is (contains? (:exports mod) e)))
    (is (some? (io/resource "kotoba/lang/wasm-packages/src/secret_record_kv_edn.kotoba")))))

(deftest process-record-kv-edn-package-registered
  "T8.3 ADR 0252: process kit W4 record-typed recursive EDN request+reply."
  (let [table (edn/read-string
               (slurp (io/resource "kotoba/lang/wasm-packages/wasm-packages-v1.edn")))
        by-name (into {} (map (juxt :name identity) (:packages table)))
        mod (get by-name :process-record-kv-edn)
        sha (fn [bs]
              (let [md (java.security.MessageDigest/getInstance "SHA-256")]
                (.update md bs)
                (format "%064x" (BigInteger. 1 (.digest md)))))]
    (is (some? mod))
    (is (= :wasm-module (:artifact-kind mod)))
    (is (= "501deb2d2466edb8a4f7da66d6c3c2a2b947184e0fefe55e3c4dbb290d98ebee" (:sha256 mod)))
    (is (= (:sha256 mod)
           (sha (-> (io/resource (:resource mod)) io/input-stream .readAllBytes))))
    (doseq [e ["edn_atom" "edn_entry" "edn_pair" "edn_print"
               "process_req_rec_kv_edn" "process_reply_ok_rec_kv_edn"
               "process_reply_error_rec_kv_edn" "main"]]
      (is (contains? (:exports mod) e)))
    (is (some? (io/resource "kotoba/lang/wasm-packages/src/process_record_kv_edn.kotoba")))))

(deftest git-record-kv-edn-package-registered
  "T8.3 ADR 0253: git kit W4 record-kv request/reply EDN."
  (let [table (edn/read-string
               (slurp (io/resource "kotoba/lang/wasm-packages/wasm-packages-v1.edn")))
        by-name (into {} (map (juxt :name identity) (:packages table)))
        mod (get by-name :git-record-kv-edn)
        sha (fn [bs]
              (let [md (java.security.MessageDigest/getInstance "SHA-256")]
                (.update md bs)
                (format "%064x" (BigInteger. 1 (.digest md)))))]
    (is (some? mod))
    (is (= :wasm-module (:artifact-kind mod)))
    (is (= "390b086e373ac321857511dfa70b4866801c18cf2d56e5b7791eb12b9ffd4347" (:sha256 mod)))
    (is (= (:sha256 mod)
           (sha (-> (io/resource (:resource mod)) io/input-stream .readAllBytes))))
    (doseq [e ["edn_atom" "edn_entry" "edn_pair" "edn_print"
               "git_req_rec_kv_edn" "git_reply_ok_rec_kv_edn"
               "git_reply_error_rec_kv_edn" "main"]]
      (is (contains? (:exports mod) e)))
    (is (some? (io/resource "kotoba/lang/wasm-packages/src/git_record_kv_edn.kotoba")))))

(deftest entropy-record-kv-edn-package-registered
  "T8.3 ADR 0254: entropy kit W4 record-typed recursive EDN request+reply."
  (let [table (edn/read-string
               (slurp (io/resource "kotoba/lang/wasm-packages/wasm-packages-v1.edn")))
        by-name (into {} (map (juxt :name identity) (:packages table)))
        mod (get by-name :entropy-record-kv-edn)
        sha (fn [bs]
              (let [md (java.security.MessageDigest/getInstance "SHA-256")]
                (.update md bs)
                (format "%064x" (BigInteger. 1 (.digest md)))))]
    (is (some? mod))
    (is (= :wasm-module (:artifact-kind mod)))
    (is (= "4131cc31606f7b7be1dd3a5a27a9fecb9b890c09d3ca7ad025441946c7ac35ad" (:sha256 mod)))
    (is (= (:sha256 mod)
           (sha (-> (io/resource (:resource mod)) io/input-stream .readAllBytes))))
    (doseq [e ["edn_atom" "edn_entry" "edn_pair" "edn_print"
               "entropy_req_rec_kv_edn" "entropy_reply_hex_rec_kv_edn"
               "entropy_reply_error_rec_kv_edn" "main"]]
      (is (contains? (:exports mod) e)))
    (is (some? (io/resource "kotoba/lang/wasm-packages/src/entropy_record_kv_edn.kotoba")))))

(deftest scoped-fs-record-kv-edn-package-registered
  "T8.3 ADR 0255: scoped-fs kit W4 record-kv request/reply EDN."
  (let [table (edn/read-string
               (slurp (io/resource "kotoba/lang/wasm-packages/wasm-packages-v1.edn")))
        by-name (into {} (map (juxt :name identity) (:packages table)))
        mod (get by-name :scoped-fs-record-kv-edn)
        sha (fn [bs]
              (let [md (java.security.MessageDigest/getInstance "SHA-256")]
                (.update md bs)
                (format "%064x" (BigInteger. 1 (.digest md)))))]
    (is (some? mod))
    (is (= :wasm-module (:artifact-kind mod)))
    (is (= "2a6b08309b73d1a826616c01fcd8ac444e5bd93f21d023f99bcaa924dda27670" (:sha256 mod)))
    (is (= (:sha256 mod)
           (sha (-> (io/resource (:resource mod)) io/input-stream .readAllBytes))))
    (doseq [e ["edn_atom" "edn_entry" "edn_pair" "edn_print"
               "fs_req_read_rec_kv_edn" "fs_req_write_rec_kv_edn"
               "fs_reply_content_rec_kv_edn" "fs_reply_written_rec_kv_edn"
               "fs_reply_error_rec_kv_edn" "main"]]
      (is (contains? (:exports mod) e)))
    (is (some? (io/resource "kotoba/lang/wasm-packages/src/scoped_fs_record_kv_edn.kotoba")))))
(deftest http-w4-host-edn-package-registered
  "T8.3 ADR 0260: W4 record-kv encode + typed-cap-call http/post host surface."
  (let [table (edn/read-string
               (slurp (io/resource "kotoba/lang/wasm-packages/wasm-packages-v1.edn")))
        by-name (into {} (map (juxt :name identity) (:packages table)))
        mod (get by-name :http-w4-host-edn)
        sha (fn [bs]
              (let [md (java.security.MessageDigest/getInstance "SHA-256")]
                (.update md bs)
                (format "%064x" (BigInteger. 1 (.digest md)))))]
    (is (some? mod))
    (is (= :wasm-module (:artifact-kind mod)))
    (is (= "a558ce394b32d6e32887a35483114b95ed08516bdf85e357ab57edca582af8b0" (:sha256 mod)))
    (is (= (:sha256 mod)
           (sha (-> (io/resource (:resource mod)) io/input-stream .readAllBytes))))
    (doseq [e ["request_rec_kv_edn" "result_ok_rec_kv_edn" "host_post_edn" "main"]]
      (is (contains? (:exports mod) e)))
    (is (some? (io/resource "kotoba/lang/wasm-packages/src/http_w4_host_edn.kotoba")))
    (is (some? (io/resource "kotoba/lang/wasm-packages/src/http_w4_host_edn.policy.edn")))))

(deftest secret-w4-host-edn-package-registered
  "T8.3 ADR 0265: secret W4 encode + typed-cap-call wire 21 host surface."
  (let [table (edn/read-string
               (slurp (io/resource "kotoba/lang/wasm-packages/wasm-packages-v1.edn")))
        by-name (into {} (map (juxt :name identity) (:packages table)))
        mod (get by-name :secret-w4-host-edn)
        sha (fn [bs]
              (let [md (java.security.MessageDigest/getInstance "SHA-256")]
                (.update md bs)
                (format "%064x" (BigInteger. 1 (.digest md)))))]
    (is (some? mod))
    (is (= :wasm-module (:artifact-kind mod)))
    (is (= "3c637641f132b570f0504e85c238a711ee3f3b892875c7e8cf02edff66c11924" (:sha256 mod)))
    (is (= (:sha256 mod)
           (sha (-> (io/resource (:resource mod)) io/input-stream .readAllBytes))))
    (doseq [e ["secret_request_rec_kv_edn" "secret_reply_value_rec_kv_edn"
               "host_get_edn" "main"]]
      (is (contains? (:exports mod) e)))
    (is (some? (io/resource "kotoba/lang/wasm-packages/src/secret_w4_host_edn.kotoba")))))

(deftest process-w4-host-edn-package-registered
  "T8.3 ADR 0266: process W4 host_spawn_edn package (cap 20)."
  (let [table (edn/read-string
               (slurp (io/resource "kotoba/lang/wasm-packages/wasm-packages-v1.edn")))
        by-name (into {} (map (juxt :name identity) (:packages table)))
        mod (get by-name :process-w4-host-edn)
        sha (fn [bs]
              (let [md (java.security.MessageDigest/getInstance "SHA-256")]
                (.update md bs)
                (format "%064x" (BigInteger. 1 (.digest md)))))]
    (is (some? mod))
    (is (= :wasm-module (:artifact-kind mod)))
    (is (= "6054506551d860d92f73db49921a338f7a170d9363569162f1558f3acfe27eeb" (:sha256 mod)))
    (is (= (:sha256 mod)
           (sha (-> (io/resource (:resource mod)) io/input-stream .readAllBytes))))
    (doseq [e ["process_req_rec_kv_edn" "process_reply_ok_rec_kv_edn"
               "host_spawn_edn" "main"]]
      (is (contains? (:exports mod) e)))
    (is (some? (io/resource "kotoba/lang/wasm-packages/src/process_w4_host_edn.kotoba")))))

(deftest ops-w4-host-packages-0267-registered
  "ADR 0267: git/entropy/fs guest host packages."
  (let [table (edn/read-string (slurp (io/resource "kotoba/lang/wasm-packages/wasm-packages-v1.edn")))
        by-name (into {} (map (juxt :name identity) (:packages table)))
        sha (fn [bs]
              (let [md (java.security.MessageDigest/getInstance "SHA-256")]
                (.update md bs)
                (format "%064x" (BigInteger. 1 (.digest md)))))
        check (fn [kw expected-sha]
                (let [mod (get by-name kw)]
                  (is (some? mod) (str kw))
                  (is (= expected-sha (:sha256 mod) (sha (-> (io/resource (:resource mod)) io/input-stream .readAllBytes))))))]
    (check :git-w4-host-edn "95152251cf0e5c7163fc831bf426da80ed2bc06ad48a19621308b207a25c1fa5")
    (check :entropy-w4-host-edn "604fe3ff74003de8656d0726375c52b60bf5c9d52e4523a630801d8ac1f25fcb")
    (check :scoped-fs-w4-host-edn "b8339220a4e01f94e8bdc37466e9f3c9c8dfcd6931f8e8c3ffc2637c273126b9")
    (is (some? (io/resource "kotoba/lang/wasm-packages/src/git_w4_host_edn.kotoba")))
    (is (some? (io/resource "kotoba/lang/wasm-packages/src/entropy_w4_host_edn.kotoba")))
    (is (some? (io/resource "kotoba/lang/wasm-packages/src/scoped_fs_w4_host_edn.kotoba")))
    (let [mod (get by-name :scoped-fs-w4-host-edn)]
      (doseq [e ["fs_req_write_rec_kv_edn" "host_write_edn" "fs_reply_written_rec_kv_edn"]]
        (is (contains? (:exports mod) e) e)))))












(deftest recursive-edn-packages-use-nominal-key-value-records
  "ADR 0281: recursive EDN variants use exact-forward-declared EdnKeyValue."
  (doseq [stem ["entropy_record_kv_edn"
                "entropy_w4_host_edn"
                "git_record_kv_edn"
                "git_w4_host_edn"
                "http_w4_host_edn"
                "process_record_kv_edn"
                "process_w4_host_edn"
                "recursive_record_kv_edn"
                "scoped_fs_record_kv_edn"
                "scoped_fs_w4_host_edn"
                "secret_record_kv_edn"
                "secret_w4_host_edn"]]
    (testing stem
      (let [source (slurp (io/resource
                           (str "kotoba/lang/wasm-packages/src/" stem ".kotoba")))]
        (is (str/includes? source "(defrecord EdnKeyValue"))
        (is (str/includes? source "/EdnKeyValue"))
        (is (not (re-find #"\(:schemas \{:\S+/EdnKeyValue" source)))
        (doseq [raw-surface ["(record-new" "(record-get"]]
          (is (not (str/includes? source raw-surface))))))))

(deftest recursive-edn-packages-use-type-directed-nth
  "ADR 0282: recursive pair projections retain their inferred descriptor."
  (doseq [stem ["entropy_record_kv_edn"
                "entropy_w4_host_edn"
                "git_record_kv_edn"
                "git_w4_host_edn"
                "http_w4_host_edn"
                "process_record_kv_edn"
                "process_w4_host_edn"
                "recursive_headers_edn"
                "recursive_http_edn"
                "recursive_kv_edn"
                "recursive_kv4_edn"
                "recursive_record_kv_edn"
                "scoped_fs_record_kv_edn"
                "scoped_fs_w4_host_edn"
                "secret_record_kv_edn"
                "secret_w4_host_edn"]]
    (testing stem
      (let [source (slurp (io/resource
                           (str "kotoba/lang/wasm-packages/src/" stem ".kotoba")))]
        (is (str/includes? source "(nth p 0)"))
        (is (str/includes? source "(nth p 1)"))
        (is (not (str/includes? source "(hetero-vector-at")))))))

(deftest secret-request-edn-component-registered
  "T8.3 ADR 0245: Component twin of secret_request_edn (Canonical dual scan)."
  (let [table (edn/read-string
               (slurp (io/resource "kotoba/lang/wasm-packages/wasm-packages-v1.edn")))
        by-name (into {} (map (juxt :name identity) (:packages table)))
        comp (get by-name :secret-request-edn-component)
        sha (fn [bs]
              (let [md (java.security.MessageDigest/getInstance "SHA-256")]
                (.update md bs)
                (format "%064x" (BigInteger. 1 (.digest md)))))]
    (is (some? comp))
    (is (= :wasm-component (:artifact-kind comp)))
    (is (= :kotoba-component/secret-request-edn
           (get-in comp [:source :component-lowering])))
    (is (= "906d9032be23ca17b1630126d6a3f2ce51da6ef7bd39e237dfaa247636836a54"
           (:sha256 comp)
           (sha (-> (io/resource (:resource comp)) io/input-stream .readAllBytes))))
    (is (contains? (:exports comp) "secret-request-edn"))
    (is (some? (io/resource "kotoba/lang/wasm-packages/src/secret_request_edn_component.kotoba")))))
