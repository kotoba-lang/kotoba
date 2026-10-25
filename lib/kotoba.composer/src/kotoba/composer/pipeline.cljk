(ns kotoba.composer.pipeline
  "Track pipeline status transitions as a pure reducer (ADR-2607031510).

  Mirrors ongakuka's own internal staging (`lyricist→composer→vocalist‖
  arranger→mixer→critic`) as track-status data, the same way
  `kotoba.webrtc.session` drives call-signaling negotiation: the reducer
  decides *what should happen next* and returns it as a list of effects; it
  never performs network I/O, never calls `ai.gftd.ongakuka.compose`/
  `regenerate` itself. The host actor (e.g. yukkuri's
  `did:web:yukkuri.gftd.ai:actor:composer`) supplies the actual XRPC
  dispatch and executes the returned effects.

  Portable (.cljc) across JVM / ClojureScript / SCI / GraalVM."
  (:require [kotoba.composer.track :as track]))

(def terminal-statuses track/terminal-statuses)

(defn- transition
  "Return the result of moving track to next-status with the given effects
  when track is not already terminal, otherwise a no-op result."
  [track next-status effects]
  (if (contains? terminal-statuses (:composer.track/status track))
    {:track track :effects []}
    {:track (assoc track :composer.track/status next-status)
     :effects effects}))

(defn apply-event
  "Apply a pipeline event to track, returning {:track :effects}. event is a
  map with :type and event-specific keys:

    {:type :start-lyric}
      :queued -> :lyric, effect [:request-lyrics]

    {:type :lyric-done :lyrics s}
      :lyric -> :compose, effect [:request-composition]

    {:type :compose-done}
      :compose -> :vocal, effects [:request-vocal :request-arrangement]
      (vocalist and arranger run in parallel under one track-status, same
      as ongakuka's own internal `vocalist‖arranger` staging)

    {:type :vocal-arrange-done}
      :vocal -> :mix, effect [:request-mix]

    {:type :mix-done :blob-key k :mime-type m}
      :mix -> :review, effect [:request-review]

    {:type :approve}
      :review -> :published, no effect (host actor derives the public post)

    {:type :reject :reason r}
      any non-terminal status -> :rejected, no effect

    {:type :fail :reason r}
      any non-terminal status -> :failed, no effect

  Unknown event types or events invalid for the current status return the
  track unchanged with no effects -- same discipline as
  `kotoba.webrtc.session/apply-event`."
  [track {:keys [type lyrics blob-key mime-type]}]
  (let [status (:composer.track/status track)]
    (case type
      :start-lyric
      (if (= status :queued)
        (transition track :lyric [[:request-lyrics]])
        {:track track :effects []})

      :lyric-done
      (if (= status :lyric)
        (let [next (cond-> track lyrics (assoc :composer.track/lyrics lyrics))]
          (transition next :compose [[:request-composition]]))
        {:track track :effects []})

      :compose-done
      (if (= status :compose)
        (transition track :vocal [[:request-vocal] [:request-arrangement]])
        {:track track :effects []})

      :vocal-arrange-done
      (if (= status :vocal)
        (transition track :mix [[:request-mix]])
        {:track track :effects []})

      :mix-done
      (if (= status :mix)
        (let [next (cond-> track
                     blob-key (assoc :composer.track/blob-key blob-key)
                     mime-type (assoc :composer.track/mime-type mime-type))]
          (transition next :review [[:request-review]]))
        {:track track :effects []})

      :approve
      (if (= status :review)
        (transition track :published [])
        {:track track :effects []})

      :reject
      (transition track :rejected [])

      :fail
      (transition track :failed [])

      {:track track :effects []})))

(defn active?
  "True when track's status is neither :queued nor a terminal status."
  [track]
  (let [status (:composer.track/status track)]
    (not (or (= status :queued) (contains? terminal-statuses status)))))
