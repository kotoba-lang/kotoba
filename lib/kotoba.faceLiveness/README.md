# face-liveness

Challenge-response liveness detection for kotoba-lang. Issues a
blink/turn-left/turn-right/smile challenge and scores a sequence of tracked
face-landmark frames against it, using real, published, classical
computer-vision math (Eye Aspect Ratio, per Soukupová & Čech 2016) — not a
neural model, and not a bundled face-tracking implementation.

## What this is and is not

**Is**: a real, tested motion-detection algorithm over landmark points you
already have. Given a sequence of `{:frame/at t :frame/landmarks {...}}`
maps, it correctly detects a genuine blink/smile/head-turn transition
pattern (open→closed→open eye, closed→open mouth, centered→committed head
angle) versus noise or a static pose.

**Is not**: a face detector, a face tracker, or a camera integration. There
is no bundled `face-liveness.ports/ILandmarkTracker` implementation — that
needs a real face-landmark detection model, which this org has no vision-
workload precedent for today (`kotoba-lang/inference`'s stated ML stance is
torch+num, not ONNX/TF.js/WebNN, and torch+num is LLM-shaped only so far).
Wiring this up to a real camera requires supplying that piece yourself.

**Defends against**: a static printed photo, or a single still image
presented to a camera — there's no motion to satisfy a challenge.

**Does NOT defend against**: a pre-recorded video replay of the correct
challenge sequence, a 3D mask, or a deepfake/video-injection attack feeding
a virtual camera. Anyone representing this as production-grade anti-spoofing
without saying so is misrepresenting it.

## Usage

```clojure
(require '[face-liveness.core :as core]
         '[face-liveness.model :as model])

(def challenge (core/issue-challenge "session-1" :blink {:issued-at (System/currentTimeMillis)}))

;; ... your own ILandmarkTracker implementation feeds real camera frames
;; through face-liveness.model/frame as the subject responds ...

(core/score-response challenge frames (System/currentTimeMillis))
;;=> {:result/status :verified :result/confidence 1.0
;;    :result/evidence {...} :result/non-adjudicating true}
```

## Calibration risk

`face-liveness.geometry/yaw-proxy`'s sign convention (positive = nose
toward image-left) may not match your capture pipeline's left/right —
front-facing cameras are commonly mirrored. Verify this against your own
setup before trusting `:turn-left`/`:turn-right` results; see
`face-liveness.core`'s module doc.

See `MATURITY.md` and `90-docs/adr/*-kotoba-lang-face-liveness.edn` (in the
`com-junkawasaki/root` superproject) for the full design rationale.
