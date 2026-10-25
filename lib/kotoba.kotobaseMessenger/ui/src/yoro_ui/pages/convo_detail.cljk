(ns yoro-ui.pages.convo-detail
  "DM/group conversation detail view — app.aozora.convo.getConvo / send.

  Signal v2 (yoro-ui.interop.signal, 1:1) / Signal group v1 (yoro-ui.interop.
  signal-group, groups): both `encrypt-*`/`decrypt-*` advance a one-shot
  ratchet, so decrypt must run exactly once per incoming message. [:convo
  :decrypted rkey] is that cache, shared by both schemes — messages-loaded
  only triggers decrypt for rkeys not already in it (or in :decrypt-failed),
  and a just-sent message's plaintext is cached directly from the local
  compose step (its own ciphertext can't be re-derived via the *receive*
  chain, the same reason a page reload can't recover older self-sent
  plaintext either — see the module docstrings on those two namespaces).

  Attachments/reactions are backend-complete but were previously never wired
  to any UI (app.aozora.convo.addAttachment/addReaction, already returned
  inline on getConvo's :attachments/:reactions). Attachments are NOT E2E
  encrypted — the addAttachment lexicon has no `encryption` field, only
  `uri`/`cid`/`contentType` — so an attached file is visible to the PDS/
  AppView even in an otherwise-encrypted conversation; this pass wires the
  UI to that existing (unencrypted) contract rather than expanding it."
  (:require [reagent.core :as r]
            [re-frame.core :as rf]
            [kotoba.lang.text :as str]
            [yoro-ui.router :as router]
            [yoro-ui.interop.atproto :as at]
            [yoro-ui.interop.signal :as signal]
            [yoro-ui.interop.signal-group :as signal-group]))

(def ^:private MAX-ATTACHMENT-BYTES (* 25 1024 1024))

;; ---------------------------------------------------------------------------
;; State

(rf/reg-sub :convo/current             (fn [db _] (get-in db [:convo :current])))
(rf/reg-sub :convo/messages            (fn [db _] (get-in db [:convo :messages] [])))
(rf/reg-sub :convo/loading?            (fn [db _] (get-in db [:convo :loading?] false)))
(rf/reg-sub :convo/sending?            (fn [db _] (get-in db [:convo :sending?] false)))
(rf/reg-sub :convo/meta                (fn [db _] (get-in db [:convo :meta])))
(rf/reg-sub :convo/not-found?          (fn [db _] (get-in db [:convo :not-found?] false)))
(rf/reg-sub :convo/decrypted           (fn [db _] (get-in db [:convo :decrypted] {})))
(rf/reg-sub :convo/decrypt-failed      (fn [db _] (get-in db [:convo :decrypt-failed] {})))
(rf/reg-sub :convo/reaction-picker-for (fn [db _] (get-in db [:convo :reaction-picker-for])))
(rf/reg-sub :convo/member-panel-open?  (fn [db _] (get-in db [:convo :member-panel-open?] false)))
(rf/reg-sub :convo/editing-rkey        (fn [db _] (get-in db [:convo :editing-rkey])))
(rf/reg-sub :convo/edit-draft          (fn [db _] (get-in db [:convo :edit-draft] "")))
(rf/reg-sub :convo/edit-error          (fn [db _] (get-in db [:convo :edit-error])))
(rf/reg-sub :convo/delete-confirm-for  (fn [db _] (get-in db [:convo :delete-confirm-for])))
(rf/reg-sub :convo/failed-sends
  (fn [db _]
    (let [current-id (get-in db [:convo :current-id])]
      (filterv #(= current-id (:convo-id %)) (get-in db [:convo :failed-sends] [])))))
(rf/reg-sub :convo/search-open?        (fn [db _] (get-in db [:convo :search-open?] false)))
(rf/reg-sub :convo/search-query        (fn [db _] (get-in db [:convo :search-query] "")))
(rf/reg-sub :convo/typing              (fn [db _] (get-in db [:convo :typing] [])))

(defn- group? [convo] (= "group" (:kind convo)))

(defn- peer-did
  "The other member's did for a 1:1 convo — Signal v2 sessions are per
  (my-did, peer-did)."
  [convo my-did]
  (some->> (:members convo) (remove #(= (:did %) my-did)) first :did))

(defn- member-dids [convo] (mapv :did (:members convo)))

(defn- parse-envelope [text]
  (try (js->clj (js/JSON.parse text) :keywordize-keys true)
       (catch :default _ nil)))

(def ^:private page-size 50)

(defn- pending-decrypts
  "Only incoming messages are decryptable here — my own past sends were
  encrypted on the *send* chain, which this session's *receive* chain (1:1
  or group) can't re-derive. Shared by the initial load and load-more (each
  batch of newly-arrived messages needs the same triage)."
  [messages my-did cached failed]
  (let [undecrypted (->> messages
                         (remove #(or (contains? cached (:rkey %)) (contains? failed (:rkey %))))
                         (remove #(= (:senderDid %) my-did)))]
    {:pending-dm (->> undecrypted
                      (filter #(= signal/scheme (:encryption %)))
                      (keep (fn [m]
                              (when-let [env (parse-envelope (:text m))]
                                {:rkey (:rkey m) :peer-did (:senderDid m) :envelope env}))))
     :pending-group (->> undecrypted
                         (filter #(= signal-group/scheme (:encryption %)))
                         (keep (fn [m]
                                 (when-let [env (parse-envelope (:text m))]
                                   {:rkey (:rkey m) :sender-did (:senderDid m) :envelope env}))))}))

(defn- decrypt-fx [{:keys [pending-dm pending-group]} my-did convo-id]
  (cond-> {}
    (seq pending-dm)
    (assoc :convo/decrypt! {:my-did my-did :items pending-dm})
    (seq pending-group)
    (assoc :convo/decrypt-group! {:my-did my-did :convo-id convo-id :items pending-group})))

(rf/reg-event-fx
 :convo/load
  (fn [{:keys [db]} [_ convo-id]]
   {:db (-> db
            (assoc-in [:convo :loading?] true)
            (assoc-in [:convo :not-found?] false)
            (assoc-in [:convo :messages] [])
            (assoc-in [:convo :cursor] nil)
            (assoc-in [:convo :has-more?] false)
            (assoc-in [:convo :current-id] convo-id))
    :atproto/query {:nsid "app.aozora.convo.getConvo"
                    :params {:convoId convo-id :limit page-size}
                    :on-success [:convo/messages-loaded]
                    :on-failure [:convo/load-failed]}}))

(rf/reg-event-fx
 :convo/messages-loaded
 (fn [{:keys [db]} [_ {:keys [convo messages notFound cursor hasMore]}]]
   (let [loaded-messages (vec (or messages []))
         convo-id (or (:convoId convo) (:convoId (first loaded-messages)))
         last-rkey (some-> loaded-messages last :rkey)
         my-did (get-in db [:auth :session :did])
         cached (get-in db [:convo :decrypted] {})
         failed (get-in db [:convo :decrypt-failed] {})
         pending (pending-decrypts loaded-messages my-did cached failed)
         db' (cond-> (-> db
                         (assoc-in [:convo :loading?] false)
                         (assoc-in [:convo :not-found?] (boolean notFound))
                         (assoc-in [:convo :meta] convo)
                         (assoc-in [:convo :messages] loaded-messages)
                         (assoc-in [:convo :cursor] cursor)
                         (assoc-in [:convo :has-more?] (boolean hasMore)))
               ;; [:convo :messages] above is the CURRENT-convo-only view
               ;; (wiped and refetched on every :convo/load); this is a
               ;; separate, ACCUMULATING per-convo cache — never wiped —
               ;; that yoro-ui.state.search reads for cross-conversation
               ;; message search, scoped honestly to convos opened this
               ;; session (see that ns's docstring for why it can't be more
               ;; than that without re-decrypting, which the one-shot
               ;; ratchet forbids).
               convo-id (assoc-in [:convo :messages-by-convo convo-id] loaded-messages))]
     (cond-> {:db db'}
       (and convo-id last-rkey)
       (assoc-in [:fx] [[:dispatch [:convo/mark-read {:convo-id convo-id
                                                       :last-rkey last-rkey}]]])
       true
       (merge (decrypt-fx pending my-did convo-id))))))

;; ---------------------------------------------------------------------------
;; Load more (older) — getConvo's before/cursor/hasMore paging (no full-scan
;; fetch of the whole history anymore); prepends onto the existing list
;; rather than replacing it the way :convo/load does.

(rf/reg-sub :convo/has-more?    (fn [db _] (get-in db [:convo :has-more?] false)))
(rf/reg-sub :convo/loading-more? (fn [db _] (get-in db [:convo :loading-more?] false)))

(rf/reg-event-fx
 :convo/load-more
 (fn [{:keys [db]} _]
   (let [convo-id (get-in db [:convo :current-id])
         cursor (get-in db [:convo :cursor])
         has-more? (get-in db [:convo :has-more?])
         loading-more? (get-in db [:convo :loading-more?])]
     (when (and convo-id cursor has-more? (not loading-more?))
       {:db (assoc-in db [:convo :loading-more?] true)
        :atproto/query {:nsid "app.aozora.convo.getConvo"
                        :params {:convoId convo-id :limit page-size :before cursor}
                        :on-success [:convo/older-messages-loaded]
                        :on-failure [:convo/older-messages-load-failed]}}))))

(rf/reg-event-fx
 :convo/older-messages-loaded
 (fn [{:keys [db]} [_ {:keys [messages cursor hasMore]}]]
   (let [older (vec (or messages []))
         convo-id (get-in db [:convo :current-id])
         my-did (get-in db [:auth :session :did])
         cached (get-in db [:convo :decrypted] {})
         failed (get-in db [:convo :decrypt-failed] {})
         pending (pending-decrypts older my-did cached failed)
         combined (into older (get-in db [:convo :messages] []))
         db' (cond-> (-> db
                         (assoc-in [:convo :loading-more?] false)
                         (assoc-in [:convo :messages] combined)
                         (assoc-in [:convo :cursor] cursor)
                         (assoc-in [:convo :has-more?] (boolean hasMore)))
               convo-id (assoc-in [:convo :messages-by-convo convo-id] combined))]
     (merge {:db db'} (decrypt-fx pending my-did convo-id)))))

(rf/reg-event-db
 :convo/older-messages-load-failed
 (fn [db [_ err]]
   (js/console.error "convo load-more failed" err)
   (assoc-in db [:convo :loading-more?] false)))

(rf/reg-event-db
 :convo/load-failed
 (fn [db [_ err]]
   (let [not-found? (str/includes? (str err) "404")]
     (when-not not-found?
       (js/console.error "convo load failed" err))
     (-> db
         (assoc-in [:convo :loading?] false)
         (assoc-in [:convo :not-found?] not-found?)))))

;; ---------------------------------------------------------------------------
;; Send — encrypt locally first (1:1 Signal v2, or group sender-keys), then
;; persist the ciphertext envelope. An optional attachment rides along in
;; the event payload (never touched by the encrypt step) and uploads AFTER
;; the message record exists, since app.aozora.convo.addAttachment
;; references an existing messageRkey.

(rf/reg-fx
 :convo/encrypt-and-send!
 (fn [{:keys [my-did peer-did convo-id text file]}]
   (-> (signal/encrypt-message my-did peer-did text)
       (.then (fn [envelope]
                (rf/dispatch [:convo/send {:convo-id convo-id
                                           :text (js/JSON.stringify (clj->js envelope))
                                           :content-type signal/content-type
                                           :encryption signal/scheme
                                           :plaintext text
                                           :file file}])))
       (.catch (fn [e]
                 (rf/dispatch [:convo/send-failed convo-id text file (str "encryption: " e)]))))))

(rf/reg-fx
 :convo/encrypt-and-send-group!
 (fn [{:keys [my-did convo-id members text file]}]
   (-> (signal-group/encrypt-group-message my-did convo-id members text)
       (.then (fn [envelope]
                (rf/dispatch [:convo/send {:convo-id convo-id
                                           :text (js/JSON.stringify (clj->js envelope))
                                           :content-type signal-group/content-type
                                           :encryption signal-group/scheme
                                           :plaintext text
                                           :file file}])))
       (.catch (fn [e]
                 (rf/dispatch [:convo/send-failed convo-id text file (str "group encryption: " e)]))))))

(rf/reg-event-fx
 :convo/send-start
 (fn [{:keys [db]} [_ {:keys [convo-id text file]}]]
   (let [my-did (get-in db [:auth :session :did])
         convo (get-in db [:convo :meta])]
     (cond
       (nil? my-did)
       {:db (assoc-in db [:convo :sending?] false)
        :fx [[:dispatch [:convo/send-failed convo-id text file "no signed-in session"]]]}

       (group? convo)
       {:db (assoc-in db [:convo :sending?] true)
        :convo/encrypt-and-send-group! {:my-did my-did :convo-id convo-id
                                        :members (member-dids convo) :text text :file file}}

       :else
       (let [to-did (peer-did convo my-did)]
         (if-not to-did
           {:db (assoc-in db [:convo :sending?] false)
            :fx [[:dispatch [:convo/send-failed convo-id text file "no peer to encrypt for"]]]}
           {:db (assoc-in db [:convo :sending?] true)
            :convo/encrypt-and-send! {:my-did my-did :peer-did to-did :convo-id convo-id :text text :file file}}))))))

(rf/reg-event-fx
 :convo/send
 (fn [{:keys [db]} [_ {:keys [convo-id text content-type encryption plaintext file]}]]
   {:db (assoc-in db [:convo :sending?] true)
    :atproto/procedure {:nsid "app.aozora.convo.send"
                        :body (cond-> {:convoId convo-id :text text}
                                (seq encryption) (assoc :encryption encryption)
                                (seq content-type) (assoc :contentType content-type))
                        :on-success [:convo/message-sent plaintext file]
                        :on-failure [:convo/send-failed convo-id plaintext file]}}))

(rf/reg-event-fx
 :convo/message-sent
 (fn [{:keys [db]} [_ plaintext file msg]]
   (let [db' (cond-> (-> db
                         (assoc-in [:convo :sending?] false)
                         (assoc-in [:convo :not-found?] false)
                         (assoc-in [:convo :current-id] (:convoId msg)))
               (and plaintext (:rkey msg))
               (assoc-in [:convo :decrypted (:rkey msg)] plaintext))]
     (if file
       {:db db'
        :atproto/upload-blob {:file file
                              :mime (or (.-type ^js file) "application/octet-stream")
                              :on-success [:convo/attachment-blob-uploaded (:convoId msg) (:rkey msg)]
                              :on-failure [:convo/attach-failed (:convoId msg)]}}
       {:db db' :fx [[:dispatch [:convo/load (:convoId msg)]]]}))))

(rf/reg-event-fx
 :convo/mark-read
 (fn [{:keys [db]} [_ {:keys [convo-id last-rkey]}]]
   (when (and (get-in db [:auth :session :did])
              convo-id
              last-rkey)
     {:atproto/procedure {:nsid "app.aozora.convo.markRead"
                          :body {:convoId convo-id
                                 :lastSeenRkey last-rkey}
                          :on-success nil
                          :on-failure nil}})))

;; Failed sends are queued (not just logged) so the user never has to
;; retype a message that failed to send — offline, a flaky network, or a
;; transient server error all land here indistinguishably, since retrying
;; with the same {convo-id text file} is the correct response to all
;; three. Auto-retried on the browser's `online` event (wired in
;; convo-detail-page's mount lifecycle), or manually via the retry button
;; on each failed-send row.

(rf/reg-event-db
 :convo/send-failed
 (fn [db [_ convo-id text file err]]
   (js/console.error "convo send failed" err)
   (cond-> (assoc-in db [:convo :sending?] false)
     (and convo-id (seq text))
     (update-in [:convo :failed-sends]
                (fnil conj [])
                {:id (str convo-id "-" (js/Date.now)) :convo-id convo-id :text text :file file :error (str err)}))))

(rf/reg-event-fx
 :convo/retry-send!
 (fn [{:keys [db]} [_ id]]
   (let [target (first (filter #(= id (:id %)) (get-in db [:convo :failed-sends] [])))]
     (when target
       {:db (update-in db [:convo :failed-sends] (fn [xs] (vec (remove #(= id (:id %)) xs))))
        :fx [[:dispatch [:convo/send-start {:convo-id (:convo-id target) :text (:text target) :file (:file target)}]]]}))))

(rf/reg-event-db
 :convo/dismiss-failed-send!
 (fn [db [_ id]]
   (update-in db [:convo :failed-sends] (fn [xs] (vec (remove #(= id (:id %)) xs))))))

(rf/reg-event-fx
 :convo/retry-all-failed-sends!
 (fn [{:keys [db]} _]
   (let [failed (get-in db [:convo :failed-sends] [])]
     (when (seq failed)
       {:db (assoc-in db [:convo :failed-sends] [])
        :fx (mapv (fn [{:keys [convo-id text file]}]
                    [:dispatch [:convo/send-start {:convo-id convo-id :text text :file file}]])
                  failed)}))))

;; ---------------------------------------------------------------------------
;; Shared "mutate then reload" tail — attachments, reactions, and member
;; add/remove all end the same way.

(rf/reg-event-fx
 :convo/reload-convo
 (fn [_ [_ convo-id]]
   {:fx [[:dispatch [:convo/load convo-id]]]}))

(rf/reg-event-db
 :convo/mutation-failed
 (fn [db [_ err]]
   (js/console.error "convo mutation failed" err)
   db))

;; ---------------------------------------------------------------------------
;; Attachments — upload the blob, then attach it to the just-sent message

(rf/reg-event-fx
 :convo/attachment-blob-uploaded
 (fn [_ [_ convo-id message-rkey resp]]
   (let [blob (:blob resp)
         cid (get-in blob [:ref :$link])]
     (if-not cid
       {:fx [[:dispatch [:convo/attach-failed convo-id "blob upload returned no cid"]]]}
       {:atproto/procedure {:nsid "app.aozora.convo.addAttachment"
                            :body {:convoId convo-id :messageRkey message-rkey
                                   :uri (at/blob-url cid) :cid cid
                                   :contentType (:mimeType blob)}
                            :on-success [:convo/reload-convo convo-id]
                            :on-failure [:convo/attach-failed convo-id]}}))))

(rf/reg-event-db
 :convo/attach-failed
 (fn [db [_ convo-id err]]
   (js/console.error "convo attachment failed" convo-id err)
   db))

;; ---------------------------------------------------------------------------
;; Reactions — plaintext metadata (the lexicon has no encryption field), so
;; no session/ratchet involvement, just a straight addReaction + reload.

(def quick-reactions ["👍" "❤️" "😂" "😮" "😢" "🙏"])

(rf/reg-event-db
 :convo/toggle-reaction-picker
 (fn [db [_ rkey]]
   (update-in db [:convo :reaction-picker-for] #(if (= % rkey) nil rkey))))

(rf/reg-event-fx
 :convo/react
 (fn [{:keys [db]} [_ {:keys [convo-id message-rkey emoji]}]]
   (when (and convo-id message-rkey (seq emoji))
     {:db (assoc-in db [:convo :reaction-picker-for] nil)
      :atproto/procedure {:nsid "app.aozora.convo.addReaction"
                          :body {:convoId convo-id :messageRkey message-rkey :emoji emoji}
                          :on-success [:convo/reload-convo convo-id]
                          :on-failure [:convo/mutation-failed]}})))

;; ---------------------------------------------------------------------------
;; Edit — same encrypt-then-persist shape as send (:convo/send-start
;; → :convo/encrypt-and-send! → :convo/send), reusing the SAME encrypt-
;; message calls: an edit is just a resend of new ciphertext under the
;; original rkey (aozora.pds.convo/edit-message preserves every field the
;; edit doesn't touch on the write side). Only one message editable at a
;; time (:editing-rkey is a single cursor, like :reaction-picker-for).

(rf/reg-event-db
 :convo/start-edit
 (fn [db [_ rkey current-text]]
   (-> db
       (assoc-in [:convo :editing-rkey] rkey)
       (assoc-in [:convo :edit-draft] (or current-text ""))
       (assoc-in [:convo :edit-error] nil))))

(rf/reg-event-db
 :convo/set-edit-draft
 (fn [db [_ text]] (assoc-in db [:convo :edit-draft] text)))

(rf/reg-event-db
 :convo/cancel-edit
 (fn [db _]
   (-> db (assoc-in [:convo :editing-rkey] nil) (assoc-in [:convo :edit-error] nil))))

(rf/reg-fx
 :convo/encrypt-and-edit!
 (fn [{:keys [my-did peer-did convo-id rkey text]}]
   (-> (signal/encrypt-message my-did peer-did text)
       (.then (fn [envelope]
                (rf/dispatch [:convo/persist-edit {:convo-id convo-id :rkey rkey
                                                    :text (js/JSON.stringify (clj->js envelope))
                                                    :plaintext text}])))
       (.catch (fn [e] (rf/dispatch [:convo/edit-failed (str "encryption: " e)]))))))

(rf/reg-fx
 :convo/encrypt-and-edit-group!
 (fn [{:keys [my-did convo-id members rkey text]}]
   (-> (signal-group/encrypt-group-message my-did convo-id members text)
       (.then (fn [envelope]
                (rf/dispatch [:convo/persist-edit {:convo-id convo-id :rkey rkey
                                                    :text (js/JSON.stringify (clj->js envelope))
                                                    :plaintext text}])))
       (.catch (fn [e] (rf/dispatch [:convo/edit-failed (str "group encryption: " e)]))))))

(rf/reg-event-fx
 :convo/save-edit
 (fn [{:keys [db]} _]
   (let [my-did (get-in db [:auth :session :did])
         convo (get-in db [:convo :meta])
         convo-id (:convoId convo)
         rkey (get-in db [:convo :editing-rkey])
         text (str/trim (get-in db [:convo :edit-draft] ""))]
     (cond
       (or (nil? rkey) (empty? text))
       {:db (assoc-in db [:convo :edit-error] "空のメッセージは送れません")}

       (nil? my-did)
       {:db (assoc-in db [:convo :edit-error] "no signed-in session")}

       (group? convo)
       {:convo/encrypt-and-edit-group! {:my-did my-did :convo-id convo-id :members (member-dids convo)
                                        :rkey rkey :text text}}

       :else
       (let [to-did (peer-did convo my-did)]
         (if-not to-did
           {:db (assoc-in db [:convo :edit-error] "no peer to encrypt for")}
           {:convo/encrypt-and-edit! {:my-did my-did :peer-did to-did :convo-id convo-id
                                      :rkey rkey :text text}}))))))

(rf/reg-event-fx
 :convo/persist-edit
 (fn [_ [_ {:keys [convo-id rkey text plaintext]}]]
   {:atproto/procedure {:nsid "app.aozora.convo.editMessage"
                        :body {:convoId convo-id :rkey rkey :text text}
                        :on-success [:convo/edit-saved rkey plaintext convo-id]
                        :on-failure [:convo/edit-failed]}}))

(rf/reg-event-fx
 :convo/edit-saved
 (fn [{:keys [db]} [_ rkey plaintext convo-id]]
   {:db (-> db
            (assoc-in [:convo :decrypted rkey] plaintext)
            (assoc-in [:convo :editing-rkey] nil)
            (assoc-in [:convo :edit-draft] "")
            (assoc-in [:convo :edit-error] nil))
    :fx [[:dispatch [:convo/reload-convo convo-id]]]}))

(rf/reg-event-db
 :convo/edit-failed
 (fn [db [_ err]]
   (js/console.error "convo edit failed" err)
   (assoc-in db [:convo :edit-error] (str err))))

;; ---------------------------------------------------------------------------
;; Delete (unsend) — a lightweight two-tap confirm (:delete-confirm-for is a
;; single cursor, same idiom as :reaction-picker-for/:editing-rkey), then a
;; plain mutate-then-reload like reactions/member add-remove above.

(rf/reg-event-db
 :convo/toggle-delete-confirm
 (fn [db [_ rkey]]
   (update-in db [:convo :delete-confirm-for] #(if (= % rkey) nil rkey))))

(rf/reg-event-fx
 :convo/delete-message!
 (fn [{:keys [db]} [_ {:keys [convo-id rkey]}]]
   {:db (assoc-in db [:convo :delete-confirm-for] nil)
    :atproto/procedure {:nsid "app.aozora.convo.deleteMessage"
                        :body {:convoId convo-id :rkey rkey}
                        :on-success [:convo/reload-convo convo-id]
                        :on-failure [:convo/mutation-failed]}}))

;; ---------------------------------------------------------------------------
;; In-conversation search — purely client-side over the already-loaded (and
;; already-decrypted) messages for the OPEN convo, since getConvo fetches
;; the whole history in one shot already (no pagination yet) — no new XRPC
;; needed.

(rf/reg-event-db
 :convo/toggle-search
 (fn [db _]
   (if (get-in db [:convo :search-open?])
     (-> db (assoc-in [:convo :search-open?] false) (assoc-in [:convo :search-query] ""))
     (assoc-in db [:convo :search-open?] true))))

(rf/reg-event-db
 :convo/set-search-query
 (fn [db [_ q]] (assoc-in db [:convo :search-query] q)))

;; ---------------------------------------------------------------------------
;; Typing indicators — there's no live-update/websocket layer in this app
;; yet (new messages aren't pushed either), so both directions are plain
;; interval polling: outgoing heartbeats are throttled client-side to
;; typing-ping-interval-ms while composing, and incoming state is polled
;; every typing-poll-interval-ms while the convo is open (started/stopped
;; in convo-detail-page's component-did-mount/component-will-unmount).
;; Plaintext-only metadata (like reactions) — no encryption involved.

(def ^:private typing-ping-interval-ms
  "Minimum gap between outgoing setTyping heartbeats while composing — the
  AppView's staleness window (aozora.appview.convo/typing-stale-ms) is 8s,
  so re-pinging every 3s keeps a continuously-typing peer's indicator up
  with comfortable margin without hammering the XRPC endpoint on every
  keystroke."
  3000)

(def typing-poll-interval-ms
  "How often the open convo polls listTyping for peers' typing state."
  3000)

(rf/reg-event-fx
 :convo/poll-typing
 (fn [{:keys [db]} _]
   (let [convo-id (get-in db [:convo :current-id])
         my-did (get-in db [:auth :session :did])]
     (when (and convo-id my-did)
       {:atproto/query {:nsid "app.aozora.convo.listTyping"
                        :params {:convoId convo-id :did my-did}
                        :on-success [:convo/typing-received]
                        :on-failure nil}}))))

(rf/reg-event-db
 :convo/typing-received
 (fn [db [_ {:keys [typing]}]]
   (assoc-in db [:convo :typing] (or typing []))))

(rf/reg-event-fx
 :convo/ping-typing!
 (fn [{:keys [db]} _]
   (let [convo-id (get-in db [:convo :current-id])
         last-ping (get-in db [:convo :last-typing-ping-at] 0)
         now (js/Date.now)]
     (when (and convo-id (> (- now last-ping) typing-ping-interval-ms))
       {:db (assoc-in db [:convo :last-typing-ping-at] now)
        :atproto/procedure {:nsid "app.aozora.convo.setTyping"
                            :body {:convoId convo-id :isTyping true}
                            :on-success nil :on-failure nil}}))))

(rf/reg-event-fx
 :convo/stop-typing!
 (fn [{:keys [db]} _]
   (let [convo-id (get-in db [:convo :current-id])]
     (when convo-id
       {:db (assoc-in db [:convo :last-typing-ping-at] 0)
        :atproto/procedure {:nsid "app.aozora.convo.setTyping"
                            :body {:convoId convo-id :isTyping false}
                            :on-success nil :on-failure nil}}))))

;; ---------------------------------------------------------------------------
;; Group membership — any current member can add/remove (matches the
;; backend's existing permissiveness, no new ACL layer). The next
;; encrypt-group-message call detects the roster change and rotates/
;; redistributes as needed (yoro-ui.interop.signal-group/ensure-sender-key!).

(rf/reg-event-db
 :convo/toggle-member-panel
 (fn [db _] (update-in db [:convo :member-panel-open?] not)))

(rf/reg-event-fx
 :convo/remove-member!
 (fn [_ [_ {:keys [convo-id did]}]]
   {:atproto/procedure {:nsid "app.aozora.convo.removeMember"
                        :body {:convoId convo-id :did did}
                        :on-success [:convo/reload-convo convo-id]
                        :on-failure [:convo/mutation-failed]}}))

;; ---------------------------------------------------------------------------
;; Leave group — self-removal via the SAME removeMember procedure
;; (aozora.pds.convo/remove-member already exempts self-removal from the
;; creator check — see PR #59), just with different post-success handling:
;; reloading the convo you just left makes no sense, so this navigates back
;; to the convo list instead.

(rf/reg-sub :convo/leave-confirm? (fn [db _] (get-in db [:convo :leave-confirm?] false)))

(rf/reg-event-db
 :convo/toggle-leave-confirm
 (fn [db _] (update-in db [:convo :leave-confirm?] not)))

(rf/reg-event-fx
 :convo/leave-group!
 (fn [_ [_ {:keys [convo-id did]}]]
   {:atproto/procedure {:nsid "app.aozora.convo.removeMember"
                        :body {:convoId convo-id :did did}
                        :on-success [:convo/left-group]
                        :on-failure [:convo/mutation-failed]}}))

(rf/reg-event-fx
 :convo/left-group
 (fn [_ _]
   {:fx [[:dispatch [:router/navigate-to "/messages"]]]}))

(rf/reg-event-fx
 :convo/add-member!
 (fn [_ [_ {:keys [convo-id did]}]]
   {:atproto/procedure {:nsid "app.aozora.convo.addMember"
                        :body {:convoId convo-id :did did}
                        :on-success [:convo/reload-convo convo-id]
                        :on-failure [:convo/mutation-failed]}}))

;; ---------------------------------------------------------------------------
;; Rename (title only) — creator-only, enforced server-side
;; (aozora.pds.convo/update-convo's require-creator); this UI doesn't hide
;; the control from non-creators, the write just rejects.

(rf/reg-sub :convo/renaming?    (fn [db _] (get-in db [:convo :renaming?] false)))
(rf/reg-sub :convo/rename-draft (fn [db _] (get-in db [:convo :rename-draft] "")))
(rf/reg-sub :convo/rename-error (fn [db _] (get-in db [:convo :rename-error])))

(rf/reg-event-db
 :convo/start-rename
 (fn [db [_ current-title]]
   (-> db
       (assoc-in [:convo :renaming?] true)
       (assoc-in [:convo :rename-draft] (or current-title ""))
       (assoc-in [:convo :rename-error] nil))))

(rf/reg-event-db
 :convo/set-rename-draft
 (fn [db [_ text]] (assoc-in db [:convo :rename-draft] text)))

(rf/reg-event-db
 :convo/cancel-rename
 (fn [db _]
   (-> db (assoc-in [:convo :renaming?] false) (assoc-in [:convo :rename-error] nil))))

(rf/reg-event-fx
 :convo/save-rename
 (fn [{:keys [db]} [_ convo-id]]
   (let [title (str/trim (get-in db [:convo :rename-draft] ""))]
     (if (empty? title)
       {:db (assoc-in db [:convo :rename-error] "空の名前にはできません")}
       {:atproto/procedure {:nsid "app.aozora.convo.updateConvo"
                            :body {:convoId convo-id :title title}
                            :on-success [:convo/rename-saved convo-id]
                            :on-failure [:convo/rename-failed]}}))))

(rf/reg-event-fx
 :convo/rename-saved
 (fn [{:keys [db]} [_ convo-id]]
   {:db (-> db (assoc-in [:convo :renaming?] false) (assoc-in [:convo :rename-error] nil))
    :fx [[:dispatch [:convo/reload-convo convo-id]]]}))

(rf/reg-event-db
 :convo/rename-failed
 (fn [db [_ err]]
   (js/console.error "convo rename failed" err)
   (assoc-in db [:convo :rename-error] (str err))))

;; ---------------------------------------------------------------------------
;; Decrypt — one shot per incoming message, cached in app-db

(rf/reg-fx
 :convo/decrypt!
 (fn [{:keys [my-did items]}]
   (doseq [{:keys [rkey peer-did envelope]} items]
     (-> (signal/decrypt-message my-did peer-did envelope)
         (.then (fn [plaintext] (rf/dispatch [:convo/message-plaintext-cached rkey plaintext])))
         (.catch (fn [e]
                   (js/console.error "convo decrypt failed" rkey e)
                   (rf/dispatch [:convo/message-decrypt-failed rkey])))))))

(rf/reg-fx
 :convo/decrypt-group!
 (fn [{:keys [my-did convo-id items]}]
   (doseq [{:keys [rkey sender-did envelope]} items]
     (-> (signal-group/decrypt-group-message my-did convo-id sender-did envelope)
         (.then (fn [plaintext] (rf/dispatch [:convo/message-plaintext-cached rkey plaintext])))
         (.catch (fn [e]
                   (js/console.error "convo group decrypt failed" rkey e)
                   (rf/dispatch [:convo/message-decrypt-failed rkey])))))))

(rf/reg-event-db
 :convo/message-plaintext-cached
 (fn [db [_ rkey plaintext]]
   (assoc-in db [:convo :decrypted rkey] plaintext)))

(rf/reg-event-db
 :convo/message-decrypt-failed
 (fn [db [_ rkey]]
   (assoc-in db [:convo :decrypt-failed rkey] true)))

;; ---------------------------------------------------------------------------
;; Time formatting

(defn- fmt-time [^string iso]
  (when iso
    (let [d (js/Date. iso)]
      (str (.toString (.getHours d)) ":"
           (.padStart (.toString (.getMinutes d)) 2 "0")))))

;; ---------------------------------------------------------------------------
;; Message bubble

(defn- e2e-scheme? [encryption] (or (= encryption signal/scheme) (= encryption signal-group/scheme)))

(defn- message-display-text [{:keys [text rkey encryption]} decrypted failed]
  (cond
    (not (e2e-scheme? encryption)) (or text "")
    (contains? decrypted rkey) (get decrypted rkey)
    (contains? failed rkey) "🔒 復号できませんでした"
    :else "🔒 復号中…"))

(defn- searchable-text
  "The text to run a search query against, or nil when there's nothing
  legitimate to search yet — an e2ee message not (yet) in `decrypted` has
  only ciphertext/envelope JSON in :text, which must never be treated as
  searchable content (matching it would be noise at best, a plaintext-
  shaped leak of ciphertext bytes at worst)."
  [{:keys [text rkey encryption]} decrypted]
  (cond
    (contains? decrypted rkey) (get decrypted rkey)
    (e2e-scheme? encryption) nil
    :else text))

(defn- filter-messages-by-query [messages decrypted query]
  (if (str/blank? query)
    messages
    (let [q (str/lower query)]
      (filter #(when-let [t (searchable-text % decrypted)]
                 (str/includes? (str/lower t) q))
              messages))))

(defn- attachment-chip [{:keys [uri contentType]}]
  (if (str/starts-with? (or contentType "") "image/")
    [:img {:src uri :class "mt-1 rounded-lg max-w-[200px] max-h-[200px] object-cover"}]
    [:a {:href uri :target "_blank" :rel "noopener noreferrer"
         :class "mt-1 inline-flex items-center gap-1 text-[12px] underline"}
     (str "📎 " (or contentType "添付ファイル"))]))

(defn- reaction-summary [reactions]
  (when (seq reactions)
    [:div {:class "flex gap-1 mt-1 flex-wrap"}
     (for [[emoji rs] (group-by :emoji reactions)]
       ^{:key emoji}
       [:span {:class "inline-flex items-center gap-0.5 rounded-full bg-gv2-bg-card border border-gv2-border px-1.5 py-0.5 text-[11px]"}
        emoji (when (> (count rs) 1) (str " " (count rs)))])]))

(defn- reaction-picker [convo-id message-rkey]
  [:div {:class "flex gap-1 mt-1 bg-gv2-bg-card border border-gv2-border rounded-full px-2 py-1 w-fit"}
   (for [emoji quick-reactions]
     ^{:key emoji}
     [:button {:class "text-[16px] hover:scale-125 transition-transform"
               :on-click #(rf/dispatch [:convo/react {:convo-id convo-id :message-rkey message-rkey :emoji emoji}])}
      emoji])])

(defn- edit-box [rkey draft error]
  [:div {:class "flex flex-col gap-1 w-full"}
   [:textarea {:class "w-full px-3 py-2 rounded-2xl text-[14px] leading-relaxed bg-gv2-bg-card text-gv2-text-primary resize-none outline-none border border-[#1CB0F6]/60"
               :rows 2
               :auto-focus true
               :value draft
               :on-change #(rf/dispatch [:convo/set-edit-draft (.. % -target -value)])
               :on-key-down #(cond
                               (and (.-metaKey %) (= (.-key %) "Enter")) (rf/dispatch [:convo/save-edit])
                               (= (.-key %) "Escape") (rf/dispatch [:convo/cancel-edit]))}]
   (when error [:p {:class "text-[11px] text-red-400"} error])
   [:div {:class "flex gap-2 justify-end"}
    [:button {:class "text-[11px] text-gv2-text-muted" :on-click #(rf/dispatch [:convo/cancel-edit])}
     "キャンセル"]
    [:button {:class "text-[11px] font-bold text-[#1CB0F6]" :on-click #(rf/dispatch [:convo/save-edit])}
     "保存"]]])

;; ---------------------------------------------------------------------------
;; Read receipts — the backend (app.aozora.convo.markRead/listReceipts, and
;; getConvo's embedded :receipts) has existed since before this UI; only the
;; UI to actually SHOW anyone's read state was missing. Only the very last
;; message in the whole conversation, when it's one of MY OWN, ever gets a
;; badge (WhatsApp/LINE-style) — annotating every past message once it's
;; read is just noise, since "read" is monotonic (reading message N implies
;; every earlier message was seen too).

(defn- rkey-index [messages rkey]
  (when rkey
    (some (fn [[i m]] (when (= (:rkey m) rkey) i)) (map-indexed vector messages))))

(defn- read-status
  "nil, or {:kind :read} (1:1 — the peer has seen at least up to this
  message), or {:kind :group :count n} (group — n OTHER members have seen
  at least up to this message). Only computed for the conversation's last
  message when it was sent by `my-did`; nil for anything else."
  [raw-messages my-did receipts is-group? msg]
  (when (and (= my-did (:senderDid msg)) (= (:rkey msg) (:rkey (last raw-messages))))
    (let [target-idx (rkey-index raw-messages (:rkey msg))
          seen-by (->> receipts
                       (remove #(= my-did (:did %)))
                       (filter #(when-let [idx (rkey-index raw-messages (:lastSeenRkey %))]
                                  (>= idx target-idx))))]
      (when (seq seen-by)
        (if is-group?
          {:kind :group :count (count seen-by)}
          {:kind :read})))))

(defn- read-badge-text [status]
  (case (:kind status)
    :read "既読"
    :group (str "既読 " (:count status))
    nil))

(defn- message-bubble [{:keys [sender senderDid createdAt editedAt] :as msg} my-did
                        {:keys [decrypted failed convo-id attachments reactions picker-for group?
                                editing-rkey edit-draft edit-error delete-confirm-for
                                raw-messages receipts]}]
  (let [sender-did (or (:did sender) senderDid)
        is-mine? (= sender-did my-did)
        rkey (:rkey msg)
        editing? (= editing-rkey rkey)
        confirming-delete? (= delete-confirm-for rkey)
        status (read-status raw-messages my-did receipts group? msg)]
    [:div {:class (str "flex mb-2 " (if is-mine? "justify-end" "justify-start"))}
     (when-not is-mine?
       (if-let [av (get-in sender [:avatar])]
         [:img {:src av :class "w-8 h-8 rounded-full mr-2 mt-1 flex-shrink-0"}]
         [:div {:class "w-8 h-8 rounded-full bg-[#1CB0F6] flex items-center justify-center text-white text-[11px] font-bold mr-2 mt-1 flex-shrink-0"}
          (first (or (get-in sender [:displayName]) "?"))]))
     [:div {:class "max-w-[70%] group"}
      (when (and group? (not is-mine?))
        [:p {:class "text-[11px] font-bold text-gv2-text-muted mb-0.5"}
         (or (:displayName sender) (:handle sender) sender-did)])
      (if editing?
        [edit-box rkey edit-draft edit-error]
        [:div {:class (str "px-3 py-2 rounded-2xl text-[14px] leading-relaxed "
                           (if is-mine?
                             "bg-[#1CB0F6] text-white rounded-br-sm"
                             "bg-gv2-bg-card text-gv2-text-primary rounded-bl-sm"))}
         (message-display-text msg decrypted failed)
         (when (seq editedAt)
           [:span {:class "text-[10px] opacity-70 ml-1"} "（編集済み）"])])
      (into [:div] (map attachment-chip attachments))
      [:div {:class "flex items-center gap-2 mt-0.5"}
       [:p {:class (str "text-[10px] text-gv2-text-muted "
                        (if is-mine? "text-right" "text-left"))}
        (fmt-time createdAt)]
       (when status
         [:span {:class "text-[10px] text-[#1CB0F6]"} (read-badge-text status)])
       [:button {:class "text-[11px] text-gv2-text-muted opacity-0 group-hover:opacity-100 transition-opacity"
                 :aria-label "リアクションする"
                 :on-click #(rf/dispatch [:convo/toggle-reaction-picker rkey])}
        "🙂+"]
       (when is-mine?
         [:button {:class "text-[11px] text-gv2-text-muted opacity-0 group-hover:opacity-100 transition-opacity"
                   :aria-label "編集する"
                   :on-click #(rf/dispatch [:convo/start-edit rkey (get decrypted rkey (:text msg))])}
          "✏️"])
       (when is-mine?
         (if confirming-delete?
           [:<>
            [:button {:class "text-[11px] text-red-400 font-bold" :aria-label "削除を確定"
                      :on-click #(rf/dispatch [:convo/delete-message! {:convo-id convo-id :rkey rkey}])}
             "削除する"]
            [:button {:class "text-[11px] text-gv2-text-muted" :aria-label "削除をやめる"
                      :on-click #(rf/dispatch [:convo/toggle-delete-confirm rkey])}
             "✕"]]
           [:button {:class "text-[11px] text-gv2-text-muted opacity-0 group-hover:opacity-100 transition-opacity"
                     :aria-label "メッセージを削除"
                     :on-click #(rf/dispatch [:convo/toggle-delete-confirm rkey])}
            "🗑"]))]
      (reaction-summary reactions)
      (when (= picker-for rkey)
        [reaction-picker convo-id rkey])]]))

(defn- typing-display-name [did members]
  (let [member (first (filter #(= (:did %) did) members))]
    (or (:displayName member) (:handle member) did)))

(defn- typing-label
  "\"○○が入力中…\" (1:1 or a single group member) / \"○○、××が入力中…\" (2+
  group members) — `typing` is already other-members-only, deduped, and
  freshness-filtered server-side (aozora.appview.convo/list-typing)."
  [typing members]
  (let [names (->> typing (map #(typing-display-name (:did %) members)) distinct)]
    (when (seq names)
      (str (str/join "、" names) "が入力中…"))))

(defn- convo-title [convo my-did]
  (let [title (:title convo)]
    (or (and (seq title) title)
        (if (group? convo)
          (str "グループ (" (count (:members convo)) ")")
          (let [member (some->> (:members convo)
                                (remove #(= (:did %) my-did))
                                first)]
            (or (:displayName member) (:handle member))))
        "メッセージ")))

(defn- convo-encryption-label
  "Reflects the *latest message's* real scheme + decrypt outcome — not a
  static convo-level claim (that was the original bug: the badge used to
  show \"E2EE\" from a hardcoded field regardless of whether anything was
  actually encrypted)."
  [messages decrypted failed]
  (when-let [last-msg (last messages)]
    (let [rkey (:rkey last-msg)]
      (cond
        (not (e2e-scheme? (:encryption last-msg))) nil
        (contains? decrypted rkey) "E2EE"
        (contains? failed rkey) "E2EE ⚠"
        :else nil))))

;; ---------------------------------------------------------------------------
;; Member panel (group only)

(defn- member-row [{:keys [did] :as member} convo-id my-did leave-confirm?]
  [:div {:class "flex items-center justify-between gap-2 px-3 py-2"}
   [:div {:class "flex items-center gap-2 min-w-0"}
    [:div {:class "w-7 h-7 rounded-full bg-[#1CB0F6] flex items-center justify-center text-white text-[10px] font-bold flex-shrink-0"}
     (first (or (:displayName member) (:handle member) "?"))]
    [:span {:class "text-[13px] text-gv2-text-primary truncate"}
     (or (:displayName member) (:handle member) did)]]
   (if (= did my-did)
     (if leave-confirm?
       [:<>
        [:button {:class "text-[11px] text-red-400 font-bold" :aria-label "退出を確定"
                  :on-click #(rf/dispatch [:convo/leave-group! {:convo-id convo-id :did did}])}
         "退出する"]
        [:button {:class "text-[11px] text-gv2-text-muted" :aria-label "退出をやめる"
                  :on-click #(rf/dispatch [:convo/toggle-leave-confirm])}
         "✕"]]
       [:button {:class "text-[11px] text-gv2-text-muted" :aria-label "グループから退出"
                 :on-click #(rf/dispatch [:convo/toggle-leave-confirm])}
        "退出"])
     [:button {:class "text-[11px] text-red-400" :aria-label "メンバーを削除"
               :on-click #(rf/dispatch [:convo/remove-member! {:convo-id convo-id :did did}])}
      "削除"])])

(defn- add-member-panel [convo-id]
  (r/with-let [query (r/atom "") results (r/atom []) loading? (r/atom false)]
    (let [run-search! (fn [q]
                         (let [q (str/trim (or q ""))]
                           (if (empty? q)
                             (reset! results [])
                             (do (reset! loading? true)
                                 (-> (at/at-appview-or-public "com.etzhayyim.yoro.actor.searchActors"
                                                              "app.bsky.actor.searchActors"
                                                              {:q q :limit 5})
                                     (.then (fn [resp] (reset! loading? false) (reset! results (vec (or (:actors resp) [])))))
                                     (.catch (fn [_] (reset! loading? false))))))))]
      [:div {:class "px-3 py-2 border-t border-gv2-border/60"}
       [:input {:type "search" :placeholder "handle で検索して追加" :value @query
                :class "w-full px-2 py-1.5 rounded-lg bg-gv2-bg-card border border-gv2-border text-[12px]"
                :on-change #(let [v (.. % -target -value)] (reset! query v) (run-search! v))}]
       (when @loading? [:p {:class "text-[11px] text-gv2-text-muted mt-1"} "検索中…"])
       (for [actor @results]
         ^{:key (:did actor)}
         [:button {:class "flex items-center justify-between w-full mt-1 px-2 py-1.5 rounded-lg hover:bg-gv2-bg-card text-left"
                   :on-click #(do (rf/dispatch [:convo/add-member! {:convo-id convo-id :did (:did actor)}])
                                  (reset! query "") (reset! results []))}
          [:span {:class "text-[12px] text-gv2-text-primary truncate"}
           (or (:displayName actor) (:handle actor))]
          [:span {:class "text-[11px] text-[#1CB0F6]"} "追加"]])])))

(defn- rename-panel [convo-id title renaming? rename-draft rename-error]
  (if renaming?
    [:div {:class "flex flex-col gap-1 px-3 py-2 border-b border-gv2-border/60"}
     [:input {:type "text" :class "w-full px-2 py-1.5 rounded-lg bg-gv2-bg-base border border-gv2-border text-[13px]"
              :auto-focus true
              :value rename-draft
              :on-change #(rf/dispatch [:convo/set-rename-draft (.. % -target -value)])
              :on-key-down #(cond
                              (= (.-key %) "Enter") (rf/dispatch [:convo/save-rename convo-id])
                              (= (.-key %) "Escape") (rf/dispatch [:convo/cancel-rename]))}]
     (when rename-error [:p {:class "text-[11px] text-red-400"} rename-error])
     [:div {:class "flex gap-2 justify-end"}
      [:button {:class "text-[11px] text-gv2-text-muted" :on-click #(rf/dispatch [:convo/cancel-rename])}
       "キャンセル"]
      [:button {:class "text-[11px] font-bold text-[#1CB0F6]" :on-click #(rf/dispatch [:convo/save-rename convo-id])}
       "保存"]]]
    [:div {:class "flex items-center justify-between px-3 py-2 border-b border-gv2-border/60"}
     [:span {:class "text-[13px] font-bold text-gv2-text-primary truncate"} title]
     [:button {:class "text-[11px] text-gv2-text-muted" :aria-label "グループ名を変更"
               :on-click #(rf/dispatch [:convo/start-rename title])}
      "✏️"]]))

(defn- member-panel [convo my-did {:keys [renaming? rename-draft rename-error leave-confirm?]}]
  [:div {:class "border-b border-gv2-border bg-gv2-bg-card/40"}
   [rename-panel (:convoId convo) (:title convo) renaming? rename-draft rename-error]
   (for [member (:members convo)]
     ^{:key (:did member)} [member-row member (:convoId convo) my-did leave-confirm?])
   [add-member-panel (:convoId convo)]])

;; ---------------------------------------------------------------------------
;; Page component

(defn convo-detail-page [route-params]
  (let [convo-id      (or (:id route-params) (:convo-id route-params))
        input         (r/atom "")
        attachment    (r/atom nil)   ; JS File — app-db never holds it
        attach-error  (r/atom nil)
        file-input    (atom nil)
        poll-id       (atom nil)
        online-listener #(rf/dispatch [:convo/retry-all-failed-sends!])]
    (r/create-class
     {:component-did-mount
      (fn [_]
        (when convo-id
          (rf/dispatch [:convo/load convo-id])
          (rf/dispatch [:convo/poll-typing])
          (reset! poll-id (js/setInterval #(rf/dispatch [:convo/poll-typing]) typing-poll-interval-ms))
          (.addEventListener js/window "online" online-listener)))

      :component-will-unmount
      (fn [_]
        (when-let [id @poll-id] (js/clearInterval id))
        (.removeEventListener js/window "online" online-listener)
        (when convo-id (rf/dispatch [:convo/stop-typing!])))

      :reagent-render
      (fn [_]
      (let [raw-messages @(rf/subscribe [:convo/messages])
            loading? @(rf/subscribe [:convo/loading?])
            sending? @(rf/subscribe [:convo/sending?])
            my-did   @(rf/subscribe [:auth/did])
            convo    @(rf/subscribe [:convo/meta])
            not-found? @(rf/subscribe [:convo/not-found?])
            decrypted @(rf/subscribe [:convo/decrypted])
            failed    @(rf/subscribe [:convo/decrypt-failed])
            picker-for @(rf/subscribe [:convo/reaction-picker-for])
            member-panel-open? @(rf/subscribe [:convo/member-panel-open?])
            editing-rkey @(rf/subscribe [:convo/editing-rkey])
            edit-draft @(rf/subscribe [:convo/edit-draft])
            edit-error @(rf/subscribe [:convo/edit-error])
            delete-confirm-for @(rf/subscribe [:convo/delete-confirm-for])
            search-open? @(rf/subscribe [:convo/search-open?])
            search-query @(rf/subscribe [:convo/search-query])
            typing @(rf/subscribe [:convo/typing])
            has-more? @(rf/subscribe [:convo/has-more?])
            loading-more? @(rf/subscribe [:convo/loading-more?])
            renaming? @(rf/subscribe [:convo/renaming?])
            rename-draft @(rf/subscribe [:convo/rename-draft])
            rename-error @(rf/subscribe [:convo/rename-error])
            leave-confirm? @(rf/subscribe [:convo/leave-confirm?])
            failed-sends @(rf/subscribe [:convo/failed-sends])
            messages (filter-messages-by-query raw-messages decrypted search-query)
            searching? (seq (str/trim search-query))
            is-group? (group? convo)
            attachments-by-msg (group-by :messageRkey (:attachments convo))
            reactions-by-msg   (group-by :messageRkey (:reactions convo))
            encryption-label (convo-encryption-label raw-messages decrypted failed)
            pick-attachment! (fn [^js e]
                                (let [^js f (aget (.. e -target -files) 0)]
                                  (set! (.-value (.-target e)) "")
                                  (cond
                                    (nil? f) nil
                                    (> (.-size f) MAX-ATTACHMENT-BYTES)
                                    (reset! attach-error "添付ファイルは 25MB までです")
                                    :else (do (reset! attach-error nil)
                                              (reset! attachment f)))))
            send!    (fn []
                       (let [txt (str/trim @input)
                             ^js f @attachment
                             txt' (if (and (empty? txt) f) (str "📎 " (.-name f)) txt)]
                         (when (seq txt')
                           (rf/dispatch [:convo/stop-typing!])
                           (rf/dispatch [:convo/send-start {:convo-id convo-id :text txt' :file f}])
                           (reset! input "")
                           (reset! attachment nil))))]
          [:div {:class "flex flex-col h-full"}

           ;; Header
           [:div {:class "flex items-center gap-3 px-4 py-3 border-b border-gv2-border sticky top-0 bg-gv2-bg-base z-10"}
            [:button {:class    "w-8 h-8 flex items-center justify-center rounded-full hover:bg-gv2-bg-card text-gv2-text-muted"
                      :on-click #(router/navigate! "/messages")}
             [:svg {:width 20 :height 20 :viewBox "0 0 24 24" :fill "none" :stroke "currentColor" :stroke-width 2}
              [:path {:d "M19 12H5M12 5l-7 7 7 7"}]]]
            [:div {:class "min-w-0 flex-1"}
             [:div {:class "flex items-center gap-2 min-w-0"}
              [:h2 {:class "text-[16px] font-bold text-gv2-text-primary truncate"}
               (convo-title convo my-did)]
              (when encryption-label
                [:span {:class "inline-flex items-center rounded-full border border-gv2-border px-2 py-0.5 text-[10px] font-bold tracking-wide text-gv2-text-muted"}
                 encryption-label])]
             [:p {:class "text-[12px] text-gv2-text-muted truncate"}
              (str "convo " convo-id)]]
            (when is-group?
              [:button {:class "w-8 h-8 flex items-center justify-center rounded-full hover:bg-gv2-bg-card text-gv2-text-muted"
                        :aria-label "メンバー"
                        :on-click #(rf/dispatch [:convo/toggle-member-panel])}
               "👥"])
            (when-let [peer (and (not is-group?) (peer-did convo my-did))]
              [:button {:class "w-8 h-8 flex items-center justify-center rounded-full hover:bg-gv2-bg-card text-gv2-text-muted"
                        :aria-label "ブロック"
                        :on-click #(rf/dispatch [:blocks/block! peer])}
               "🚫"])
            [:button {:class "w-8 h-8 flex items-center justify-center rounded-full hover:bg-gv2-bg-card text-gv2-text-muted"
                      :aria-label "会話内を検索"
                      :on-click #(rf/dispatch [:convo/toggle-search])}
             "🔍"]]

           (when search-open?
             [:div {:class "px-4 py-2 border-b border-gv2-border sticky top-[57px] z-10 bg-gv2-bg-base"}
              [:input {:type "search" :placeholder "この会話を検索" :auto-focus true
                       :class "w-full px-3 py-2 rounded-xl bg-gv2-bg-card border border-gv2-border text-[13px] outline-none focus:border-[#1CB0F6]/50"
                       :value search-query
                       :on-change #(rf/dispatch [:convo/set-search-query (.. % -target -value)])}]])

           (when (and is-group? member-panel-open?)
             [member-panel convo my-did
              {:renaming? renaming? :rename-draft rename-draft :rename-error rename-error
               :leave-confirm? leave-confirm?}])

           ;; Message list
           [:div {:class "flex-1 overflow-y-auto px-4 py-4 flex flex-col"}
            (cond
              loading?
              [:div {:class "flex justify-center py-8"}
               [:div {:class "w-6 h-6 border-2 border-[#1CB0F6] border-t-transparent rounded-full animate-spin"}]]

              (empty? raw-messages)
              (if not-found?
                [:div {:class "flex flex-col items-center justify-center flex-1 text-center"}
                 [:div {:class "text-4xl mb-3"} "🫥"]
                 [:p {:class "text-[13px] text-gv2-text-muted"} "会話が見つかりません"]]
                [:div {:class "flex flex-col items-center justify-center flex-1 text-center"}
                 [:div {:class "text-4xl mb-3"} "💬"]
                 [:p {:class "text-[13px] text-gv2-text-muted"} "まだメッセージはありません"]])

              (and searching? (empty? messages))
              [:div {:class "flex flex-col items-center justify-center flex-1 text-center"}
               [:div {:class "text-4xl mb-3"} "🔍"]
               [:p {:class "text-[13px] text-gv2-text-muted"} "見つかりませんでした"]]

              :else
              [:<>
               (when has-more?
                 [:div {:class "flex justify-center py-2"}
                  [:button {:class "text-[12px] text-[#1CB0F6] disabled:opacity-50"
                            :disabled loading-more?
                            :on-click #(rf/dispatch [:convo/load-more])}
                   (if loading-more? "読み込み中…" "▲ 過去のメッセージを読み込む")]])
               (for [msg messages]
                ^{:key (or (:rkey msg) (:createdAt msg) (:sentAt msg))}
                [message-bubble msg my-did
                 {:decrypted decrypted :failed failed :convo-id convo-id
                  :attachments (get attachments-by-msg (:rkey msg))
                  :reactions (get reactions-by-msg (:rkey msg))
                  :picker-for picker-for
                  :group? is-group?
                  :editing-rkey editing-rkey :edit-draft edit-draft :edit-error edit-error
                  :delete-confirm-for delete-confirm-for
                  :raw-messages raw-messages :receipts (:receipts convo)}])])]

           ;; Typing indicator
           (when (seq typing)
             [:p {:class "px-4 py-1 text-[12px] text-gv2-text-muted italic"}
              (typing-label typing (:members convo))])

           ;; Failed sends — queued for retry (manual, or automatic on the
           ;; browser's next `online` event), never silently dropped.
           (when (seq failed-sends)
             [:div {:class "flex flex-col gap-1 px-4 py-2"}
              (for [{:keys [id text]} failed-sends]
                ^{:key id}
                [:div {:class "flex items-center gap-2 rounded-xl border border-red-400/40 bg-red-400/10 px-3 py-2"}
                 [:span {:class "flex-1 min-w-0 text-[13px] text-gv2-text-primary truncate"} text]
                 [:span {:class "text-[11px] text-red-400 flex-shrink-0"} "送信できませんでした"]
                 [:button {:class "text-[11px] font-bold text-[#1CB0F6] flex-shrink-0" :aria-label "再送信"
                           :on-click #(rf/dispatch [:convo/retry-send! id])}
                  "再送信"]
                 [:button {:class "text-[11px] text-gv2-text-muted flex-shrink-0" :aria-label "破棄"
                           :on-click #(rf/dispatch [:convo/dismiss-failed-send! id])}
                  "✕"]])])

           ;; Composer
           [:div {:class "flex flex-col gap-1 px-4 py-3 border-t border-gv2-border bg-gv2-bg-base"}
            (when-let [^js f @attachment]
              [:div {:class "flex items-center justify-between gap-2 rounded-xl border border-gv2-border/60 bg-gv2-bg-card/50 px-3 py-2"}
               [:span {:class "text-[12px] text-gv2-text-muted truncate"} (str "📎 " (.-name f))]
               [:button {:class "text-[11px] text-gv2-text-muted" :aria-label "添付を外す"
                         :on-click #(reset! attachment nil)}
                "✕"]])
            (when-let [ae @attach-error] [:p {:class "text-[12px] text-red-400"} ae])
            [:div {:class "flex items-end gap-2"}
             [:input {:type "file" :class "hidden" :ref #(reset! file-input %) :on-change pick-attachment!}]
             [:button {:class "w-9 h-9 flex items-center justify-center rounded-full hover:bg-gv2-bg-card text-gv2-text-muted flex-shrink-0"
                       :aria-label "ファイルを添付"
                       :on-click #(some-> ^js @file-input .click)}
              "📎"]
             [:div {:class "flex-1 bg-gv2-bg-card rounded-2xl px-3 py-2.5 min-h-[40px] flex items-end"}
              [:textarea {:class       "flex-1 bg-transparent text-[14px] text-gv2-text-primary placeholder:text-gv2-text-muted resize-none outline-none max-h-[120px]"
                          :placeholder "メッセージを入力…"
                          :rows        1
                          :value       @input
                          :on-change   #(let [v (.. % -target -value)]
                                          (reset! input v)
                                          (if (seq (str/trim v))
                                            (rf/dispatch [:convo/ping-typing!])
                                            (rf/dispatch [:convo/stop-typing!])))
                          :on-key-down #(when (and (.-metaKey %) (= (.-key %) "Enter"))
                                          (send!))}]]
             [:button {:class    (str "w-9 h-9 flex items-center justify-center rounded-full flex-shrink-0 transition-colors "
                                      (if (and (or (seq @input) @attachment) (not sending?))
                                        "bg-[#1CB0F6] text-white"
                                        "bg-gv2-bg-card text-gv2-text-muted cursor-not-allowed"))
                       :disabled (or (and (empty? @input) (nil? @attachment)) sending?)
                       :on-click send!}
              (if sending?
                [:div {:class "w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"}]
                [:svg {:width 18 :height 18 :viewBox "0 0 24 24" :fill "none" :stroke "currentColor" :stroke-width 2}
                 [:path {:d "M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"}]])]]]]))})))
