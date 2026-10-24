(ns hinshitsu.mokushi
  "mokushi (黙視 — to watch in silence) — visual/snapshot testing on top of
  hinshitsu.core's evidence shape. Capture a screen/render to a PNG, diff it
  against a committed baseline, and return pass/fail evidence.

  Capture and diff are both delegated to system binaries (a caller-supplied
  capture command — `xcrun simctl io <udid> screenshot`, `adb exec-out
  screencap`, a headless-browser CLI, whatever fits the target — and
  ImageMagick's `compare` for the actual pixel diff) rather than hinshitsu
  linking an image-processing library itself. This keeps the namespace
  portable .cljc data/orchestration; only `capture!` and `compare!` touch a
  process, and only on :clj/:bb hosts (mirrors the etzhayyim/root convention:
  shelling out to an installed system binary is not 'a shell script').

  No baseline exists yet for a given check the first time it runs — `check!`
  treats a missing baseline as :skipped with instructions to record one via
  `save-baseline!`, not as a failure."
  (:require [hinshitsu.core :as h]
            #?(:clj [clojure.java.io :as io])
            #?(:clj [clojure.java.shell :as sh])))

#?(:clj
   (defn capture!
     "Run `capture-command` (a vector, e.g.
     [\"xcrun\" \"simctl\" \"io\" udid \"screenshot\" out-path]) and return
     evidence. Data on success carries :out-path."
     [capture-command out-path]
     (let [{:keys [exit out err]} (apply sh/sh capture-command)]
       (if (zero? exit)
         (h/evidence :passed ["mokushi/capture"] (str "captured " out-path)
                     {:command capture-command :stdout out :stderr err
                      :data {:out-path out-path}})
         (h/evidence :failed ["mokushi/capture"] (str "capture command exited " exit)
                     {:command capture-command :stdout out :stderr err})))))

#?(:clj
   (defn compare!
     "Pixel-diff `candidate` against `baseline` via ImageMagick `compare
     -metric RMSE`, returning evidence whose :data carries the numeric RMSE
     distortion (0 = identical). Passes when distortion <= `threshold`
     (default 0.02, i.e. within 2% RMSE — tolerant of anti-aliasing /
     sub-pixel rendering noise across runs, not exact-byte comparison)."
     ([baseline candidate] (compare! baseline candidate {}))
     ([baseline candidate {:keys [threshold diff-path]
                            :or {threshold 0.02}}]
      (if-not (.exists (io/file baseline))
        (h/evidence :skipped ["mokushi/compare"]
                    (str "no baseline at " baseline "; run save-baseline! to record one"))
        (let [diff-path (or diff-path (str candidate ".diff.png"))
              {:keys [exit err]} (sh/sh "compare" "-metric" "RMSE" baseline candidate diff-path)
              ;; ImageMagick's `compare` writes the metric to stderr and exits
              ;; 1 when the images differ at all (even a tiny amount), so exit
              ;; code alone isn't pass/fail — the parsed distortion is. The
              ;; normalized distortion in parens is scientific notation
              ;; (e.g. "1.6277e-05") for near-identical images — exactly the
              ;; common should-pass case — so the pattern must allow e/E/sign,
              ;; not just digits and a dot.
              distortion (some-> (re-find #"\(([0-9.eE+-]+)\)" err) second parse-double)]
          (cond
            (= exit 2)
            (h/evidence :failed ["mokushi/compare"] (str "compare failed: " err)
                        {:command ["compare" "-metric" "RMSE" baseline candidate diff-path]
                         :stderr err})

            (nil? distortion)
            (h/evidence :failed ["mokushi/compare"] (str "could not parse RMSE from: " err)
                        {:stderr err})

            (<= distortion threshold)
            (h/evidence :passed ["mokushi/compare"]
                        (str "within threshold (" distortion " <= " threshold ")")
                        {:data {:distortion distortion :threshold threshold :diff-path diff-path}})

            :else
            (h/evidence :failed ["mokushi/compare"]
                        (str "distortion " distortion " exceeds threshold " threshold)
                        {:data {:distortion distortion :threshold threshold :diff-path diff-path}}))))))

   :cljs
   (defn compare! [_baseline _candidate & _opts]
     (h/evidence :skipped ["mokushi/compare"]
                 "hinshitsu.mokushi/compare! requires a :clj/:bb host (shells out to ImageMagick)")))

#?(:clj
   (defn check!
     "Capture + compare in one call: (check! capture-command baseline
     candidate-out-path opts?) -> a single gated evidence combining both
     steps via hinshitsu.core/gate."
     ([capture-command baseline candidate-out-path]
      (check! capture-command baseline candidate-out-path {}))
     ([capture-command baseline candidate-out-path opts]
      (let [cap (capture! capture-command candidate-out-path)]
        (if (h/failed? cap)
          cap
          (h/gate [cap (compare! baseline candidate-out-path opts)]))))))

#?(:clj
   (defn save-baseline!
     "Promote `candidate-path` to be the new baseline at `baseline-path`
     (creating parent dirs as needed). Call this deliberately when a visual
     change is intentional — mokushi never overwrites a baseline on its own."
     [candidate-path baseline-path]
     (io/make-parents baseline-path)
     (io/copy (io/file candidate-path) (io/file baseline-path))
     (h/evidence :passed ["mokushi/save-baseline"] (str "baseline updated: " baseline-path))))
