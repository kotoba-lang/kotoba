(ns filecoin.node.actors
  "The singleton system actors — the addresses that exist because the network
  exists, rather than because anyone created them.

  `f00`–`f07`, `f010` and `f099` are allocated in the genesis block and are
  the same on every Filecoin network. `f0100` is the first ID handed to an
  actor someone actually made, which is why `first-non-singleton-actor-id`
  is worth naming: an ID below it did not come from the init actor, and
  looking one up in an init-actor map finds nothing.

  Source: `go-state-types/builtin/singletons.go`. Method numbers are
  deliberately absent — they are per-actor, versioned with the actor bundle,
  and inventing them from memory is how a message calls the wrong entry
  point with the right-looking parameters."
  (:require [filecoin.address :as addr]))

(def ^:const system 0)
(def ^:const init 1)
(def ^:const reward 2)
(def ^:const cron 3)
(def ^:const storage-power 4)
(def ^:const storage-market 5)
(def ^:const verified-registry 6)
(def ^:const datacap 7)

(def ^:const ethereum-address-manager
  "The EAM: `f4` addresses are minted here, which is why it sits apart from
  the 0–7 block rather than after it."
  10)

(def ^:const burnt-funds
  "Where burnt gas goes. An ordinary account actor with no key behind it, so
  the funds are unrecoverable by construction rather than by policy."
  99)

(def ^:const first-non-singleton-actor-id 100)

(def singletons
  {:system system
   :init init
   :reward reward
   :cron cron
   :storage-power storage-power
   :storage-market storage-market
   :verified-registry verified-registry
   :datacap datacap
   :ethereum-address-manager ethereum-address-manager
   :burnt-funds burnt-funds})

(defn address
  "The `f0…` address of a singleton, by keyword or by ID."
  ([k] (address k :mainnet))
  ([k network]
   (let [id (if (keyword? k)
              (or (get singletons k)
                  (throw (ex-info "actors: unknown singleton" {:name k})))
              k)]
     (addr/id id network))))

(defn address-string
  "The same, as `f0…`."
  ([k] (address-string k :mainnet))
  ([k network] (addr/to-string (address k network))))

(defn singleton?
  "Whether an actor ID belongs to the genesis-allocated set. Not simply
  `< 100`: 8, 9 and 11–98 are inside that range and are allocated to
  nothing."
  [id]
  (contains? (set (vals singletons)) id))
