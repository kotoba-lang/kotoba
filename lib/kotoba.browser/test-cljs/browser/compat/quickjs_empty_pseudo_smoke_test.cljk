(ns browser.compat.quickjs-empty-pseudo-smoke-test
  "Real page-script round-trip proof that :empty genuinely works through
  the JS-facing selector engine (matches()/querySelectorAll()) --
  evaluated through the actual webapi shim string inside real QuickJS
  WASM, not a JVM stand-in.

  Before this cycle's fix, :empty was entirely absent -- any selector
  using it always returned an empty/false result, regardless of whether
  the element actually had zero children of any node type.

  Note: this engine's own HTML parser discards whitespace-only text
  (and comments) between tags entirely at parse time, so <div> </div>
  parses to a genuinely childless div here -- the script below
  constructs a real whitespace text node programmatically via
  document.createTextNode()/appendChild() to prove the fix's own
  non-zero-length-text-still-counts-as-content rule against an actual
  text node, not just HTML-parsed structure."
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
     (let [url "https://app.example/empty-pseudo-round-trip"
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
   var childless = document.getElementById('childless');
   var withText = document.getElementById('withText');
   var withChild = document.getElementById('withChild');
   var nestedSpan = document.getElementById('nestedSpan');
   var wsHolder = document.getElementById('wsHolder');

   r.push(childless.matches(':empty') === true ? 1 : 'childless-not-empty');
   r.push(withText.matches(':empty') === false ? 1 : 'text-content-wrongly-empty');
   r.push(withChild.matches(':empty') === false ? 1 : 'element-child-wrongly-empty');
   // a genuinely childless element ITSELF still matches :empty even
   // though it disqualifies its own parent from matching
   r.push(nestedSpan.matches(':empty') === true ? 1 : 'nested-empty-element-wrongly-not-empty');

   // real, non-HTML-parsed whitespace text node, constructed
   // programmatically -- proves non-zero-length whitespace still
   // counts as content (real CSS: <div> </div> does NOT match :empty)
   wsHolder.appendChild(document.createTextNode(' '));
   r.push(wsHolder.matches(':empty') === false ? 1 : 'whitespace-text-node-wrongly-empty');

   // at this point childless and nestedSpan are the only genuinely
   // empty elements in the whole document
   var emptyIds = document.querySelectorAll(':empty');
   r.push(emptyIds.length === 2 ? 1 : 'query-selector-all-wrong:' + emptyIds.length);
   r.push(Array.prototype.indexOf.call(emptyIds, childless) >= 0 ? 1 : 'childless-missing-from-query');
   r.push(Array.prototype.indexOf.call(emptyIds, nestedSpan) >= 0 ? 1 : 'nested-span-missing-from-query');

   var bad = r.filter(function(x) { return x !== 1; });
   document.title = bad.length === 0 ? 'PASS' : 'FAIL:' + bad.join(';');")

(deftest quickjs-real-empty-pseudo-class-round-trip-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main>"
              "<div id=\"childless\"></div>"
              "<div id=\"withText\">hello</div>"
              "<div id=\"withChild\"><span id=\"nestedSpan\"></span></div>"
              "<div id=\"wsHolder\"></div>"
              "<script>" script "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real :empty pseudo-class round-trip ->" (pr-str title))
                 (is (= "PASS" title)
                     (str "expected :empty to genuinely work through matches()/"
                          "querySelectorAll() on real QuickJS -- got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (println "quickjs :empty smoke ERROR ->" err)
                  (is false (str "smoke threw: " err))
                  (done))))))
