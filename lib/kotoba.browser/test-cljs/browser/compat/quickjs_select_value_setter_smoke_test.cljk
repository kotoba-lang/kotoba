(ns browser.compat.quickjs-select-value-setter-smoke-test
  "Real page-script round-trip proof that a scripted `select.value = 'y'`
  genuinely toggles the underlying <option>s' `selected` state (and not
  just an inert attribute write on the <select> node itself that nothing
  reads back) -- evaluated through the actual webapi shim string inside
  real QuickJS WASM, not a JVM stand-in.

  Before this cycle's fix, the value setter fell straight through to the
  generic setAttribute('value', ...) path used by every other input -- no
  option's `selected` attribute ever changed, so el.value = 'y' was a
  complete, silent no-op with respect to actual selection state."
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

(defn- run-page-and-read-title!
  [html]
  (js/Promise.
   (fn [resolve reject]
     (let [url "https://app.example/select-value-setter-round-trip"
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

(def ^:private script
  "var r = [];
   var s = document.getElementById('s');
   var optX = document.getElementById('optX');
   var optY = document.getElementById('optY');

   r.push(s.value === 'x' ? 1 : 'initial-value:' + s.value);

   s.value = 'y';
   r.push(s.value === 'y' ? 1 : 'after-assign-value:' + s.value);
   r.push(optY.selected === true ? 1 : 'optY-not-selected');
   r.push(optX.selected === false ? 1 : 'optX-still-selected');
   r.push(s.selectedIndex === 1 ? 1 : 'selectedIndex:' + s.selectedIndex);

   // Deliberately NOT asserting a specific selectedIndex here: this
   // engine's __kotobaSelectedIndex falls back to 0 whenever nothing has
   // an explicit `selected` attribute, a pre-existing simplification
   // (unrelated to this fix) that does not distinguish 'never had a
   // selection' from 'explicitly cleared to nothing via .value='. What
   // THIS fix is responsible for -- and what real spec requires -- is
   // that no option is left falsely selected after an unmatched assign.
   s.value = 'does-not-exist';
   r.push(optX.selected === false && optY.selected === false ? 1 : 'unmatched-value-left-something-selected');

   var bad = r.filter(function(x) { return x !== 1; });
   document.title = bad.length === 0 ? 'PASS' : 'FAIL:' + bad.join(';');")

(deftest quickjs-real-select-value-setter-toggles-option-selectedness-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><select id=\"s\">"
              "<option id=\"optX\" value=\"x\" selected>X</option>"
              "<option id=\"optY\" value=\"y\">Y</option>"
              "</select><script>" script "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real select.value setter round-trip ->" (pr-str title))
                 (is (= "PASS" title)
                     (str "expected select.value = 'y' to genuinely toggle option "
                          "selectedness on real QuickJS -- got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (println "quickjs select.value setter smoke ERROR ->" err)
                  (is false (str "smoke threw: " err))
                  (done))))))
