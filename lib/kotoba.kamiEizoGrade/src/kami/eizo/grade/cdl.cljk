(ns kami.eizo.grade.cdl
  "ASC CDL (Color Decision List) primary color correction: Slope/Offset/Power
   per channel, applied as `out = ((in * slope) + offset) ^ power`, plus a
   luma-preserving saturation adjustment. This is the same math underlying
   the \"Lift/Gamma/Gain\" 3-wheel model exposed by every grading tool
   (DaVinci Resolve, Baselight, etc.) — `slope` ~ gain, `offset` ~ lift,
   `power` ~ inverse gamma. We use the ASC CDL parameter names directly
   since that is the unambiguous, spec-defined form; UIs may relabel them.

   Luma uses Rec. 709 coefficients (0.2126 R + 0.7152 G + 0.0722 B) —
   chosen because it is the modern broadcast/streaming standard; Rec. 601
   would give slightly different (but equally valid) saturation results."
  (:require [kami.eizo.grade.mathutil :as m]))

(defn cdl
  "Build a CDL node. `slope`/`offset`/`power` are each [r g b] triples
   (defaulting to slope=1, offset=0, power=1, i.e. identity). `saturation`
   is a scalar multiplier on chroma distance from luma (1.0 = identity,
   0.0 = full desaturation, >1.0 = boosted saturation)."
  [{:keys [slope offset power saturation]
    :or {slope [1.0 1.0 1.0] offset [0.0 0.0 0.0] power [1.0 1.0 1.0] saturation 1.0}}]
  {:kami.eizo.grade/type :cdl
   :slope slope :offset offset :power power :saturation saturation})

(defn- clamp01 [x] (max 0.0 (min 1.0 (double x))))

(defn- signed-pow
  "x^p defined for x possibly negative or > range by preserving sign,
   since intermediate SOP values (before clamping) can leave [0,1]."
  [x p]
  (let [x (double x) p (double p)]
    (if (neg? x)
      (- (m/pow (- x) p))
      (m/pow x p))))

(defn apply-sop
  "Apply Slope/Offset/Power to a single channel value. No clamping —
   callers clamp at the end of the full pipeline (matches how real
   grading pipelines keep intermediate headroom)."
  [in slope offset power]
  (signed-pow (+ (* (double in) (double slope)) (double offset)) power))

(def ^:const rec709-luma [0.2126 0.7152 0.0722])

(defn luma [[r g b]]
  (let [[lr lg lb] rec709-luma]
    (+ (* r lr) (* g lg) (* b lb))))

(defn apply-saturation
  "Luma-preserving saturation: mixes [r g b] toward its own luma by
   `1 - saturation`, and away from it (chroma-boosted) for saturation > 1."
  [[r g b] saturation]
  (let [y (luma [r g b])
        s (double saturation)]
    [(+ y (* s (- r y)))
     (+ y (* s (- g y)))
     (+ y (* s (- b y)))]))

(defn apply-cdl
  "Apply a cdl node to an [r g b] triple (values conventionally in [0,1]
   but not required to be — headroom above 1.0 is preserved through SOP).
   Returns a clamped-to-[0,1] [r g b] triple, matching CDL's defined
   output range."
  [{:keys [slope offset power saturation]} [r g b]]
  (let [[sr sg sb] slope [or_ og ob] offset [pr pg pb] power
        sop [(apply-sop r sr or_ pr)
             (apply-sop g sg og pg)
             (apply-sop b sb ob pb)]
        [sr' sg' sb'] (apply-saturation sop saturation)]
    [(clamp01 sr') (clamp01 sg') (clamp01 sb')]))
