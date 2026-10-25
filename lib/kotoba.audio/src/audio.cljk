(ns audio
  "KAMI Audio — spatial audio mixer core. Restored from kami-engine's
  `kami-audio` Rust crate (`src/lib.rs`, deleted PR #82 \"Remove Rust
  workspace from kami-engine\") to zero-dep portable CLJC as part of the
  clj-wgsl migration (ADR-2607010930, com-junkawasaki/root).

  Owns `AudioSource` / `Listener` / `AudioMixer` — 3D positional audio
  sources, distance attenuation (rolloff), a simplified stereo pan
  (dot product against the listener's right vector), a per-channel /
  master volume mix, and priority-based voice limiting.

  Ledger class `:port-to-WGSL-compute` (\"mixer loop + voice alloc + SR
  buffer mgmt; emit :native stays for real-time latency\"). Per owner
  decision this is restored as a plain interim CLJC port of the pure
  mixer/voice-allocation math — not actual WGSL compute code, and not
  a real-time audio-hardware callback (the original had none in this
  file; `AudioMixer::spatialize`/`active_voices` are pure functions
  over plain data, with no device/callback code to exclude).

  Sub-namespaces `audio.binaural` (ITD/ILD spherical-head spatialization,
  restored from `binaural.rs`) and `audio.wav` (PCM16 WAV encoding,
  restored from `wav.rs`) mirror the original `pub mod` declarations.")

;; ---------------------------------------------------------------------
;; Enums (Rust `enum` -> CLJC keyword, with a `*-values` set documenting
;; the valid values and, where order matters, an index map).
;; ---------------------------------------------------------------------

(def rolloff-values
  "Valid values for `:rolloff` on an `AudioSource`."
  #{:linear :inverse :exponential})

(def channel-values
  "Valid values for `:channel` on an `AudioSource`, in original Rust enum
  discriminant order (0..4) — matters because `:channel-volumes` on the
  mixer is a 5-element vector indexed by this order (mirrors
  `source.channel as usize` in the original `spatialize`)."
  [:master :music :sfx :voice :ambient :ui])

(def channel->index
  "`:channel` keyword -> index into `AudioMixer`'s `:channel-volumes`."
  (into {} (map-indexed (fn [i c] [c i]) channel-values)))

;; ---------------------------------------------------------------------
;; Data constructors (Rust `struct` -> plain CLJC map with defaults).
;; ---------------------------------------------------------------------

(defn audio-source
  "A source in 3D space. `opts` may override any default:
  `:id 0 :position [0 0 0] :volume 1.0 :pitch 1.0 :looping false
  :max-distance 100.0 :rolloff :linear :priority 0 :channel :sfx`."
  ([] (audio-source {}))
  ([opts]
   (merge {:id 0
           :position [0.0 0.0 0.0]
           :volume 1.0
           :pitch 1.0
           :looping false
           :max-distance 100.0
           :rolloff :linear
           :priority 0
           :channel :sfx}
          opts)))

(defn listener
  "Listener (camera/player ears). Default: at the origin, facing -Z,
  up +Y (matches Rust `Listener::default`)."
  ([] (listener {}))
  ([opts]
   (merge {:position [0.0 0.0 0.0]
           :forward [0.0 0.0 -1.0]
           :up [0.0 1.0 0.0]}
          opts)))

(defn audio-mixer
  "A fresh mixer: default listener, no sources, unity channel volumes,
  0.8 master volume, 32 max voices (matches Rust `AudioMixer::new`)."
  ([] (audio-mixer {}))
  ([opts]
   (merge {:listener (listener)
           :sources []
           :channel-volumes (vec (repeat (count channel-values) 1.0))
           :master-volume 0.8
           :max-voices 32}
          opts)))

;; ---------------------------------------------------------------------
;; Vec3 math (Rust `glam::Vec3` -> plain `[x y z]` + local helpers).
;; ---------------------------------------------------------------------

(defn- v-sub [[ax ay az] [bx by bz]] [(- ax bx) (- ay by) (- az bz)])
(defn- v-length [[x y z]] (Math/sqrt (+ (* x x) (* y y) (* z z))))
(defn- v-scale [[x y z] s] [(* x s) (* y s) (* z s)])
(defn- v-cross [[ax ay az] [bx by bz]]
  [(- (* ay bz) (* az by)) (- (* az bx) (* ax bz)) (- (* ax by) (* ay bx))])
(defn- v-dot [[ax ay az] [bx by bz]] (+ (* ax bx) (* ay by) (* az bz)))
(defn- v-normalize [v]
  (let [l (v-length v)]
    (if (zero? l) [0.0 0.0 0.0] (v-scale v (/ 1.0 l)))))
(defn- clamp [x lo hi] (max lo (min hi x)))

;; ---------------------------------------------------------------------
;; Mixer logic.
;; ---------------------------------------------------------------------

(defn spatialize
  "Stereo `[left right pan]` for `source` against `mixer`'s listener.
  `pan` is -1 (hard left) .. +1 (hard right). Beyond `:max-distance`
  the source is silent (`[0.0 0.0 0.0]`). Distance attenuation follows
  `:rolloff` (`:linear` / `:inverse` / `:exponential`); stereo panning
  is a simplified HRTF (dot product of the source direction with the
  listener's right vector, `forward x up`)."
  [mixer source]
  (let [lst (:listener mixer)
        diff (v-sub (:position source) (:position lst))
        dist (v-length diff)
        max-dist (:max-distance source)]
    (if (> dist max-dist)
      [0.0 0.0 0.0]
      (let [attenuation (case (:rolloff source)
                           :linear (- 1.0 (min 1.0 (/ dist max-dist)))
                           :inverse (/ 1.0 (+ 1.0 dist))
                           :exponential (Math/exp (- (* dist 0.1))))
            right (v-normalize (v-cross (:forward lst) (:up lst)))
            dir (if (> dist 0.001) (v-scale diff (/ 1.0 dist)) [0.0 0.0 0.0])
            pan (clamp (v-dot dir right) -1.0 1.0)
            vol (* (:volume source)
                   attenuation
                   (:master-volume mixer)
                   (nth (:channel-volumes mixer) (channel->index (:channel source))))
            left (* vol (- 1.0 (max 0.0 pan)))
            right-vol (* vol (+ 1.0 (min 0.0 pan)))]
        [left right-vol pan]))))

(defn active-voices
  "Indices into `(:sources mixer)` sorted by descending `:priority`,
  truncated to `:max-voices` (voice limiting)."
  [mixer]
  (let [sources (:sources mixer)
        indices (range (count sources))
        sorted (sort-by #(- (:priority (nth sources %))) indices)]
    (vec (take (:max-voices mixer) sorted))))
