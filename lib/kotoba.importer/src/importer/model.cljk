(ns importer.model
  "What a source is, as data: printable, diffable, storable.

  The connector plane already describes how to *call* a service. A source
  describes how to *keep up with* one, which needs three facts a connector
  descriptor does not carry:

    - the streams it has, and what kind of cursor each one takes. Gmail's
      history, Drive's change page token and Calendar's sync token are three
      independent cursors on one grant; Graph's mail delta is one cursor style
      over a folder tree. That asymmetry is why Google Workspace and Microsoft
      365 are two importers and not one parameterised importer.

    - how long a cursor stays valid. A lapsed Gmail historyId costs a full
      backfill; an expired Graph delta token costs a resync of one folder.
      The number decides the operational shape, so it is declared rather than
      discovered at three in the morning.

    - the governance the collection runs under. An importer holds somebody
      else's mail. `governance` is required, and a source that does not declare
      a PII tier and a retention period will not validate -- deny-by-default,
      the same posture m365-ingest's gate already takes toward effects.")

(def cursor-styles
  "Named for what the provider gives back, because that is what decides the
  failure mode when it lapses.

    :delta-token  opaque, resumable, expirable  (Graph @odata.deltaLink)
    :sync-token   opaque, resumable, expirable  (Google Calendar syncToken)
    :page-token   opaque, positional            (Drive changes pageToken)
    :watermark    a value from the records themselves, always comparable
    :none         no incremental path; every run is a full read"
  #{:delta-token :sync-token :page-token :watermark :none})

(def retention-values
  "`:unknown` is a legal answer and absence is not. A provider that does not
  publish an expiry gets `:unknown` written down, so the reader can tell a
  measured `we do not know` from a field nobody filled in."
  #{:unbounded :unknown})

;; --- builder --------------------------------------------------------------

(defn governance
  "The terms the collection runs under.

  Mirrors the fields m365-ingest's actor-manifest already declares, so an
  importer and its actor manifest cannot disagree about the PII tier."
  [{:keys [classification pii-tier retention-days consent-required? purpose]}]
  (cond-> {:importer.governance/classification classification
           :importer.governance/pii-tier pii-tier
           :importer.governance/retention-days retention-days
           :importer.governance/consent-required? consent-required?}
    purpose (assoc :importer.governance/purpose purpose)))

(defn source
  "A source descriptor with no streams yet.

  opts: {:summary :origin-domain :tenant :connector-id :governance :docs-url}

  `:connector-id` points at the connector repository that already knows how to
  call this service, so the two planes are joined by a recorded id rather than
  by a reader noticing they are about the same product."
  ([id name] (source id name nil))
  ([id name opts]
   (cond-> {:importer.source/id id
            :importer.source/name name
            :importer.source/streams {}}
     (:summary opts)       (assoc :importer.source/summary (:summary opts))
     (:origin-domain opts) (assoc :importer.source/origin-domain (:origin-domain opts))
     (:tenant opts)        (assoc :importer.source/tenant (:tenant opts))
     (:connector-id opts)  (assoc :importer.source/connector-id (:connector-id opts))
     (:docs-url opts)      (assoc :importer.source/docs-url (:docs-url opts))
     (:governance opts)    (assoc :importer.source/governance (:governance opts)))))

(defn add-stream
  "Declare one stream.

  opts: {:cursor-style :history-retention :resync-on :backfill? :description}

  `:history-retention` is milliseconds, or `:unbounded`, or `:unknown`.
  `:resync-on` is the set of provider conditions that invalidate the cursor and
  force a full read -- naming them here is what lets the actor handle a 410 as
  a planned path rather than as a crash."
  [src kind opts]
  (assoc-in src [:importer.source/streams kind]
            (cond-> {:importer.stream/kind kind
                     :importer.stream/cursor-style (:cursor-style opts)
                     :importer.stream/history-retention (:history-retention opts)}
              (:description opts) (assoc :importer.stream/description (:description opts))
              (contains? opts :backfill?) (assoc :importer.stream/backfill? (:backfill? opts))
              (seq (:resync-on opts)) (assoc :importer.stream/resync-on (set (:resync-on opts))))))

;; --- queries --------------------------------------------------------------

(defn streams [src] (->> src :importer.source/streams vals (sort-by :importer.stream/kind) vec))
(defn stream [src kind] (get-in src [:importer.source/streams kind]))
(defn stream-kinds [src] (->> src :importer.source/streams keys sort vec))

(defn history-retention
  "Milliseconds, `:unbounded`, `:unknown`, or nil when the stream is unknown."
  [src kind]
  (:importer.stream/history-retention (stream src kind)))

(defn resyncs-on?
  [src kind condition]
  (boolean (contains? (:importer.stream/resync-on (stream src kind)) condition)))

;; --- validation -----------------------------------------------------------

(defn- problem [severity code id msg]
  {:importer/severity severity :importer/code code :importer/id id :importer/msg msg})

(defn- validate-governance [id g]
  (if (nil? g)
    [(problem :error :governance/missing id
              (str id " declares no :importer.source/governance. An importer holds"
                   " somebody else's records; the terms are not optional."))]
    (->> [[:importer.governance/classification :governance/no-classification]
          [:importer.governance/pii-tier :governance/no-pii-tier]
          [:importer.governance/retention-days :governance/no-retention]
          [:importer.governance/consent-required? :governance/no-consent-decision]]
         (keep (fn [[k code]]
                 (when (nil? (get g k))
                   (problem :error code id (str id " governance says nothing about " (name k))))))
         vec)))

(defn- validate-stream [id kind s]
  (let [ps (transient [])
        style (:importer.stream/cursor-style s)
        ret (:importer.stream/history-retention s)]
    (when (not= kind (:importer.stream/kind s))
      (conj! ps (problem :error :stream/kind-mismatch id
                         (str id " stream key " (pr-str kind) " disagrees with "
                              (pr-str (:importer.stream/kind s))))))
    (when-not (cursor-styles style)
      (conj! ps (problem :error :stream/unknown-cursor-style id
                         (str id " stream " kind " has cursor style " (pr-str style)))))
    ;; Absence is the error; `:unknown` is a legal, measured answer.
    (when-not (or (contains? retention-values ret)
                  (and (number? ret) (pos? ret)))
      (conj! ps (problem :error :stream/no-history-retention id
                         (str id " stream " kind " does not say how long its cursor"
                              " stays valid (ms, :unbounded or :unknown)"))))
    ;; A cursor that can expire and names nothing that expires it leaves the
    ;; actor with no planned path back -- it will meet the condition anyway.
    (when (and (#{:delta-token :sync-token} style)
               (empty? (:importer.stream/resync-on s)))
      (conj! ps (problem :error :stream/no-resync-condition id
                         (str id " stream " kind " uses an expirable " (name style)
                              " but names no :resync-on condition"))))
    (persistent! ps)))

(defn problems
  [src]
  (let [id (:importer.source/id src)
        ps (transient [])]
    (when (or (nil? id) (= "" (str id)))
      (conj! ps (problem :error :source/no-id nil "source has no :importer.source/id")))
    (when (and (seq (str id)) (not (re-matches #"[a-z0-9]+(\.[a-z0-9-]+)+" (str id))))
      (conj! ps (problem :error :source/bad-id id
                         (str "source id " (pr-str id) " is not reverse-DNS"))))
    (when (= "" (str (:importer.source/name src)))
      (conj! ps (problem :error :source/no-name id "source has no :importer.source/name")))
    (when (empty? (:importer.source/streams src))
      (conj! ps (problem :error :source/no-streams id (str id " declares no streams"))))
    (when (nil? (:importer.source/origin-domain src))
      (conj! ps (problem :warn :source/no-origin-domain id
                         (str id " records no origin domain"))))
    (doseq [p (validate-governance id (:importer.source/governance src))] (conj! ps p))
    (doseq [[k s] (:importer.source/streams src)
            p (validate-stream id k s)]
      (conj! ps p))
    (persistent! ps)))

(defn errors [src] (filterv #(= :error (:importer/severity %)) (problems src)))
(defn valid? [src] (empty? (errors src)))

(defn validated
  "The source, or a throw. An actor repository calls this at load time on
  purpose: a source that cannot validate should fail where it is written."
  [src]
  (let [errs (errors src)]
    (when (seq errs)
      (throw (ex-info (str "invalid source descriptor: " (:importer.source/id src))
                      {:type :importer/invalid-source
                       :importer.source/id (:importer.source/id src)
                       :importer/problems errs})))
    src))
