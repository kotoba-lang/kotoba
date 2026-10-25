(ns yoro-ui.state.convo-search
  "Cross-conversation search for the messenger. Namespaced :convo-search/*
  (own db path [:convo-search ...]) rather than the existing generic
  yoro-ui.state.search's :search/* (actor/post search, [:search ...]) —
  distinct feature, distinct state, would silently collide if it reused
  those keywords.

  Convo METADATA (title/participant name) is always searchable from
  :convos/list — no encryption involved there.

  MESSAGE CONTENT search is deliberately scoped to conversations already
  opened this session: e2ee message text only ever exists as plaintext in
  [:convo :decrypted] (a global rkey→text cache yoro-ui.pages.convo-detail
  builds up as messages are actually delivered/viewed) and [:convo
  :messages-by-convo] (an accumulating per-convo message-list cache, same
  file). There is no server-side text index to query — E2E means the PDS
  never sees plaintext — and yoro-ui.interop.signal/decrypt-message is a
  documented ONE-SHOT ratchet step (never call it twice for the same
  message), so eagerly bulk-decrypting every conversation just to make
  search 'complete' wouldn't just be slow, it would silently expand how
  much plaintext ends up cached on this device beyond what the user
  actually chose to open. This is the same trade Signal's own search
  makes (local-database-only, never a network replay-decrypt)."
  (:require [kotoba.lang.text :as str]
            [re-frame.core :as rf]
            [yoro-ui.interop.signal :as signal]
            [yoro-ui.interop.signal-group :as signal-group]))

(rf/reg-sub :convo-search/query (fn [db _] (get-in db [:convo-search :query] "")))

(rf/reg-event-db
 :convo-search/set-query!
 (fn [db [_ q]] (assoc-in db [:convo-search :query] q)))

(defn- includes-ci? [haystack needle]
  (str/includes? (str/lower (or haystack "")) needle))

(defn- convo-display-name [c my-did]
  (let [peer (first (remove #(= (:did %) my-did) (:members c)))
        title (:title c)]
    (or (and (seq title) title)
        (:displayName peer) (:handle peer) "")))

(defn- e2e-scheme? [encryption] (or (= encryption signal/scheme) (= encryption signal-group/scheme)))

(defn- searchable-text
  "Mirrors yoro-ui.pages.convo-detail's private searchable-text — same
  reasoning (never search raw e2ee ciphertext), duplicated rather than
  cross-required to avoid a state→page dependency inversion."
  [{:keys [text rkey encryption]} decrypted]
  (cond
    (contains? decrypted rkey) (get decrypted rkey)
    (e2e-scheme? encryption) nil
    :else text))

(rf/reg-sub
 :convo-search/matching-convos
 (fn [db _]
   (let [q (str/lower (str/trim (get-in db [:convo-search :query] "")))
         my-did (get-in db [:auth :session :did])
         convos (get-in db [:convos :list] [])]
     (if (empty? q)
       []
       (filterv #(includes-ci? (convo-display-name % my-did) q) convos)))))

(rf/reg-sub
 :convo-search/matching-messages
 (fn [db _]
   (let [q (str/lower (str/trim (get-in db [:convo-search :query] "")))
         decrypted (get-in db [:convo :decrypted] {})
         by-convo (get-in db [:convo :messages-by-convo] {})
         convos-by-id (into {} (map (juxt :id identity)) (get-in db [:convos :list] []))
         my-did (get-in db [:auth :session :did])]
     (if (empty? q)
       []
       (->> (for [[convo-id messages] by-convo
                  msg messages
                  :let [text (searchable-text msg decrypted)]
                  :when (and text (includes-ci? text q))]
              {:convo-id convo-id :rkey (:rkey msg) :snippet text
               :convo-title (convo-display-name (get convos-by-id convo-id) my-did)})
            (sort-by :rkey)
            reverse
            vec)))))
