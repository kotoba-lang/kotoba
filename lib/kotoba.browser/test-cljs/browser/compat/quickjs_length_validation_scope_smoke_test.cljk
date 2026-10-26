(ns browser.compat.quickjs-length-validation-scope-smoke-test
  "Real page-script round-trip proof that real HTML5's minlength/
  maxlength restriction to text/search/url/tel/email/password
  <input>s and <textarea> -- NOT number/range/color/date/
  datetime-local/month/week/time -- is honored, evaluated through the
  actual webapi shim string inside real QuickJS WASM, not a JVM
  stand-in.

  Previously __kotobaValidationReason had NO type guard on minlength/
  maxlength at all, so a real, common shape like
  <input type=\"number\" value=\"12345\" maxlength=\"3\"> was
  spuriously flagged tooLong -- matches(':invalid')/checkValidity()
  wrongly reported an invalid, blockable control for an attribute
  HTML5 says doesn't apply to that type at all."
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
     (let [url "https://app.example/length-validation-scope"
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
   var n = document.getElementById('n');
   r.push(n.matches(':valid') && n.checkValidity() ? 1 : 'number-maxlength-should-be-ignored:' + n.matches(':invalid'));

   var t = document.getElementById('t');
   r.push(!t.matches(':valid') && !t.checkValidity() && t.validity.tooLong ? 1 : 'text-maxlength-should-still-apply:' + t.checkValidity());

   var ta = document.getElementById('ta');
   r.push(!ta.matches(':valid') && ta.validity.tooLong ? 1 : 'textarea-maxlength-should-still-apply:' + ta.checkValidity());

   var bad = r.filter(function(x) { return x !== 1; });
   document.title = bad.length === 0 ? 'PASS' : 'FAIL:' + bad.join(';');")

(deftest quickjs-real-length-validation-restricted-to-text-like-controls-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main>"
              "<input id=\"n\" type=\"number\" value=\"12345\" maxlength=\"3\">"
              "<input id=\"t\" type=\"text\" value=\"12345\" maxlength=\"3\">"
              "<textarea id=\"ta\" maxlength=\"3\">12345</textarea>"
              "<script>" script "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real length-validation scope round-trip ->" (pr-str title))
                 (is (= "PASS" title)
                     (str "expected minlength/maxlength to be ignored for type=number but still "
                          "enforced for type=text/textarea on real QuickJS -- got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (println "quickjs length-validation scope smoke ERROR ->" err)
                  (is false (str "smoke threw: " err))
                  (done))))))
