(ns browser.compat.quickjs-focus-within-smoke-test
  "Real page-script round-trip proof that :focus-within is genuinely
  supported by the JS-facing selector engine (matches()/closest()/
  querySelector()), not just by CSS styling -- evaluated through the
  actual webapi shim string inside real QuickJS WASM, not a JVM
  stand-in.

  Before this cycle's fix, :focus-within was entirely absent from
  __kotobaMatchesSimple's pseudo switch -- any selector using it fell
  into the default branch, which fails the WHOLE simple-selector match
  unconditionally, regardless of actual focus state."
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
     (let [url "https://app.example/focus-within-round-trip"
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
   var wrap = document.getElementById('wrap');
   var inp = document.getElementById('inp');
   var other = document.getElementById('other');

   r.push(wrap.matches(':focus-within') === false ? 1 : 'wrap-should-not-match-before-focus');

   inp.focus();

   r.push(wrap.matches(':focus-within') === true ? 1 : 'wrap-should-match-after-focus');
   r.push(inp.matches(':focus-within') === true ? 1 : 'focused-element-itself-should-match');
   r.push(other.matches(':focus-within') === false ? 1 : 'unrelated-element-should-not-match');
   r.push(document.querySelector('#wrap:focus-within') === wrap ? 1 : 'query-selector-should-find-wrap');
   r.push(inp.closest(':focus-within') === inp ? 1 : 'closest-should-find-focused-element-itself');

   var bad = r.filter(function(x) { return x !== 1; });
   document.title = bad.length === 0 ? 'PASS' : 'FAIL:' + bad.join(';');")

(deftest quickjs-real-focus-within-selector-round-trip-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main>"
              "<div id=\"wrap\"><input id=\"inp\"></div>"
              "<div id=\"other\">unrelated</div>"
              "<script>" script "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real :focus-within round-trip ->" (pr-str title))
                 (is (= "PASS" title)
                     (str "expected :focus-within to genuinely work through matches()/"
                          "querySelector()/closest() on real QuickJS -- got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (println "quickjs :focus-within smoke ERROR ->" err)
                  (is false (str "smoke threw: " err))
                  (done))))))
