(ns koe.media
  "The audio side of a live call: the carrier's frames, and knowing when the
  caller has finished a sentence.

  A media stream is not a recording. It arrives as a continuous run of 20 ms
  frames whether or not anybody is talking, and nothing in it says 'that was an
  utterance'. Deciding where one ends is this namespace's job, and it is the
  decision the whole turn hangs on: end it too early and the receptionist
  answers half a sentence; too late and it sits there while the caller waits.

  ## Pure, because it has to be testable without a telephone

  Frames in, frames out, and a segmenter that is a fold over frames. The
  WebSocket, the file handling and the HTTP call to the speech engine are the
  host's. Everything here can be driven from a vector of frames in a test, which
  is the only way any of it gets exercised before a carrier account exists.

  ## μ-law, kept as μ-law

  The carrier sends 8 kHz μ-law and takes 8 kHz μ-law back. A host that renders
  its lines ahead of time in that same format never converts audio on the call. Audio coming in is decoded to linear only to measure
  loudness — the bytes handed to the speech engine are the original ones."
  (:require [kotoba.lang.text :as str]))

(def frame-ms 20)
(def sample-rate 8000)
(def samples-per-frame (/ (* sample-rate frame-ms) 1000))   ; 160

;; ── μ-law ────────────────────────────────────────────────────────────────────

(defn ulaw->linear
  "One μ-law byte → a signed 16-bit sample (ITU-T G.711).

  Used only to measure loudness. The bytes that reach the speech engine are the
  ones the carrier sent."
  [b]
  ;; BIAS is 0x84 (132), not 128. The first version here used 128, which is the
  ;; shape the formula seems to want and is wrong by about 1.6% at full scale.
  ;; It would never have been noticed through an energy threshold — which is
  ;; exactly why it is worth getting right rather than approximately right.
  (let [bias 132
        u (bit-and (bit-not (bit-and b 0xFF)) 0xFF)
        sign (bit-and u 0x80)
        exponent (bit-and (bit-shift-right u 4) 0x07)
        mantissa (bit-and u 0x0F)
        magnitude (- (bit-shift-left (+ (bit-shift-left mantissa 3) bias) exponent) bias)]
    (if (zero? sign) magnitude (- magnitude))))

