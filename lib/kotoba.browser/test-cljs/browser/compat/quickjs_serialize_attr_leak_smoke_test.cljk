(ns browser.compat.quickjs-serialize-attr-leak-smoke-test
  "Real page-script round-trip proof that `.attributes`/`innerHTML`/
   `outerHTML` no longer enumerate this engine's own internal bookkeeping
   attrs (`default-value`/`default-checked`/`default-selected`,
   `scroll-top`/`scroll-left`, `selection-start`/`selection-end`,
   `composition`/`composing`, `invalid`/`validation-reason`,
   `dirty-value`, `files`, every cascade-resolved `style/<prop>` longhand,
   and `style-inline`/`style-inline-important`) -- previously ALL of these
   were written via the exact same generic `dom/set-attribute` real-attribute
   path author-visible attributes use (see `cssom.core/style-element`,
   `htmldom.core/initialize-form-node`, `browser.document_input`'s
   selection/composition/validation/file-list tracking), and
   `__kotobaSerializeNode`/`__kotobaAttributes` enumerated `Object.keys`
   with zero filtering, so any styled element or form control's real
   `outerHTML`/`.attributes` leaked dozens of attributes no real browser
   ever shows (confirmed via a temporary diagnostic test before touching
   source: a plain `<input value=\"hi\">` serialized as `<input
   default-value=\"hi\" id=\"x\" style-inline=\"[object Object]\" ...>`).

   Also covers a second, adjacent bug found in the same
   `__kotobaSerializeNode` function while diagnosing the first: void
   elements (`<input>`/`<img>`/`<br>`/...) were serialized with a bogus
   closing tag (`</input>`), which no real browser's `outerHTML` ever
   produces for a void element."
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
     (let [url "https://app.example/serialize-attr-leak-round-trip"
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

(deftest quickjs-real-outerhtml-does-not-leak-default-value-or-style-internals-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><input id=\"x\" value=\"hi\" style=\"color:red\"></main>"
              "<script>"
              "document.title = document.getElementById('x').outerHTML;"
              "</script>"))
        (.then (fn [title]
                 (println "quickjs real outerHTML (no internal-attr leak) ->" (pr-str title))
                 (is (= "<input id=\"x\" value=\"hi\">" title)
                     (str "expected outerHTML to show only the real id/value attributes -- "
                          "no default-value, no style-inline, no style/* longhands -- got "
                          (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-attributes-namedmap-does-not-enumerate-internal-keys-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><input id=\"x\" value=\"hi\" style=\"color:red\"></main>"
              "<script>"
              "var x = document.getElementById('x');"
              "var names = [];"
              "for (var i = 0; i < x.attributes.length; i++) { names.push(x.attributes[i].name); }"
              "document.title = names.sort().join(',');"
              "</script>"))
        (.then (fn [title]
                 (println "quickjs real .attributes (no internal-key leak) ->" (pr-str title))
                 (is (= "id,value" title)
                     (str "expected .attributes to enumerate only id/value -- got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-outerhtml-void-element-has-no-closing-tag-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><img id=\"pic\" src=\"a.png\"></main>"
              "<script>"
              "document.title = document.getElementById('pic').outerHTML;"
              "</script>"))
        (.then (fn [title]
                 (println "quickjs real outerHTML (void element, no closing tag) ->" (pr-str title))
                 (is (= "<img id=\"pic\" src=\"a.png\">" title)
                     (str "a void element's outerHTML must not include a bogus closing tag -- got "
                          (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-outerhtml-non-void-element-still-closes-normally-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><div id=\"d\" class=\"box\">hi</div></main>"
              "<script>"
              "document.title = document.getElementById('d').outerHTML;"
              "</script>"))
        (.then (fn [title]
                 (println "quickjs real outerHTML (ordinary non-void element) ->" (pr-str title))
                 (is (= "<div class=\"box\" id=\"d\">hi</div>" title)
                     (str "a non-void element must keep its real closing tag and children -- got "
                          (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-outerhtml-real-boolean-attribute-still-shows-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><input id=\"cb\" type=\"checkbox\" checked></main>"
              "<script>"
              "document.title = document.getElementById('cb').outerHTML;"
              "</script>"))
        (.then (fn [title]
                 (println "quickjs real outerHTML (real checked attribute survives) ->" (pr-str title))
                 (is (re-find #"checked" title)
                     (str "a real, author-visible boolean attribute like checked must still show "
                          "up in outerHTML -- only THIS engine's own internal bookkeeping is "
                          "filtered -- got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))
