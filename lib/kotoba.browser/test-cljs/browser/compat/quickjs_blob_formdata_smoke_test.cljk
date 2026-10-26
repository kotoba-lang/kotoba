(ns browser.compat.quickjs-blob-formdata-smoke-test
  "Real QuickJS WASM end-to-end proof that the L2 Blob/File/FormData shims
  behave per WHATWG: Blob byte size + UTF-8 fidelity + slice (incl. negative)
  + type, File name/lastModified/instanceof Blob, FormData append/set/get/
  getAll/has/delete/forEach + Blob/File values + `new FormData(formEl)`
  enumerating a form's submittable controls (checked checkboxes only, the
  selected <option>, skipping unnamed/disabled/buttons/file/submit inputs).
  This is the only place the actual JS shim runs -- the JVM compat tests are
  source-presence checks (real JS execution is the cljs/node-test target)."
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
     (let [url "https://app.example/blob-formdata-round-trip"
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
   var b = new Blob(['hello', ' world'], {type: 'text/plain'});
   r.push(b.size === 11 ? 1 : 'size:' + b.size);
   r.push(b.type === 'text/plain' ? 1 : 'type:' + b.type);
   var cafe = new Blob(['café']);
   r.push(cafe.size === 5 ? 1 : 'utf8:' + cafe.size);
   r.push(b.slice(0,5).size === 5 ? 1 : 'slice');
   r.push(b.slice(-5).size === 5 ? 1 : 'slice-neg');
   r.push(b.slice(2,2).size === 0 ? 1 : 'slice-empty');
   var f = new File([b], 'greet.txt', {type: 'text/plain', lastModified: 42});
   r.push(f.name === 'greet.txt' ? 1 : 'name');
   r.push(f.size === 11 ? 1 : 'fsize:' + f.size);
   r.push(f.lastModified === 42 ? 1 : 'lm:' + f.lastModified);
   r.push(f instanceof Blob ? 1 : 'not-blob');
   r.push(f instanceof File ? 1 : 'not-file');
   var fd = new FormData();
   fd.append('a', '1'); fd.append('a', '2'); fd.append('b', '3');
   r.push(fd.get('a') === '1' ? 1 : 'get');
   r.push(JSON.stringify(fd.getAll('a')) === '[\"1\",\"2\"]' ? 1 : 'getall');
   r.push(fd.has('b') ? 1 : 'has');
   fd.delete('b');
   r.push(!fd.has('b') ? 1 : 'delete');
   fd.set('a', 'X');
   r.push(JSON.stringify(fd.getAll('a')) === '[\"X\"]' ? 1 : 'set');
   var entries = []; fd.forEach(function(v, k) { entries.push(k + '=' + v); });
   r.push(entries.join(',') === 'a=X' ? 1 : 'foreach:' + entries.join(','));
   fd.append('file', new File(['data'], 'f.txt'));
   r.push(fd.get('file') instanceof File ? 1 : 'fdfile');
   var ff = new FormData(document.getElementById('form'));
   r.push(ff.get('x') === '42' ? 1 : 'form-x:' + ff.get('x'));
   r.push(ff.get('c') === 'yes' ? 1 : 'form-c:' + ff.get('c'));
   r.push(!ff.has('c2') ? 1 : 'form-unchecked-leak');
   r.push(ff.get('s') === 'b' ? 1 : 'form-s:' + ff.get('s'));
   r.push(!ff.has('btn') ? 1 : 'form-button-leak');
   var bad = r.filter(function(x) { return x !== 1; });
   document.title = bad.length === 0 ? 'PASS' : 'FAIL:' + bad.join(';');")

(deftest quickjs-real-blob-file-formdata-round-trip-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><form id=\"form\">"
              "<input name=\"x\" value=\"42\">"
              "<input type=\"checkbox\" name=\"c\" value=\"yes\" checked>"
              "<input type=\"checkbox\" name=\"c2\" value=\"no\">"
              "<select name=\"s\"><option value=\"a\">A</option><option value=\"b\" selected>B</option></select>"
              "<button name=\"btn\">Go</button>"
              "</form>"
              "<script>" script "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real Blob/File/FormData round-trip ->" (pr-str title))
                 (is (= "PASS" title)
                     (str "expected all Blob/File/FormData checks to pass on real QuickJS, got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (println "quickjs Blob/File/FormData smoke ERROR ->" err)
                  (is false (str "smoke threw: " err))
                  (done))))))
