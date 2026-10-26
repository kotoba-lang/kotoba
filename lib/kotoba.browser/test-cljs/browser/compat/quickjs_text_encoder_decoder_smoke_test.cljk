(ns browser.compat.quickjs-text-encoder-decoder-smoke-test
  "Real page-script round-trip proof that TextEncoder/TextDecoder exist
  and correctly round-trip real multi-byte UTF-8 text, evaluated through
  the actual webapi shim string inside real QuickJS WASM, not a JVM
  stand-in.

  Before this cycle's fix, `new TextEncoder()`/`new TextDecoder()` threw
  a bare ReferenceError -- every other commonly-paired webapi capability
  (Blob, FormData, AbortController, ...) was defined, but not these two,
  even though the exact UTF-8 codec they need already existed internally
  for Blob's own text()/arrayBuffer()."
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

(defn- run-page-and-read-title!
  [html]
  (js/Promise.
   (fn [resolve reject]
     (let [url "https://app.example/text-encoder-decoder"
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

   var enc = new TextEncoder();
   var dec = new TextDecoder();

   r.push(enc.encoding === 'utf-8' ? 1 : 'encoder-encoding-mismatch:' + enc.encoding);
   r.push(dec.encoding === 'utf-8' ? 1 : 'decoder-encoding-mismatch:' + dec.encoding);

   var ascii = enc.encode('hello');
   r.push(ascii instanceof Uint8Array ? 1 : 'encode-should-return-uint8array');
   r.push(ascii.length === 5 ? 1 : 'ascii-length-mismatch:' + ascii.length);
   r.push(dec.decode(ascii) === 'hello' ? 1 : 'ascii-round-trip-failed:' + dec.decode(ascii));

   // multi-byte UTF-8: accented (2-byte), Japanese (3-byte), emoji (4-byte surrogate pair)
   var text = 'café 日本語 🎉';
   var bytes = enc.encode(text);
   r.push(dec.decode(bytes) === text ? 1 : 'multibyte-round-trip-failed:' + dec.decode(bytes));

   // decode() accepts a raw ArrayBuffer, not just a Uint8Array view
   r.push(dec.decode(bytes.buffer) === text ? 1 : 'arraybuffer-decode-failed:' + dec.decode(bytes.buffer));

   // an unsupported label throws
   var threw = false;
   try { new TextDecoder('iso-8859-1'); } catch (e) { threw = String(e).indexOf('RangeError') !== -1; }
   r.push(threw ? 1 : 'unsupported-label-should-throw');

   var bad = r.filter(function(x) { return x !== 1; });
   document.title = bad.length === 0 ? 'PASS' : 'FAIL:' + bad.join(';');")

(deftest quickjs-real-text-encoder-decoder-round-trip-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><script>" script "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real TextEncoder/TextDecoder round-trip ->" (pr-str title))
                 (is (= "PASS" title)
                     (str "expected TextEncoder/TextDecoder to correctly round-trip real "
                          "multi-byte UTF-8 text on real QuickJS -- got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (println "quickjs TextEncoder/TextDecoder smoke ERROR ->" err)
                  (is false (str "smoke threw: " err))
                  (done))))))
