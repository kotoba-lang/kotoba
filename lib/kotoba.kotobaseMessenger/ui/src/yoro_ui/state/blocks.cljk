(ns yoro-ui.state.blocks
  "re-frame layer for app.aozora.actor.{block,unblock,listBlocks} — mirrors
  yoro-ui.state.convos' set-preference! optimistic-update/revert shape
  (:atproto/procedure fx), and app.aozora.convo.listConvos' :atproto/query
  shape for the read side (both routes live on the same AppView router)."
  (:require [re-frame.core :as rf]))

(rf/reg-sub :blocks/list (fn [db _] (get-in db [:blocks :list] [])))
(rf/reg-sub :blocks/is-loading? (fn [db _] (get-in db [:blocks :is-loading?] false)))
(rf/reg-sub :blocks/blocked-dids
  :<- [:blocks/list]
  (fn [blocks _] (set (map :blockedDid blocks))))

(rf/reg-event-fx
  :blocks/refresh
  (fn [{:keys [db]} _]
    (when-let [did (get-in db [:auth :session :did])]
      {:db (assoc-in db [:blocks :is-loading?] true)
       :atproto/query {:nsid "app.aozora.actor.listBlocks"
                       :params {:did did :limit 200}
                       :on-success [:blocks/refresh-success]
                       :on-failure [:blocks/refresh-failure]}})))

(rf/reg-event-db
  :blocks/refresh-success
  (fn [db [_ resp]]
    (-> db
        (assoc-in [:blocks :list] (vec (:blocks resp)))
        (assoc-in [:blocks :is-loading?] false)
        (assoc-in [:blocks :error] nil))))

(rf/reg-event-db
  :blocks/refresh-failure
  (fn [db [_ err]]
    (-> db
        (assoc-in [:blocks :is-loading?] false)
        (assoc-in [:blocks :error] (str err)))))

(rf/reg-event-fx
  :blocks/block!
  (fn [{:keys [db]} [_ blocked-did]]
    (when (seq blocked-did)
      {;; optimistic — the target disappears from any DM-eligible picker /
       ;; appears in the settings list immediately; a failure reverts it.
       :db (update-in db [:blocks :list]
                      (fnil conj [])
                      {:blockedDid blocked-did :createdAt nil})
       :atproto/procedure
       {:nsid "app.aozora.actor.block"
        :body {:blockedDid blocked-did}
        :on-failure [:blocks/block-failed blocked-did]}})))

(rf/reg-event-db
  :blocks/block-failed
  (fn [db [_ blocked-did]]
    (update-in db [:blocks :list]
               (fn [blocks] (vec (remove #(= (:blockedDid %) blocked-did) blocks))))))

(rf/reg-event-fx
  :blocks/unblock!
  (fn [{:keys [db]} [_ blocked-did]]
    (let [prev (get-in db [:blocks :list] [])]
      {:db (update-in db [:blocks :list]
                      (fn [blocks] (vec (remove #(= (:blockedDid %) blocked-did) blocks))))
       :atproto/procedure
       {:nsid "app.aozora.actor.unblock"
        :body {:blockedDid blocked-did}
        :on-failure [:blocks/unblock-failed prev]}})))

(rf/reg-event-db
  :blocks/unblock-failed
  (fn [db [_ prev]]
    (assoc-in db [:blocks :list] prev)))
