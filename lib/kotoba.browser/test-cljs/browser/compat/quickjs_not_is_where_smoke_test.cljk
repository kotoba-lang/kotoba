(ns browser.compat.quickjs-not-is-where-smoke-test
  "Real page-script round-trip proof that :not()/:is()/:where() genuinely
  work through the JS-facing selector engine (matches()/querySelectorAll())
  -- evaluated through the actual webapi shim string inside real QuickJS
  WASM, not a JVM stand-in.

  Before this cycle's fix, all three were entirely absent -- any selector
  using one always returned an empty/false result, regardless of the
  candidate node's actual class/id/tag state."
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
     (let [url "https://app.example/not-is-where-round-trip"
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
   var bar = document.getElementById('bar');
   var foo = document.getElementById('foo');

   // :not() -- node must match NONE of the group
   r.push(a.matches('li:not(.a)') === false ? 1 : 'a-wrongly-matches-not-a');
   r.push(b.matches('li:not(.a)') === true ? 1 : 'b-should-match-not-a');

   // multiple occurrences on one compound -- each is its own group,
   // ALL groups must independently pass (no extra grouping logic in
   // the shim -- the existing per-pseudo loop already requires it)
   r.push(a.matches('li:not(.a):not(.b)') === false ? 1 : 'a-wrongly-matches-not-a-not-b');
   r.push(c.matches('li:not(.a):not(.b)') === true ? 1 : 'c-should-match-not-a-not-b');

   // comma-separated group inside :not()
   r.push(a.matches('li:not(.b, .c)') === true ? 1 : 'a-should-match-not-b-or-c');

   // :is()/:where() -- node must match AT LEAST ONE of the group
   r.push(a.matches('li:is(.a, .b)') === true ? 1 : 'a-should-match-is-a-or-b');
   r.push(c.matches('li:is(.a, .b)') === false ? 1 : 'c-wrongly-matches-is-a-or-b');
   r.push(a.matches('li:where(.a, .b)') === true ? 1 : 'a-should-match-where-a-or-b');
   r.push(c.matches('li:where(.a, .b)') === false ? 1 : 'c-wrongly-matches-where-a-or-b');

   // nested id selector inside is()/not() -- one level of nesting
   r.push(bar.matches('div:is(#bar)') === true ? 1 : 'bar-should-match-is-id');
   r.push(foo.matches('span:not(#bar)') === true ? 1 : 'foo-should-match-not-other-id');

   // real query pipeline, not just matches()
   var notAIds = document.querySelectorAll('#list li:not(.a)');
   r.push(notAIds.length === 2 ? 1 : 'query-not-a-count-wrong:' + notAIds.length);

   var isIds = document.querySelectorAll('#list li:is(.a, .c)');
   r.push(isIds.length === 2 ? 1 : 'query-is-a-c-count-wrong:' + isIds.length);

   var bad = r.filter(function(x) { return x !== 1; });
   document.title = bad.length === 0 ? 'PASS' : 'FAIL:' + bad.join(';');")

(deftest quickjs-real-not-is-where-pseudo-classes-round-trip-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main>"
              "<ul id=\"list\">"
              "<li id=\"a\" class=\"a\">A</li>"
              "<li id=\"b\" class=\"b\">B</li>"
              "<li id=\"c\" class=\"c\">C</li>"
              "</ul>"
              "<div id=\"bar\">bar</div>"
              "<span id=\"foo\">foo</span>"
              "<script>" script "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real :not()/:is()/:where() round-trip ->" (pr-str title))
                 (is (= "PASS" title)
                     (str "expected :not()/:is()/:where() to genuinely work through "
                          "matches()/querySelectorAll() on real QuickJS -- got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (println "quickjs :not()/:is()/:where() smoke ERROR ->" err)
                  (is false (str "smoke threw: " err))
                  (done))))))
