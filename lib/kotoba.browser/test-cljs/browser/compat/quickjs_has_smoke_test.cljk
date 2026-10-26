(ns browser.compat.quickjs-has-smoke-test
  "Real page-script round-trip proof that :has() genuinely works through
  the JS-facing selector engine (matches()/querySelectorAll()) --
  evaluated through the actual webapi shim string inside real QuickJS
  WASM, not a JVM stand-in.

  Before this cycle's fix, :has() was entirely absent -- any selector
  using it always returned an empty/false result, regardless of the
  candidate node's actual subtree contents."
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
     (let [url "https://app.example/has-round-trip"
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
   var card1 = document.getElementById('card1');
   var card2 = document.getElementById('card2');
   var gallery = document.getElementById('gallery');
   var wrapper = document.getElementById('wrapper');
   var emptyDiv = document.getElementById('emptyDiv');

   // descendant-anywhere form -- matches however deeply nested
   r.push(card1.matches('.card:has(.badge)') === true ? 1 : 'card1-should-have-badge-anywhere');
   r.push(card2.matches('.card:has(.badge)') === false ? 1 : 'card2-should-not-have-badge');

   // direct-child form -- must NOT fall back to a deeper descendant match
   r.push(gallery.matches('.gallery:has(> img)') === true ? 1 : 'gallery-should-have-direct-img-child');
   r.push(wrapper.matches('div:has(> img)') === true ? 1 : 'wrapper-should-have-direct-img-child');
   r.push(card1.matches('.card:has(> .badge)') === false ? 1 : 'card1-badge-is-nested-not-direct-child');

   // no descendants at all
   r.push(emptyDiv.matches('div:has(.anything)') === false ? 1 : 'emptyDiv-has-no-descendants');

   // comma-separated group -- OR semantics
   r.push(card1.matches('.card:has(.missing, .badge)') === true ? 1 : 'card1-should-match-via-second-group-item');
   r.push(card2.matches('.card:has(.missing, .badge)') === false ? 1 : 'card2-should-match-neither-group-item');

   // real query pipeline, not just matches()
   var withBadge = document.querySelectorAll('.card:has(.badge)');
   r.push(withBadge.length === 1 && withBadge[0] === card1 ? 1 : 'query-has-badge-wrong:' + withBadge.length);

   var bad = r.filter(function(x) { return x !== 1; });
   document.title = bad.length === 0 ? 'PASS' : 'FAIL:' + bad.join(';');")

(deftest quickjs-real-has-pseudo-class-round-trip-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main>"
              "<div id=\"card1\" class=\"card\"><div class=\"wrap\"><span class=\"badge\">new</span></div></div>"
              "<div id=\"card2\" class=\"card\"><p>no badge here</p></div>"
              "<div id=\"gallery\" class=\"gallery\"><img src=\"a.png\">"
              "<div id=\"wrapper\"><img src=\"b.png\"></div></div>"
              "<div id=\"emptyDiv\"></div>"
              "<script>" script "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real :has() round-trip ->" (pr-str title))
                 (is (= "PASS" title)
                     (str "expected :has() to genuinely work through "
                          "matches()/querySelectorAll() on real QuickJS -- got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (println "quickjs :has() smoke ERROR ->" err)
                  (is false (str "smoke threw: " err))
                  (done))))))
