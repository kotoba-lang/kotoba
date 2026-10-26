(ns browser.compat.quickjs-attr-case-insensitive-smoke-test
  "Real page-script round-trip proof that the CSS Selectors Level 4
  attribute case-insensitivity flag ([attr=val i]) genuinely works
  through the JS-facing selector engine (matches()/querySelectorAll())
  -- evaluated through the actual webapi shim string inside real
  QuickJS WASM, not a JVM stand-in.

  Before this cycle's fix, the attrPattern regex had no flag capture
  group at all and required ']' immediately after the value, so
  '[type=\"text\" i]' failed to match the whole attribute clause --
  the constraint was silently DROPPED entirely (matching any value at
  all), not merely case-folded."
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
     (let [url "https://app.example/attr-case-insensitive-round-trip"
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
   var upper = document.getElementById('upper');
   var lower = document.getElementById('lower');
   var edgeCase = document.getElementById('edgeCase');

   // previously the flag broke parsing entirely -- without this fix
   // even the plain (non-flagged) selector's own matching would be a
   // false negative here since the whole clause failed to parse
   r.push(upper.matches('[data-kind=\"note\" i]') === true ? 1 : 'upper-should-match-with-i-flag');
   r.push(lower.matches('[data-kind=\"note\" i]') === true ? 1 : 'lower-should-match-with-i-flag');

   // without the flag, real CSS attribute matching stays case-sensitive
   r.push(upper.matches('[data-kind=\"note\"]') === false ? 1 : 'upper-should-not-match-without-flag');
   r.push(lower.matches('[data-kind=\"note\"]') === true ? 1 : 'lower-should-match-without-flag-exact-case');

   // flag applies uniformly across every operator, not just '='
   r.push(upper.matches('[data-kind^=\"NO\" i]') === true ? 1 : 'starts-with-should-honor-flag');
   r.push(upper.matches('[data-kind$=\"TE\" i]') === true ? 1 : 'ends-with-should-honor-flag');
   r.push(upper.matches('[data-kind*=\"OT\" i]') === true ? 1 : 'contains-should-honor-flag');

   // an unquoted value ending in 's' must NOT be misread as a
   // whitespace-less 's' flag -- the value itself is 'abcs', literally
   r.push(edgeCase.matches('[data-x=abcs]') === true ? 1 : 'trailing-s-in-value-wrongly-read-as-flag');

   // real query pipeline, not just matches()
   var notes = document.querySelectorAll('[data-kind=\"NOTE\" i]');
   r.push(notes.length === 2 ? 1 : 'query-case-insensitive-count-wrong:' + notes.length);

   var bad = r.filter(function(x) { return x !== 1; });
   document.title = bad.length === 0 ? 'PASS' : 'FAIL:' + bad.join(';');")

(deftest quickjs-real-attribute-case-insensitive-flag-round-trip-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main>"
              "<div id=\"upper\" data-kind=\"NOTE\">a</div>"
              "<div id=\"lower\" data-kind=\"note\">b</div>"
              "<div id=\"edgeCase\" data-x=\"abcs\">c</div>"
              "<script>" script "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real attribute case-insensitivity flag round-trip ->" (pr-str title))
                 (is (= "PASS" title)
                     (str "expected [attr=val i] to genuinely work through "
                          "matches()/querySelectorAll() on real QuickJS -- got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (println "quickjs attribute case-insensitivity smoke ERROR ->" err)
                  (is false (str "smoke threw: " err))
                  (done))))))
