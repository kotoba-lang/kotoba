(ns browser.compat.quickjs
  "QuickJS/QuickJS-NG WASM adapter descriptor.

   This namespace does not execute JavaScript on the JVM. It defines the
   component contract that a QuickJS WASM guest must implement."
  (:require [browser.compat :as compat]
            [browser.runtime :as runtime]))

(def default-component
  (runtime/component-manifest (runtime/quickjs)))

(defn new-adapter
  [{:keys [origin profile-id component capabilities] :as opts}]
  (compat/adapter {:engine :quickjs-ng
                   :wasm-component (or component default-component)
                   :origin origin
                   :profile-id profile-id
                   :capabilities (or capabilities compat/capability-set)
                   :opts (dissoc opts :origin :profile-id :component :capabilities)}))

(defn evaluate-request
  [adapter {:keys [source url module?]}]
  (compat/request adapter :js/call
                  {:js/call :js/evaluate
                   :source source
                   :url url
                   :module? (boolean module?)}))

(defn module-load-request
  [adapter specifier referrer]
  (compat/request adapter :js/call
                  {:js/call :js/module-load
                   :specifier specifier
                   :referrer referrer}))

(defn job-drain-request
  [adapter]
  (compat/request adapter :js/call
                  {:js/call :js/job-drain}))

(defn boot-requests
  [adapter scripts]
  (conj (mapv #(evaluate-request adapter %) scripts)
        (job-drain-request adapter)))
