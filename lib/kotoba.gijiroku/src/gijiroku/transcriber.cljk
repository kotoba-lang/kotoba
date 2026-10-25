(ns gijiroku.transcriber
  "Transcriber — turns a captured audio file into gijiroku.model transcript
  segments. Only the bot-join Platform path (`gijiroku.bot-join`) needs this:
  the official Zoom/Meet/Teams API path gets a platform-native transcript and
  never calls it. Mirrors the Advisor/Platform injection discipline (mock
  default, a real STT swapped in — see `gijiroku.whisper`).

  Bot-captured audio is a single mixed track: unlike the platform-native
  transcripts the official API path returns (each segment attributed to a
  participant), a Transcriber over that audio produces :speaker nil (no
  diarization) unless a given impl adds one. This is a real capability gap
  of the bot-join path, not an oversight.")

(defprotocol Transcriber
  (-transcribe [t audio-path] "audio-path → gijiroku.model/transcript"))

(defn- demo-segments []
  [{:seg-id "s1" :speaker nil :t0 0 :t1 8 :text "(mock transcript segment 1)" :sensitive #{}}
   {:seg-id "s2" :speaker nil :t0 8 :t1 20 :text "(mock transcript segment 2)" :sensitive #{}}])

(defrecord MockTranscriber []
  Transcriber
  (-transcribe [_ audio-path]
    {:id (str "t-" (hash audio-path)) :meeting-id nil :source :stt-generated
     :lang "ja" :segments (demo-segments)}))

(defn mock-transcriber [] (->MockTranscriber))

(defn with-meeting-id
  "STT transcripts are produced independent of a meeting-id; stamp one on
  after the fact so the shape matches gijiroku.model/transcript."
  [transcript meeting-id]
  (assoc transcript :meeting-id meeting-id))
