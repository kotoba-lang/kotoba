(ns importer.cursor
  "A watermark over one provider stream, and the rule for when it may move.

  That rule is the reason this is a namespace and not a string in a map:

    **A cursor may only advance past records that are durably persisted.**

  Advance it when the page was half written, and the missing half is
  unrecoverable. The next delta call starts after the new token, so no later
  run will ever mention those records again -- and every run afterwards reports
  success. The hole is permanent, silent, and invisible to every check that
  asks the importer how it is doing.

  So `advance` does not take a token. It takes the plan's count and the sink's
  own report of what it committed, and refuses when they disagree.

  ## Two phases, because the hole is usually made between them

  `:backfill` reads history, paginated, with no incremental guarantee. Its
  watermark moves in whatever order the provider pages. `:incremental` follows
  a delta and its watermark must never go backwards. Promoting from the first
  to the second before the backfill is exhausted skips everything not yet read,
  which looks exactly like a healthy incremental importer from the outside."
  (:require [importer.model :as m]))

(defn cursor
  "A fresh, never-advanced cursor over one stream of one source.

  `key` names which instance of that stream -- a mailbox address, a calendar
  id, a drive id. One cursor per (source, stream, key); a single cursor shared
  across mailboxes is a cursor that is wrong for all but one of them."
  [src kind key]
  (let [s (m/stream src kind)]
    (when (nil? s)
      (throw (ex-info "no such stream on this source"
                      {:type :importer/unknown-stream
                       :importer.source/id (:importer.source/id src)
                       :importer.stream/kind kind})))
    {:importer.cursor/source-id (:importer.source/id src)
     :importer.cursor/stream kind
     :importer.cursor/key key
     :importer.cursor/cursor-style (:importer.stream/cursor-style s)
     :importer.cursor/history-retention (:importer.stream/history-retention s)
     :importer.cursor/phase (if (false? (:importer.stream/backfill? s)) :incremental :backfill)
     :importer.cursor/token nil
     :importer.cursor/watermark nil
     :importer.cursor/at nil
     :importer.cursor/advances 0
     :importer.cursor/exhausted? false
     :importer.cursor/resets []}))

(defn started? [c] (pos? (:importer.cursor/advances c 0)))
(defn token [c] (:importer.cursor/token c))
(defn phase [c] (:importer.cursor/phase c))
(defn watermark [c] (:importer.cursor/watermark c))
(defn exhausted? [c] (boolean (:importer.cursor/exhausted? c)))

(defn stream-key
  "The identity of the stream this cursor follows. Coverage is keyed by it, so
  it is one function rather than three inline destructurings."
  [c]
  [(:importer.cursor/source-id c) (:importer.cursor/stream c) (:importer.cursor/key c)])

(defn- held [c reason detail]
  {:importer.cursor/state :held
   :importer.cursor/reason reason
   :importer.cursor/detail detail
   :importer.cursor/cursor c})

(defn- advanced [c]
  {:importer.cursor/state :advanced :importer.cursor/cursor c})

(defn advance
  "Move the cursor, or refuse and say why.

  report: {:outcome :next-token :planned :persisted :watermark :at}

    :planned    records the plan said this page contained
    :persisted  records the sink says it committed

  Returns {:importer.cursor/state :advanced|:held ...}. On :held the cursor
  comes back unchanged -- callers that pull `:importer.cursor/cursor` out
  without looking at the state re-run the same page rather than skipping it,
  which is the safe direction to be wrong in."
  [c {:keys [outcome next-token planned persisted watermark at]}]
  (let [planned (or planned 0)
        persisted (or persisted 0)]
    (cond
      (not= :synced outcome)
      (held c :not-synced
            (str "outcome was " (pr-str outcome) "; a cursor moves only on :synced"))

      (< persisted planned)
      (held c :partial-write
            (str "sink committed " persisted " of " planned
                 " planned records; advancing would strand " (- planned persisted)
                 " that no later delta will mention"))

      (> persisted planned)
      (held c :over-persist
            (str "sink committed " persisted " but the plan held " planned
                 "; the two disagree about what this page was"))

      (and (= :incremental (:importer.cursor/phase c))
           (#{:delta-token :sync-token :page-token} (:importer.cursor/cursor-style c))
           (nil? next-token))
      (held c :no-token
            (str "an incremental " (name (:importer.cursor/cursor-style c))
                 " stream returned no next token; without it the next run has"
                 " no resume point and would silently re-read from the start"))

      (and (= :incremental (:importer.cursor/phase c))
           (some? watermark)
           (some? (:importer.cursor/watermark c))
           (neg? (compare watermark (:importer.cursor/watermark c))))
      (held c :watermark-regressed
            (str "watermark went backwards, from "
                 (pr-str (:importer.cursor/watermark c)) " to " (pr-str watermark)))

      :else
      (advanced (-> c
                    (assoc :importer.cursor/token next-token)
                    (assoc :importer.cursor/at at)
                    (assoc :importer.cursor/exhausted? (nil? next-token))
                    (update :importer.cursor/advances inc)
                    (cond-> (some? watermark)
                      (assoc :importer.cursor/watermark watermark)))))))

(defn promote
  "Backfill -> incremental.

  Refuses unless the backfill is exhausted. Promoting early is the quiet
  version of this whole class of bug: the importer starts following a delta
  from now, every subsequent run is green, and everything older than the
  promotion was never read."
  [c incremental-token at]
  (cond
    (= :incremental (:importer.cursor/phase c))
    (held c :already-incremental "cursor is already following a delta")

    (not (exhausted? c))
    (held c :backfill-incomplete
          "backfill has not returned a final page; promoting now would skip everything not yet read")

    (and (#{:delta-token :sync-token} (:importer.cursor/cursor-style c))
         (nil? incremental-token))
    (held c :no-token "an expirable stream needs a token to follow from")

    :else
    {:importer.cursor/state :promoted
     :importer.cursor/cursor (assoc c
                                    :importer.cursor/phase :incremental
                                    :importer.cursor/token incremental-token
                                    :importer.cursor/exhausted? false
                                    :importer.cursor/at at)}))

(defn reset
  "Back to backfill, because the provider invalidated the cursor.

  The watermark is kept: it remains a true statement about what was once
  imported, and coverage uses the phase -- not the watermark -- to know the
  stream is being re-read."
  [c reason at]
  (-> c
      (assoc :importer.cursor/phase :backfill
             :importer.cursor/token nil
             :importer.cursor/exhausted? false
             :importer.cursor/at at)
      (update :importer.cursor/resets (fnil conj [])
              {:importer.cursor/reason reason
               :importer.cursor/at at
               :importer.cursor/from-token (:importer.cursor/token c)})))

(defn expired?
  "true / false / nil.

  nil when the stream declares `:unknown` retention -- the honest answer, and
  the reason `retention-values` admits `:unknown` but not absence. A caller
  reading nil as false will let a lapsed cursor run until the provider rejects
  it; reading nil as true will force needless full backfills. Neither is
  something this namespace should decide on the caller's behalf."
  [c now]
  (let [ret (:importer.cursor/history-retention c)
        at (:importer.cursor/at c)]
    (cond
      (= :unbounded ret) false
      (= :unknown ret) nil
      (nil? at) false
      (number? ret) (> (- now at) ret)
      :else nil)))
