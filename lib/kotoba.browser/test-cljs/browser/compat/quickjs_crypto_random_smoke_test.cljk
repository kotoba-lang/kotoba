(ns browser.compat.quickjs-crypto-random-smoke-test
  "Real page-script round-trip proof for `crypto.getRandomValues`/
  `crypto.randomUUID`.

  Before this change, both always returned a fixed, predictable result --
  `getRandomValues` filled the passed array with zeros, `randomUUID` always
  returned the literal string '00000000-0000-4000-8000-000000000000' -- no
  matter what real randomness the host queued up. `quickjs-execution/
  evaluate!` computes a REAL `crypto-snapshot` (the host-side
  `:crypto/random-bytes`/`:crypto/random-uuids` queues -- the SAME queues
  `take-random-bytes`/`take-random-uuid` already consumed for the
  post-hoc audit trail) host-side BEFORE the script runs, threads it into
  `quickjs-wasm` as `:crypto/snapshot`, which installs it as
  `globalThis.__kotobaCryptoSnapshot` before eval, and the webapi shim's
  `getRandomValues`/`randomUUID` now read from it with a per-script-tag
  cursor instead of hardcoding zeros/the placeholder UUID.

  Mirrors `quickjs-geolocation-smoke-test`'s seeding technique exactly: a
  real queue is seeded into the session's page-lifetime `quickjs-execution`
  runtime state (`:browser.session/quickjs-runtime-state`) BEFORE the real
  `<script>` tag runs, mirroring how a real host CSPRNG would back this
  API. The engine, the JS execution, and the capability request queuing are
  all real -- nothing here is mocked or inlined. The proof is genuinely
  JS-visible: every test asserts the REAL committed `document.title` a real
  `<script>` tag set from what `getRandomValues`/`randomUUID` actually
  returned, not a host-side `:capability/results` log entry."
  (:require [cljs.test :refer [deftest is async]]
            [browser.compat.quickjs-runner :as quickjs-runner]
            [browser.session :as session]
            [kotoba.wasm.host :as host]))

(defn- dispose-engine!
  [session]
  (when-let [engine (get-in session [:browser.session/script-engine :script-engine/engine])]
    (when-let [dispose (:quickjs.engine/dispose engine)]
      (dispose engine))))

(defn- seed-crypto
  "Seed real random-byte/UUID queues into `session`'s page-lifetime
  `quickjs-execution` runtime state, tagged with the generation the page
  `load-html!` is about to commit -- mirrors `quickjs-geolocation-smoke-
  test`'s `seed-geolocation` exactly, just for `:crypto/random-bytes`/
  `:crypto/random-uuids` instead of `:geolocation`."
  [session bytes uuids]
  (assoc session :browser.session/quickjs-runtime-state
         {:quickjs-runtime/generation (inc (:browser.session/page-generation session 0))
          :quickjs-runtime/state {:crypto/random-bytes (vec bytes)
                                   :crypto/random-uuids (vec uuids)}}))

