(ns koe.bridge
  "One live call, as a fold over the frames a carrier sends.

  `koe.session` drives a *turn* — an utterance in, a reply out. This drives the
  **call**: when the caller has finished a sentence, when the receptionist is
  allowed to talk, what happens when they talk over each other, and when it ends.

  ## Why it is a fold and not a loop

  A socket loop is the one part of a voice agent nobody can test. Written as a
  fold, every one of those decisions is a function from a frame to a state, and
  the socket becomes the twenty lines that read a message and write the answers.
  The host does the I/O; nothing here opens anything, reads a file, or blocks.

  ## The two things the host does between calls into this namespace

  `on-frame` may return `:koe/transcribe` — a completed utterance the host should
  send to a speech engine — and `on-transcript` may return `:koe/say`, text the
  host should turn into audio (from a pre-rendered file, or a synthesizer). Both
  are slow and both are I/O, which is exactly why they are returned rather than
  performed.

  ## Barge-in

  While the receptionist is speaking, a caller who starts talking wins: the host
  is told to send `clear` and the queued audio is dropped. A receptionist that
  keeps talking over somebody is worse than a slow one, and this is the only
  state where an incoming frame means *stop* rather than *listen*."
  (:require [kotoba.lang.text :as str]
            [koe.media :as media]))

(def states
  "Where a call can be. `:speaking` is the only one where inbound speech is
  interpreted as interruption rather than as an utterance."
  #{:greeting :listening :speaking :ended})

(defn start
  "Begin a call.

  `dialog-state` is whatever the host's dialog carries; this namespace never
  looks inside it. `greeting` is optional — a line to say before listening."
  [{:keys [stream-id dialog-state vad greeting]}]
  {:koe/state (if greeting :greeting :listening)
   :koe/stream-id stream-id
   :koe/dialog dialog-state
   :koe/segmenter (media/segmenter (or vad {}))
   :koe/pending-greeting greeting
   :koe/turns 0})

(defn- listening
  "Return to listening with a fresh segmenter — used when the receptionist has
  finished speaking and nothing has been said yet."
  [bridge]
  (assoc bridge :koe/state :listening
         :koe/segmenter (media/segmenter (get-in bridge [:koe/segmenter :media/vad]))))

(defn- interrupted
  "Return to listening WITHOUT resetting the segmenter.

  The difference matters and is not cosmetic. Barge-in is detected part-way
  through the caller's sentence — they are already saying 「いや、6人で」 — so
  discarding the collected frames would throw away the beginning of it and
  transcribe 「人で」. The audio that triggered the interruption is the first part
  of what they said."
  [bridge]
  (assoc bridge :koe/state :listening))

(defn on-frame
  "Fold one decoded carrier message in.

  Returns `{:koe/bridge b' :koe/out [frames] :koe/transcribe bytes|nil}`.
  `:koe/out` is always a vector, possibly empty — a caller should be able to send
  it without checking.

  `decode-audio` turns the carrier's base64 payload into bytes. It is injected
  because base64 is platform-specific (`java.util.Base64`, `atob`) and this
  namespace stays portable; it defaults to identity so a test can pass a byte
  vector as the payload directly."
  ([bridge decoded] (on-frame bridge decoded identity))
  ([bridge decoded decode-audio]
  (let [{:keys [media/event media/payload media/stream-id]} (media/parse-frame decoded)
        sid (or (:koe/stream-id bridge) stream-id)
        bridge (cond-> bridge stream-id (assoc :koe/stream-id stream-id))]
    (case event
      :start {:koe/bridge bridge :koe/out [] :koe/transcribe nil}

      :stop {:koe/bridge (assoc bridge :koe/state :ended) :koe/out [] :koe/transcribe nil}

      ;; The carrier echoes a mark when our audio has finished playing. That —
      ;; not a timer, and not the length of the audio — is when the receptionist
      ;; has actually stopped talking and may start listening.
      :mark {:koe/bridge (listening bridge) :koe/out [] :koe/transcribe nil}

      :audio
      (let [seg (media/absorb-frame (:koe/segmenter bridge)
                                    (if payload (decode-audio payload) []))
            b (assoc bridge :koe/segmenter seg)]
        (cond
          (= :ended (:koe/state bridge))
          {:koe/bridge b :koe/out [] :koe/transcribe nil}

          ;; Talking over the receptionist: drop what is queued and listen.
          (and (#{:speaking :greeting} (:koe/state bridge)) (media/barge-in? seg))
          {:koe/bridge (interrupted b)
           :koe/out [(media/clear-audio sid)]
           :koe/transcribe nil}

          (and (= :listening (:koe/state bridge)) (:media/utterance seg))
          {:koe/bridge b :koe/out [] :koe/transcribe (:media/utterance seg)}

          :else {:koe/bridge b :koe/out [] :koe/transcribe nil}))

      ;; :connected and :unknown carry nothing to act on. Unknown is not an error
      ;; here -- `koe.media/parse-frame` already made it visible.
      {:koe/bridge bridge :koe/out [] :koe/transcribe nil}))))

(defn on-transcript
  "Feed a completed transcript into the dialog and get the reply.

  `turn-fn` is `(fn [dialog-state utterance] -> {:state .. :reply .. :ended? ..})`
  — the host's, because what a reply *means* is the host's business. This
  namespace only decides that a reply means the receptionist is now speaking.

  A nil or blank transcript is not passed to the dialog at all: the speech engine
  failing, or a caller who said nothing intelligible, must not arrive as an
  utterance. The call simply keeps listening."
  [bridge transcript turn-fn]
  (if-not (and (string? transcript) (seq (str/trim transcript)))
    {:koe/bridge (listening bridge) :koe/out [] :koe/say nil}
    (let [{:keys [state reply ended?]} (turn-fn (:koe/dialog bridge) transcript)
          b (-> bridge
                (assoc :koe/dialog state)
                (update :koe/turns inc))]
      (cond
        ended? {:koe/bridge (assoc b :koe/state :ended) :koe/out [] :koe/say reply}
        (seq reply) {:koe/bridge (assoc b :koe/state :speaking) :koe/out [] :koe/say reply}
        :else {:koe/bridge (listening b) :koe/out [] :koe/say nil}))))

(defn audio-frames
  "Split rendered audio into carrier frames, plus the mark that says it ended.

  The mark is what returns the call to listening — see `on-frame`. Emitting the
  audio without it leaves the receptionist speaking forever."
  [bridge encoded-frames mark-name]
  (let [sid (:koe/stream-id bridge)]
    (conj (mapv #(media/outbound-audio sid %) encoded-frames)
          (media/outbound-mark sid mark-name))))

(defn greeting-due
  "The greeting to say, once, at the start of a call. nil afterwards."
  [bridge]
  (:koe/pending-greeting bridge))

(defn greeting-sent [bridge]
  (-> bridge (dissoc :koe/pending-greeting) (assoc :koe/state :speaking)))

(defn ended? [bridge] (= :ended (:koe/state bridge)))
