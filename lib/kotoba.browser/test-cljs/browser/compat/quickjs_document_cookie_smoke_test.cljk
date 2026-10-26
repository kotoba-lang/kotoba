(ns browser.compat.quickjs-document-cookie-smoke-test
  "Real page-script round-trip proof that `document.cookie`'s getter now
   returns the real, current cookie header for this page's URL instead of
   always returning `''` -- previously a dead getter (confirmed via a
   temporary diagnostic test before touching source: a `document.cookie =
   'probe=hello123'` write in one <script> tag, read back in a LATER
   <script> tag on the same page, still showed `document.title ===
   'cookie=[]'`, even though the underlying cookie store + `:cookie/set`
   capability handling was already fully real and RFC-6265bis-correct --
   the JS-facing getter simply never consulted it). Mirrors the exact
   `storage-snapshot`/`localStorage.getItem` pattern already established
   for this same class of gap: a snapshot installed as a VM global BEFORE
   each script tag evaluates, since this engine runs a whole script
   synchronously in one pass with no way to defer settlement -- so, like
   `localStorage`, a write earlier in the SAME script tag is not reflected
   until the NEXT tag (an already-established, documented convention, not
   a new gap this fix introduces)."
  (:require [cljs.test :refer [deftest is async]]
            [browser.compat.quickjs-runner :as quickjs-runner]
            [browser.profile :as profile]
            [browser.session :as session]
            [browser.storage :as storage]
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
  [url html]
  (js/Promise.
   (fn [resolve reject]
     (let [fetch-fn (canned-fetch-fn {url html})
           h (host/recording-host)
           base-session (session/new-session
                         (quickjs-runner/quickjs-session-opts
                          {:host h :fetch-fn fetch-fn
                           :store (storage/empty-store)
                           :profile (profile/new-profile {:id "default"})}))]
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

(deftest quickjs-real-document-cookie-getter-reflects-a-cookie-set-in-an-earlier-script-tag-test
  (async done
    (-> (run-page-and-read-title!
         "https://app.example/cookie-round-trip"
         (str "<main></main>"
              "<script>document.cookie = 'probe=hello123';</script>"
              "<script>document.title = 'cookie=[' + document.cookie + ']';</script>"))
        (.then (fn [title]
                 (println "quickjs real document.cookie getter ->" (pr-str title))
                 (is (= "cookie=[probe=hello123]" title)
                     (str "expected a cookie set in an earlier script tag to be readable via "
                          "document.cookie in a later one, got document.title = " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-document-cookie-getter-is-empty-with-no-cookies-set-test
  (async done
    (-> (run-page-and-read-title!
         "https://app.example/cookie-empty-round-trip"
         (str "<main></main>"
              "<script>document.title = 'cookie=[' + document.cookie + ']';</script>"))
        (.then (fn [title]
                 (println "quickjs real document.cookie getter (no cookies) ->" (pr-str title))
                 (is (= "cookie=[]" title)
                     (str "expected an empty cookie header with no cookies ever set, got "
                          "document.title = " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-document-cookie-getter-reflects-a-second-cookie-appended-in-a-later-tag-test
  (async done
    (-> (run-page-and-read-title!
         "https://app.example/cookie-multi-round-trip"
         (str "<main></main>"
              "<script>document.cookie = 'a=1';</script>"
              "<script>document.cookie = 'b=2';</script>"
              "<script>document.title = 'cookie=[' + document.cookie + ']';</script>"))
        (.then (fn [title]
                 (println "quickjs real document.cookie getter (two cookies) ->" (pr-str title))
                 (is (= "cookie=[a=1; b=2]" title)
                     (str "expected both cookies, set in two separate earlier script tags, to "
                          "both be readable, got document.title = " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))
