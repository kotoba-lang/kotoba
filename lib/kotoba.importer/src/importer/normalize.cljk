(ns importer.normalize
  "Provider records to the canonical shape.

  Two decisions here are load-bearing rather than tidying.

  **An address is identity; a display name is not.** Gmail hands over an RFC
  5322 header string, Graph hands over a nested map, and both carry a name that
  changes between messages from the same person. Keying on anything but the
  lower-cased address splits the person graph, which is exactly the join a
  corpus exists to make possible.

  **A message id must not name its provider.** The same message reaches a
  Gmail mailbox and an Exchange mailbox with different provider ids and the
  same RFC 5322 Message-ID. Keying on the provider id stores it twice, and
  every later count, thread and answer is quietly doubled for anyone in both
  systems -- which, for a company that migrated, is everyone."
  (:require [kotoba.lang.text :as str]))

(def ^:private angled #"^\s*(.*?)\s*<([^>]+)>\s*$")

(defn- unquote-name [s]
  (let [s (str/trim (str s))]
    (if (and (>= (count s) 2) (str/starts-with? s "\"") (str/ends-with? s "\""))
      (str/trim (subs s 1 (dec (count s))))
      s)))

(defn address
  "One address, from any of the shapes the two providers use, or nil.

  Accepts an RFC 5322 header fragment (`Jun Kawasaki <jun@example.com>` or a
  bare address), a Graph recipient map with keyword or string keys, and nil.
  Returns {:person/address <lower-cased> :person/name <as written, or absent>}."
  [x]
  (cond
    (nil? x) nil

    (map? x)
    ;; Graph nests the pair under emailAddress; a caller may also hand the
    ;; inner map straight in. Both keyings appear depending on how the JSON was
    ;; parsed, and guessing wrong loses the whole recipient list silently.
    (let [inner (or (get x :emailAddress) (get x "emailAddress") x)
          addr (or (get inner :address) (get inner "address"))
          nm (or (get inner :name) (get inner "name"))]
      (when-not (str/blank? (str addr))
        (cond-> {:person/address (str/lower (str/trim (str addr)))}
          (not (str/blank? (str nm))) (assoc :person/name (unquote-name nm)))))

    :else
    (let [s (str/trim (str x))]
      (when-not (str/blank? s)
        (if-let [[_ nm addr] (re-matches angled s)]
          (cond-> {:person/address (str/lower (str/trim addr))}
            (not (str/blank? nm)) (assoc :person/name (unquote-name nm)))
          {:person/address (str/lower s)})))))

(defn addresses
  "A recipient list, deduplicated by address, order preserved."
  [xs]
  (->> (if (or (nil? xs) (sequential? xs)) xs [xs])
       (keep address)
       (reduce (fn [{:keys [seen out]} a]
                 (if (seen (:person/address a))
                   {:seen seen :out out}
                   {:seen (conj seen (:person/address a)) :out (conj out a)}))
               {:seen #{} :out []})
       :out))

(defn mail-id
  "The provider-independent identity of a message.

  Prefers the RFC 5322 Message-ID, which both providers carry and which
  survives a migration between them. Falls back to the content address of the
  raw message, which is provider-independent for a different reason: it is the
  bytes.

  The prefix is not decoration -- without it a Message-ID that happened to look
  like a CID would collide with one."
  [{:keys [message-id cid]}]
  (let [m (some-> message-id str str/trim)
        m (when-not (str/blank? m)
            (-> m (str/replace #"^<" "") (str/replace #">$" "") str/trim))]
    (cond
      (not (str/blank? (str m))) (str "rfc5322:" m)
      (not (str/blank? (str cid))) (str "blob:" cid)
      :else (throw (ex-info "a message needs a Message-ID or a content address"
                            {:type :importer/unidentifiable-mail})))))

(defn mail
  "A canonical mail record.

  opts: {:message-id :cid :thread :subject :at :from :to :cc :labels
         :snippet :media-type :size}

  `:at` is milliseconds since epoch -- a number, comparable without a timezone
  database, and the value a watermark is taken from."
  [{:keys [message-id cid thread subject at from to cc labels snippet
           media-type size]}]
  (let [id (mail-id {:message-id message-id :cid cid})]
    (cond-> {:mail/id id}
      thread (assoc :mail/thread thread)
      subject (assoc :mail/subject subject)
      (some? at) (assoc :mail/at at)
      (address from) (assoc :mail/from (address from))
      (seq (addresses to)) (assoc :mail/to (addresses to))
      (seq (addresses cc)) (assoc :mail/cc (addresses cc))
      (seq labels) (assoc :mail/labels (vec labels))
      snippet (assoc :mail/snippet snippet)
      cid (assoc :mail/blob (cond-> {:blob/cid cid}
                              media-type (assoc :blob/media-type media-type)
                              (some? size) (assoc :blob/size size))))))

(defn watermark-of
  "The high-water mark of a page of canonical mail: the largest `:mail/at`.

  nil for an empty page, which `importer.cursor/advance` treats as `no
  watermark to check` rather than as zero -- a page of nothing must not push a
  watermark backwards."
  [records]
  (let [ts (keep :mail/at records)]
    (when (seq ts) (apply max ts))))