(defn frame-energy
  "Mean absolute amplitude of a frame, 0–32767.

  Mean rather than peak: a single click should not read as speech, and a quiet
  steady voice should not read as silence."
  [bytes]
  (if (zero? (count bytes))
    0
    (long (/ (reduce + 0 (map #(Math/abs (long (ulaw->linear %))) bytes))
             (count bytes)))))

;; ── the carrier's frames ─────────────────────────────────────────────────────

(defn parse-frame
  "One decoded media message → what it means here.

  `decoded` is the JSON the host already parsed, so this namespace never picks a
  JSON library. Unknown events are `:unknown` rather than dropped — a carrier
  adding an event should be visible, not silently ignored."
  [decoded]
  (let [event (get decoded "event")]
    (case event
      "connected" {:media/event :connected}
      "start" {:media/event :start
               :media/stream-id (get-in decoded ["start" "streamSid"])
               :media/call-id (get-in decoded ["start" "callSid"])}
      "media" {:media/event :audio
               :media/payload (get-in decoded ["media" "payload"])
               :media/timestamp-ms (some-> (get-in decoded ["media" "timestamp"]) str
                                           (#(try (#?(:clj Long/parseLong :cljs js/parseInt) %)
                                                  (catch #?(:clj Exception :cljs :default) _ nil))))}
      "stop" {:media/event :stop}
      "mark" {:media/event :mark :media/name (get-in decoded ["mark" "name"])}
      {:media/event :unknown :media/raw event})))

(defn outbound-audio
  "A frame of our audio, addressed to this stream. `payload` is base64 μ-law,
  the carrier's own encoding, so nothing is converted here."
  [stream-id payload]
  {"event" "media" "streamSid" stream-id "media" {"payload" payload}})

(defn outbound-mark
  "A marker the carrier echoes back when our audio has finished playing.

  This is how the receptionist knows it has stopped talking. Without it, the
  moment to start listening again has to be guessed from the length of the audio,
  which is wrong whenever the network is."
  [stream-id name]
  {"event" "mark" "streamSid" stream-id "mark" {"name" name}})

(defn clear-audio
  "Discard audio we queued but have not played. Sent on barge-in: when the caller
  starts talking over the receptionist, the receptionist stops."
  [stream-id]
  {"event" "clear" "streamSid" stream-id})

;; ── where an utterance ends ──────────────────────────────────────────────────

(def default-vad
  "Thresholds, as data, so they can be tuned against a real line rather than
  edited in code.

  `:silence-ms` is the pause that ends a sentence. 700 ms is a compromise
  measured against nothing yet: long enough to survive the gap inside 「えーと、
  四人です」, short enough not to feel dead. **This number is a guess and is
  labelled as one** — the first real call is what sets it."
  {:media.vad/speech-energy 500      ; mean |amplitude| that counts as talking
   :media.vad/silence-ms 700         ; pause that ends an utterance
   :media.vad/min-speech-ms 200      ; shorter than this is a click, not a word
   :media.vad/max-utterance-ms 15000}) ; a hard stop, so one turn cannot run forever

(defn segmenter
  "Initial state for the fold below."
  ([] (segmenter default-vad))
  ([vad] {:media/vad (merge default-vad vad)
          :media/speech? false
          :media/speech-ms 0
          :media/silence-ms 0
          :media/frames []}))

(defn absorb-frame
  "Fold one audio frame in. Returns the state, with `:media/utterance` set to the
  collected frames on the frame that ends one.

  Silence before speech is discarded rather than accumulated: otherwise every
  utterance carries however long the caller took to start, and the speech engine
  spends its fixed window on nothing."
  [state frame-bytes]
  (let [{:media.vad/keys [speech-energy silence-ms min-speech-ms max-utterance-ms]}
        (:media/vad state)
        loud? (>= (frame-energy frame-bytes) speech-energy)
        st (-> state
               (dissoc :media/utterance)
               (update :media/speech-ms #(if loud? (+ % frame-ms) %))
               (update :media/silence-ms #(if loud? 0 (+ % frame-ms))))
        st (cond-> st
             loud? (assoc :media/speech? true)
             (or loud? (:media/speech? st)) (update :media/frames conj frame-bytes))
        talked (:media/speech-ms st)
        quiet (:media/silence-ms st)
        elapsed (* frame-ms (count (:media/frames st)))]
    (cond
      ;; A pause after real speech ends the utterance.
      (and (:media/speech? st) (>= quiet silence-ms) (>= talked min-speech-ms))
      (assoc (segmenter (:media/vad st)) :media/utterance (:media/frames st))

      ;; A pause after nothing but clicks: forget it and keep listening.
      (and (:media/speech? st) (>= quiet silence-ms))
      (segmenter (:media/vad st))

      ;; Nobody can hold the line forever.
      (>= elapsed max-utterance-ms)
      (assoc (segmenter (:media/vad st)) :media/utterance (:media/frames st))

      :else st)))

(defn barge-in?
  "Whether the caller has started talking while we are still speaking.

  One loud frame is not enough — a cough would cut the receptionist off
  mid-sentence. `min-speech-ms` of it is."
  [state]
  (and (:media/speech? state)
       (>= (:media/speech-ms state)
           (get-in state [:media/vad :media.vad/min-speech-ms]))))

;; ── what the engine is handed ────────────────────────────────────────────────

(defn utterance-ms [frames] (* frame-ms (count frames)))

(defn- ascii
  "The code points of an ASCII string.

  Not `(map int s)`. On the JVM a character is a `Character` and `int` of one
  is its code point; under ClojureScript there is no character type, `(seq
  s)` yields one-character STRINGS, and `int` of a string is 0. So `(map int
  \"RIFF\")` is `[82 73 70 70]` here and `[0 0 0 0]` there — a WAV header
  whose magic is four zero bytes, which is exactly the failure `wav-header`'s
  docstring warns about: not an error, a transcript of noise."
  [s]
  #?(:clj (mapv #(bit-and (int %) 0xFF) (.getBytes ^String s "US-ASCII"))
     :cljs (mapv #(.charCodeAt s %) (range (count s)))))

(defn wav-header
  "A 44-byte μ-law WAV header for `n` bytes of payload.

  The speech engine takes a file, and the carrier sends a bare byte stream, so
  somebody has to write the header. Doing it here keeps the host's job to
  'write these bytes' — and lets the header be tested, which matters because a
  wrong one produces not an error but a transcript of noise."
  [n]
  (let [le (fn [v width] (mapv #(bit-and (bit-shift-right v (* 8 %)) 0xFF) (range width)))]
    (vec (concat (ascii "RIFF") (le (+ 38 n) 4)
                 (ascii "WAVEfmt ") (le 18 4)
                 (le 7 2)                       ; format 7 = μ-law
                 (le 1 2)                       ; mono
                 (le sample-rate 4)
                 (le sample-rate 4)             ; byte rate = 8000 * 1 * 1
                 (le 1 2) (le 8 2) (le 0 2)     ; block align, bits, cbSize
                 (ascii "data") (le n 4)))))
