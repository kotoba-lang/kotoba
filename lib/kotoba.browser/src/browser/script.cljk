(ns browser.script
  "Document scripting hook for kotoba-clj/WASM document guests."
  (:require [browser.dom-bridge :as dom-bridge]))

(defn script-descriptor
  [{:keys [id lang wasm entry imports exports] :as opts}]
  {:script/id id
   :script/lang (or lang :kotoba)
   :script/runtime :wasm
   :script/wasm wasm
   :script/entry (or entry :document/run)
   :script/imports (set imports)
   :script/exports (set exports)
   :script/no-ambient-access true
   :script/meta (dissoc opts :id :lang :wasm :entry :imports :exports)})

(defn run-script
  "Runs a document script through an injected runner.

   runner receives {:script script :document document :event event} and returns
   {:requests [...] :result ...}. DOM requests are applied through dom-bridge."
  [document script event runner]
  (let [{:keys [requests result error] :as report}
        (runner {:script script :document document :event event})
        reduced (reduce (fn [{:keys [document results]} request]
                          (let [{next-doc :document :as r} (dom-bridge/handle-request document request)]
                            {:document next-doc
                             :results (conj results (dissoc r :document))}))
                        {:document document :results []}
                        requests)]
    (merge reduced
           {:script script
            :script/result result
            :script/error error
            :script/report report})))
