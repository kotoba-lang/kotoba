(ns kotoba.actor-host-test
  "kotoba-lang/kototama's `actor:host` ABI (kototama.contract / kototama.tender,
  ADR-2607062330/2607062400): the 6 host-imports net-new to this repo's
  capability_contract.edn (log-write/clock-monotonic already existed,
  registered independently for aiueos's kernel capabilities with identical
  wire signatures -- kototama renamed :now/:log-append! to reuse them
  instead of duplicating the registration, see kototama#21).

  Mirrors kotoba.aiueos-kernel-caps-test's shape exactly: each demo below is
  a real, capability-gated `.kotoba` -> Wasm compile -- denies without a
  policy, emits a genuine Wasm binary with one. This closes the loop
  ADR-2607062330's addendum 3 opened: kototama.tender's HostFunctions were
  wired long before any `.kotoba` source could actually reach them."
  (:require [clojure.edn :as edn]
            [clojure.test :refer [deftest is]]
            [kotoba.launcher :as launcher]
            [kotoba.runtime :as runtime])
  (:import [java.io File]))

(def positive-lock "test/fixtures/package/positive-lock.edn")
(def trust "test/fixtures/package/trust.edn")

(defn- denied-without-policy? [demo-path]
  (let [result (launcher/dispatch ["run" demo-path "--json"])]
    (and (false? (:kotoba.cli/ok? result))
         (= :capability-not-granted
            (get-in result [:kotoba.cli/data :kotoba.runtime/result
                            :kotoba.runtime/problems 0 :kotoba.runtime/problem])))))

(defn- wasm-emits-with-policy? [demo-path policy-path expected-import]
  (let [forms (runtime/read-file demo-path :kotoba)
        policy (edn/read-string (slurp policy-path))
        wasm (runtime/wasm-binary forms policy)
        output (doto (File/createTempFile "kotoba-actor-host-demo" ".wasm") (.deleteOnExit))
        emitted (launcher/dispatch ["wasm" "emit" demo-path "--policy" policy-path
                                    "--output" (.getPath output) "--json" "--package-lock" positive-lock "--trust" trust])]
    (and (:kotoba.wasm/ok? wasm)
         (= [expected-import] (:kotoba.wasm/imports wasm))
         (:kotoba.cli/ok? emitted)
         (= :wasm/binary-emitted (:kotoba.cli/code emitted))
         (= 1 (get-in emitted [:kotoba.cli/data :kotoba.wasm/import-count]))
         (= [0 97 115 109]
            (mapv #(bit-and % 0xff)
                  (take 4 (java.nio.file.Files/readAllBytes (.toPath output))))))))

(def actor-host-demos
  "6 of kototama.contract's 8 actor:host imports, net-new to this repo
  (log-write/clock-monotonic already covered by kotoba.aiueos-kernel-caps-test)."
  [{:demo "src/demo_actor_host_keypair.kotoba" :policy "src/demo_actor_host_keypair_policy.edn"
    :import {:module "kotoba" :field "gen_keypair" :capability "identity/keypair"
             :params [:i32 :i32] :result :i32}}
   {:demo "src/demo_actor_host_sign.kotoba" :policy "src/demo_actor_host_sign_policy.edn"
    :import {:module "kotoba" :field "sign" :capability "identity/sign"
             :params [:i32 :i32 :i32 :i32 :i32] :result :i32}}
   {:demo "src/demo_actor_host_verify.kotoba" :policy "src/demo_actor_host_verify_policy.edn"
    :import {:module "kotoba" :field "verify" :capability "identity/verify"
             :params [:i32 :i32 :i32 :i32 :i32 :i32] :result :i32}}
   {:demo "src/demo_actor_host_sha256.kotoba" :policy "src/demo_actor_host_sha256_policy.edn"
    :import {:module "kotoba" :field "sha256_hex" :capability "hash/sha256"
             :params [:i32 :i32 :i32 :i32] :result :i32}}
   {:demo "src/demo_actor_host_http_post.kotoba" :policy "src/demo_actor_host_http_post_policy.edn"
    :import {:module "kotoba" :field "http_post" :capability "http/post"
             :params [:i32 :i32 :i32 :i32 :i32 :i32] :result :i32}}
   {:demo "src/demo_actor_host_log_read.kotoba" :policy "src/demo_actor_host_log_read_policy.edn"
    :import {:module "kotoba" :field "log_read" :capability "log/read"
             :params [:i32 :i32] :result :i32}}])

(deftest all-actor-host-demos-deny-without-policy
  (doseq [{:keys [demo]} actor-host-demos]
    (is (denied-without-policy? demo) demo)))

(deftest all-actor-host-demos-compile-to-real-wasm-with-a-granting-policy
  (doseq [{:keys [demo policy import]} actor-host-demos]
    (is (wasm-emits-with-policy? demo policy import) demo)))

(deftest all-six-actor-host-imports-are-registered
  ;; No op->kind entry expected or needed: these ops don't participate in
  ;; the cap-acquire/<op>-with capability-passing extension (that's an
  ;; aiueos-specific S4b feature) -- a plain :capability-gated host-imports
  ;; entry is sufficient, same as kgraph-assert!/clipboard-write.
  (doseq [op '[gen-keypair sign verify sha256-hex http-post log-read]]
    (is (contains? runtime/host-imports op) (str op " missing from host-imports"))
    (is (not (contains? runtime/op->kind op))
        (str op " unexpectedly in op->kind -- does it need cap-passing after all?"))))
