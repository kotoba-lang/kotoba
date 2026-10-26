(ns browser.compat.quickjs-replace-child-smoke-test
  "Real page-script round-trip proof that `Node.replaceChild(newChild,
  oldChild)` -- one of the oldest, most common DOM Level 1 mutation
  methods, previously entirely missing from the webapi shim (confirmed via
  a repo-wide grep returning zero matches; calling it threw a real
  `TypeError`) -- now works through actual QuickJS WASM, not a JVM
  stand-in.

  `replaceChild` composes the already-existing, already-tested
  `insertBefore`/`removeChild` methods verbatim (the same composition
  `replaceWith` already uses, just called on the PARENT with the
  `(newChild, oldChild)` argument order and returning the REMOVED node
  per spec, not the new one)."
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
     (let [url "https://app.example/replace-child-round-trip"
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

(deftest quickjs-real-replace-child-swaps-node-in-place-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><ul id=\"list\"><li id=\"old\">old</li></ul>"
              "<script>"
              "var list = document.getElementById('list');"
              "var oldChild = document.getElementById('old');"
              "var newChild = document.createElement('li');"
              "newChild.id = 'new';"
              "newChild.textContent = 'new';"
              "var returned = list.replaceChild(newChild, oldChild);"
              "document.title = String(list.children.length) + ':' + "
              "list.firstChild.textContent + ':' + (returned === oldChild);"
              "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real replaceChild swap-in-place ->" (pr-str title))
                 (is (= "1:new:true" title)
                     (str "expected exactly 1 remaining child, its text 'new', and the "
                          "returned node to be the REMOVED old child per spec, got "
                          "document.title = " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-replace-child-preserves-sibling-order-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><ul id=\"list\">"
              "<li id=\"first\">first</li><li id=\"old\">old</li><li id=\"last\">last</li>"
              "</ul>"
              "<script>"
              "var list = document.getElementById('list');"
              "var oldChild = document.getElementById('old');"
              "var newChild = document.createElement('li');"
              "newChild.textContent = 'middle';"
              "list.replaceChild(newChild, oldChild);"
              "var texts = [];"
              "for (var i = 0; i < list.children.length; i++) { texts.push(list.children[i].textContent); }"
              "document.title = texts.join(',');"
              "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real replaceChild preserves order ->" (pr-str title))
                 (is (= "first,middle,last" title)
                     (str "expected the replaced node to land in the EXACT position the old "
                          "child occupied, got document.title = " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))
