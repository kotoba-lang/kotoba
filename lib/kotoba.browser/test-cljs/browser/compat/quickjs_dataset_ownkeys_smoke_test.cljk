(ns browser.compat.quickjs-dataset-ownkeys-smoke-test
  "Real page-script round-trip proof that `element.dataset` (a real
  DOMStringMap) enumerates like a plain object -- `Object.keys()`,
  `for...in`, and object-spread all see every real `data-*` attribute --
  matching direct property access (`el.dataset.foo`), which already
  worked correctly.

  Previously `__kotobaDataSet`'s Proxy had `get`/`set`/`deleteProperty`
  traps but no `ownKeys`/`getOwnPropertyDescriptor` traps, so every one
  of those enumeration paths fell through to the Proxy's own
  permanently-empty `{}` target instead, silently returning nothing."
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
     (let [url "https://app.example/dataset-ownkeys-round-trip"
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

(deftest quickjs-real-dataset-object-keys-for-in-and-spread-all-enumerate-real-data-attributes-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><div id=\"x\" data-foo=\"1\" data-bar-baz=\"2\">y</div>"
              "<script>"
              "var el = document.getElementById('x');"
              "var keys = Object.keys(el.dataset);"
              "var forin = [];"
              "for (var k in el.dataset) { forin.push(k); }"
              "var spread = Object.keys(Object.assign({}, el.dataset));"
              "document.title = 'direct=' + el.dataset.foo + '|keys=' + keys.join(',') + "
              "'|forin=' + forin.join(',') + '|spread=' + spread.join(',');"
              "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real dataset enumeration ->" (pr-str title))
                 (is (= "direct=1|keys=foo,barBaz|forin=foo,barBaz|spread=foo,barBaz" title)
                     (str "expected direct property access AND all three enumeration paths "
                          "(Object.keys/for-in/spread) to agree on the same real, "
                          "correctly-camelCased data-* keys, got document.title = "
                          (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-dataset-deleting-a-key-removes-it-from-enumeration-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><div id=\"x\" data-foo=\"1\" data-bar=\"2\">y</div>"
              "<script>"
              "var el = document.getElementById('x');"
              "delete el.dataset.foo;"
              "var keys = Object.keys(el.dataset);"
              "document.title = 'keys=' + keys.join(',');"
              "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real dataset delete then enumerate ->" (pr-str title))
                 (is (= "keys=bar" title)
                     (str "expected the deleted key to no longer appear in enumeration "
                          "while the untouched sibling key survives, got document.title = "
                          (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-dataset-with-no-data-attributes-enumerates-empty-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><div id=\"x\">y</div>"
              "<script>"
              "var el = document.getElementById('x');"
              "var keys = Object.keys(el.dataset);"
              "document.title = 'keys.length=' + keys.length;"
              "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real dataset no attrs ->" (pr-str title))
                 (is (= "keys.length=0" title)
                     (str "expected an element with no data-* attributes at all to "
                          "enumerate as genuinely empty, not throw or leak unrelated "
                          "attributes, got document.title = " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))
