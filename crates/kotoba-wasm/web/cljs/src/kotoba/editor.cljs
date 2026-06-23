(ns kotoba.editor
  "Minimal sovereign office editor (docs/gftd-office), UI written in **Hiccup** data
   (kotoba.hiccup, no React). Wires the DOM to the office layer: passkey unlock →
   pull latest (or local) → edit → save (encrypt-doc + store-doc! local-first, then
   enqueue + flush to the server). Re-syncs the offline queue when connectivity
   returns. Same-origin (remote = \"\")."
  (:require [kotoba.office :as office]
            [kotoba.passkey :as passkey]
            [kotoba.syncq :as syncq]
            [kotoba.hiccup :as h]))

(defn- el [id] (js/document.getElementById id))
(defn- getv [id] (let [e (el id)] (if e (.-value e) "")))
(defn- setv! [id v] (when-let [e (el id)] (set! (.-value e) (or v ""))))
(defn- sett! [id v] (when-let [e (el id)] (set! (.-textContent e) v)))

(defn- read-model []
  {:id "doc1" :kind :doc/document :title (getv "title") :owner-org "self"
   :created-at (js/Date.now)
   :blocks [{:id "b0" :kind :block/paragraph :text (getv "body") :order "a0"}]})

(defn- render! [model]
  (setv! "title" (:title model))
  (setv! "body" (get-in model [:blocks 0 :text])))

(defn- save! [^js node remote]
  ;; local-first + sovereign: encrypt, store locally, build the SIGNED request now
  ;; (passkey is unlocked here), enqueue it to IndexedDB, then let the Service Worker
  ;; deliver it (immediately if online, on Background Sync if offline/closed).
  (let [enc (office/encrypt-doc node (read-model))]
    (-> (office/store-doc! node enc)
        (.then (fn [_] (office/prepare-sync-request node enc {:remote remote})))
        (.then (fn [req] (syncq/enqueue! req)))
        (.then (fn [_]
                 (syncq/register-bg-sync!)
                 (syncq/nudge-sw!)
                 (-> (syncq/pending) (.then (fn [p] (sett! "sync" (str "queued · pending " p))))))))))

(defn- load! [^js node remote]
  (-> (office/pull-doc node {:remote remote})
      (.then (fn [m] (render! (if (:title m) m {})) "server"))
      (.catch (fn [_]
                (render! (try (office/load-doc node "doc1") (catch :default _ {})))
                "local"))))

(defn- view
  "The editor UI as Hiccup data."
  [^js node remote]
  [:div
   [:h1 "gftd office — sovereign editor "
    [:span.meta "passkey-unlocked · client-encrypted · same-origin sync"]]
   [:div.meta "account: " [:span#account "—"]]
   [:input#title {:placeholder "タイトル"}]
   [:textarea#body {:placeholder "本文（端末で暗号化され、サーバには暗号文のみ同期）"}]
   [:div.bar
    [:button#save {:onclick (fn [_] (save! node remote))} "保存 + 同期"]
    [:span#status "booting…"]
    [:span#sync "—"]]])

(defn- register-sw! []
  ;; Register the Background-Sync SW + reflect its drain reports in the UI.
  (when-let [swc (.-serviceWorker js/navigator)]
    (.addEventListener swc "message"
      (fn [^js e]
        (let [d (.-data e)]
          (when (= "office-synced" (.-type d))
            (sett! "sync" (str "synced " (.-synced d) " · pending " (.-remaining d)))))))
    (.register swc "/office-sw.js")))

(defn init!
  "Boot the editor on `node`: render the Hiccup UI into #app, register the
   Background-Sync SW, passkey unlock/enroll → load → drain the queue. The SW owns
   draining (works tab-closed); the page enqueues + nudges. Returns Promise<true>."
  [^js node]
  (let [remote "" rp (.-hostname js/location)]
    (h/mount! "app" (view node remote))
    (register-sw!)
    (sett! "status" "unlocking…")
    (-> (if (passkey/enrolled?)
          (passkey/unlock! node rp)
          (passkey/enroll! node rp "owner"))
        (.then (fn [did]
                 (sett! "account" did)
                 (.addEventListener js/window "online" (fn [_] (syncq/nudge-sw!)))
                 (load! node remote)))
        (.then (fn [_]
                 (when (.-onLine js/navigator) (syncq/nudge-sw!))
                 (sett! "status" "ready")
                 true)))))

(def ^:export initEditor init!)
