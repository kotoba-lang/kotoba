(ns browser.compat.quickjs-notification-options-close-smoke-test
  "Real page-script round-trip proof that Notification instances actually
  reflect the NotificationOptions dict a script passes in, and have a
  working close() method.

  Previously `options` (body/icon/tag/data/...) was only ever forwarded
  into the outbound `:notification/show` request, never read back onto
  `this` -- `new Notification('hi', {body: 'x'}).body` was silently
  `undefined`, dropping data a script wrote in. There was also no
  `Notification.prototype.close` at all -- a perfectly conformant script
  calling `n.close()` crashed the whole script with a TypeError, not just
  a missing feature. Confirmed via actual QuickJS WASM end-to-end."
  (:require [cljs.test :refer [deftest is async]]
            [browser.compat.quickjs-runner :as quickjs-runner]
            [browser.profile :as profile]
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
     (let [allowed-profile (-> (profile/new-profile {:id "notification-options-allowed"})
                               (profile/grant-permission "kotoba://notification-options-round-trip"
                                                          :notification/show))
           h (host/recording-host)
           base-session (session/new-session
                         (quickjs-runner/quickjs-session-opts {:host h :profile allowed-profile}))]
       (-> (session/ensure-script-engine! base-session)
           (.then
            (fn [ready-session]
              (try
                (let [after (session/load-html! ready-session
                                                {:url "kotoba://notification-options-round-trip"
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

(deftest quickjs-real-notification-reflects-options-onto-the-instance-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><script>"
              "var n = new Notification('hi', {body: 'hello there', icon: 'icon.png', tag: 'x'});"
              "document.title = n.title + '|' + n.body + '|' + n.icon + '|' + n.tag;"
              "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real Notification options reflection ->" (pr-str title))
                 (is (= "hi|hello there|icon.png|x" title)
                     (str "expected the real NotificationOptions dict to be reflected onto the "
                          "instance (previously all silently undefined), got document.title = "
                          (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-notification-defaults-when-no-options-given-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><script>"
              "var n = new Notification('no options at all');"
              "document.title = JSON.stringify([n.body, n.icon, n.dir, n.silent]);"
              "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real Notification with no options object ->" (pr-str title))
                 (is (= "[\"\",\"\",\"auto\",null]" title)
                     (str "expected real spec defaults (empty strings for body/icon, 'auto' for "
                          "dir, null for the tri-state silent) when no options object is passed "
                          "at all, not a crash, got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))

(deftest quickjs-real-notification-close-does-not-crash-the-script-test
  (async done
    (-> (run-page-and-read-title!
         (str "<main><script>"
              "var n = new Notification('closeable');"
              "n.close();"
              "document.title = 'closed-without-crashing';"
              "</script></main>"))
        (.then (fn [title]
                 (println "quickjs real Notification.close() ->" (pr-str title))
                 (is (= "closed-without-crashing" title)
                     (str "expected n.close() to exist and not crash the script (previously "
                          "close() did not exist at all -- a TypeError), got " (pr-str title)))
                 (done)))
        (.catch (fn [err]
                  (is false (str "QuickJS WASM engine initialization / page load failed: "
                                 (or (.-message err) err)))
                  (done))))))
