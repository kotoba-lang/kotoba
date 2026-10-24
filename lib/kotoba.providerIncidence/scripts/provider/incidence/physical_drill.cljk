(ns provider.incidence.physical-drill
  "One-shot commands used by the three-machine durability drill."
  (:require [kotoba.lang.capability-values :as capabilities]
            [kotoba.lang.incidence :as incidence]
            [kotoba.lang.incidence-port :as port]
            [kotoba.lang.incidence-replication :as replication]
            [provider.incidence :as durable])
  (:import [java.nio.file Files Path Paths StandardOpenOption]))

(def dataspace "dataspace:physical-recovery/v1")
(def actor (incidence/typed-ref :did "did:key:z6MkPhysicalRecovery"))
(def append-cap (capabilities/make-cap port/append-kind dataspace))

(def parent
  (incidence/assertion
   (incidence/incidence :recovery/source {:organization #{actor}} {})))

(def child
  (incidence/assertion
   (incidence/incidence :recovery/replicated
                        {:organization #{actor}}
                        {:parents #{(:incidence/cid parent)}})))

(defn- path [value]
  (Paths/get value (make-array String 0)))

(defn- report [store role]
  (let [entries (durable/entries store)]
    {:physical/role role
     :physical/dataspace dataspace
     :physical/count (count entries)
     :physical/cids (sort (map :incidence/cid entries))}))

(defn- seed! [^Path root ^Path bundle-path]
  (let [store (durable/open-store root dataspace)]
    (doseq [entry [parent child]]
      (durable/append! store {:dataspace dataspace
                              :entry entry
                              :capability append-cap}))
    (Files/write bundle-path (durable/export-bundle store)
                 (into-array java.nio.file.OpenOption
                             [StandardOpenOption/CREATE
                              StandardOpenOption/TRUNCATE_EXISTING
                              StandardOpenOption/WRITE]))
    (report store :source)))

(defn- import! [^Path root ^Path bundle-path]
  (let [store (durable/open-store root dataspace)]
    (durable/import-bundle! store append-cap (Files/readAllBytes bundle-path))
    (report store :replica)))

(defn- recover! [^Path root]
  (let [store (durable/open-store root dataspace)
        replica (durable/recover store)]
    (assoc (report store :recovered)
           :physical/projection-ok?
           (:ok? (replication/projection replica)))))

(defn -main [& [command root bundle]]
  (let [result (case command
                 "seed" (when (and root bundle)
                          (seed! (path root) (path bundle)))
                 "import" (when (and root bundle)
                            (import! (path root) (path bundle)))
                 "recover" (when root (recover! (path root)))
                 nil)]
    (when-not result
      (throw (ex-info "usage: seed ROOT BUNDLE | import ROOT BUNDLE | recover ROOT"
                      {:problem :physical-drill/arguments})))
    (prn result)))
