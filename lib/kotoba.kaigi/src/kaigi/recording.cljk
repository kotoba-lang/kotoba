(ns kaigi.recording
  "Recording: what to capture, where it goes, and what is handed to
  `kotoba-lang/gijiroku` afterwards. Pure decisions only.

  ## Consent is not consulted here — it is the gate above here

  `kaigi.model/start-recording` already refuses unless every admitted
  participant has explicitly consented, and `revoke-recording-consent` turns an
  in-progress recording off the moment unanimity breaks. This namespace
  therefore asks one question — `capturing?` — and derives it from the meeting
  value rather than from a flag of its own.

  That is the whole reason revocation works. If a browser kept its own
  \"am I recording\" boolean, withdrawing consent would change the model and
  leave every recorder running; the model would say off while the microphones
  stayed on. Making the client's behaviour a function of the shared value means
  the stop is a consequence of the state, not a message somebody has to
  remember to send.

  ## Media never enters the meeting value

  Objects live in storage; the meeting carries an `:asset-ref` and nothing
  else. `handoff` — the record `gijiroku` consumes — carries the same reference
  plus the consent evidence, and `handoff-problems` refuses to build one that
  could be mistaken for a recording nobody agreed to. This is `gijiroku`'s
  charter G4 (raw audio/video never enters the store) and G3 (consent is a
  ground fact, never inferred) applied at the producing end."
  (:require [kotoba.lang.text :as str]
            [kaigi.model :as m]))

(def container
  "The recording container. WebM because `MediaRecorder` produces it
  everywhere the console runs; the value is stated once so the object key, the
  manifest and the handoff cannot disagree about what was written."
  {:mime "video/webm" :extension "webm"})

(defn capturing?
  "Whether `participant-id` should have a recorder running right now.

  Every condition comes from the meeting value: recording armed, the meeting
  live, and this participant admitted and actually in the media room. A
  participant who is admitted but has not joined has nothing to capture, and a
  participant whose consent withdrawal turned recording off stops because this
  returns false — not because anyone told them to."
  [mtg participant-id]
  (boolean (and (m/recording-on? mtg)
                (m/live? mtg)
                (m/admitted? mtg participant-id)
                (m/in-room? mtg participant-id))))

(def ^:private seq-width
  "Digits in the zero-padded sequence number. Six allows ~11 hours at one part
  per second — far past any meeting, and the point is that the width never has
  to change, because changing it would reorder every key already written."
  6)

(defn- zero-pad
  "Left-pad `n` to `seq-width` digits.

  Written out rather than using `.padStart`, which exists only in JavaScript:
  the JVM run of this suite failed with `No matching method padStart` while the
  nbb run was fully green. `format` would work on the JVM and not under
  ClojureScript; this works on both."
  [n]
  (let [s (str n)
        pad (- seq-width (count s))]
    (if (pos? pad) (str (apply str (repeat pad "0")) s) s)))

(defn object-key
  "Where one part of one participant's recording is stored.

  `meeting/participant/seq` with the sequence zero-padded, so a listing sorts
  in capture order. Lexical order matters: object stores list lexically, and
  `part-10` sorting before `part-2` is how a stitched recording ends up
  scrambled with nothing reporting an error."
  [meeting-id participant-id seq]
  (str "kaigi/" meeting-id "/" participant-id "/"
       (zero-pad seq) "." (:extension container)))

(defn parse-object-key
  "Inverse of `object-key`, or nil. Used to rebuild a manifest from a listing
  when local bookkeeping is gone (a reconnect, a new host)."
  [k]
  (let [parts (str/split (str k) #"/")]
    (when (and (= 4 (count parts)) (= "kaigi" (first parts)))
      (let [[_ meeting participant file] parts
            n (first (str/split file #"\."))]
        (when (re-matches #"^\d{6}$" n)
          {:kaigi.recording/meeting-id meeting
           :kaigi.recording/participant-id participant
           :kaigi.recording/seq #?(:clj (Long/parseLong n) :cljs (js/parseInt n 10))})))))

(defn manifest
  "What an `:asset-ref` points at: the parts, grouped by participant.

  A meeting recorded in a mesh has one stream per participant and no composite
  — there is nothing that mixed them, so claiming a single file would be a
  lie. The manifest says so explicitly and lists what actually exists.

  `parts` is a seq of object keys."
  [mtg parts]
  (let [parsed (keep parse-object-key parts)]
    {:kaigi.recording/meeting-id (:kaigi/id mtg)
     :kaigi.recording/container (:mime container)
     :kaigi.recording/composited? false
     :kaigi.recording/participants
     (into {}
           (map (fn [[pid ps]]
                  [pid (mapv #(object-key (:kaigi.recording/meeting-id %)
                                          (:kaigi.recording/participant-id %)
                                          (:kaigi.recording/seq %))
                             (sort-by :kaigi.recording/seq ps))]))
           (group-by :kaigi.recording/participant-id parsed))}))

(defn asset-ref
  "The reference stored on the meeting. A prefix, not a URL: a signed URL
  expires and a bucket name is deployment configuration, and neither belongs in
  a value that outlives both."
  [meeting-id]
  (str "kaigi/" meeting-id "/"))

;; ---------------------------------------------------------------------------
;; gijiroku handoff
;; ---------------------------------------------------------------------------

(defn handoff-problems
  "Why `mtg` cannot be handed to gijiroku, as a vector of problem maps.

  `:handoff/no-asset-ref`   — nothing was captured, so there is nothing to
                              transcribe
  `:handoff/not-ended`      — a meeting still running has more to record
  `:handoff/consent-missing` — an admitted participant never consented

  The consent check is re-run HERE rather than trusted from the fact that a
  recording exists. `gijiroku`'s G3 says consent is a ground fact and never
  inferred; \"there is a file, so they must have agreed\" is exactly the
  inference it forbids."
  [mtg]
  (cond-> []
    (str/blank? (str (get-in mtg [:kaigi/recording :kaigi.recording/asset-ref])))
    (conj {:kaigi.recording/code :handoff/no-asset-ref
           :kaigi.recording/message "no recording was captured"})

    (not (m/ended? mtg))
    (conj {:kaigi.recording/code :handoff/not-ended
           :kaigi.recording/message "the meeting is still in progress"})

    (seq (m/missing-recording-consents mtg))
    (conj {:kaigi.recording/code :handoff/consent-missing
           :kaigi.recording/message
           (str "these admitted participants never consented: "
                (str/join ", " (sort (m/missing-recording-consents mtg))))})))

(defn handoff
  "The record `gijiroku` consumes, or nil when `handoff-problems` is non-empty.

  Carries the asset reference, who was present, and the consent set — never
  media, and never a transcript. gijiroku drafts minutes from this; it does not
  receive, and cannot be given, audio through this record."
  [mtg]
  (when (empty? (handoff-problems mtg))
    (let [rec (:kaigi/recording mtg)]
      {:gijiroku/source :kaigi
       :gijiroku/meeting-id (:kaigi/id mtg)
       :gijiroku/title (:kaigi/title mtg)
       :gijiroku/channel (:kaigi/channel mtg)
       :gijiroku/asset-ref (:kaigi.recording/asset-ref rec)
       :gijiroku/container (:mime container)
       ;; Sorted so two handoffs for the same meeting are equal values —
       ;; a set's seq order is not stable, and an unstable record defeats
       ;; deduplication on the consuming side.
       :gijiroku/participants (vec (sort (m/admitted-ids mtg)))
       :gijiroku/consents (vec (sort (:kaigi.recording/consents rec)))
       :gijiroku/host (:kaigi/host mtg)})))
