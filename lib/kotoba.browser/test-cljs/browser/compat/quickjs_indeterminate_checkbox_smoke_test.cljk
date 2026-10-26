(ns browser.compat.quickjs-indeterminate-checkbox-smoke-test
  "Real QuickJS WASM end-to-end proof that `checkbox.indeterminate = true`
  round-trips through a real script and is reflected in the real
  accessibility tree as an aria-checked of \"mixed\".

  Before this cycle's fix, `.indeterminate` had no getter/setter on
  <input> at all, so a script setting it had zero effect anywhere in
  the stack -- the underlying node never gained any representation of
  the indeterminate state, and checked-state (org-w3-aria) never
  considered it, silently reporting plain false/true instead."
  (:require [cljs.test :refer [deftest is async]]
            [browser.compat.quickjs-runner :as quickjs-runner]
            [browser.session :as session]
            [browser.accessibility :as a11y]
            [browser.dom-bridge :as bridge]
            [kotoba.wasm.host :as host]))

(defn- dispose-engine!
  [session]
  (when-let [engine (get-in session [:browser.session/script-engine :script-engine/engine])]
    (when-let [dispose (:quickjs.engine/dispose engine)]
      (dispose engine))))

(defn- canned-fetch-fn [pages]
  (fn [{:keys [url]}]
    (if-let [html (get pages url)]
      {:status 200 :headers {} :body html}
      {:status 404 :headers {} :body "<main>not found</main>"})))

(defn- node-by-a11y-id
  [tree id]
  (or (when (= id (:a11y/id tree))
        tree)
      (some #(node-by-a11y-id % id) (:a11y/children tree))))

(defn- run-page-and-read! [html]
  (js/Promise.
   (fn [resolve reject]
     (let [url "https://app.example/indeterminate-checkbox"
           fetch-fn (canned-fetch-fn {url html})
           h (host/recording-host)
           base-session (session/new-session
                         (quickjs-runner/quickjs-session-opts {:host h :fetch-fn fetch-fn}))]
       (-> (session/ensure-script-engine! base-session)
           (.then (fn [ready-session]
                    (try
                      (let [after (session/navigate! ready-session url)
                            title (get-in after [:browser.session/page :browser/title])
                            document (get-in after [:browser.session/page :browser/document])
                            tree (a11y/tree document)
                            cb (node-by-a11y-id tree (bridge/query-selector document "#cb"))]
                        (dispose-engine! ready-session)
                        (resolve {:title title :checked (:a11y/checked cb)}))
                      (catch :default e
                        (dispose-engine! ready-session)
                        (reject e)))))
           (.catch (fn [err]
                     (dispose-engine! base-session)
                     (reject err))))))))

(def ^:private script
  "var r = [];
   var cb = document.getElementById('cb');
   r.push(cb.indeterminate === false ? 1 : 'default-not-false:' + cb.indeterminate);
   cb.indeterminate = true;
   r.push(cb.indeterminate === true ? 1 : 'set-true-not-reflected:' + cb.indeterminate);
   r.push(cb.checked === false ? 1 : 'set-indeterminate-should-not-affect-checked:' + cb.checked);
   cb.indeterminate = false;
   r.push(cb.indeterminate === false ? 1 : 'set-false-not-reflected:' + cb.indeterminate);
   cb.indeterminate = true;

   var bad = r.filter(function(x) { return x !== 1; });
   document.title = bad.length === 0 ? 'PASS' : 'FAIL:' + bad.join(';');")

(deftest quickjs-real-indeterminate-checkbox-round-trips-to-mixed-aria-checked-test
  (async done
    (-> (run-page-and-read!
         (str "<main><input type=\"checkbox\" id=\"cb\">"
              "<script>" script "</script></main>"))
        (.then (fn [{:keys [title checked]}]
                 (println "quickjs real indeterminate checkbox round-trip ->"
                          (pr-str title) "a11y checked ->" (pr-str checked))
                 (is (= "PASS" title)
                     (str "expected checkbox.indeterminate to round-trip through get/set on real "
                          "QuickJS -- got " (pr-str title)))
                 (is (= "mixed" checked)
                     (str "expected the real accessibility tree to report aria-checked \"mixed\" "
                          "for an indeterminate checkbox -- got " (pr-str checked)))
                 (done)))
        (.catch (fn [err]
                  (println "quickjs indeterminate checkbox smoke ERROR ->" err)
                  (is false (str "smoke threw: " err))
                  (done))))))

(defn- run-page-and-read-title!
  [html]
  (js/Promise.
   (fn [resolve reject]
     (let [url "https://app.example/indeterminate-checkbox-click"
           fetch-fn (canned-fetch-fn {url html})
           h (host/recording-host)
           base-session (session/new-session
                         (quickjs-runner/quickjs-session-opts {:host h :fetch-fn fetch-fn}))]
       (-> (session/ensure-script-engine! base-session)
           (.then
            (fn [ready-session]
              (try
                (let [after (session/navigate! ready-session url)
                      title (get-in after [:browser.session/page :browser/title])]
                  (dispose-engine! ready-session)
                  (resolve title))
                (catch :default e
                  (dispose-engine! ready-session)
                  (reject e)))))
           (.catch (fn [err]
                     (dispose-engine! base-session)
                     (reject err))))))))

(deftest quickjs-real-checkbox-click-permanently-clears-indeterminate-test
  ;; Real spec: a checkbox's pre-click activation steps unconditionally
  ;; clear `indeterminate` to false, permanently -- previously
  ;; __kotobaDispatchClickWithActivation's checkbox branch flipped
  ;; `checked` but never touched `indeterminate` at all, so a checkbox
  ;; set indeterminate stayed indeterminate forever after a real
  ;; .click(). This must hold true EVEN when a click listener calls
  ;; preventDefault() -- unlike `checked` (which correctly reverts on a
  ;; canceled click), `indeterminate` is never reverted once cleared.
  (async done
    (-> (run-page-and-read-title!
         (str "<main><input id=\"cb\" type=\"checkbox\" indeterminate>"
              "<script>"
              "var cb = document.getElementById('cb');"
              "var r = [];"
              "r.push(cb.indeterminate === true ? 1 : 'not-initially-indeterminate');"
              "cb.click();"
              "r.push(cb.checked === true ? 1 : 'click-did-not-check');"
              "r.push(cb.indeterminate === false ? 1 : 'click-did-not-clear-indeterminate');"
              "cb.indeterminate = true;"
              "cb.addEventListener('click', function(e) { e.preventDefault(); });"
              "cb.click();"
              "r.push(cb.checked === true ? 1 : 'canceled-click-wrongly-toggled-checked:' + cb.checked);"
              "r.push(cb.indeterminate === false ? 1 : 'canceled-click-did-not-clear-indeterminate');"
              "var bad = r.filter(function(x) { return x !== 1; });"
              "document.title = bad.length === 0 ? 'PASS' : 'FAIL:' + bad.join(';');"
              "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real checkbox click clears indeterminate ->" (pr-str title))
                 (is (= "PASS" title)
                     (str "expected .click() to permanently clear indeterminate (even when "
                          "canceled) on real QuickJS -- got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (println "quickjs checkbox click indeterminate smoke ERROR ->" err)
                  (is false (str "smoke threw: " err))
                  (done))))))
