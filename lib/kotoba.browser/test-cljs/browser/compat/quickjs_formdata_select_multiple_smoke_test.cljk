(ns browser.compat.quickjs-formdata-select-multiple-smoke-test
  "Real QuickJS WASM end-to-end proof that `new FormData(formEl)`
  contributes ONE entry per selected `<option>` for a `<select multiple>`,
  not a single collapsed value.

  Before this cycle's fix, the FormData constructor's form-enumeration
  loop reused `__kotobaControlValue`/`__kotobaSelectValue` (a SINGLE-
  value function that `return`s on the FIRST selected option) for
  entry-list construction too, so a real multi-select with two+
  selections silently lost every selection after the first, and a
  multi-select with NOTHING selected produced a spurious '' entry
  instead of contributing no entry at all."
  (:require [cljs.test :refer [deftest is async]]
            [browser.compat.quickjs-runner :as quickjs-runner]
            [browser.session :as session]
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

(defn- run-page-and-read-title! [html]
  (js/Promise.
   (fn [resolve reject]
     (let [url "https://app.example/formdata-select-multiple"
           fetch-fn (canned-fetch-fn {url html})
           h (host/recording-host)
           base-session (session/new-session
                         (quickjs-runner/quickjs-session-opts {:host h :fetch-fn fetch-fn}))]
       (-> (session/ensure-script-engine! base-session)
           (.then (fn [ready-session]
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

(def ^:private script
  "var r = [];
   var multi = new FormData(document.getElementById('multi-form'));
   var colors = multi.getAll('colors');
   r.push(JSON.stringify(colors) === JSON.stringify(['red','green']) ? 1 : 'multi-selected:' + JSON.stringify(colors));

   var empty = new FormData(document.getElementById('empty-form'));
   r.push(!empty.has('colors') ? 1 : 'multi-none-selected-should-have-no-entry:' + JSON.stringify(empty.getAll('colors')));

   var single = new FormData(document.getElementById('single-form'));
   r.push(single.get('color') === 'b' ? 1 : 'single-select-regression:' + single.get('color'));

   var bad = r.filter(function(x) { return x !== 1; });
   document.title = bad.length === 0 ? 'PASS' : 'FAIL:' + bad.join(';');")

(deftest quickjs-real-formdata-select-multiple-one-entry-per-option-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main>"
              "<form id=\"multi-form\"><select name=\"colors\" multiple>"
              "<option value=\"red\" selected>Red</option>"
              "<option value=\"green\" selected>Green</option>"
              "<option value=\"blue\">Blue</option>"
              "</select></form>"
              "<form id=\"empty-form\"><select name=\"colors\" multiple>"
              "<option value=\"red\">Red</option>"
              "<option value=\"green\">Green</option>"
              "</select></form>"
              "<form id=\"single-form\"><select name=\"color\">"
              "<option value=\"a\">A</option>"
              "<option value=\"b\" selected>B</option>"
              "</select></form>"
              "<script>" script "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real FormData select-multiple round-trip ->" (pr-str title))
                 (is (= "PASS" title)
                     (str "expected new FormData(formEl) to contribute one entry per selected "
                          "<option> for a <select multiple> (and no entry at all when nothing is "
                          "selected) on real QuickJS -- got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (println "quickjs FormData select-multiple smoke ERROR ->" err)
                  (is false (str "smoke threw: " err))
                  (done))))))
