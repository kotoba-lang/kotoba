(ns comfyui.diffusion.scheduler
  "Real diffusion noise scheduling and deterministic DDIM stepping over
  num NDArrays. No model assumptions: a UNet/DiT supplies epsilon prediction;
  this namespace performs the mathematically defined latent transition."
  (:require [num.array :as arr]
            [num.tensor :as t]))

(defn linear-betas
  "Inclusive linear beta schedule with `steps` entries."
  [steps beta-start beta-end]
  (when-not (and (pos-int? steps) (< 0 beta-start beta-end 1))
    (throw (ex-info "invalid linear beta schedule"
                    {:steps steps :beta-start beta-start :beta-end beta-end})))
  (if (= steps 1)
    [(double beta-start)]
    (mapv (fn [i]
            (+ (double beta-start)
               (* (/ i (double (dec steps))) (- (double beta-end) beta-start))))
          (range steps))))

(defn scaled-linear-betas
  "Diffusers/CompVis `scaled_linear`: interpolate square roots of the beta
  endpoints, then square each value. Stable Diffusion checkpoints use this
  schedule rather than direct linear beta interpolation."
  [steps beta-start beta-end]
  (when-not (and (pos-int? steps) (< 0 beta-start beta-end 1))
    (throw (ex-info "invalid scaled-linear beta schedule"
                    {:steps steps :beta-start beta-start :beta-end beta-end})))
  (let [start (Math/sqrt beta-start) end (Math/sqrt beta-end)]
    (if (= steps 1)
      [(double beta-start)]
      (mapv (fn [i]
              (let [value (+ start (* (/ i (double (dec steps))) (- end start)))]
                (* value value)))
            (range steps)))))

(defn alphas-cumprod [betas]
  (loop [remaining betas product 1.0 out []]
    (if-let [beta (first remaining)]
      (let [product (* product (- 1.0 (double beta)))]
        (recur (next remaining) product (conj out product)))
      out)))

(defn- same-handle? [a b]
  (and a b (identical? (:handle a) (:handle b))))

