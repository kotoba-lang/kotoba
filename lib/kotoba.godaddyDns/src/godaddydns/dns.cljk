(ns godaddydns.dns
  "The DNS capability — an injected host protocol, mirroring the slice of
  the GoDaddy Domains API the agent needs (list domains, read records,
  replace/delete records of a (type,name) pair).

  `IDns` is the seam: the real implementation (`godaddydns.godaddy`) talks
  to api.godaddy.com over an injected HTTP/JSON capability; `mock-dns`
  here is a deterministic in-memory zone so tests and demos run with no
  network and no API key (the DNS analogue of computer-use-clj's
  `mock-computer`).

  Record maps are GoDaddy-shaped: {:type \"A\" :name \"blog\" :data
  \"1.2.3.4\" :ttl 600}. `name` is the host label relative to the zone
  ('@' for the apex). GoDaddy's PUT-by-(type,name) semantics REPLACE the
  full set of records for that pair — `-upsert-records!` follows that
  contract exactly so the mock and the real host agree."
  #?(:clj (:require [kotoba.lang.text :as str])
     :cljs (:require [kotoba.lang.text :as str])))

(defprotocol IDns
  "DNS host capability. All record maps use {:type :name :data :ttl}."
  (-list-domains [this]
    "All domains on the account: [{:domain \"example.com\" :status \"ACTIVE\"} …].")
  (-list-records [this domain filt]
    "Records in `domain`, optionally filtered by {:type :name}. Returns
    a vector of record maps. Both filter keys are optional; nil matches all.")
  (-upsert-records! [this domain type name records]
    "REPLACE every record of (`type`,`name`) in `domain` with `records`
    (a seq of {:data :ttl …}). GoDaddy PUT-by-(type,name) semantics.")
  (-delete-records! [this domain type name]
    "Delete every record of (`type`,`name`) in `domain`."))

;; ───────────────────────────── helpers ─────────────────────────────

(defn normalize-record
  "Coerce a record map to the canonical {:type :name :data :ttl} shape:
  upper-case type, default name '@', default ttl 600."
  [{:keys [type name data ttl] :as r}]
  (merge r
         {:type (some-> (or type (:type r)) clojure.core/name str/upper)
          :name (or name "@")
          :data data
          :ttl  (or ttl 600)}))

(defn- match? [filt r]
  (let [{:keys [type name]} filt]
    (and (or (nil? type) (= (str/upper (clojure.core/name type))
                            (:type r)))
         (or (nil? name) (= name (:name r))))))

;; ───────────────────────────── mock ────────────────────────────────

(defrecord MockDns [state]
  IDns
  (-list-domains [_]
    (mapv (fn [d] {:domain d :status "ACTIVE"})
          (keys (:zones @state))))
  (-list-records [_ domain filt]
    (->> (get-in @state [:zones domain])
         (filterv #(match? filt %))))
  (-upsert-records! [_ domain type name records]
    (let [type (str/upper (clojure.core/name type))
          incoming (mapv (fn [r] (normalize-record (assoc r :type type :name name)))
                         records)]
      (swap! state update-in [:zones domain]
             (fn [recs]
               (-> (vec (remove #(and (= (:type %) type) (= (:name %) name))
                                (or recs [])))
                   (into incoming))))
      incoming))
  (-delete-records! [_ domain type name]
    (let [type (str/upper (clojure.core/name type))]
      (swap! state update-in [:zones domain]
             (fn [recs]
               (vec (remove #(and (= (:type %) type) (= (:name %) name))
                            (or recs [])))))
      :deleted)))

(defn mock-dns
  "An in-memory IDns. `zones` is {domain [record-map …]} — records are
  normalized on the way in. Deterministic, no network, no key.

    (mock-dns {\"example.com\" [{:type \"A\" :name \"@\" :data \"1.2.3.4\"}]})"
  ([] (mock-dns {}))
  ([zones]
   (let [norm (reduce-kv (fn [m d recs] (assoc m d (mapv normalize-record recs)))
                         {} zones)]
     (->MockDns (atom {:zones norm})))))
