(ns browser.compat.quickjs-replacechildren-smoke-test
  "Real page-script round-trip proof that `ParentNode.replaceChildren(
  ...nodes)` accepts bare strings, not just real Node arguments, through
  actual QuickJS WASM.

  Unlike its siblings append/prepend/before/after/replaceWith (which all
  wrap each argument through the shared __kotobaNodeArg helper before
  handing it to appendChild/insertBefore), replaceChildren previously
  called `this.appendChild(arguments[i])` directly. appendChild only
  recognizes a real node (it reads `child.__kotobaRef`), so a bare
  string argument had no `__kotobaRef` and was silently dropped: calling
  `el.replaceChildren('hello')` cleared el's real children and then
  added nothing at all, leaving el completely empty -- no thrown error,
  no partial effect."
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
     (let [url "https://app.example/replace-children-round-trip"
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

(deftest quickjs-real-replacechildren-accepts-a-bare-string-argument-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><div id=\"x\">old content</div>"
              "<script>"
              "document.getElementById('x').replaceChildren('hello');"
              "document.title = 'text=\"' + document.getElementById('x').textContent + "
              "'\"|children=' + document.getElementById('x').childNodes.length;"
              "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real replaceChildren bare string ->" (pr-str title))
                 (is (= "text=\"hello\"|children=1" title)
                     (str "expected a bare string arg to become a real text-node child, got "
                          "document.title = " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-replacechildren-accepts-mixed-node-and-string-arguments-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><div id=\"x\"><span id=\"stale\">stale</span></div>"
              "<script>"
              "var x = document.getElementById('x');"
              "var child1 = document.createElement('em');"
              "child1.textContent = 'A';"
              "var child2 = document.createElement('strong');"
              "child2.textContent = 'C';"
              "x.replaceChildren(child1, 'B', child2);"
              "document.title = x.textContent + '|' + x.childNodes.length;"
              "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real replaceChildren mixed node+string ->" (pr-str title))
                 (is (= "ABC|3" title)
                     (str "expected the string arg between two real nodes to survive as its "
                          "own text-node child (not dropped), got document.title = "
                          (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))
