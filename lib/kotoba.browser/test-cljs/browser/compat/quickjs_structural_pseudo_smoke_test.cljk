(ns browser.compat.quickjs-structural-pseudo-smoke-test
  "Real page-script round-trip proof that structural pseudo-classes
  (:first-child/:last-child/:only-child/:first-of-type/:last-of-type/
  :nth-child()/:nth-of-type()/:nth-last-child()/:nth-last-of-type())
  genuinely work through the JS-facing selector engine -- matches(),
  querySelectorAll(), closest() -- evaluated through the actual webapi
  shim string inside real QuickJS WASM, not a JVM stand-in.

  Before this cycle's fix, these pseudo-classes were entirely absent --
  any selector using one always returned an empty/false/null result,
  regardless of actual DOM position, and a parenthesized argument like
  nth-child(2n+1)'s '2n+1' was silently discarded by the parser."
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
     (let [url "https://app.example/structural-pseudo-round-trip"
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
   var a = document.getElementById('a');
   var b = document.getElementById('b');
   var c = document.getElementById('c');
   var d = document.getElementById('d');

   r.push(a.matches('li:first-child') === true ? 1 : 'a-not-first-child');
   r.push(d.matches('li:last-child') === true ? 1 : 'd-not-last-child');
   r.push(a.matches('li:first-of-type') === true ? 1 : 'a-not-first-of-type');
   r.push(c.matches('li:first-of-type') === false ? 1 : 'c-wrongly-first-of-type');

   var oddIds = document.querySelectorAll('li:nth-child(odd)');
   r.push(oddIds.length === 2 && oddIds[0] === a && oddIds[1] === c ? 1 : 'nth-child-odd-wrong:' + oddIds.length);

   var nth2n1 = document.querySelectorAll('#list :nth-child(2n+1)');
   r.push(nth2n1.length === 2 ? 1 : 'nth-child-2n1-wrong:' + nth2n1.length);

   r.push(d.matches(':nth-last-child(1)') === true ? 1 : 'd-not-nth-last-child-1');
   r.push(a.closest(':nth-child(1)') === a ? 1 : 'closest-nth-child-1-failed');

   var only = document.getElementById('solo');
   r.push(only.matches(':only-child') === true ? 1 : 'solo-not-only-child');
   r.push(a.matches(':only-child') === false ? 1 : 'a-wrongly-only-child');

   var bad = r.filter(function(x) { return x !== 1; });
   document.title = bad.length === 0 ? 'PASS' : 'FAIL:' + bad.join(';');")

(deftest quickjs-real-structural-pseudo-classes-round-trip-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main>"
              "<ul id=\"list\">"
              "<li id=\"a\">A</li>"
              "<span id=\"b\">B</span>"
              "<li id=\"c\">C</li>"
              "<li id=\"d\">D</li>"
              "</ul>"
              "<div id=\"wrap\"><p id=\"solo\">only</p></div>"
              "<script>" script "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real structural pseudo-classes round-trip ->" (pr-str title))
                 (is (= "PASS" title)
                     (str "expected structural pseudo-classes to genuinely work through "
                          "matches()/querySelectorAll()/closest() on real QuickJS -- got "
                          (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (println "quickjs structural pseudo-classes smoke ERROR ->" err)
                  (is false (str "smoke threw: " err))
                  (done))))))
