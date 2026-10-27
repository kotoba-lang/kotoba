(ns browser.compat.quickjs-remove-attribute-op-smoke-test
  "Real page-script round-trip proof that `element.removeAttribute(...)`
  (and every boolean-attribute-off setter routed through the same
  `__kotobaRemoveAttribute` shim, e.g. `el.checked = false`) now emits a
  real `:dom/remove-attr` op reaching the actual GPU-rendered host's
  retained tree -- previously it only ever dissoc'd the JS-facing
  document's own `:attrs` map, emitting NO op at all, so the real host
  (which mutates ONLY by replaying `:browser/ops` through
  `kotoba.wasm.host.retained/apply-op`, never by re-reading the JS-facing
  document) kept a removed attribute stale forever once set."
  (:require [cljs.test :refer [deftest is async]]
            [browser.compat.quickjs-runner :as quickjs-runner]
            [browser.session :as session]
            [kotoba.wasm.host :as host]))

(defn- dispose-engine!
  [session]
  (when-let [engine (get-in session [:browser.session/script-engine :script-engine/engine])]
    (when-let [dispose (:quickjs.engine/dispose engine)]
      (dispose engine))))

(defn- canned-fetch-fn
  [pages]
  (fn [{:keys [url]}]
    (if-let [html (get pages url)]
      {:status 200 :headers {} :body html}
      {:status 404 :headers {} :body (str "<main>not found: " url "</main>")})))

(deftest quickjs-real-remove-attribute-emits-a-real-dom-remove-attr-op-test
  (async done
    (let [url "https://app.example/remove-attribute-op-round-trip"
          fetch-fn (canned-fetch-fn
                    {url (str "<main><input id=\"field\" checked></main>"
                              "<script>"
                              "document.getElementById('field').removeAttribute('checked');"
                              "</script>")})
          h (host/recording-host)
          base-session (session/new-session
                        (quickjs-runner/quickjs-session-opts {:host h :fetch-fn fetch-fn}))]
      (-> (session/ensure-script-engine! base-session)
          (.then
           (fn [ready-session]
             (try
               (let [after (session/navigate! ready-session url)
                     ;; `:browser/ops` on the final committed page only ever
                     ;; reflects the LAST commit's ops (page-load's own
                     ;; `run-page-scripts!` commits separately per <script>
                     ;; tag AND per DOMContentLoaded/load lifecycle
                     ;; dispatch, each draining `:ops` down to `[]` again) --
                     ;; the recording host's own accumulated `:ops`, across
                     ;; every real `host/commit!` call this whole navigation
                     ;; made, is what actually proves the op reached the
                     ;; real GPU-rendered host at all.
                     ops (:ops (host/recorded h))]
                 (println "quickjs real removeAttribute() -> real host-recorded ops ->" (pr-str ops))
                 (is (some #(and (= :remove-attr (:op %)) (= "checked" (:name %))) ops)
                     (str "expected a real :remove-attr op (encoded by kotoba.wasm.abi/op->record "
                          "from the :dom/remove-attr op kotoba.wasm.dom/remove-attribute emits) to "
                          "have actually reached the real GPU-rendered host -- the exact mechanism "
                          "that used to be entirely missing -- got " (pr-str ops)))
                 (dispose-engine! after)
                 (done))
               (catch :default e
                 (is false (str "QuickJS WASM engine initialization / page load failed: "
                                (or (.-message e) e)))
                 (dispose-engine! ready-session)
                 (done)))))
          (.catch (fn [err]
                    (is false (str "QuickJS WASM engine initialization / page load failed: "
                                   (or (.-message err) err)))
                    (dispose-engine! base-session)
                    (done)))))))
