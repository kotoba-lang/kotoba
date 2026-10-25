(ns kotoba.live.lint
  "Lint — validate a `:dance/*` scene before it silently falls back.

  `kotoba.live.scene/from-edn` is deliberately tolerant: an unknown
  `:stage`, a mistyped `:dance` preset, or an out-of-range intensity all
  resolve to a default rather than throw. That's right at runtime, but it
  hides authoring mistakes — `:stage :halll` just becomes `:hall`. This
  module re-reads the raw EDN and reports those silent corrections so an
  author (or an editor) can catch them.

  ```clojure
  (doseq [l (lint/lint-scene edn-str)]
    (println (:severity l) (:path l) \"—\" (:message l)))
  ```"
  (:require [kotoba.live.edn-util :as eu]
            [kotoba.live.mathx :as mathx]))

(def ^:private stages #{"club" "hall" "festival"})
(def ^:private expr-sources #{"cheer" "beat" "blink"})
(def ^:private waves #{"sine" "square" "triangle" "sawtooth"})
(def ^:private vowels #{"a" "i" "u" "e" "o" "aa" "ih" "ou" "ee" "oh"})
(def ^:private dances
  #{"idle" "four-on-floor" "wota" "kpop-point" "shuffle" "hold" "bounce" "sway"
    "spin" "headbang" "clap"})
(def ^:private cue-kinds #{"drop" "breakdown" "callout" "custom"})
(def ^:private trigger-on #{"drop" "breakdown" "callout" "custom" "beat" "bar" "phrase" "track"})
(def ^:private fixtures #{"front-par" "back-par" "spot" "blinder" "laser" "strobe"})
(def ^:private envelopes #{"hold" "breathe" "ramp" "pulse" "strobe"})
(def ^:private vj-patterns #{"solid" "stripes" "pulse" "rings" "scope" "noise"})
(def ^:private post-fx
  #{"bloom" "outline" "vignette" "crt" "color-grade" "pixelate" "ssao"
    "depth-of-field" "dof" "ssr" "aces-tonemap" "aces" "film-grain"
    "chromatic-aberration" "chromatic" "god-rays" "fxaa"})

(defn- warn [path msg] {:severity :warn :path path :message msg})
(defn- err [path msg] {:severity :error :path path :message msg})

(defn- enum-check [path v known what]
  (when-let [n (eu/ident v)]
    (when-not (contains? known n)
      [(warn path (str "unknown " what " `" n "` — falls back to a default; expected one of " known))])))

(defn- range-check [path v lo hi]
  (when (number? v)
    (when (or (< v lo) (> v hi))
      [(warn path (str "value " v " out of range [" lo ", " hi "] — clamped"))])))

(defn lint-scene
  "Validate a dance scene's EDN. Returns findings in scene order; an empty
  seq means the scene is clean (no silent corrections, no structural
  errors)."
  [src]
  (let [root (eu/root-map src)]
    (if (nil? root)
      [(err "<root>" "top-level form is not an EDN map")]
      (vec
       (concat
        ;; :dance/show
        (when-let [sm (:dance/show root)]
          (concat
           (enum-check "dance/show.stage" (:stage sm) stages "stage")
           (when-let [b (:bpm sm)]
             (when (and (number? b) (<= b 0))
               [(warn "dance/show.bpm" (str "bpm " b " must be > 0 — defaults to 128"))]))
           (range-check "dance/show.swing" (:swing sm) -0.5 0.5)))

        ;; :dance/setlist (+ collect cue tags)
        (let [tracks (:dance/setlist root)]
          (if (empty? tracks)
            [(warn "dance/setlist" "empty or missing setlist — the show has no tracks to play")]
            (mapcat
             (fn [[i tm]]
               (let [p (str "dance/setlist[" i "]")]
                 (concat
                  (enum-check (str p ".dance") (:dance tm) dances "dance preset")
                  (mapcat
                   (fn [[j cm]]
                     (let [cp (str p ".cues[" j "]")]
                       (concat
                        (enum-check (str cp ".kind") (:kind cm) cue-kinds "cue kind")
                        (when (and (number? (:beat cm)) (<= (:beat cm) 0))
                          [(warn (str cp ".beat")
                                 "cue at :beat 0 never fires (dispatch is open-closed (prev, beat]); use :beat >= 1")]))))
                   (map-indexed vector (:cues tm))))))
             (map-indexed vector tracks))))

        ;; :dance/lighting
        (mapcat
         (fn [[i cm]]
           (let [p (str "dance/lighting[" i "]")]
             (concat
              (enum-check (str p ".fixture") (:fixture cm) fixtures "fixture")
              (range-check (str p ".intensity") (:intensity cm) 0.0 1.0)
              (when-let [n (eu/ident (:envelope cm))]
                (when-not (contains? envelopes n)
                  [(warn (str p ".envelope") (str "unknown envelope `" n "` — defaults to :hold"))])))))
         (map-indexed vector (:dance/lighting root)))

        ;; :dance/vj
        (mapcat
         (fn [[i sm]]
           (let [p (str "dance/vj[" i "]")]
             (concat
              (enum-check (str p ".pattern") (:pattern sm) vj-patterns "pattern")
              (when-let [n (eu/ident (:palette sm))]
                (when-not (contains? #{"neon-pink" "cool-wave" "sunset" "monochrome"} n)
                  [(warn (str p ".palette") (str "unknown palette `" n "` — defaults to :cool-wave"))])))))
         (map-indexed vector (:dance/vj root)))

        ;; :dance/triggers (+ dangling-tag check)
        (let [cue-tags (into #{}
                              (mapcat (fn [tm] (keep :tag (:cues tm))))
                              (:dance/setlist root))]
          (mapcat
           (fn [[i tm]]
             (let [p (str "dance/triggers[" i "]")
                   n (eu/ident (:on tm))]
               (concat
                (cond
                  (nil? n) [(warn (str p ".on") "trigger missing `:on` — it will never fire")]
                  (not (contains? trigger-on n))
                  [(warn (str p ".on") (str "unknown trigger `:on " n "` — it will never fire; expected one of " trigger-on))]
                  :else [])
                (when-let [tag (:tag tm)]
                  (when-not (contains? cue-tags tag)
                    [(warn (str p ".tag")
                           (str "dangling `:tag \"" tag "\"` — no cue in the setlist carries it, so this trigger never fires"))])))))
           (map-indexed vector (:dance/triggers root))))

        ;; :dance/clips (+ collect names)
        (mapcat
         (fn [[i cm]]
           (concat
            (when-not (and (string? (:name cm)) (not-empty (:name cm)))
              [(warn (str "dance/clips[" i "].name") "clip has no `:name`")])
            (when (empty? (:tracks cm))
              [(warn (str "dance/clips[" i "].tracks") "clip has no `:tracks` — nothing to play")])))
         (map-indexed vector (:dance/clips root)))

        ;; :dance/post
        (mapcat
         (fn [[i em]]
           (let [n (or (eu/ident (:effect em)) (eu/ident (:fx em)))]
             (cond
               (nil? n) [(warn (str "dance/post[" i "].effect") "post effect missing `:effect`")]
               (not (contains? post-fx n))
               [(warn (str "dance/post[" i "].effect") (str "unknown post effect `" n "` — expected one of " post-fx))]
               :else [])))
         (map-indexed vector (:dance/post root)))

        ;; :dance/avatar (VRM)
        (when-let [av (:dance/avatar root)]
          (let [clip-names (into #{} (keep :name) (:dance/clips root))]
            (concat
             (when (empty? (:vrm av))
               [(warn "dance/avatar.vrm" "no `:vrm` model bound — the avatar won't load")])
             (when (and (number? (:scale av)) (<= (:scale av) 0))
               [(warn "dance/avatar.scale" "scale must be > 0")])
             (when-let [clip (eu/ident (:clip av))]
               (when-not (contains? clip-names clip)
                 [(warn "dance/avatar.clip" (str "references clip `" clip "` not defined in :dance/clips"))]))
             (mapcat
              (fn [[k v]]
                (let [nm (eu/ident k)
                      src (eu/ident (:from v))]
                  (when (and src (not (contains? expr-sources src)))
                    [(warn (str "dance/avatar.expressions." nm)
                           (str "unknown expression source `:from " src "` — defaults to :beat; expected one of " expr-sources))])))
              (:expressions av))
             (mapcat
              (fn [[i pm]]
                (let [vw (eu/ident (:vowel pm))]
                  (when (and vw (not (contains? vowels vw)))
                    [(warn (str "dance/avatar.voice.phonemes[" i "].vowel")
                           (str "unknown vowel `" vw "` — phoneme skipped; expected a/i/u/e/o"))])))
              (map-indexed vector (get-in av [:voice :phonemes]))))))

        ;; :dance/camera
        (when-let [cam (:dance/camera root)]
          (when-let [fv (:fov cam)]
            (when (and (number? fv) (or (<= fv 0) (> fv mathx/pi)))
              [(warn "dance/camera.fov" "fov must be in (0, π] radians — defaults to 0.9")])))

        ;; :dance/audio :bank
        (mapcat
         (fn [[k v]]
           (let [nm (eu/ident k) wave (:wave v)]
             (when (and (string? wave) (not (contains? waves wave)))
               [(warn (str "dance/audio.bank." nm ".wave")
                      (str "unknown wave `" wave "` — defaults to sine; expected one of " waves))])))
         (get-in root [:dance/audio :bank]))

        ;; :dance/live2d
        (when-let [l2 (:dance/live2d root)]
          (let [motion-names (into #{} (keep :name) (:motions l2))]
            (concat
             (when (empty? (:model l2))
               [(warn "dance/live2d.model" "no `:model` bound — the Live2D avatar won't load")])
             (when (and (number? (:scale l2)) (<= (:scale l2) 0))
               [(warn "dance/live2d.scale" "scale must be > 0")])
             (mapcat
              (fn [[i mm]]
                (let [has-file (seq (:file mm))
                      has-keys (seq (:keys mm))]
                  (when (and (not has-file) (not has-keys))
                    [(warn (str "dance/live2d.motions[" i "]")
                           "motion has neither `:file` nor inline `:keys` — nothing to play")])))
              (map-indexed vector (:motions l2)))
             (when-let [motion (eu/ident (:motion l2))]
               (when-not (contains? motion-names motion)
                 [(warn "dance/live2d.motion" (str "references motion `" motion "` not defined in :motions"))]))))))))))
