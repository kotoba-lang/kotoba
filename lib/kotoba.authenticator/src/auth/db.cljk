(ns auth.db
  "The account vault as a Datomic-API store.

  Backed by langchain.db — a pure-.cljc, dependency-free, Datomic-shaped EAV
  engine (create-conn / transact! / q / pull / entity). Accounts are entities;
  lookups are Datalog. `:account/id` is a `:db.unique/identity` attribute, so
  re-adding the same issuer+name upserts instead of duplicating (the behaviour
  you want when re-scanning a QR code).

  WHY THIS VAULT IS A SNAPSHOT AND NOT A JOURNAL. The decision ledgers in
  `authentication` and `authorization` persist through `kotoba-lang/journal`,
  an append-only history replayed on open -- the right shape for an audit
  trail, and the wrong one here. An append-only file keeps every value it was
  ever given, so `remove!` would retract a secret from the index while leaving
  it on disk forever. A vault's delete has to actually erase, so `auth.vault`
  rewrites the whole state instead."
  (:require [langchain.db :as d]
            [kotoba.lang.text :as str]))

(def schema-tx-data
  "The vault schema, written in Datomic's installation tx-data dialect -- the
  one dialect the rest of this workspace's datom corpora are declared in.
  `langchain.db/schema-from-tx-data` converts it to the map the store reads,
  so the attributes are stated once rather than once per host."
  [{:db/ident :account/id :db/valueType :db.type/string
    :db/cardinality :db.cardinality/one :db/unique :db.unique/identity
    :db/doc "issuer:name, or name -- unique, so re-scanning a QR code upserts instead of duplicating."}
   {:db/ident :account/issuer :db/valueType :db.type/string :db/cardinality :db.cardinality/one}
   {:db/ident :account/name :db/valueType :db.type/string :db/cardinality :db.cardinality/one}
   {:db/ident :account/secret :db/valueType :db.type/string :db/cardinality :db.cardinality/one
    :db/doc "The Base32 shared secret. Cleartext -- see the security note in auth.vault."}
   {:db/ident :account/type :db/valueType :db.type/keyword :db/cardinality :db.cardinality/one
    :db/doc ":totp or :hotp."}
   {:db/ident :account/algorithm :db/valueType :db.type/keyword :db/cardinality :db.cardinality/one}
   {:db/ident :account/digits :db/valueType :db.type/long :db/cardinality :db.cardinality/one}
   {:db/ident :account/period :db/valueType :db.type/long :db/cardinality :db.cardinality/one}
   {:db/ident :account/counter :db/valueType :db.type/long :db/cardinality :db.cardinality/one
    :db/doc "The HOTP moving factor."}])

(def schema
  "`schema-tx-data` in the map dialect `langchain.db` reads."
  (d/schema-from-tx-data schema-tx-data))

(defn account-id
  "Canonical identity for an account: `issuer:name`, or just `name`."
  [{:account/keys [issuer name]}]
  (if (seq issuer) (str issuer ":" name) (str name)))

(defn empty-conn [] (d/create-conn schema))

(defn ->state
  "Serialises the whole connection to plain EDN data (for the vault file)."
  [conn] @conn)

(defn state->conn
  "Rebuilds a connection from previously-serialised EDN state, refreshing the
  schema so code changes take effect on reload."
  [state]
  (atom (assoc-in (or state {:db (:db @(empty-conn)) :log []})
                  [:db :schema] schema)))

;; ───────────────────────── writes ─────────────────────────

(defn put!
  "Upserts an account (a map of :account/* keys, minus :account/id which is
  derived). Returns the tx report."
  [conn account]
  (let [acct (->> account
                  (remove (fn [[_ v]] (nil? v)))
                  (into {}))]
    (d/transact! conn [(assoc acct :account/id (account-id acct))])))

(defn remove!
  "Removes the account with the given canonical id. Returns true if it existed."
  [conn id]
  (if-let [eid (d/entid (d/db conn) [:account/id id])]
    (do (d/transact! conn [[:db/retractEntity eid]]) true)
    false))

(defn bump-counter!
  "Increments the HOTP moving factor for `id` and returns the new counter."
  [conn id]
  (let [n (inc (or (:account/counter (d/pull (d/db conn) [:account/counter] [:account/id id])) 0))]
    (d/transact! conn [{:account/id id :account/counter n}])
    n))

;; ───────────────────────── reads (Datalog) ─────────────────────────

(defn all
  "All accounts, sorted by issuer then name."
  [conn]
  (let [dbv (d/db conn)]
    (->> (d/q '[:find [?id ...] :where [?e :account/id ?id]] dbv)
         (map #(d/pull dbv '[*] [:account/id %]))
         (sort-by (juxt #(str/lower (or (:account/issuer %) ""))
                        #(str/lower (or (:account/name %) "")))))))

(defn get-by-id [conn id]
  (d/pull (d/db conn) '[*] [:account/id id]))

(defn search
  "Case-insensitive substring match over id / issuer / name. `q` blank → all."
  [conn q]
  (if (str/blank? q)
    (all conn)
    (let [needle (str/lower q)]
      (filter (fn [a]
                (some #(and % (str/includes? (str/lower (str %)) needle))
                      [(:account/id a) (:account/issuer a) (:account/name a)]))
              (all conn)))))
