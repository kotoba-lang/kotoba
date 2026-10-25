(ns importer.schema
  "One canonical shape for both importers.

  Gmail and Microsoft Graph disagree about almost everything at the wire, and
  agree about what a message is. If each importer kept its own shape, the join
  that motivates having a corpus at all -- `what has this customer said to us`,
  across a mailbox on each side -- would be two queries and a merge in every
  caller. That cost is real and it is the reason for one shape here; it is
  not that the join becomes impossible. Root ADR-2809040800 supersedes
  ADR-260726's \"exactly one ref\": reach follows composition, so the failure
  is an uncomposed split, not a split as such. Paying for the composition once
  here beats paying for it in every caller.

  DataScript-style, not Datomic-native vectors, so both the JVM store and the
  nbb query surface load the same map. `kotoba-lang/mail-archive` established
  that shape for a Gmail-only corpus; this is it with a second provider and a
  provenance attribute."
  )

(def schema
  {;; --- people -----------------------------------------------------------
   ;; Identity is the address, lower-cased. The display name is carried but is
   ;; not identity: the same person is `Jun Kawasaki`, `jun`, and `""` across
   ;; three messages, and making any of those identity splits the person graph.
   :person/address {:db/unique :db.unique/identity}
   :person/name {}

   ;; --- blobs ------------------------------------------------------------
   :blob/cid {:db/unique :db.unique/identity}
   :blob/media-type {}
   :blob/size {}

   ;; --- mail -------------------------------------------------------------
   ;; :mail/id is provider-independent on purpose -- see importer.normalize.
   ;; The same message imported from Gmail and from Graph is one entity.
   :mail/id {:db/unique :db.unique/identity}
   :mail/thread {}
   :mail/subject {}
   :mail/at {}
   :mail/from {:db/valueType :db.type/ref}
   :mail/to {:db/valueType :db.type/ref :db/cardinality :db.cardinality/many}
   :mail/cc {:db/valueType :db.type/ref :db/cardinality :db.cardinality/many}
   :mail/labels {:db/cardinality :db.cardinality/many}
   :mail/blob {:db/valueType :db.type/ref}
   :mail/snippet {}

   ;; --- calendar ---------------------------------------------------------
   :event/id {:db/unique :db.unique/identity}
   :event/title {}
   :event/start {}
   :event/end {}
   :event/organizer {:db/valueType :db.type/ref}
   :event/attendees {:db/valueType :db.type/ref :db/cardinality :db.cardinality/many}
   :event/calendar {}

   ;; --- files ------------------------------------------------------------
   :file/id {:db/unique :db.unique/identity}
   :file/name {}
   :file/media-type {}
   :file/modified-at {}
   :file/owner {:db/valueType :db.type/ref}
   :file/blob {:db/valueType :db.type/ref}

   ;; --- provenance -------------------------------------------------------
   ;; Every record says which source and which stream key it arrived on. Not
   ;; decoration: a retention sweep, a tenant offboarding and a resync all need
   ;; to select exactly one source's records, and a corpus that cannot do that
   ;; cannot honour the governance its source declared.
   :record/source-id {}
   :record/stream {}
   :record/stream-key {}
   :record/imported-at {}})

(def kinds
  "Which identity attribute belongs to which record kind."
  {:mail :mail/id
   :event :event/id
   :file :file/id
   :person :person/address
   :blob :blob/cid})

(defn identity-attr [kind] (get kinds kind))

(defn provenance
  "Stamp a record with where it came from. Applied by the importer, never by a
  caller, so that `:record/source-id` cannot be forged by the shape of an
  incoming map."
  [record cursor now]
  (assoc record
         :record/source-id (:importer.cursor/source-id cursor)
         :record/stream (:importer.cursor/stream cursor)
         :record/stream-key (:importer.cursor/key cursor)
         :record/imported-at now))
