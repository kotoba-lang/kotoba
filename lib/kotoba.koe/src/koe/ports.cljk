(ns koe.ports
  "Host-injected ports for a voice session. koe-clj defines the protocols; the host
  (an actor like denwaban) supplies concrete implementations backed by real actors
  (twilio-compat / whisper-compat / kotoba-llm / elevenlabs-compat / yotei).

  No SDK, model, or credential lives in this library — only the shapes a voice agent
  is built from. Portable .cljc (JVM + WASM hosts).")

(defprotocol ITelephony
  "Inbound/outbound voice channel (PSTN/SIP or WebRTC soft-phone)."
  (answer  [this call]   "Accept an inbound call; return a session handle.")
  (say     [this session audio] "Play synthesized audio back over the channel.")
  (hangup  [this session] "End the call."))

(defprotocol ISTT
  "Speech-to-text. `stream` yields partial transcripts for barge-in."
  (transcribe [this audio]        "Non-streaming: audio → final text.")
  (stream     [this audio-chan]   "Streaming: chunks → seq of partial/final transcripts."))

(defprotocol IDialog
  "Dialog policy: one utterance → a reply plus an optional action (e.g. :book)."
  (step [this state utterance] "Return {:reply text :action act|nil :state state'}."))

(defprotocol ITTS
  "Text-to-speech."
  (synth [this text opts] "text → audio for ITelephony/say."))

(defprotocol IBooking
  "Booking delegation. `confirm` MUST be member-signed by the downstream actor
  (yotei); a koe-clj host never confirms a booking server-side."
  (propose [this slot]   "Hold a tentative slot (no-double-book enforced downstream).")
  (confirm [this proposal signature] "Member-signed confirm; returns the booking."))
