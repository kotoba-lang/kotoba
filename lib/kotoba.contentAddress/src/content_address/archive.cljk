(ns content-address.archive
  "Putting a document where a copy can be fetched, and proving it landed.

  The archive is Location, not authority: it stores bytes under the CID the
  bytes already have, and it recomputes the digest on receipt (422 on
  mismatch). Losing it costs availability, never identity — anyone holding
  the bytes can re-derive the same address (ADR-2608039000's削除テスト).

  `publish!` is fail-closed. It PUTs, GETs the object back, and compares the
  returned bytes to what it sent. A 201 alone is not evidence: the failure
  this guards against is a manifest recording an address nothing serves.

  ⚠ `PUT /ipfs/{cid}` accepts raw CIDv1 only. A dag-cbor identity must be
  archived under the raw CID of the same bytes — one object, two codecs."
  (:require [kotoba.lang.text :as str]
            [content-address.core :as ca]
            [content-address.digest :as digest])
  #?(:clj (:import [java.net URI]
                   [java.net.http HttpClient HttpRequest
                    HttpRequest$BodyPublishers HttpResponse$BodyHandlers]
                   [java.time Duration])))

(def default-origin "https://kotobase.net")

(def max-object-bytes
  "kotobase.archive-put/max-object-bytes. Larger documents need the
  large-object plane, not this one."
  (* 4 1024 1024))

#?(:clj
   (defonce ^:private client
     (delay (-> (HttpClient/newBuilder)
                (.connectTimeout (Duration/ofSeconds 30))
                (.build)))))

(defn put!
  "PUT the bytes under their own CID. Returns `{:status :body :url}`.

  Async on cljs (returns a promise), synchronous on the JVM."
  [{:keys [origin cid octets token content-type]
    :or {origin default-origin content-type "application/octet-stream"}}]
  (let [url (ca/archive-url origin cid)]
    #?(:clj
       (let [req (-> (HttpRequest/newBuilder (URI/create url))
                     (.header "content-type" content-type)
                     (.header "authorization" (str "Bearer " token))
                     (.PUT (HttpRequest$BodyPublishers/ofByteArray
                            (digest/->bytes octets)))
                     (.build))
             res (.send @client req (HttpResponse$BodyHandlers/ofString))]
         {:status (.statusCode res) :body (.body res) :url url})
       :cljs
       (-> (js/fetch url #js {:method "PUT"
                              :headers #js {"content-type" content-type
                                            "authorization" (str "Bearer " token)}
                              :body (digest/->bytes octets)})
           (.then (fn [r] (-> (.text r)
                              (.then (fn [b] {:status (.-status r) :body b :url url})))))))))

(defn get-object
  "GET the object back. Returns `{:status :octets :url}`."
  [{:keys [origin cid] :or {origin default-origin}}]
  (let [url (ca/archive-url origin cid)]
    #?(:clj
       (let [req (-> (HttpRequest/newBuilder (URI/create url)) (.GET) (.build))
             res (.send @client req (HttpResponse$BodyHandlers/ofByteArray))]
         {:status (.statusCode res)
          :octets (digest/->octets (.body res))
          :url url})
       :cljs
       (-> (js/fetch url)
           (.then (fn [r] (-> (.arrayBuffer r)
                              (.then (fn [ab]
                                       {:status (.-status r)
                                        :octets (digest/->octets (js/Buffer.from ab))
                                        :url url})))))))))

(defn address
  "The identity of `document` — its raw CIDv1 — plus its size.

  Pure. This is the whole of \"giving a document a name\": no server is
  consulted, and the same bytes produce the same answer anywhere."
  [document]
  (let [octets (digest/->octets document)]
    {:cid (ca/cid-string :raw (digest/sha256 octets))
     :size (count octets)
     :octets octets}))

(defn refusals
  "Why this document cannot be archived, as data. Empty = it can."
  [{:keys [cid size token]}]
  (cond-> []
    (not (ca/raw-cid? cid))
    (conj {:refusal :not-raw-sha256 :cid cid})

    (and (number? size) (> size max-object-bytes))
    (conj {:refusal :over-archive-cap :size size :cap max-object-bytes})

    (not (number? size))
    (conj {:refusal :no-size :detail "size is required — an unmeasured object cannot be capped"})

    (str/blank? (str token))
    (conj {:refusal :no-token :detail "archive PUT is authenticated"})))

(defn verify
  "Re-derive the address of what the archive returns for `cid`.

  This is the check that a Location still holds the identity it claims:
  fetch, hash, compare. A GET that succeeds but returns different bytes is
  a failure, and is reported as one."
  [{:keys [origin cid] :or {origin default-origin}}]
  (let [handle (fn [got]
                 (let [derived (when (= 200 (:status got))
                                 (ca/cid-string :raw (digest/sha256 (:octets got))))]
                   {:cid cid
                    :status (:status got)
                    :url (:url got)
                    :size (count (:octets got))
                    :derived derived
                    :verified? (= derived cid)}))]
    #?(:clj (handle (get-object {:origin origin :cid cid}))
       :cljs (.then (get-object {:origin origin :cid cid}) handle))))
