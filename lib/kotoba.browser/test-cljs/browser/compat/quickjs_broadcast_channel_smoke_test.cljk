(ns browser.compat.quickjs-broadcast-channel-smoke-test
  "Real page-script round-trip proof that BroadcastChannel.postMessage()
  actually delivers to OTHER same-name channel instances' onmessage --
  previously it was a write-only sink to a host-side audit log
  (:broadcast/messages) that nothing ever read back into any channel
  instance at all: onmessage was never even initialized, and no registry
  existed for a delivery step to walk, unlike WebSocket/Worker which both
  already had exactly this machinery. Confirmed via actual QuickJS WASM
  end-to-end, mirroring Worker's own never-same-tick delivery discipline
  (a message posted in one <script> tag is delivered into the receiving
  channel's onmessage at the START of the NEXT <script> tag's eval, never
  within the posting script's own run)."
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
  [html]
  (js/Promise.
   (fn [resolve reject]
     (let [h (host/recording-host)
           base-session (session/new-session (quickjs-runner/quickjs-session-opts {:host h}))]
       (-> (session/ensure-script-engine! base-session)
           (.then
            (fn [ready-session]
              (try
                (let [after (session/load-html! ready-session
                                                {:url "kotoba://broadcast-channel-round-trip"
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

(deftest quickjs-real-broadcast-channel-delivers-to-a-same-name-peer-across-script-tags-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><script>"
              "var a = new BroadcastChannel('updates');"
              "var b = new BroadcastChannel('updates');"
              "var received = null;"
              "b.onmessage = function(e) { received = e.data; };"
              "a.postMessage('hello from a');"
              "document.title = 'immediately-after-post:' + String(received);"
              "</script>"
              "<script>"
              "document.title = 'after-next-tag:' + String(received);"
              "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real BroadcastChannel cross-script-tag delivery ->" (pr-str title))
                 (is (= "after-next-tag:hello from a" title)
                     (str "expected b.onmessage to fire with a's real posted message, but only "
                          "once the NEXT script tag's snapshot installs (never within a's own "
                          "posting script), got document.title = " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-broadcast-channel-does-not-deliver-within-the-same-script-tag-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><script>"
              "var a = new BroadcastChannel('same-tick');"
              "var b = new BroadcastChannel('same-tick');"
              "var received = 'not-yet';"
              "b.onmessage = function(e) { received = e.data; };"
              "a.postMessage('too-soon');"
              "document.title = received;"
              "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real BroadcastChannel same-tick delivery attempt ->" (pr-str title))
                 (is (= "not-yet" title)
                     (str "expected delivery to still be deferred to the NEXT script tag's "
                          "snapshot install, never within the posting script's own run "
                          "(mirroring Worker's established discipline), got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-broadcast-channel-does-not-deliver-to-itself-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><script>"
              "var a = new BroadcastChannel('self-test');"
              "var selfReceived = false;"
              "a.onmessage = function(e) { selfReceived = true; };"
              "a.postMessage('echo');"
              "</script>"
              "<script>"
              "document.title = 'self-received:' + String(selfReceived);"
              "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real BroadcastChannel self-delivery check ->" (pr-str title))
                 (is (= "self-received:false" title)
                     (str "expected a channel to NEVER receive its own posted message, per real "
                          "spec, got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-broadcast-channel-does-not-deliver-to-a-different-name-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><script>"
              "var a = new BroadcastChannel('room-a');"
              "var b = new BroadcastChannel('room-b');"
              "var received = 'nothing';"
              "b.onmessage = function(e) { received = e.data; };"
              "a.postMessage('wrong room');"
              "</script>"
              "<script>"
              "document.title = received;"
              "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real BroadcastChannel different-name isolation ->" (pr-str title))
                 (is (= "nothing" title)
                     (str "expected channels with DIFFERENT names to never receive each other's "
                          "messages, got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-broadcast-channel-close-stops-further-delivery-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><script>"
              "var a = new BroadcastChannel('closing');"
              "var b = new BroadcastChannel('closing');"
              "var received = 'none';"
              "b.onmessage = function(e) { received = e.data; };"
              "b.close();"
              "a.postMessage('too-late');"
              "</script>"
              "<script>"
              "document.title = received;"
              "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real BroadcastChannel close() stops delivery ->" (pr-str title))
                 (is (= "none" title)
                     (str "expected a closed channel to never receive a message posted after "
                          "its own close(), got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))
