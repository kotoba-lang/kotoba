(ns mail.mailbox
  "Portable mailbox/thread/label state. Transport and persistence are injected."
  (:refer-clojure :exclude [deliver])
  (:require [kotoba.lang.text :as str]))

(def system-labels #{:inbox :sent :drafts :spam :trash :starred :important})

(defn mailbox [id address]
  {:mailbox/id id
   :mailbox/address (str/lower address)
   :mailbox/messages {}
   :mailbox/threads {}
   :mailbox/labels system-labels
   :mailbox/used-bytes 0})

(defn- body-bytes [message]
  (reduce + 0 (map #(count (str (:mail.part/body %))) (:mail/parts message))))

(defn message-entry
  "`attrs` may carry `:sealed` — an opaque map describing content this mailbox
  holds but cannot read (an encryption envelope and whatever the holder needs
  to open it). This model does not interpret it; it exists so that a sealed
  message can BE a message here.

  Without it the only way to store one was to fabricate an empty `message`,
  which is not a smaller truth than the real one but a different and false one:
  a reader cannot tell an empty message from one whose content is elsewhere.

  A sealed entry should pass `:size-bytes`, since `body-bytes` of a message
  with no parts is 0 and a mailbox that reports 0 bytes used is wrong rather
  than merely imprecise."
  [id thread-id message attrs]
  (cond-> {:mailbox.message/id id
           :mailbox.message/thread-id thread-id
           :mailbox.message/message message
           :mailbox.message/attachments (vec (:attachments attrs))
           :mailbox.message/labels (set (or (:labels attrs) #{:inbox}))
           :mailbox.message/read? (boolean (:read? attrs))
           :mailbox.message/received-at (:received-at attrs)
           :mailbox.message/size-bytes (or (:size-bytes attrs) (body-bytes message))}
    (:sealed attrs) (assoc :mailbox.message/sealed (:sealed attrs))))

(defn sealed?
  "Is this entry's content sealed — i.e. present in the mailbox but unreadable
  by whoever is holding the mailbox?"
  [entry]
  (some? (:mailbox.message/sealed entry)))

(defn deliver
  "Idempotently add a message and attach it to a thread."
  [box entry]
  (let [id (:mailbox.message/id entry)
        thread-id (:mailbox.message/thread-id entry)]
    (if (get-in box [:mailbox/messages id])
      box
      (-> box
          (assoc-in [:mailbox/messages id] entry)
          (update-in [:mailbox/threads thread-id]
                     (fn [thread]
                       (-> (or thread {:mailbox.thread/id thread-id
                                       :mailbox.thread/message-ids []})
                           (update :mailbox.thread/message-ids conj id))))
          (update :mailbox/used-bytes + (:mailbox.message/size-bytes entry))))))

(defn set-read [box message-id read?]
  (assoc-in box [:mailbox/messages message-id :mailbox.message/read?] (boolean read?)))

(defn add-label [box message-id label]
  (-> box
      (update :mailbox/labels conj label)
      (update-in [:mailbox/messages message-id :mailbox.message/labels] conj label)))

(defn remove-label [box message-id label]
  (update-in box [:mailbox/messages message-id :mailbox.message/labels] disj label))

(defn trash [box message-id]
  (-> box
      (remove-label message-id :inbox)
      (add-label message-id :trash)))

(defn thread [box thread-id]
  (let [ids (get-in box [:mailbox/threads thread-id :mailbox.thread/message-ids])]
    (mapv #(get-in box [:mailbox/messages %]) ids)))

(defn messages-with-label [box label]
  (->> (:mailbox/messages box) vals
       (filter #(contains? (:mailbox.message/labels %) label)) vec))

(defn unread-count [box]
  (count (filter #(and (contains? (:mailbox.message/labels %) :inbox)
                       (not (:mailbox.message/read? %)))
                 (vals (:mailbox/messages box)))))

(defn search
  "Case-insensitive search over envelope, subject and body with optional
  filters.

  **Sealed entries can only ever match on what is not sealed.** Whatever is
  inside the envelope is invisible here, so a query that would have matched the
  subject or the body of a sealed message returns nothing — a false negative,
  by construction, and not a bug to be fixed at this layer. Callers that must
  search sealed content have to do it where the content can be opened, which is
  the client. This is stated rather than left to be discovered because a search
  that silently under-reports is worse than one that refuses."
  [box query {:keys [label unread?]}]
  (let [needle (str/lower (or query ""))
        matches? (fn [entry]
                   (let [m (:mailbox.message/message entry)
                         haystack (str/lower
                                   (str (:mail/from m) " " (:mail/to m) " " (:mail/cc m) " "
                                        (:mail/subject m) " "
                                        (str/join " " (map :mail.part/body (:mail/parts m)))))]
                     (and (or (str/blank? needle) (str/includes? haystack needle))
                          (or (nil? label) (contains? (:mailbox.message/labels entry) label))
                          (or (nil? unread?) (= unread? (not (:mailbox.message/read? entry)))))))]
    (->> (:mailbox/messages box) vals (filter matches?)
         (sort-by :mailbox.message/received-at #(compare %2 %1)) vec)))
