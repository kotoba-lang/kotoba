(ns loop-ka.evaluate
  "evaluate — read the producer's own report of what each leg actually did.

  This namespace deliberately does NOT score craft. The repository-rules
  `loop-*` contract forbids owning domain scoring truth, and there is a concrete
  reason here beyond compliance: quality already has homes (design-quality's
  fitness functions, the gen-quality ledger's ffprobe metrics). What has NO home
  is the question this loop must answer before publishing — *did the generative
  legs actually run, or did the pipeline degrade and produce something that
  merely plays?*

  That question is answerable from the producer's `:legs` map alone, which is
  why dougaka.pipeline emits one: per-shot :murakumo/:comfy/:placeholder for the
  image, :murakumo/:local/:silent for the voice, plus whether a bed and cues
  landed. Two weeks of flat-colour cards shipped nightly because nothing looked
  at it."
  (:require [kotoba.lang.text :as str]))

(def degraded-video #{:placeholder})
(def degraded-voice #{:silent})

(defn leg-counts
  "legs -> {:shots n :video {kind count} :voice {kind count} :bed? :cues n}."
  [{:keys [video voice bed sfx overlays]}]
  {:shots (count video)
   :video (frequencies video)
   :voice (frequencies voice)
   :bed? (boolean bed)
   :cues (count sfx)
   :overlays (or overlays 0)})

(defn degraded-shots
  "Indices of shots whose image fell back to a placeholder. These are the flat
  cards — the specific thing that shipped unnoticed."
  [{:keys [video]}]
  (vec (keep-indexed (fn [i k] (when (degraded-video k) i)) video)))

(defn silent-shots
  [{:keys [voice]}]
  (vec (keep-indexed (fn [i k] (when (degraded-voice k) i)) voice)))

(defn verdict
  "legs (+ thresholds) -> {:grade :reasons :counts}.

  :clean     every shot got a generated image and a voice; bed present
  :thin      nothing degraded, but the bed or cues are missing
  :degraded  at least one shot fell back — publishable only on an explicit
             override, because it is a flat card or dead air
  :empty     no shots at all (a producer that reported nothing)

  Thresholds are arguments, not constants: a channel that legitimately has no
  bed (a silent-format channel) passes `:require-bed? false` rather than being
  permanently graded :thin."
  [legs & [{:keys [require-bed? allow-degraded-shots]
            :or {require-bed? true allow-degraded-shots 0}}]]
  (let [counts (leg-counts legs)
        bad (degraded-shots legs)
        mute (silent-shots legs)
        reasons (cond-> []
                  (seq bad) (conj {:reason :placeholder-images :shots bad})
                  (seq mute) (conj {:reason :silent-narration :shots mute})
                  (and require-bed? (not (:bed? counts))) (conj {:reason :no-music-bed}))]
    {:counts counts
     :reasons reasons
     :grade (cond
              (zero? (:shots counts)) :empty
              (> (count bad) (long allow-degraded-shots)) :degraded
              (seq mute) :degraded
              (seq reasons) :thin
              :else :clean)}))

(defn explain
  "A verdict -> one human line. The app and the CLI show the same sentence, so
  an operator reading the panel and an operator reading the log agree."
  [{:keys [grade counts reasons]}]
  (str (str/upper (name grade))
       "  shots=" (:shots counts)
       " bed=" (if (:bed? counts) "yes" "no")
       " cues=" (:cues counts)
       (when (seq reasons)
         (str "  [" (str/join "; " (map (fn [{:keys [reason shots]}]
                                          (str (name reason)
                                               (when (seq shots) (str " " (vec shots)))))
                                        reasons))
              "]"))))
