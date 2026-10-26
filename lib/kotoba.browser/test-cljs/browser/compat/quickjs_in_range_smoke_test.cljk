(ns browser.compat.quickjs-in-range-smoke-test
  "Real page-script round-trip proof that :in-range/:out-of-range
  genuinely work through the JS-facing selector engine (matches()/
  querySelectorAll()) -- evaluated through the actual webapi shim string
  inside real QuickJS WASM, not a JVM stand-in.

  Before this cycle's fix, these pseudo-classes were entirely absent --
  any selector using one always returned an empty/false result,
  regardless of whether the control's value actually satisfied its own
  min/max."
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
     (let [url "https://app.example/in-range-round-trip"
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
   var inb = document.getElementById('inb');
   var oob = document.getElementById('oob');
   var unbounded = document.getElementById('unbounded');
   var textLike = document.getElementById('textLike');

   r.push(inb.matches(':in-range') === true ? 1 : 'inb-not-in-range');
   r.push(inb.matches(':out-of-range') === false ? 1 : 'inb-wrongly-out-of-range');
   r.push(oob.matches(':out-of-range') === true ? 1 : 'oob-not-out-of-range');
   r.push(oob.matches(':in-range') === false ? 1 : 'oob-wrongly-in-range');
   r.push(unbounded.matches(':in-range') === false ? 1 : 'unbounded-wrongly-in-range');
   r.push(unbounded.matches(':out-of-range') === false ? 1 : 'unbounded-wrongly-out-of-range');
   r.push(textLike.matches(':in-range') === false ? 1 : 'text-type-wrongly-in-range');

   var inRangeIds = document.querySelectorAll(':in-range');
   r.push(inRangeIds.length === 1 && inRangeIds[0] === inb ? 1 : 'query-selector-all-wrong:' + inRangeIds.length);

   var bad = r.filter(function(x) { return x !== 1; });
   document.title = bad.length === 0 ? 'PASS' : 'FAIL:' + bad.join(';');")

(deftest quickjs-real-in-range-out-of-range-round-trip-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main>"
              "<input id=\"inb\" type=\"number\" min=\"1\" max=\"10\" value=\"5\">"
              "<input id=\"oob\" type=\"number\" min=\"1\" max=\"10\" value=\"15\">"
              "<input id=\"unbounded\" type=\"number\" value=\"5\">"
              "<input id=\"textLike\" type=\"text\" min=\"1\" max=\"10\" value=\"5\">"
              "<script>" script "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real :in-range/:out-of-range round-trip ->" (pr-str title))
                 (is (= "PASS" title)
                     (str "expected :in-range/:out-of-range to genuinely work through "
                          "matches()/querySelectorAll() on real QuickJS -- got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (println "quickjs :in-range smoke ERROR ->" err)
                  (is false (str "smoke threw: " err))
                  (done))))))
