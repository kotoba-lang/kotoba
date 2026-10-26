(ns browser.compat.quickjs-form-elements-smoke-test
  "Real page-script round-trip proof that form.elements genuinely
  exposes a real, indexable, name/id-keyed collection of the form's
  listed controls -- evaluated through the actual webapi shim string
  inside real QuickJS WASM, not a JVM stand-in.

  Before this cycle's fix, form.elements was entirely absent -- a
  script reading it got undefined, and any indexed/named access threw
  a bare TypeError."
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
     (let [url "https://app.example/form-elements-round-trip"
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
   var form = document.getElementById('f');
   var els = form.elements;

   r.push(els.length === 3 ? 1 : 'length-wrong:' + els.length);
   r.push(els[0].name === 'q' ? 1 : 'index-0-wrong');
   r.push(els['q'].name === 'q' ? 1 : 'name-access-wrong');
   r.push(els['submitBtn'].tagName === 'BUTTON' ? 1 : 'id-access-wrong');
   r.push(els.namedItem('q').name === 'q' ? 1 : 'namedItem-wrong');
   r.push(els.namedItem('missing') === null ? 1 : 'namedItem-missing-should-be-null');

   var disabledField = els['dis'];
   r.push(disabledField && disabledField.disabled === true ? 1 : 'disabled-control-should-still-be-included');

   var foundImage = false;
   for (var i = 0; i < els.length; i++) {
     if (els[i].type === 'image') foundImage = true;
   }
   r.push(!foundImage ? 1 : 'image-input-should-be-excluded');

   var tags = [];
   for (var el of els) tags.push(el.tagName);
   r.push(tags.join(',') === 'INPUT,BUTTON,INPUT' ? 1 : 'for-of-iteration-wrong:' + tags.join(','));

   var bad = r.filter(function(x) { return x !== 1; });
   document.title = bad.length === 0 ? 'PASS' : 'FAIL:' + bad.join(';');")

(deftest quickjs-real-form-elements-round-trip-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><form id=\"f\">"
              "<input name=\"q\" type=\"text\" value=\"hello\">"
              "<button id=\"submitBtn\">Go</button>"
              "<input type=\"image\" name=\"shouldExclude\" src=\"x.png\">"
              "<input name=\"dis\" type=\"text\" disabled>"
              "</form><script>" script "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real form.elements round-trip ->" (pr-str title))
                 (is (= "PASS" title)
                     (str "expected form.elements to genuinely expose an indexable, "
                          "name/id-keyed collection on real QuickJS -- got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (println "quickjs form.elements smoke ERROR ->" err)
                  (is false (str "smoke threw: " err))
                  (done))))))
