(ns browser.compat.quickjs-form-reset-smoke-test
  "Real page-script round-trip proof that form.reset() genuinely restores
  every form control to its default value/checkedness/selectedness (and
  dispatches a real `reset` event) -- evaluated through the actual webapi
  shim string inside real QuickJS WASM, not a JVM stand-in.

  Before this cycle's fix, form.reset() was entirely absent -- calling it
  threw a bare TypeError, even though browser.document-input's own
  reset-control-state already correctly implements the same real-spec
  reset algorithm for native, non-scripted form resets."
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
     (let [url "https://app.example/form-reset-round-trip"
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
   var form = document.getElementById('f');
   var text = document.getElementById('text');
   var chk = document.getElementById('chk');
   var sel = document.getElementById('sel');
   var optX = document.getElementById('optX');
   var optY = document.getElementById('optY');
   var resetFired = false;
   form.addEventListener('reset', function() { resetFired = true; });

   text.value = 'changed';
   chk.checked = true;
   sel.value = 'y';

   r.push(text.value === 'changed' ? 1 : 'pre-reset-text-not-changed');
   r.push(chk.checked === true ? 1 : 'pre-reset-chk-not-checked');
   r.push(sel.value === 'y' ? 1 : 'pre-reset-sel-not-y');

   form.reset();

   r.push(text.value === 'orig' ? 1 : 'text-not-reset:' + text.value);
   r.push(chk.checked === false ? 1 : 'chk-not-reset');
   r.push(sel.value === 'x' ? 1 : 'sel-not-reset:' + sel.value);
   r.push(optX.selected === true ? 1 : 'optX-not-selected');
   r.push(optY.selected === false ? 1 : 'optY-still-selected');
   r.push(resetFired === true ? 1 : 'reset-event-not-dispatched');

   var bad = r.filter(function(x) { return x !== 1; });
   document.title = bad.length === 0 ? 'PASS' : 'FAIL:' + bad.join(';');")

(deftest quickjs-real-form-reset-restores-defaults-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><form id=\"f\">"
              "<input id=\"text\" type=\"text\" value=\"orig\">"
              "<input id=\"chk\" type=\"checkbox\">"
              "<select id=\"sel\">"
              "<option id=\"optX\" value=\"x\" selected>X</option>"
              "<option id=\"optY\" value=\"y\">Y</option>"
              "</select>"
              "</form><script>" script "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real form.reset() round-trip ->" (pr-str title))
                 (is (= "PASS" title)
                     (str "expected form.reset() to genuinely restore all defaults on real "
                          "QuickJS -- got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (println "quickjs form.reset() smoke ERROR ->" err)
                  (is false (str "smoke threw: " err))
                  (done))))))
