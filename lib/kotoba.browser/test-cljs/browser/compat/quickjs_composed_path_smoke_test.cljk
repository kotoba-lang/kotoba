(ns browser.compat.quickjs-composed-path-smoke-test
  "Real page-script round-trip proof that Event.prototype.composedPath()
  exists and returns the real spec-shaped dispatch path -- target through
  ancestors, then document, then window for an in-document event, unaffected
  by a later stopPropagation() call, correctly empty for a never-dispatched
  event, and correct for document-level dispatch too -- evaluated through
  the actual webapi shim string inside real QuickJS WASM, not a JVM
  stand-in.

  Before this cycle's fix, composedPath was undefined on every event,
  everywhere -- __kotobaEvent is the single event-construction helper every
  Event/CustomEvent/MouseEvent/KeyboardEvent constructor and every dispatch
  path shares, and it never attached one at all."
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
     (let [url "https://app.example/composed-path-round-trip"
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

   // Real page structure wraps every page in a synthetic :document root
   // node ABOVE <main> (confirmed via direct REPL inspection of
   // browser.core/load-html's own node tree: root(tag :document) -> main
   // -> ...page content), so a target's real ancestor chain is longer
   // than its literal HTML nesting alone suggests -- length checks below
   // account for both <main> and that synthetic root node, then the
   // shim's own document/window objects on top.
   var outer = document.getElementById('outer');
   var inner = document.getElementById('inner');
   var btn = document.getElementById('btn');
   var capturedPath = null;
   outer.addEventListener('click', function(e) { capturedPath = e.composedPath(); });
   btn.dispatchEvent(new Event('click', { bubbles: true }));
   r.push(capturedPath && capturedPath.length === 7 ? 1 : 'path-length:' + (capturedPath && capturedPath.length));
   r.push(capturedPath && capturedPath[0] === btn ? 1 : 'path-target-first');
   r.push(capturedPath && capturedPath[1] === inner ? 1 : 'path-inner-second');
   r.push(capturedPath && capturedPath[2] === outer ? 1 : 'path-outer-third');
   r.push(capturedPath && capturedPath[capturedPath.length - 2] === document ? 1 : 'path-document-second-to-last');
   r.push(capturedPath && capturedPath[capturedPath.length - 1] === window ? 1 : 'path-window-last');

   var pathAfterStop = null;
   var box = document.getElementById('box');
   box.addEventListener('click', function(e) { e.stopPropagation(); pathAfterStop = e.composedPath(); });
   box.dispatchEvent(new Event('click', { bubbles: true }));
   r.push(pathAfterStop && pathAfterStop.length === 5 ? 1 : 'stop-propagation-shrunk-path:' + (pathAfterStop && pathAfterStop.length));
   r.push(pathAfterStop && pathAfterStop[0] === box ? 1 : 'stop-propagation-path-target-first');
   r.push(pathAfterStop && pathAfterStop[pathAfterStop.length - 1] === window ? 1 : 'stop-propagation-path-window-last');

   var freshEvent = new Event('nope');
   r.push(freshEvent.composedPath().length === 0 ? 1 : 'never-dispatched-nonempty');

   var docPath = null;
   document.addEventListener('custom', function(e) { docPath = e.composedPath(); });
   document.dispatchEvent(new CustomEvent('custom'));
   r.push(docPath && docPath.length === 2 ? 1 : 'doc-dispatch-path-length:' + (docPath && docPath.length));
   r.push(docPath && docPath[0] === document ? 1 : 'doc-dispatch-first-document');
   r.push(docPath && docPath[1] === window ? 1 : 'doc-dispatch-second-window');

   var bad = r.filter(function(x) { return x !== 1; });
   document.title = bad.length === 0 ? 'PASS' : 'FAIL:' + bad.join(';');")

(deftest quickjs-real-composed-path-round-trip-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main>"
              "<div id=\"outer\"><div id=\"inner\"><button id=\"btn\">go</button></div></div>"
              "<div id=\"box\">content</div>"
              "<script>" script "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real composedPath round-trip ->" (pr-str title))
                 (is (= "PASS" title)
                     (str "expected composedPath() to return the real spec-shaped dispatch "
                          "path on real QuickJS -- got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (println "quickjs composedPath smoke ERROR ->" err)
                  (is false (str "smoke threw: " err))
                  (done))))))
