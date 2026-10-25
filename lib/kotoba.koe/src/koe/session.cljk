(ns koe.session
  "The reusable voice dialog loop: STT in → dialog step → optional booking → TTS out,
  with barge-in. Pure orchestration over koe.ports protocols — no I/O of its own, so
  it is testable offline with fixture ports. Hosts (denwaban) inject real actors.

  Booking is ALWAYS delegated through IBooking/confirm (member-signed); this kernel
  never confirms a booking itself."
  (:require [koe.ports :as p]))

(defn converse
  "Drive one turn. Given injected ports and the current dialog `state`, plus an
  incoming `utterance` (already transcribed), produce the reply audio and any booking
  action. Returns {:state state' :reply text :audio audio :action act|nil :booking b|nil}.

  `:barge-in?` in opts signals the utterance interrupted in-flight TTS; the caller
  should stop prior playback before `say`-ing the new reply."
  [{:keys [dialog tts booking]} state utterance & [{:keys [voice signature]}]]
  (let [{:keys [reply action state]} (p/step dialog state utterance)
        audio   (when reply (p/synth tts reply {:voice voice}))
        booking (when (= action :book)
                  ;; delegate — propose then member-signed confirm (never server-side)
                  (let [proposal (p/propose booking (:slot state))]
                    (when signature (p/confirm booking proposal signature))))]
    {:state state :reply reply :audio audio :action action :booking booking}))

(defn booking-delegated?
  "Invariant guard a host can assert in tests: a turn that books must go through
  IBooking (propose/confirm), not fabricate a confirmation locally."
  [turn]
  (or (and (nil? (:action turn))
           (nil? (:booking turn)))                         ; ordinary turn: no fabricated booking
      (and (= :book (:action turn))
           (or (nil? (:booking turn))                      ; held: no signature yet, not confirmed
               (some? (:signed-by (:booking turn)))))))    ; confirmed: non-nil member signature
                                                              ; return shape carries :signed-by -- a
                                                              ; fabricated/hand-built :booking that never
                                                              ; went through confirm won't have it
