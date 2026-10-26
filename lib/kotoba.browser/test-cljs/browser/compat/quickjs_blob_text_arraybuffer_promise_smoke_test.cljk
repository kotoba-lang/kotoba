(ns browser.compat.quickjs-blob-text-arraybuffer-promise-smoke-test
  "Real QuickJS WASM end-to-end proof that `Blob.prototype.text()` and
  `Blob.prototype.arrayBuffer()` return REAL thenables whose `.then()`
  callback genuinely fires within the same script tag, not a real, native
  QuickJS `Promise.resolve()` whose reactions never run.

  Both previously returned `Promise.resolve(...)` directly -- the ONLY
  place in the whole webapi shim that did (confirmed via `grep -n
  \"Promise.resolve\"` returning exactly these two hits). Every other
  async-shaped webapi in this file (`fetch()`/`Response.text`,
  `clipboard.readText`/`writeText`, `getUserMedia`,
  `Notification.requestPermission`, `requestFullscreen`/
  `exitFullscreen`) already used the hand-rolled `__kotobaMakeDeferred`
  thenable instead, specifically because this engine's `eval-result`/
  `dump-requests` never call `runtime.executePendingJobs()` (confirmed
  via `grep -rn executePendingJobs` across the whole repo: zero real call
  sites, only the explanatory comment) -- a real native Promise's `.then()`
  reactions are queued as VM jobs that, without that pump, never run.
  `quickjs_blob_arraybuffer_smoke_test.cljs` (the prior cycle's own test)
  had to deliberately route around this via synchronous `.size`/
  `.__bytes`/`.slice()` checks instead of `.text()`/`.arrayBuffer()`,
  which is exactly what surfaced this bug in the first place. This test
  proves the fix: real `.then()` callbacks on both now genuinely fire,
  synchronously within the same script tag (matching `__kotobaMakeDeferred`'s
  own settle-synchronously design, documented in quickjs_wasm.cljc)."
  (:require [cljs.test :refer [deftest is async]]
            [browser.compat.quickjs-runner :as quickjs-runner]
            [browser.session :as session]
            [kotoba.wasm.host :as host]))

(defn- dispose-engine!
  [session]
  (when-let [engine (get-in session [:browser.session/script-engine :script-engine/engine])]
    (when-let [dispose (:quickjs.engine/dispose engine)]
      (dispose engine))))

(defn- canned-fetch-fn [pages]
  (fn [{:keys [url]}]
    (if-let [html (get pages url)]
      {:status 200 :headers {} :body html}
      {:status 404 :headers {} :body "<main>not found</main>"})))

(defn- run-page-and-read-title! [html]
  (js/Promise.
   (fn [resolve reject]
     (let [url "https://app.example/blob-text-arraybuffer-promise"
           fetch-fn (canned-fetch-fn {url html})
           h (host/recording-host)
           base-session (session/new-session
                         (quickjs-runner/quickjs-session-opts {:host h :fetch-fn fetch-fn}))]
       (-> (session/ensure-script-engine! base-session)
           (.then (fn [ready-session]
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
  "document.title = 'pending';
   var b = new Blob(['hello']);
   var textResult = b.text();
   document.title = (typeof textResult.then === 'function') ? 'text-has-then' : 'text-no-then';
   textResult.then(function(txt) {
     document.title = document.title + ':text-resolved:' + txt;
     var ab = new ArrayBuffer(3);
     new Uint8Array(ab).set([65, 66, 67]);
     var b2 = new Blob([ab]);
     var abResult = b2.arrayBuffer();
     document.title = document.title + ':' + ((typeof abResult.then === 'function') ? 'ab-has-then' : 'ab-no-then');
     abResult.then(function(buf) {
       var bytes = Array.prototype.slice.call(new Uint8Array(buf)).join(',');
       document.title = document.title + ':ab-resolved:' + bytes;
     });
   });")

(deftest quickjs-real-blob-text-and-arraybuffer-then-callbacks-fire-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><script>" script "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real Blob.text()/arrayBuffer() .then() smoke: document.title ->"
                          (pr-str title))
                 (is (= "text-has-then:text-resolved:hello:ab-has-then:ab-resolved:65,66,67" title)
                     (str "expected both Blob.text() and Blob.arrayBuffer() to return real thenables "
                          "whose .then() callbacks genuinely fire within the same script tag on real "
                          "QuickJS -- got document.title = " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (println "quickjs Blob.text()/arrayBuffer() smoke ERROR ->" err)
                  (is false (str "smoke threw: " err))
                  (done))))))
