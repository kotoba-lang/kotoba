(ns whisper.engine
  "Binding a real speech engine to the clean-room surface.

  `whisper.main` was written for this: it says in its own docstring that the
  in-memory store exists 'before a live engine binds', and `solve` raises. This
  namespace is the binding. What it adds is an engine boundary, the audio
  conversion a telephone call needs, and one invariant that matters more than
  either.

  ## Silence and failure are not the same answer

  A telephone dialog reads an empty transcript as **the caller said nothing** —
  and acts on it, by asking again or by ending the call. So an engine that is not
  installed, a model file that is missing, a conversion that failed and a caller
  who actually stayed quiet must not produce the same value. Every failure path
  here returns `{:whisper/failed <reason>}` and **never** a transcript, empty or
  otherwise. `transcript` returns nil for anything that failed, so a caller that
  forgets to check gets nil rather than a plausible empty string.

  This is the single most likely way this component would have been wrong, and it
  is the kind of wrong that is invisible: the receptionist would have behaved
  exactly as though the room were quiet.

  ## The engine is injected

  Nothing here shells out on its own. `run` is supplied by the host — a process
  call on a fleet node, a fixture in a test — so the parsing, the shaping and the
  invariant above are all testable without an engine present, and the engine is
  replaceable without touching them.

  ## Telephone audio is not the audio whisper wants

  A carrier delivers 8 kHz μ-law mono. Whisper wants 16 kHz signed PCM. The
  conversion is lossy in the direction that matters — the 8 kHz original threw
  away everything above 4 kHz and no upsampling returns it — so **accuracy must
  be measured on converted telephone audio, never on the studio-quality file the
  same sentence produces**. `telephony-conversion` names the conversion so a
  measurement can say which one it ran."
  (:require [kotoba.lang.text :as str]))

(def telephony-format
  "What the carrier delivers, and what whisper needs. Kept as data so a
  measurement can report the path it actually measured rather than the path
  somebody assumed."
  {:carrier {:codec :ulaw :sample-rate 8000 :channels 1}
   :engine  {:codec :pcm-s16le :sample-rate 16000 :channels 1}})

(defn telephony-conversion
  "The argument vector for converting a carrier recording into engine input.

  macOS `afconvert` on the fleet. Named and returned rather than executed: the
  host runs it, and a test can assert the conversion asked for without a file."
  [in-path out-path]
  ["afconvert" "-f" "WAVE" "-d" "LEI16@16000" "-c" "1" in-path out-path])

(defn command
  "The argument vector for one transcription.

  `--language ja` is passed explicitly rather than left to auto-detection: on a
  short utterance ('はい') detection is unreliable, and a misdetected language
  produces confident nonsense rather than an error. A restaurant's line knows
  what language it answers in — that is the `:locale` the session already
  carries."
  [{:keys [binary model audio language beam-size threads]
    :or {binary "whisper-cli" beam-size 5 threads 4}}]
  (concat [binary "-m" model "-f" audio
           "-l" (or language "ja")
           "-bs" (str beam-size) "-t" (str threads)
           ;; No timestamps and no progress: the caller wants the sentence.
           "-nt" "-np"]))

(defn- clean [s]
  (-> (str s)
      (str/replace #"\[[^\]]*\]" "")         ; [BLANK_AUDIO], [Music] and friends
      (str/replace #"\s+" " ")
      str/trim))

(def silence-markers
  "What whisper.cpp emits when it heard nothing. Silence has to be *stated* by
  the engine; it is never inferred from the absence of output."
  [#"\[BLANK_AUDIO\]" #"\[SILENCE\]" #"\(無音\)"])

(defn- states-silence? [out]
  (boolean (some #(re-find % (str out)) silence-markers)))

(defn parse
  "Engine stdout → a transcript, a stated silence, or a failure.

  **Empty output is a failure, not silence.** That distinction was measured, not
  reasoned: on 2026-08-15 a half-downloaded model made `whisper-cli` crash with a
  stack trace on stderr and **exit 0**, printing nothing to stdout. An earlier
  version of this function called that silence, which in a telephone dialog means
  'the caller said nothing' — eight test utterances in a row came back as eight
  quiet callers, and the crash was invisible.

  So silence must be *stated* by the engine (`[BLANK_AUDIO]`), and stdout that is
  simply empty is `:engine-produced-no-transcript`. The stderr is carried in the
  detail rather than discarded, because that is where the reason was the whole
  time."
  [{:keys [exit out err]}]
  (cond
    (not (zero? (or exit 0)))
    {:whisper/failed :engine-exit-nonzero :whisper/detail (str/trim (str err))}

    (nil? out)
    {:whisper/failed :engine-produced-no-output :whisper/detail (str/trim (str err))}

    :else
    (let [text (clean out)]
      (cond
        (seq text) {:whisper/text text}
        (states-silence? out) {:whisper/silence true}
        :else {:whisper/failed :engine-produced-no-transcript
               :whisper/detail (str/trim (str err))}))))

(defn transcribe-file
  "Run the engine over one audio file. Returns a transcript, a silence, or a
  failure — never a transcript that was not produced.

  `run` is `(fn [argv] -> {:exit :out :err})`. Anything it throws is caught and
  reported as a failure, because a receptionist that crashes mid-call is worse
  than one that says it could not hear."
  [{:keys [run] :as opts}]
  (cond
    (not (fn? run))
    {:whisper/failed :no-engine-runner}

    (str/blank? (str (:model opts)))
    {:whisper/failed :no-model}

    (str/blank? (str (:audio opts)))
    {:whisper/failed :no-audio}

    :else
    (try
      (parse (run (vec (command opts))))
      (catch #?(:clj Exception :cljs :default) e
        {:whisper/failed :engine-threw
         :whisper/detail #?(:clj (.getMessage ^Exception e) :cljs (str e))}))))

(defn transcript
  "The words, or nil.

  nil for a failure AND nil for silence, because neither is something the caller
  said. A caller that needs to tell them apart reads the result map; a caller
  that just wants the sentence cannot accidentally receive an empty string that
  means 'the engine is not installed'."
  [result]
  (when (and (map? result) (not (:whisper/failed result)) (not (:whisper/silence result)))
    (:whisper/text result)))

(defn heard?
  "Whether this result is something a dialog may act on."
  [result]
  (some? (transcript result)))
