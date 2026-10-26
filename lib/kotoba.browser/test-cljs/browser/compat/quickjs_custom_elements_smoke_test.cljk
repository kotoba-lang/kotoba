(ns browser.compat.quickjs-custom-elements-smoke-test
  "Real page-script round-trip proof that globalThis.customElements --
  previously entirely missing (webapi/webapi-surface's :window list
  declared :customElements as supported, but no code anywhere installed
  it, so any real script touching it crashed the whole script tag with a
  ReferenceError) -- now exists and runs real define()/get()/
  whenDefined() registration semantics through actual QuickJS WASM
  end-to-end."
  (:require [cljs.test :refer [deftest is async]]
            [browser.compat.quickjs-runner :as quickjs-runner]
            [browser.session :as session]
            [kotoba.wasm.host :as host]))

(defn- dispose-engine!
  [session]
  (when-let [engine (get-in session [:browser.session/script-engine :script-engine/engine])]
    (when-let [dispose (:quickjs.engine/dispose engine)]
      (dispose engine))))

(defn- run-page-and-read-title!
  [{:keys [html]}]
  (js/Promise.
   (fn [resolve reject]
     (let [h (host/recording-host)
           base-session (session/new-session (quickjs-runner/quickjs-session-opts {:host h}))]
       (-> (session/ensure-script-engine! base-session)
           (.then
            (fn [ready-session]
              (try
                (let [after (session/load-html! ready-session
                                                {:url "kotoba://custom-elements-round-trip"
                                                 :html html})
                      title (get-in after [:browser.session/page :browser/title])]
                  (dispose-engine! after)
                  (resolve title))
                (catch :default e
                  (dispose-engine! ready-session)
                  (reject e)))))
           (.catch (fn [err]
                     (dispose-engine! base-session)
                     (reject err))))))))

(deftest quickjs-real-custom-elements-define-and-get-round-trip-test
  (async done
    (-> (run-page-and-read-title!
         {:html (str "<script>"
                     "function MyWidget() {}"
                     "customElements.define('my-widget', MyWidget);"
                     "document.title = (customElements.get('my-widget') === MyWidget) + ':' + "
                     "(customElements.get('unknown-thing') === undefined);"
                     "</script>")})
        (.then (fn [title]
                 (println "quickjs real customElements.define()/.get() ->" (pr-str title))
                 (is (= "true:true" title)
                     (str "expected get() to return the exact constructor passed to define(), and "
                          "undefined for an unregistered name, got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-custom-elements-define-rejects-an-invalid-name-test
  (async done
    (-> (run-page-and-read-title!
         {:html (str "<script>"
                     "var threw = false;"
                     "try { customElements.define('nohyphen', function(){}); }"
                     "catch (e) { threw = (e instanceof TypeError); }"
                     "document.title = String(threw);"
                     "</script>")})
        (.then (fn [title]
                 (println "quickjs real customElements.define() with an invalid name ->" (pr-str title))
                 (is (= "true" title)
                     (str "expected define() with a hyphen-less name to throw a real TypeError, "
                          "got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-custom-elements-define-rejects-a-name-with-uppercase-letters-test
  ;; Real spec (PotentialCustomElementName): the name must start with a
  ;; lowercase ASCII letter and contain no uppercase ASCII letters
  ;; anywhere. Previously unchecked -- customElements.define('Foo-Bar', ...)
  ;; silently succeeded instead of throwing.
  (async done
    (-> (run-page-and-read-title!
         {:html (str "<script>"
                     "var threw = false;"
                     "try { customElements.define('Foo-Bar', function(){}); }"
                     "catch (e) { threw = (e instanceof TypeError); }"
                     "document.title = String(threw);"
                     "</script>")})
        (.then (fn [title]
                 (println "quickjs real customElements.define() with an uppercase-containing name ->" (pr-str title))
                 (is (= "true" title)
                     (str "expected define() with a name containing uppercase letters to throw a "
                          "real TypeError, got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-custom-elements-define-rejects-a-duplicate-name-test
  (async done
    (-> (run-page-and-read-title!
         {:html (str "<script>"
                     "customElements.define('dup-widget', function A(){});"
                     "var threw = false;"
                     "try { customElements.define('dup-widget', function B(){}); }"
                     "catch (e) { threw = (e instanceof TypeError); }"
                     "document.title = String(threw);"
                     "</script>")})
        (.then (fn [title]
                 (println "quickjs real customElements.define() with a duplicate name ->" (pr-str title))
                 (is (= "true" title)
                     (str "expected a second define() call for an already-registered name to throw, "
                          "got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-custom-elements-when-defined-resolves-immediately-for-an-already-defined-name-test
  (async done
    (-> (run-page-and-read-title!
         {:html (str "<script>"
                     "customElements.define('ready-widget', function(){});"
                     "customElements.whenDefined('ready-widget').then(function() {"
                     "  document.title = 'resolved';"
                     "});"
                     "</script>")})
        (.then (fn [title]
                 (println "quickjs real customElements.whenDefined() (already defined) ->" (pr-str title))
                 (is (= "resolved" title)
                     (str "expected whenDefined() on an already-registered name to resolve, "
                          "got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-custom-elements-when-defined-resolves-once-a-later-define-call-lands-test
  (async done
    (-> (run-page-and-read-title!
         {:html (str "<script>"
                     "var order = [];"
                     "customElements.whenDefined('later-widget').then(function() {"
                     "  order.push('resolved');"
                     "  document.title = order.join(',');"
                     "});"
                     "order.push('before-define');"
                     "customElements.define('later-widget', function(){});"
                     "order.push('after-define');"
                     "</script>")})
        (.then (fn [title]
                 (println "quickjs real customElements.whenDefined() (defined later) ->" (pr-str title))
                 (is (= "before-define,resolved" title)
                     (str "expected whenDefined() registered before define() to resolve the moment "
                          "define() runs, synchronously within the same script tag (mirroring "
                          "__kotobaMakeDeferred's already-established synchronous-settle posture), "
                          "got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))
