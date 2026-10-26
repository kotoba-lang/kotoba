(ns browser.compat.quickjs-formdata-filename-smoke-test
  "Real QuickJS WASM end-to-end proof that `FormData.append()`/`.set()`
  correctly implement real spec's \"create an entry\" Blob-handling
  algorithm: a plain Blob defaults to a File named 'blob', and a filename
  argument ALWAYS renames the resulting File -- even when the value given
  was ALREADY a File.

  Before this cycle's fix, `__kotobaFormValue` got both wrong: a plain
  Blob appended with no filename stayed a plain Blob (never normalized
  into a File at all), and a filename argument was silently dropped
  whenever the value was already a File -- `fd.append('x', existingFile,
  'renamed.txt')` kept `existingFile`'s ORIGINAL name instead of being
  renamed, real browsers' actual, common behavior."
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
     (let [url "https://app.example/formdata-filename-round-trip"
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
  "var r = [];
   var fd = new FormData();
   var plainBlob = new Blob(['hi'], {type: 'text/plain'});
   fd.append('a', plainBlob);
   var got = fd.get('a');
   r.push(got instanceof File ? 1 : 'plain-blob-not-file');
   r.push(got.name === 'blob' ? 1 : 'plain-blob-name:' + got.name);

   var existingFile = new File(['x'], 'original.txt', {type: 'text/plain', lastModified: 12345});
   fd.append('b', existingFile, 'renamed.txt');
   var b = fd.get('b');
   r.push(b.name === 'renamed.txt' ? 1 : 'rename-append:' + b.name);
   r.push(b.type === 'text/plain' ? 1 : 'rename-type:' + b.type);
   r.push(b.lastModified === 12345 ? 1 : 'rename-lm:' + b.lastModified);

   fd.set('c', existingFile, 'set-renamed.txt');
   var c = fd.get('c');
   r.push(c.name === 'set-renamed.txt' ? 1 : 'rename-set:' + c.name);

   fd.append('d', existingFile);
   var d = fd.get('d');
   r.push(d.name === 'original.txt' ? 1 : 'no-filename-unchanged:' + d.name);
   r.push(d === existingFile ? 1 : 'no-filename-same-ref');

   var bad = r.filter(function(x) { return x !== 1; });
   document.title = bad.length === 0 ? 'PASS' : 'FAIL:' + bad.join(';');")

(deftest quickjs-real-formdata-filename-arg-honored-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><script>" script "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real FormData filename round-trip ->" (pr-str title))
                 (is (= "PASS" title)
                     (str "expected FormData.append()/.set() to correctly normalize a plain Blob "
                          "into a File named 'blob' and to always honor a filename arg (even "
                          "renaming an already-File value) on real QuickJS -- got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (println "quickjs FormData filename smoke ERROR ->" err)
                  (is false (str "smoke threw: " err))
                  (done))))))
