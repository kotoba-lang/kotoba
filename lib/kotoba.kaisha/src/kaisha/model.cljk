(ns kaisha.model
  "EDN-native communication space (Slack/Teams 相当): one space per company
  (会社), channels, threaded messages, mentions, reactions, read markers.
  Pure data + pure functions; hosts render/persist/transport it elsewhere.")

(defn space
  ([id] (space id {}))
  ([id attrs]
   (merge {:kaisha/id id
           :kaisha/type :space
           :kaisha/name id
           :kaisha/members {}
           :kaisha/channels {}
           :kaisha/read {}}
          attrs)))

(defn member
  ([id] (member id {}))
  ([id attrs]
   (merge {:kaisha/id id
          :kaisha/handle id
           :kaisha/display-name id
           :kaisha/did nil}
          attrs)))

(defn channel
  ([id] (channel id {}))
  ([id attrs]
   (merge {:kaisha/id id
           :kaisha/kind :channel
           :kaisha/name id
           :kaisha/topic nil
           :kaisha/visibility :public
           :kaisha/members #{}
           :kaisha/messages {}
           :kaisha/archived? false}
          attrs)))

(defn message
  ([id] (message id {}))
  ([id attrs]
   (merge {:kaisha/id id
           :kaisha/author nil
           :kaisha/body ""
           :kaisha/at nil
           :kaisha/thread nil
           :kaisha/reactions {}
           :kaisha/edited-at nil}
          attrs)))

;; ---------------------------------------------------------------------------
;; Direct messages
;;
;; A DM is a channel with `:kaisha/kind :dm`, `:private` visibility and exactly
;; two members. It is not a separate collection: threads, reactions, read
;; markers, mentions and validation all apply unchanged, and a host that can
;; render a private channel can render a DM.
;;
;; THE ID IS DERIVED, NOT ALLOCATED. That is the whole design. If each side
;; allocated a fresh id when it opened a conversation, two people messaging each
;; other at the same time would create two DM channels for the same pair, with
;; the history split between them and nothing anywhere detecting it — each
;; client would show a conversation that looks complete and is missing half the
;; messages. Deriving the id from the (sorted) pair makes that state
;; unrepresentable: both sides compute the same id without coordinating, and
;; `open-dm` is idempotent.
;; ---------------------------------------------------------------------------

(defn dm-id
  "The canonical channel id for the conversation between `a` and `b`.

  Length-prefixed rather than separator-joined. A plain `\"dm:a|b\"` collides as
  soon as a member id contains the separator — `[\"x|y\" \"z\"]` and
  `[\"x\" \"y|z\"]` both render `dm:x|y|z`, silently merging two different
  people's conversations into one channel. kaisha does not constrain the
  character set of a member id, so the encoding has to be unambiguous for any
  content."
  [a b]
  (let [[x y] (sort [(str a) (str b)])]
    (str "dm:" (count x) ":" x ":" y)))

(defn dm
  "Construct a DM channel between `a` and `b`.

  Always private, always exactly these two members, and its id is `dm-id`.
  `attrs` may carry `:kaisha/topic` and the like, but not membership or
  visibility — those are what make it a DM."
  ([a b] (dm a b {}))
  ([a b attrs]
   (merge (channel (dm-id a b)
                   {:kaisha/kind :dm
                    :kaisha/name (dm-id a b)
                    :kaisha/visibility :private
                    ;; `(into #{} [a b])`, not `#{a b}`: a set literal with two
                    ;; equal elements is a reader-level duplicate-key error, so
                    ;; a note-to-self DM would throw at construction rather than
                    ;; collapsing to one member.
                    :kaisha/members (into #{} [a b])})
          (dissoc attrs :kaisha/members :kaisha/visibility :kaisha/kind :kaisha/id))))

(defn dm? [ch] (= :dm (:kaisha/kind ch)))

(defn self-dm?
  "True when both sides of a DM are the same member — a note-to-self.

  Allowed (a private scratch channel is a real use), but named so callers can
  tell it apart from a two-person conversation instead of treating a
  one-member DM as malformed."
  [ch]
  (and (dm? ch) (= 1 (count (:kaisha/members ch)))))

(defn add-member [sp m]
  (assoc-in sp [:kaisha/members (:kaisha/id m)] m))

(defn member-by-id [sp id]
  (get-in sp [:kaisha/members id]))

(defn add-channel [sp ch]
  (assoc-in sp [:kaisha/channels (:kaisha/id ch)] ch))

(defn channel-by-id [sp id]
  (get-in sp [:kaisha/channels id]))

(defn open-dm
  "Ensure a DM between `a` and `b` exists, and return the space.

  Idempotent: opening an existing conversation returns it untouched rather
  than replacing it with an empty one. Both sides calling this concurrently
  converge on the same channel because `dm-id` is derived."
  ([sp a b] (open-dm sp a b {}))
  ([sp a b attrs]
   (let [id (dm-id a b)]
     (if (channel-by-id sp id)
       sp
       (add-channel sp (dm a b attrs))))))

(defn dm-with
  "The DM channel between `me` and `other`, or nil."
  [sp me other]
  (channel-by-id sp (dm-id me other)))

(defn dms-of
  "Every DM `member-id` participates in, oldest id first.

  Separate from the channel list because a DM is addressed by *who* it is
  with, not by a name — a sidebar that mixes them shows the derived id as a
  channel name."
  [sp member-id]
  (->> (vals (:kaisha/channels sp))
       (filter dm?)
       (filter #(contains? (:kaisha/members %) member-id))
       (sort-by :kaisha/id)
       vec))

(defn dm-counterpart
  "The other member of a DM, from `member-id`'s point of view. For a
  note-to-self DM that is `member-id` itself."
  [ch member-id]
  (or (first (disj (:kaisha/members ch) member-id)) member-id))

(defn join
  "Add `member-id` to a channel.

  Refused for a DM: its membership is fixed at creation and its id is derived
  from exactly that pair, so adding a third person would produce a channel
  whose id no longer describes who is in it — and the two original members
  would keep resolving to it via `dm-id` without knowing someone else is
  reading. Use `open-dm` for a different pair, or a private channel for a
  group."
  [sp channel-id member-id]
  (if (dm? (channel-by-id sp channel-id))
    sp
    (update-in sp [:kaisha/channels channel-id :kaisha/members] (fnil conj #{}) member-id)))

(defn leave
  "Remove `member-id` from a channel. Refused for a DM, for the same reason
  `join` is: a one-sided DM is not a state either participant can be shown
  coherently."
  [sp channel-id member-id]
  (if (dm? (channel-by-id sp channel-id))
    sp
    (update-in sp [:kaisha/channels channel-id :kaisha/members] disj member-id)))

(defn post [sp channel-id msg]
  (assoc-in sp [:kaisha/channels channel-id :kaisha/messages (:kaisha/id msg)] msg))

(defn reply [sp channel-id parent-id msg]
  (post sp channel-id (assoc msg :kaisha/thread parent-id)))

(defn message-by-id [sp channel-id msg-id]
  (get-in sp [:kaisha/channels channel-id :kaisha/messages msg-id]))

(defn react [sp channel-id msg-id emoji member-id]
  (update-in sp [:kaisha/channels channel-id :kaisha/messages msg-id :kaisha/reactions emoji]
             (fnil conj #{}) member-id))

(defn unreact
  "Withdraw `member-id`'s `emoji` reaction. Drops the emoji key entirely
  once the last reactor leaves, so a message never carries
  `{\"+1\" #{}}` -- an empty reactor set still renders as a visible
  zero-count badge in every host that iterates the reactions map."
  [sp channel-id msg-id emoji member-id]
  (let [path [:kaisha/channels channel-id :kaisha/messages msg-id :kaisha/reactions]
        remaining (disj (get-in sp (conj path emoji) #{}) member-id)]
    (if (seq remaining)
      (assoc-in sp (conj path emoji) remaining)
      (update-in sp path dissoc emoji))))

(defn edit
  "Replace a message body and stamp `:kaisha/edited-at`. The `at` argument
  is the host's clock -- this model never reads a clock itself, the same
  reason `message` takes `:kaisha/at` from its caller."
  [sp channel-id msg-id body at]
  (if (message-by-id sp channel-id msg-id)
    (update-in sp [:kaisha/channels channel-id :kaisha/messages msg-id]
               assoc :kaisha/body body :kaisha/edited-at at)
    sp))

(defn set-topic [sp channel-id topic]
  (if (channel-by-id sp channel-id)
    (assoc-in sp [:kaisha/channels channel-id :kaisha/topic] topic)
    sp))

(defn archive
  "Close a channel to new activity. Archiving is reversible and never
  deletes messages -- `messages-in-order`/`thread` keep working, so an
  archived channel stays readable exactly as Slack/Teams leave it."
  [sp channel-id]
  (if (channel-by-id sp channel-id)
    (assoc-in sp [:kaisha/channels channel-id :kaisha/archived?] true)
    sp))

(defn unarchive [sp channel-id]
  (if (channel-by-id sp channel-id)
    (assoc-in sp [:kaisha/channels channel-id :kaisha/archived?] false)
    sp))

(defn messages-in-order
  "Top-level messages of a channel (thread replies excluded), oldest first."
  [sp channel-id]
  (->> (vals (get-in sp [:kaisha/channels channel-id :kaisha/messages]))
       (remove :kaisha/thread)
       (sort-by (juxt :kaisha/at :kaisha/id))
       vec))

(defn thread
  "Parent message followed by its replies, oldest first."
  [sp channel-id parent-id]
  (let [parent (message-by-id sp channel-id parent-id)
        replies (->> (vals (get-in sp [:kaisha/channels channel-id :kaisha/messages]))
                     (filter #(= parent-id (:kaisha/thread %)))
                     (sort-by (juxt :kaisha/at :kaisha/id)))]
    (when parent (vec (cons parent replies)))))

(defn mentions
  "Handles mentioned as @handle in a message body."
  [body]
  (->> (re-seq #"@([A-Za-z0-9_-]+)" (or body ""))
       (map second)
       set))

(defn mentioned?
  "Does this message mention the member (by handle)?"
  [sp msg member-id]
  (let [handle (:kaisha/handle (member-by-id sp member-id))]
    (boolean (and handle (contains? (mentions (:kaisha/body msg)) handle)))))

(defn visible-channels
  "Channels the member can see: public ones plus private ones they belong to."
  [sp member-id]
  (->> (vals (:kaisha/channels sp))
       (filter #(or (= :public (:kaisha/visibility %))
                    (contains? (:kaisha/members %) member-id)))
       (sort-by :kaisha/id)
       vec))

(defn active-channels
  "`visible-channels` minus the archived ones -- the default sidebar list.
  Archived channels stay visible and readable through `visible-channels`;
  this is the narrower view a host shows by default, not an access rule.

  DMs are excluded — they belong in their own list (`dms-of`), addressed by
  who they are with rather than by a name. `visible-channels` still returns
  them, so nothing that needs the complete set loses anything."
  [sp member-id]
  (vec (remove #(or (:kaisha/archived? %) (dm? %))
               (visible-channels sp member-id))))

(defn mark-read [sp member-id channel-id msg-id]
  (assoc-in sp [:kaisha/read member-id channel-id] msg-id))

(defn unread
  "Top-level messages after the member's read marker, oldest first. If the
  marker doesn't match any top-level message (e.g. it points at a thread
  reply -- mark-read never validates that msg-id is top-level -- or the
  marked message was since deleted/moved), fails open and treats
  everything as unread rather than silently reporting nothing: with
  drop-while finding no match, it would otherwise consume the entire
  sequence and `rest` on the resulting empty seq stays empty, hiding
  genuinely unread messages. Under-reporting unread is a worse failure
  mode than over-reporting."
  [sp member-id channel-id]
  (let [marker (get-in sp [:kaisha/read member-id channel-id])
        msgs (messages-in-order sp channel-id)]
    (if (or (nil? marker) (not-any? #(= marker (:kaisha/id %)) msgs))
      msgs
      (->> msgs
           (drop-while #(not= marker (:kaisha/id %)))
           rest
           vec))))

(defn seed-space []
  (-> (space "acme" {:kaisha/name "Acme"})
      (add-member (member "jun" {:kaisha/display-name "Jun"}))
      (add-channel (channel "general" {:kaisha/topic "company-wide announcements"}))
      (join "general" "jun")
      (post "general" (message "m-1" {:kaisha/author "jun"
                                      :kaisha/body "Welcome to kaisha."
                                      :kaisha/at "2026-07-07T00:00:00Z"}))))