(defn- run-page-and-read-title!
  [{:keys [html bytes uuids]}]
  (js/Promise.
   (fn [resolve reject]
     (let [h (host/recording-host)
           base-session (session/new-session (quickjs-runner/quickjs-session-opts {:host h}))]
       (-> (session/ensure-script-engine! base-session)
           (.then
            (fn [ready-session]
              (try
                (let [seeded-session (cond-> ready-session
                                       (or bytes uuids)
                                       (seed-crypto (or bytes []) (or uuids [])))
                      after (session/load-html! seeded-session
                                                {:url "kotoba://crypto-random-round-trip"
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

(deftest quickjs-real-get-random-values-returns-the-real-seeded-bytes-test
  (async done
    (-> (run-page-and-read-title!
         {:bytes [11 22 33 44 55]
          :html (str "<script>"
                     "var arr = new Uint8Array(5);"
                     "crypto.getRandomValues(arr);"
                     "document.title = Array.from(arr).join(',');"
                     "</script>")})
        (.then (fn [title]
                 (println "quickjs real crypto.getRandomValues() ->" (pr-str title))
                 (is (= "11,22,33,44,55" title)
                     (str "expected getRandomValues to fill the array with the REAL host-seeded "
                          "bytes [11 22 33 44 55] (previously always all zeros regardless of what "
                          "was seeded), got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-get-random-values-across-two-calls-consumes-the-queue-in-order-test
  (async done
    (-> (run-page-and-read-title!
         {:bytes [1 2 3 4 5 6]
          :html (str "<script>"
                     "var first = new Uint8Array(2);"
                     "crypto.getRandomValues(first);"
                     "var second = new Uint8Array(4);"
                     "crypto.getRandomValues(second);"
                     "document.title = Array.from(first).join(',') + '|' + Array.from(second).join(',');"
                     "</script>")})
        (.then (fn [title]
                 (println "quickjs real crypto.getRandomValues() across two calls ->" (pr-str title))
                 (is (= "1,2|3,4,5,6" title)
                     (str "expected a SECOND getRandomValues call in the same script tag to "
                          "consume the NEXT prefix of the seeded queue, not repeat the first two "
                          "bytes or reset to zeros, got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-get-random-values-pads-with-zero-once-the-seeded-queue-is-exhausted-test
  (async done
    (-> (run-page-and-read-title!
         {:bytes [9 8]
          :html (str "<script>"
                     "var arr = new Uint8Array(4);"
                     "crypto.getRandomValues(arr);"
                     "document.title = Array.from(arr).join(',');"
                     "</script>")})
        (.then (fn [title]
                 (println "quickjs real crypto.getRandomValues() exhausting the seeded queue ->" (pr-str title))
                 (is (= "9,8,0,0" title)
                     (str "expected getRandomValues to hand out the 2 real seeded bytes then pad "
                          "the remaining 2 slots with zero once the queue is exhausted (mirroring "
                          "take-random-bytes' own established fallback), got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-get-random-values-with-no-seeded-queue-returns-all-zeros-test
  (async done
    (-> (run-page-and-read-title!
         {:html (str "<script>"
                     "var arr = new Uint8Array(3);"
                     "crypto.getRandomValues(arr);"
                     "document.title = Array.from(arr).join(',');"
                     "</script>")})
        (.then (fn [title]
                 (println "quickjs real crypto.getRandomValues() with no seeded queue ->" (pr-str title))
                 (is (= "0,0,0" title)
                     (str "expected getRandomValues to fall back to all zeros when no real queue "
                          "was ever seeded, mirroring take-random-bytes' own default, got "
                          (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-random-uuid-returns-the-real-seeded-uuid-test
  (async done
    (-> (run-page-and-read-title!
         {:uuids ["aaaaaaaa-1111-4111-8111-111111111111" "bbbbbbbb-2222-4222-8222-222222222222"]
          :html (str "<script>"
                     "document.title = crypto.randomUUID() + '|' + crypto.randomUUID();"
                     "</script>")})
        (.then (fn [title]
                 (println "quickjs real crypto.randomUUID() across two calls ->" (pr-str title))
                 (is (= (str "aaaaaaaa-1111-4111-8111-111111111111|"
                             "bbbbbbbb-2222-4222-8222-222222222222")
                        title)
                     (str "expected randomUUID() to return the REAL host-seeded UUIDs in order "
                          "(previously always the same fixed placeholder), got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-random-uuid-with-no-seeded-queue-returns-the-placeholder-test
  (async done
    (-> (run-page-and-read-title!
         {:html "<script>document.title = crypto.randomUUID();</script>"})
        (.then (fn [title]
                 (println "quickjs real crypto.randomUUID() with no seeded queue ->" (pr-str title))
                 (is (= "00000000-0000-4000-8000-000000000000" title)
                     (str "expected randomUUID() to fall back to the placeholder UUID when no real "
                          "queue was ever seeded, mirroring take-random-uuid's own zero-uuid "
                          "default, got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))
