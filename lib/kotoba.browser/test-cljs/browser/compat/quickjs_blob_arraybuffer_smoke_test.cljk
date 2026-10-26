(ns browser.compat.quickjs-blob-arraybuffer-smoke-test
  "Real QuickJS WASM end-to-end proof that `new Blob([arrayBuffer])` reads
  the ArrayBuffer's REAL bytes, not the stringified `[object ArrayBuffer]`
  text.

  Companion to `quickjs_blob_formdata_smoke_test.cljs`, which never
  exercises a raw ArrayBuffer part (only strings and Blobs) -- this is
  what let the bug this cycle fixed go uncaught. A real ArrayBuffer has NO
  `.length` property in real JS (only `.byteLength`), so
  `__kotobaBlobPartsToBytes`'s typed-array branch
  (`typeof p.length === 'number'`) was never reached for it; execution
  fell through to the final `String(p)` else branch, encoding the literal
  20-character text `[object ArrayBuffer]` instead of the buffer's real
  contents. Fixed with a dedicated `p instanceof globalThis.ArrayBuffer`
  branch that wraps it in a real `Uint8Array` view."
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
     (let [url "https://app.example/blob-arraybuffer-round-trip"
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
  ;; Deliberately synchronous throughout (.size / .__bytes / .slice()),
  ;; not .arrayBuffer()/.text() -- those return a REAL, native QuickJS
  ;; Promise.resolve(), whose .then() callback needs the VM job queue
  ;; drained to ever run, which this engine's eval-result/dump-requests
  ;; never do (see __kotobaMakeDeferred's own docstring for why every
  ;; OTHER async-shaped webapi in this file avoids native Promise for
  ;; exactly this reason) -- matching quickjs_blob_formdata_smoke_test
  ;; .cljs's own established, already-working pattern.
  "var r = [];
   var ab = new ArrayBuffer(4);
   var view = new Uint8Array(ab);
   view[0] = 0xDE; view[1] = 0xAD; view[2] = 0xBE; view[3] = 0xEF;
   var b = new Blob([ab]);
   r.push(b.size === 4 ? 1 : 'size:' + b.size);
   r.push(b.__bytes.join(',') === '222,173,190,239' ? 1 : 'bytes:' + b.__bytes.join(','));
   var empty = new Blob([new ArrayBuffer(0)]);
   r.push(empty.size === 0 ? 1 : 'empty:' + empty.size);
   var mixedAb = new ArrayBuffer(2);
   new Uint8Array(mixedAb).set([65, 66]);
   var mixed = new Blob(['hi-', mixedAb, new Blob([new Uint8Array([67])])]);
   r.push(mixed.size === 6 ? 1 : 'mixed:' + mixed.size);
   r.push(mixed.__bytes.join(',') === '104,105,45,65,66,67' ? 1 : 'mixed-bytes:' + mixed.__bytes.join(','));
   var sliced = mixed.slice(3, 5);
   r.push(sliced.__bytes.join(',') === '65,66' ? 1 : 'sliced:' + sliced.__bytes.join(','));
   var bad = r.filter(function(x) { return x !== 1; });
   document.title = bad.length === 0 ? 'PASS' : 'FAIL:' + bad.join(';');")

(deftest quickjs-real-blob-arraybuffer-part-reads-real-bytes-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><script>" script "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real Blob(ArrayBuffer) round-trip ->" (pr-str title))
                 (is (= "PASS" title)
                     (str "expected new Blob([arrayBuffer]) to read the ArrayBuffer's real bytes "
                          "on real QuickJS, not the stringified [object ArrayBuffer] text -- got "
                          (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (println "quickjs Blob(ArrayBuffer) smoke ERROR ->" err)
                  (is false (str "smoke threw: " err))
                  (done))))))
