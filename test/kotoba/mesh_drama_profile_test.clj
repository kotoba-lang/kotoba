(ns kotoba.mesh-drama-profile-test
  "ADR-2607082400's first cljc-ported mesh app: proves
  src/mesh_drama_profile.kotoba (the port of minidrama's ON-MESH
  drama-profile component, orgs/etzhayyim/com-etzhayyim-minidrama/mesh/
  drama_profile.clj) really compiles, emits, and executes through
  kotoba.wasm-exec/com.dylibso.chicory -- same rigor as
  kotoba.wasm-exec-test's own kgraph round-trip test, applied to a real
  application's identity facts instead of a synthetic demo."
  (:require [clojure.edn :as edn]
            [clojure.test :refer [deftest is testing]]
            [kotoba.launcher :as launcher]
            [kotoba.runtime :as runtime]
            [kotoba.wasm-exec :as wasm-exec]))

(deftest drama-profile-asserts-and-serves-its-identity-facts-through-real-chicory
  (testing "compile -> emit -> Chicory-execute: kgraph-assert! really writes minidrama's
            identity facts, kgraph-query really reads the handle back"
    (let [forms (runtime/read-file "src/mesh_drama_profile.kotoba" :kotoba)
          policy (edn/read-string (slurp "src/mesh_drama_profile_policy.edn"))
          checked (runtime/check (launcher/safe-analyzer-fact-classification)
                                 (launcher/source-plan "src/mesh_drama_profile.kotoba")
                                 forms policy)
          wasm (runtime/wasm-binary forms policy)
          store (atom [])
          instance (wasm-exec/instantiate (:kotoba.wasm/binary wasm)
                                          (wasm-exec/kgraph-host-functions store))
          result (.apply (.export instance "main") (long-array 0))
          written (aget ^longs result 0)
          buf-ptr (:kotoba.wasm/heap-base wasm)]
      (is (:kotoba.runtime/ok? checked) "static capability check admits :graph/kotoba")
      (is (:kotoba.wasm/ok? wasm))
      (is (pos? written) "kgraph_query wrote a real result into the guest buffer")
      (is (= [["minidrama.aozora.app"]]
             (edn/read-string (wasm-exec/read-memory-string instance buf-ptr written)))
          "the query result matches the handle asserted moments earlier -- not a stub")
      (testing "the host-side kgraph store received all three identity datoms"
        (is (= #{[1 :handle "minidrama.aozora.app"]
                 [1 :did "did:key:z6MkfF8hVc4xtEdDudV1jJiyTtQDdmYBEXrhzGGaqYsHv16b"]
                 [1 :registry "aozora.appview.creator-actors"]}
               (set @store)))))))
