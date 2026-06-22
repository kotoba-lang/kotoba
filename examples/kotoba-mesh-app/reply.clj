;; reply.clj — KOTOBA Mesh default-language component (Clojure / kotoba-clj).
;;
;; Compiled by `kotoba-clj::component::compile_kais_component_str` into a real
;; `kotoba:kais/kotoba-node` WASM component and driven by kotoba-runtime's
;; WasmExecutor. This is the *default* way to write a mesh component — same
;; language family as the manifest (EDN) and the data (Datomic/Datalog).
;;
;; host-imports used:  kqe-assert! / kqe-query  → kotoba:kais/kqe
;;                     llm-infer               → kotoba:kais/llm  (needs cap/llm link)
(ns reply)

(defn run [ctx]
  ;; record that we handled a request (a Datom assertion into graph "g")
  (kqe-assert! "g" "reply" "status" "ok")
  ;; read it back via Datalog — the query language is Datalog over the same datoms
  (kqe-query "status(?s) :- reply(?s)."))