(defn- release-except! [tensors protected]
  (let [protected-handles (set (keep :handle protected))]
    (arr/release-all!
     (remove #(contains? protected-handles (:handle %)) (keep identity tensors)))))

(defn- conditioning-tensors [conditioning]
  (cond
    (and (map? conditioning) (:handle conditioning)) [conditioning]
    (map? conditioning) (keep #(when (and (map? %) (:handle %)) %)
                              (vals conditioning))
    :else []))

(defn- audit-event [event retain-step-tensors?]
  (if retain-step-tensors?
    event
    (dissoc event :epsilon :sample :predicted-original-sample)))

(defn- scale [tensor value]
  (t/scale tensor value))

(defn add-noise
  "Forward process `sqrt(alpha)*clean + sqrt(1-alpha)*noise`."
  [clean noise alpha-cumprod]
  (when-not (= (:shape clean) (:shape noise))
    (throw (ex-info "clean/noise shapes differ" {:clean (:shape clean) :noise (:shape noise)})))
  (let [clean-term (scale clean (Math/sqrt alpha-cumprod))
        noise-term (scale noise (Math/sqrt (- 1.0 alpha-cumprod)))
        output (t/add clean-term noise-term)]
    (arr/release-all! [clean-term noise-term])
    output))

(defn ddim-step
  "One DDIM epsilon-prediction step. Returns both `:previous-sample` and
  `:predicted-original-sample`. `noise` is used only when eta>0; eta=0 is the
  deterministic sampler used for reproducible verification."
  ([sample epsilon alpha alpha-prev]
   (ddim-step sample epsilon alpha alpha-prev {}))
  ([sample epsilon alpha alpha-prev {:keys [eta noise] :or {eta 0.0}}]
   (when-not (= (:shape sample) (:shape epsilon))
     (throw (ex-info "sample/epsilon shapes differ"
                     {:sample (:shape sample) :epsilon (:shape epsilon)})))
   (when-not (and (< 0 alpha 1.0) (< 0 alpha-prev) (<= alpha-prev 1.0) (<= 0 eta))
     (throw (ex-info "invalid DDIM coefficients"
                     {:alpha alpha :alpha-prev alpha-prev :eta eta})))
   (let [epsilon-term (scale epsilon (Math/sqrt (- 1.0 alpha)))
         residual (t/sub sample epsilon-term)
         predicted-x0 (scale residual (/ 1.0 (Math/sqrt alpha)))
         sigma (* eta
                  (Math/sqrt (* (/ (- 1.0 alpha-prev) (- 1.0 alpha))
                                (- 1.0 (/ alpha alpha-prev)))))
         direction-scale (Math/sqrt (max 0.0 (- 1.0 alpha-prev (* sigma sigma))))
         x0-term (scale predicted-x0 (Math/sqrt alpha-prev))
         direction-term (scale epsilon direction-scale)
         mean (t/add x0-term direction-term)
         previous (if (pos? sigma)
                    (do
                      (when-not noise
                        (throw (ex-info "DDIM eta>0 requires noise" {:eta eta})))
                      (let [noise-term (scale noise sigma)
                            output (t/add mean noise-term)]
                        (arr/release! noise-term)
                        output))
                    mean)]
     (arr/release-all! [epsilon-term residual x0-term direction-term])
     (when-not (same-handle? mean previous) (arr/release! mean))
     {:previous-sample previous
      :predicted-original-sample predicted-x0
      :sigma sigma})))

(defn classifier-free-guidance
  "`unconditional + cfg * (conditional - unconditional)`."
  [unconditional conditional cfg]
  (when-not (= (:shape unconditional) (:shape conditional))
    (throw (ex-info "CFG epsilon shapes differ"
                    {:unconditional (:shape unconditional)
                     :conditional (:shape conditional)})))
  (let [difference (t/sub conditional unconditional)
        guided-difference (scale difference cfg)
        output (t/add unconditional guided-difference)]
    (arr/release-all! [difference guided-difference])
    output))

(defn select-timesteps
  "Select Diffusers-compatible descending inference timesteps."
  ([training-steps steps] (select-timesteps training-steps steps {}))
  ([training-steps steps {:keys [spacing steps-offset]
                          :or {spacing "linspace" steps-offset 0}}]
   (when-not (and (pos-int? training-steps) (pos-int? steps) (<= steps training-steps))
     (throw (ex-info "invalid inference timestep count"
                     {:training-steps training-steps :steps steps})))
   (case spacing
     "linspace"
     (if (= steps 1)
       [(dec training-steps)]
       (mapv (fn [i]
               (long (Math/round (* (- 1.0 (/ i (double (dec steps))))
                                    (dec training-steps)))))
             (range steps)))
     "leading"
     (let [ratio (quot training-steps steps)]
       (mapv #(+ (long steps-offset) (* ratio %)) (reverse (range steps))))
     "trailing"
     (let [ratio (/ training-steps (double steps))]
       (mapv #(dec (long (Math/round (- training-steps (* % ratio)))))
             (range steps)))
     (throw (ex-info "unsupported timestep spacing" {:spacing spacing})))))

(defn ddim-sample
  "Iterative classifier-free-guided DDIM sampling.

  `denoise-fn` receives `(sample timestep conditioning)` and returns predicted
  epsilon. `alphas` is the model training schedule; `timesteps` are descending
  indices into it. `noise-fn`, required only for eta>0, receives
  `(shape timestep)`. Returns the final latent and per-step audit history."
  [{:keys [sample alphas timesteps denoise-fn positive negative cfg eta noise-fn on-step
           final-alpha retain-step-tensors?]
    :or {cfg 1.0 eta 0.0 final-alpha 1.0 retain-step-tensors? false}}]
  (when-not (and sample (seq alphas) (seq timesteps) (fn? denoise-fn))
    (throw (ex-info "DDIM sampler requires sample, alphas, timesteps, and denoise-fn" {})))
  (loop [current sample current-owned? false remaining (seq timesteps) history []]
    (if-let [timestep (first remaining)]
      (let [next-timestep (second remaining)
            alpha (double (nth alphas timestep))
            alpha-prev (if (some? next-timestep)
                         (double (nth alphas next-timestep))
                         (double final-alpha))
            unconditional (denoise-fn current timestep negative)
            conditional (denoise-fn current timestep positive)
            epsilon (classifier-free-guidance unconditional conditional cfg)
            noise (when (pos? eta)
                    (when-not noise-fn
                      (throw (ex-info "DDIM eta>0 requires noise-fn" {:eta eta})))
                    (noise-fn (:shape current) timestep))
            step (ddim-step current epsilon alpha alpha-prev {:eta eta :noise noise})
            event {:timestep timestep :alpha alpha :alpha-prev alpha-prev
                   :sigma (:sigma step) :epsilon epsilon
                   :predicted-original-sample (:predicted-original-sample step)
                   :sample (:previous-sample step)}
            audited (audit-event event retain-step-tensors?)
            protected (concat [sample current (:previous-sample step)]
                              (conditioning-tensors positive)
                              (conditioning-tensors negative))]
        (when on-step (on-step audited))
        (release-except! [unconditional conditional noise] protected)
        (when-not retain-step-tensors?
          (release-except! [epsilon (:predicted-original-sample step)] protected)
          (when current-owned?
            (release-except! [current] [sample (:previous-sample step)])))
        (recur (:previous-sample step) true (next remaining)
               (conj history audited)))
      {:sample current :history history})))

(defn alpha->sigma
  "Convert cumulative alpha to the Euler/Karras noise level
  `sqrt((1-alpha)/alpha)`."
  [alpha]
  (when-not (< 0.0 alpha 1.0)
    (throw (ex-info "alpha must be in (0,1)" {:alpha alpha})))
  (Math/sqrt (/ (- 1.0 (double alpha)) (double alpha))))

(defn karras-sigmas
  "Construct k-diffusion's Karras noise schedule, including terminal zero."
  ([steps sigma-min sigma-max] (karras-sigmas steps sigma-min sigma-max 7.0))
  ([steps sigma-min sigma-max rho]
   (when-not (and (pos-int? steps) (< 0.0 sigma-min sigma-max) (pos? rho))
     (throw (ex-info "invalid Karras schedule"
                     {:steps steps :sigma-min sigma-min
                      :sigma-max sigma-max :rho rho})))
   (let [min-root (Math/pow sigma-min (/ 1.0 rho))
         max-root (Math/pow sigma-max (/ 1.0 rho))]
     (conj
      (mapv (fn [index]
              (let [ramp (if (= steps 1) 0.0 (/ index (double (dec steps))))]
                (Math/pow (+ max-root (* ramp (- min-root max-root))) rho)))
            (range steps))
      0.0))))

(defn exponential-sigmas
  "Construct k-diffusion's log-linearly spaced exponential schedule, including
  terminal zero."
  [steps sigma-min sigma-max]
  (when-not (and (pos-int? steps) (< 0.0 sigma-min sigma-max))
    (throw (ex-info "invalid exponential schedule"
                    {:steps steps :sigma-min sigma-min :sigma-max sigma-max})))
  (let [log-min (Math/log sigma-min)
        log-max (Math/log sigma-max)]
    (conj
     (mapv (fn [index]
             (let [ramp (if (= steps 1)
                          1.0
                          (- 1.0 (/ index (double (dec steps)))))]
               (Math/exp (+ log-min (* ramp (- log-max log-min))))))
           (range steps))
     0.0)))

(defn polyexponential-sigmas
  "Construct k-diffusion's polynomial curve in log-sigma space. `rho=1`
  equals the exponential schedule; larger rho concentrates steps near
  `sigma-min`. Includes terminal zero."
  ([steps sigma-min sigma-max]
   (polyexponential-sigmas steps sigma-min sigma-max 1.0))
  ([steps sigma-min sigma-max rho]
   (when-not (and (pos-int? steps) (< 0.0 sigma-min sigma-max) (pos? rho))
     (throw (ex-info "invalid polyexponential schedule"
                     {:steps steps :sigma-min sigma-min
                      :sigma-max sigma-max :rho rho})))
   (let [log-min (Math/log sigma-min)
         log-max (Math/log sigma-max)]
     (conj
      (mapv (fn [index]
              (let [linear (if (= steps 1)
                             1.0
                             (- 1.0 (/ index (double (dec steps)))))
                    ramp (Math/pow linear rho)]
                (Math/exp (+ log-min (* ramp (- log-max log-min))))))
            (range steps))
      0.0))))

(defn sigma-schedule
  "Dispatch a ComfyUI/k-diffusion continuous sigma schedule by name."
  [schedule steps sigma-min sigma-max]
  (case schedule
    ("karras" :karras) (karras-sigmas steps sigma-min sigma-max)
    ("exponential" :exponential)
    (exponential-sigmas steps sigma-min sigma-max)
    ("polyexponential" :polyexponential)
    (polyexponential-sigmas steps sigma-min sigma-max)
    (throw (ex-info "unsupported continuous sigma schedule"
                    {:schedule schedule}))))

(defn sigma->timestep
  "Map a continuous sigma to a fractional discrete model timestep by linear
  interpolation in log-sigma space, matching k-diffusion DiscreteSchedule."
  [alphas sigma]
  (when-not (and (seq alphas) (pos? sigma))
    (throw (ex-info "sigma->timestep requires alphas and positive sigma"
                    {:sigma sigma})))
  (let [logs (mapv #(Math/log (alpha->sigma (double %))) alphas)
        target (Math/log sigma)
        last-index (dec (count logs))]
    (cond
      (<= target (first logs)) 0.0
      (>= target (last logs)) (double last-index)
      :else
      (let [low (first (filter #(<= (nth logs %) target (nth logs (inc %)))
                               (range last-index)))
            low-log (nth logs low) high-log (nth logs (inc low))
            weight (/ (- target low-log) (- high-log low-log))]
        (+ low weight)))))

(defn- resolve-sigmas [alphas timesteps sigmas]
  (if sigmas
    (do
      (when-not (and (= (inc (count timesteps)) (count sigmas))
                     (zero? (last sigmas))
                     (every? pos? (butlast sigmas)))
        (throw (ex-info "explicit sigma schedule must have one positive value per timestep plus zero"
                        {:timesteps (count timesteps) :sigmas sigmas})))
      (mapv double sigmas))
    (conj (mapv #(alpha->sigma (double (nth alphas %))) timesteps) 0.0)))

(defn- ancestral-step [sigma sigma-next eta]
  (let [sigma-up (if (zero? sigma-next)
                   0.0
                   (min sigma-next
                        (* eta
                           (Math/sqrt
                            (max 0.0
                                 (/ (* sigma-next sigma-next
                                       (- (* sigma sigma)
                                          (* sigma-next sigma-next)))
                                    (* sigma sigma)))))))]
    {:sigma-up sigma-up
     :sigma-down (Math/sqrt (max 0.0 (- (* sigma-next sigma-next)
                                          (* sigma-up sigma-up))))}))

(defn euler-sample
  "Classifier-free-guided Euler discrete sampling for epsilon-prediction
  models. Model input is scaled by `1/sqrt(sigma^2+1)`; each step integrates
  the ODE derivative from the current training sigma to the next (final 0)."
  [{:keys [sample alphas timesteps sigmas denoise-fn positive negative cfg on-step
           retain-step-tensors?]
    :or {cfg 1.0 retain-step-tensors? false}}]
  (when-not (and sample (seq alphas) (seq timesteps) (fn? denoise-fn))
    (throw (ex-info "Euler sampler requires sample, alphas, timesteps, and denoise-fn" {})))
  (loop [current sample current-owned? false remaining (seq timesteps)
         sigma-remaining (seq (resolve-sigmas alphas timesteps sigmas)) history []]
    (if-let [timestep (first remaining)]
      (let [sigma (first sigma-remaining)
            sigma-next (second sigma-remaining)
            model-input (scale current (/ 1.0 (Math/sqrt (+ 1.0 (* sigma sigma)))))
            unconditional (denoise-fn model-input timestep negative)
            conditional (denoise-fn model-input timestep positive)
            epsilon (classifier-free-guidance unconditional conditional cfg)
            epsilon-at-sigma (scale epsilon sigma)
            predicted-x0 (t/sub current epsilon-at-sigma)
            dt (- sigma-next sigma)
            derivative-step (scale epsilon dt)
            next-sample (t/add current derivative-step)
            event {:timestep timestep :sigma sigma :sigma-next sigma-next
                   :predicted-original-sample predicted-x0}
            audited (audit-event event retain-step-tensors?)
            protected (concat [sample current next-sample]
                              (conditioning-tensors positive)
                              (conditioning-tensors negative))]
        (when on-step (on-step audited))
        (release-except! [model-input unconditional conditional
                          epsilon-at-sigma derivative-step] protected)
        (when-not retain-step-tensors?
          (release-except! [epsilon predicted-x0] protected)
          (when current-owned? (release-except! [current] [sample next-sample])))
        (recur next-sample true (next remaining) (next sigma-remaining)
               (conj history audited)))
      {:sample current :history history})))

(defn euler-ancestral-sample
  "Euler ancestral sampling. Each transition decomposes target sigma into a
  deterministic `sigma-down` step plus fresh noise at `sigma-up`; `eta=1`
  matches the standard ancestral schedule."
  [{:keys [sample alphas timesteps sigmas denoise-fn positive negative cfg eta noise-fn on-step
           retain-step-tensors?]
    :or {cfg 1.0 eta 1.0 retain-step-tensors? false}}]
  (when-not (and sample (seq alphas) (seq timesteps) (fn? denoise-fn)
                 (<= 0.0 eta))
    (throw (ex-info "Euler ancestral sampler received invalid arguments" {:eta eta})))
  (loop [current sample current-owned? false remaining (seq timesteps)
         sigma-remaining (seq (resolve-sigmas alphas timesteps sigmas)) history []]
    (if-let [timestep (first remaining)]
      (let [sigma (first sigma-remaining)
            sigma-next (second sigma-remaining)
            model-input (scale current (/ 1.0 (Math/sqrt (+ 1.0 (* sigma sigma)))))
            unconditional (denoise-fn model-input timestep negative)
            conditional (denoise-fn model-input timestep positive)
            epsilon (classifier-free-guidance unconditional conditional cfg)
            {:keys [sigma-up sigma-down]} (ancestral-step sigma sigma-next eta)
            derivative-step (scale epsilon (- sigma-down sigma))
            mean (t/add current derivative-step)
            noise (when (pos? sigma-up)
                    (when-not noise-fn
                      (throw (ex-info "Euler ancestral sampling requires noise-fn" {})))
                    (noise-fn (:shape current) timestep))
            noise-step (when noise (scale noise sigma-up))
            next-sample (if noise-step (t/add mean noise-step) mean)
            event {:timestep timestep :sigma sigma :sigma-next sigma-next
                   :sigma-up sigma-up :sigma-down sigma-down}
            audited (audit-event event retain-step-tensors?)
            protected (concat [sample current next-sample]
                              (conditioning-tensors positive)
                              (conditioning-tensors negative))]
        (when on-step (on-step audited))
        (release-except! [model-input unconditional conditional derivative-step
                          noise noise-step] protected)
        (when-not (same-handle? mean next-sample) (arr/release! mean))
        (when-not retain-step-tensors?
          (release-except! [epsilon] protected)
          (when current-owned? (release-except! [current] [sample next-sample])))
        (recur next-sample true (next remaining) (next sigma-remaining)
               (conj history audited)))
      {:sample current :history history})))

(defn dpmpp-2s-ancestral-sample
  "k-diffusion DPM-Solver++(2S) ancestral sampling for epsilon models. Each
  non-terminal transition evaluates the denoiser at its log-sigma midpoint,
  advances to sigma-down with that second x0 estimate, then adds seeded
  sigma-up noise."
  [{:keys [sample alphas timesteps sigmas denoise-fn positive negative cfg eta
           noise-fn on-step retain-step-tensors?]
    :or {cfg 1.0 eta 1.0 retain-step-tensors? false}}]
  (when-not (and sample (seq alphas) (seq timesteps) (fn? denoise-fn)
                 (<= 0.0 eta))
    (throw (ex-info "DPM++ 2S ancestral sampler received invalid arguments"
                    {:eta eta})))
  (loop [current sample current-owned? false remaining (seq timesteps)
         sigma-remaining (seq (resolve-sigmas alphas timesteps sigmas)) history []]
    (if-let [timestep (first remaining)]
      (let [sigma (first sigma-remaining)
            sigma-next (second sigma-remaining)
            {:keys [sigma-up sigma-down]} (ancestral-step sigma sigma-next eta)
            model-input (scale current (/ 1.0 (Math/sqrt (+ 1.0 (* sigma sigma)))))
            unconditional (denoise-fn model-input timestep negative)
            conditional (denoise-fn model-input timestep positive)
            epsilon (classifier-free-guidance unconditional conditional cfg)
            epsilon-at-sigma (scale epsilon sigma)
            denoised (t/sub current epsilon-at-sigma)
            midpoint? (pos? sigma-down)
            h (when midpoint? (- (Math/log sigma) (Math/log sigma-down)))
            sigma-mid (when midpoint? (Math/exp (- (+ (- (Math/log sigma)) (* 0.5 h)))))
            current-mid (when midpoint? (scale current (/ sigma-mid sigma)))
            denoised-mid (when midpoint? (scale denoised (- (Math/expm1 (* -0.5 h)))))
            x-mid (when midpoint? (t/add current-mid denoised-mid))
            midpoint-timestep (when midpoint? (sigma->timestep alphas sigma-mid))
            midpoint-input (when midpoint?
                             (scale x-mid (/ 1.0 (Math/sqrt (+ 1.0 (* sigma-mid sigma-mid))))))
            unconditional-mid (when midpoint?
                                (denoise-fn midpoint-input midpoint-timestep negative))
            conditional-mid (when midpoint?
                              (denoise-fn midpoint-input midpoint-timestep positive))
            epsilon-mid (when midpoint?
                          (classifier-free-guidance unconditional-mid conditional-mid cfg))
            epsilon-mid-scaled (when midpoint? (scale epsilon-mid sigma-mid))
            denoised-2 (when midpoint? (t/sub x-mid epsilon-mid-scaled))
            base-current (when midpoint? (scale current (/ sigma-down sigma)))
            base-denoised (when midpoint?
                            (scale denoised-2 (- (Math/expm1 (- h)))))
            mean (if midpoint? (t/add base-current base-denoised) denoised)
            noise (when (pos? sigma-up)
                    (when-not noise-fn
                      (throw (ex-info "DPM++ 2S ancestral sampling requires noise-fn" {})))
                    (noise-fn (:shape current) timestep))
            noise-step (when noise (scale noise sigma-up))
            next-sample (if noise-step (t/add mean noise-step) mean)
            event {:timestep timestep :sigma sigma :sigma-next sigma-next
                   :sigma-up sigma-up :sigma-down sigma-down
                   :midpoint-sigma sigma-mid :order (if midpoint? 2 1)}
            audited (audit-event event retain-step-tensors?)
            protected (concat [sample current next-sample]
                              (conditioning-tensors positive)
                              (conditioning-tensors negative))]
        (when on-step (on-step audited))
        (release-except!
         [model-input unconditional conditional epsilon epsilon-at-sigma denoised
          current-mid denoised-mid x-mid midpoint-input unconditional-mid conditional-mid
          epsilon-mid epsilon-mid-scaled denoised-2 base-current base-denoised noise noise-step]
         protected)
        (when-not (same-handle? mean next-sample) (arr/release! mean))
        (when (and current-owned? (not retain-step-tensors?))
          (release-except! [current] [sample next-sample]))
        (recur next-sample true (next remaining) (next sigma-remaining)
               (conj history audited)))
      {:sample current :history history})))

(defn dpmpp-2m-sample
  "Deterministic k-diffusion DPM-Solver++(2M) sampling.

  The denoiser predicts epsilon, so each call is converted to the denoised
  estimate `x0 = x - sigma*epsilon`. Non-final steps use the exponential
  first-order update, upgraded from the second step onward by the previous
  denoised estimate. The terminal sigma-zero step returns x0 exactly."
  [{:keys [sample alphas timesteps sigmas denoise-fn positive negative cfg on-step
           retain-step-tensors?]
    :or {cfg 1.0 retain-step-tensors? false}}]
  (when-not (and sample (seq alphas) (seq timesteps) (fn? denoise-fn))
    (throw (ex-info "DPM++ 2M sampler requires sample, alphas, timesteps, and denoise-fn"
                    {})))
  (loop [current sample current-owned? false remaining (seq timesteps)
         sigma-remaining (seq (resolve-sigmas alphas timesteps sigmas))
         old-denoised nil previous-time nil history []]
    (if-let [timestep (first remaining)]
      (let [sigma (first sigma-remaining)
            sigma-next (second sigma-remaining)
            model-input (scale current (/ 1.0 (Math/sqrt (+ 1.0 (* sigma sigma)))))
            unconditional (denoise-fn model-input timestep negative)
            conditional (denoise-fn model-input timestep positive)
            epsilon (classifier-free-guidance unconditional conditional cfg)
            epsilon-at-sigma (scale epsilon sigma)
            denoised (t/sub current epsilon-at-sigma)
            time (- (Math/log sigma))
            update
            (if (zero? sigma-next)
              {:sample denoised :temporaries []}
              (let [next-time (- (Math/log sigma-next))
                    h (- next-time time)
                    effective
                    (if old-denoised
                      (let [h-last (- time previous-time)
                            r (/ h-last h)
                            previous-factor (/ 1.0 (* 2.0 r))
                            current-term (scale denoised (+ 1.0 previous-factor))
                            previous-term (scale old-denoised previous-factor)
                            value (t/sub current-term previous-term)]
                        {:value value :temporaries [current-term previous-term]})
                      {:value denoised :temporaries []})
                    ratio (/ sigma-next sigma)
                    denoised-factor (- (Math/expm1 (- h)))
                    current-term (scale current ratio)
                    denoised-term (scale (:value effective) denoised-factor)
                    value (t/add current-term denoised-term)]
                {:sample value
                 :temporaries (concat (:temporaries effective)
                                      [current-term denoised-term]
                                      (when-not (same-handle? (:value effective) denoised)
                                        [(:value effective)]))}))
            next-sample (:sample update)
            event {:timestep timestep :sigma sigma :sigma-next sigma-next
                   :order (if (and old-denoised (pos? sigma-next)) 2 1)
                   :predicted-original-sample denoised :sample next-sample}
            audited (audit-event event retain-step-tensors?)
            protected (concat [sample current next-sample denoised]
                              (conditioning-tensors positive)
                              (conditioning-tensors negative))]
        (when on-step (on-step audited))
        (release-except! (concat [model-input unconditional conditional
                                  epsilon-at-sigma]
                                 (:temporaries update)) protected)
        (when-not retain-step-tensors?
          (release-except! [epsilon old-denoised] protected)
          (when current-owned? (release-except! [current] [sample next-sample denoised])))
        (recur next-sample true (next remaining) (next sigma-remaining) denoised time
               (conj history audited)))
      {:sample current :history history})))
