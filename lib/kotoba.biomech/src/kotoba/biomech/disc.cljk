(ns kotoba.biomech.disc
  "Axial compression of an intervertebral disc. Zero-dep, pure .cljc.

  WHY THIS EXISTS. cloud-itonami/suji computes, for every intervertebral level,
  an axial force and divides it by a disc area to report a `:stress-mpa`. It then
  cross-checks that against Wilke et al. 1999's in-vivo intradiscal pressure. So
  a consumer of this family already has a STRESS on a disc and no way to turn it
  into a DEFORMATION, because until now this repo carried no disc tissue at all.

  This namespace closes that step — and its most useful behaviour is that it
  REFUSES to close it at the stress the consumer actually has.

  THE MEASUREMENT THAT MOTIVATES THE REFUSAL. Wilke's relaxed-sitting L4/L5
  pressure is 0.46 MPa. The annulus fibrosus reference aggregate modulus from
  Iatridis et al. 1998 is 0.56 MPa. Dividing gives a linear axial strain of
  0.82 — EIGHTY-TWO PERCENT. On a 10 mm disc that is 8.2 mm of height loss, from
  a disc that is 10 mm tall, at the load of sitting still on a stool. In-vivo
  diurnal disc height loss over an entire day is on the order of a millimetre.
  The linear answer is not merely imprecise, it is impossible, and a library that
  returned 8.2 mm would be handing a consumer a number that looks like a result.

  WHY IT COMES OUT THAT WAY, FROM THE SOURCES THEMSELVES, NOT FROM HINDSIGHT:

  - H_A0 IS A REFERENCE MODULUS OF A NONLINEAR MODEL. The same sentence of
    Iatridis 1998 that reports 0.56 +/- 0.21 MPa also reports a nonlinear
    stiffening coefficient beta = 2.13 +/- 1.48 for normal tissue. H_A0 is the
    stiffness at the zero-strain reference state; the tissue stiffens from there.
    Using it as if it were constant therefore OVERSTATES deformation, and
    overstates it more the further you go.
  - IN VIVO THE LOAD IS NOT CARRIED BY THE SOLID MATRIX. Johannessen & Elliott
    2005 conclude, verbatim, `Swelling is the primary load-bearing mechanism in
    both nondegenerate and degenerate nucleus pulposus`. An elastic modulus
    describes matrix deformation, which is not the path the load takes.
  - A CONFINED-COMPRESSION MODULUS IS AN EQUILIBRIUM PROPERTY OF A CONFINED
    SPECIMEN. A disc in a living spine is neither that specimen nor at
    equilibrium.

  So this namespace computes the linear strain, states it, and withholds the
  height loss whenever the linear reading cannot be defended. This is the same
  shape as `suji.methods.muscle/ligament-at-limit?`, which refuses to extrapolate
  a ligament curve past its calibration for the same reason: its author found
  that extrapolating gave the nuchal ligament 52,312 N at an ordinary posture.

  WHAT THIS IS NOT. Not a disc model. There is no fluid phase, no swelling
  pressure, no time, no creep, no annulus/nucleus interaction, no nonlinearity —
  a real disc is a pressurised vessel whose annulus is loaded in hoop tension by
  a nucleus that behaves as a fluid, and none of that is here. This is the one
  linear step from stress to strain, with an honest boundary on where it holds."
  (:require [kotoba.biomech.tissue :as tissue]))

(def default-linear-strain-limit
  "Strain past which this namespace stops reporting a height loss (0.05 = 5%).

  THIS NUMBER IS A MODELLING CONVENTION OF THIS NAMESPACE. It is NOT from
  Iatridis 1998 and is not claimed to be. What the source supplies is the
  DIRECTION of the argument — a nonlinear stiffening coefficient beta =
  2.13 +/- 1.48, which says the linear reading degrades as strain grows and in
  which direction it errs. It does not supply a cut-off, and inventing one and
  attributing it would be worse than choosing one and saying so.

  Callers who want a different boundary should pass their own; callers who want
  none can pass a limit of 1.0 and own the result."
  0.05)

(defn axial-strain
  "Linear axial strain (dimensionless) for a compressive `stress-pa` against an
  aggregate modulus `modulus-pa`.

  epsilon = sigma / H_A. Sign convention: both arguments are positive magnitudes
  for compression, and the returned strain is a positive magnitude of shortening.

  Returns nil rather than throwing when the modulus is absent or non-positive —
  a tissue with no modulus (the nucleus pulposus carries no Young's modulus at
  all, deliberately) must not produce a strain."
  [stress-pa modulus-pa]
  (when (and (number? stress-pa) (number? modulus-pa)
             (pos? (double modulus-pa)))
    (/ (double stress-pa) (double modulus-pa))))

(defn beyond-linear-range?
  "True when `strain` is at or past `limit`, i.e. when a linear modulus should no
  longer be read as a deformation. Nil strain is beyond the range: an answer that
  could not be computed is not an answer inside the range."
  ([strain] (beyond-linear-range? strain default-linear-strain-limit))
  ([strain limit]
   (or (nil? strain)
       (>= (double strain) (double limit)))))

(defn axial-compression
  "Compress a disc tissue axially and report what can and cannot be defended.

  Arguments: a tissue map `t` (annulus fibrosus or nucleus pulposus from the
  presets), the axial compressive stress in PASCALS, the unloaded disc height in
  METRES, and optionally a strain limit.

  NOTE ON UNITS. Consumers quote disc stress in MPa because that is the unit
  in-vivo disc tolerances are published in — cloud-itonami/suji reports
  `:stress-mpa`. This function takes PASCALS, like every other modulus and stress
  in this repo. Multiply by 1e6 at the boundary; `stress-mpa->pa` does it.

  Returns a map:
    :strain                 linear axial strain, always present when computable
    :height-loss-m/-mm      NIL when the linear reading is beyond its range
    :refused                nil, or a keyword saying why no height loss is given
    :beyond-linear-range?   boolean
    :aggregate-modulus-pa   the modulus actually used
    :tissue, :source        what answered, and its provenance

  THE HEIGHT LOSS IS WITHHELD, NOT CLAMPED. Clamping would return a number at the
  limit, and a caller would use it. The absence is the message."
  ([t stress-pa height-m]
   (axial-compression t stress-pa height-m default-linear-strain-limit))
  ([t stress-pa height-m limit]
   (let [h-a    (tissue/aggregate-modulus t)
         strain (axial-strain stress-pa h-a)
         beyond (beyond-linear-range? strain limit)
         base   {:tissue (:name t)
                 :aggregate-modulus-pa h-a
                 :stress-pa (when (number? stress-pa) (double stress-pa))
                 :strain strain
                 :beyond-linear-range? beyond
                 :limit (double limit)
                 :source (tissue/source t)}]
     (cond
       (nil? h-a)
       (assoc base :height-loss-m nil :height-loss-mm nil
              :refused :no-aggregate-modulus
              :note (str "tissue " (pr-str (:name t))
                         " carries no confined-compression aggregate modulus,"
                         " so no axial strain can be computed from it"))

       (nil? strain)
       (assoc base :height-loss-m nil :height-loss-mm nil
              :refused :strain-not-computable
              :note "stress and a positive aggregate modulus are both required")

       beyond
       (assoc base :height-loss-m nil :height-loss-mm nil
              :refused :beyond-linear-range
              :note (str "linear strain " strain " is at or past the limit " limit
                         "; H_A0 is the zero-strain reference modulus of a"
                         " NONLINEAR model (Iatridis 1998 reports a stiffening"
                         " coefficient beta = 2.13 +/- 1.48 for normal tissue),"
                         " so a linear reading OVERSTATES deformation here and"
                         " the height loss is withheld rather than clamped"))

       :else
       (let [loss-m (* (double height-m) (double strain))]
         (assoc base
                :height-loss-m loss-m
                :height-loss-mm (* 1000.0 loss-m)
                :refused nil
                :note nil))))))

(defn stress-mpa->pa
  "Megapascals to pascals. Present because the consumers of this namespace quote
  disc stress in MPa (suji's `:stress-mpa`, Wilke's published pressures) while
  this repo works in Pa, and a silent factor of 1e6 in that conversion is exactly
  the kind of error a disc stress is large enough to hide."
  [mpa]
  (when (number? mpa) (* 1.0e6 (double mpa))))

;; ---------------------------------------------------------------------------
;; THE TIME-DEPENDENT PATH, AND WHAT MEASURING IT SETTLED.
;;
;; Everything above is one modulus and no clock. Three explanations were on the
;; table for why that gives 82% strain at a pressure a person sits at:
;;
;;   (1) H_A is an EQUILIBRIUM modulus. It says where the tissue ends up after
;;       the fluid has left, not where it is minutes after a load is applied.
;;       A single modulus cannot carry a time scale.
;;   (2) The load is borne by fluid pressurisation and osmotic swelling, not by
;;       the solid matrix whose deformation the modulus describes.
;;   (3) The measured quantity is not the stress on the solid phase at all, so
;;       feeding it to a solid modulus is a category error, and the answer is a
;;       differently shaped model rather than a better number.
;;
;; This section implements (1) AND (2) -- the whole of both, with every constant
;; read from a source -- BECAUSE THEY ARE THE ONES THAT CAN BE MEASURED AND
;; DISPOSED OF. Measuring them disposes of them. Three readings of the same
;; 0.46 MPa, against Botsford 1994's measured diurnal volume loss of 16.2% (mean
;; of the lower three lumbar discs) and 18.7-21.6% (per level):
;;
;;   sigma / H_A                      0.455   the reading above. Refuted.
;;   (sigma - P_swelling) / H_A       0.319   (2) removed. Still ~1.5x the
;;                                            largest measured value, and 2x
;;                                            the mean. Refuted.
;;   time-dependent, t = 16 h         0.317   (1) removed as well -- and it
;;                                            barely moves, because the nucleus
;;                                            is 2.1 time constants into its
;;                                            creep by then. THE TIME SCALE IS
;;                                            REAL AND IT IS NOT THE EXPLANATION.
;;   ((sigma / index) - P_sw) / H_A   0.131   (3) removed, using Nachemson's
;;                            to 0.167        measured pressure index. Inside
;;                                            the measured band, or under it.
;;
;; Only the last one lands, and the last one is the one that stops treating a
;; hydrostatic pressure read in the nucleus as a stress on a specimen. So (3) is
;; what the evidence supports, and this namespace names it as missing, offers the
;; conversion with the index as a REQUIRED argument, and still refuses -- because
;; 16.7% is not inside a linear reading of H_A0 either, and a number that has
;; stopped being absurd has not thereby become defensible.
;;
;; The evidence for each of those claims is in the tests, against numbers from
;; van der Veen 2013, Botsford 1994 and Nachemson 1960 rather than against this
;; file.

(def biphasic-theory-source
  "Provenance for the theory this section implements, not for a number.

  Mow VC, Kuei SC, Lai WM, Armstrong CG. Biphasic creep and stress relaxation of
  articular cartilage in compression: theory and experiments. J Biomech Eng.
  1980;102(1):73-84. doi:10.1115/1.3138202, PMID 7382457.

  OBTAINED :abstract, via the Crossref work record (api.crossref.org). PubMed's
  HTML serves a cookie page, Europe PMC holds no abstract for this record, and
  the ASME page returns 403; the Crossref <jats:abstract> is the publisher's own
  deposit and is quoted here verbatim, in the two places it decides something:

    `the solid matrix was assumed to be intrinsically incompressible, linearly
    elastic and nondissipative while the interstitial fluid was assumed to be
    intrinsically incompressible and nondissipative. Further, it was assumed
    that the only dissipation comes from the frictional drag of relative motion
    between the phases.`

  -- which is why a creep time constant exists at all and why it is a product of
  a stiffness and a permeability rather than a viscosity -- and

    `A constant \"average\" permeability of the tissue was assumed, i.e.,
    independent of deformation... We concluded that the large spread in the
    permeability coefficients is due to the assumption of a constant deformation
    independent permeability.`

  -- which is the authors of the theory saying, in the paper that founded it,
  that the assumption this namespace also makes is the weak one."
  {:citation "Mow VC, Kuei SC, Lai WM, Armstrong CG. Biphasic creep and stress relaxation of articular cartilage in compression: theory and experiments. J Biomech Eng. 1980;102(1):73-84."
   :doi "10.1115/1.3138202"
   :pmid "7382457"
   :obtained :abstract
   :via :crossref})

(def measured-whole-disc-creep-time-constant-band-h
  "[3.6 17.0] hours. THE NUMBER THIS SECTION IS CHECKED AGAINST.

  van der Veen AJ, van Dieen JH, Smit TH. Modelling creep behaviour of the human
  intervertebral disc. J Biomech. 2013;46(12):2101-2103.
  doi:10.1016/j.jbiomech.2013.05.026, PMID 23796401. :obtained :abstract.

  Verbatim: `human thoracic discs were preloaded at 0.1 MPa for 12h, compressed
  (0.8 MPa) for 24h and finally unloaded (0.1 MPa) for 24h`, and `The estimated
  time constant varied with test duration from 3.6 to 17h.`

  READ IT FOR WHAT IT IS. This is not one measurement of one constant; it is the
  same discs fitted over six test durations and giving six answers, which is the
  authors telling you the quantity is protocol-dependent. Their own conclusion,
  verbatim: `The 24h experiment was still too short for an accurate
  determination of the parameters.` A derived time constant landing inside this
  band has cleared a real, externally measured bar and has not been validated to
  a figure."
  [3.6 17.0])

(def measured-diurnal-disc-loss
  "The in-vivo diurnal loss this namespace's height predictions are judged by.

  Botsford DJ, Esses SI, Ogilvie-Harris DJ. In vivo diurnal variation in
  intervertebral disc volume and morphology. Spine. 1994;19(8):935-940.
  doi:10.1097/00007632-199404150-00012, PMID 8009352. :obtained :abstract.
  Eight normal males, 3-D MRI, 6 h supine versus 4 h standing + 3 h sitting.

  Verbatim: `The mean decrease in disc volume at the L3-4 level after standing
  was 21.1%. At the L4-5 level, it decreased a mean of 18.7%, whereas at the
  L5-S1 level, there was a 21.6% mean decrease.` and `The mean simulated diurnal
  volume decrease in the lower three lumbar discs is 16.2%.`

  THESE ARE VOLUME FRACTIONS, NOT HEIGHT STRAINS, and the difference matters in
  a direction that makes them a CEILING rather than a target. The same abstract
  reports that AP diameter fell too -- verbatim, `Volume height and AP diameter
  of the lumbar intervertebral discs decreased significantly` -- so with V = A*h
  and A falling, the height strain is SMALLER than the volume fraction. A model
  whose height strain exceeds 21.6% has therefore been refuted by this
  measurement; a model below it has not thereby been confirmed by it."
  {:volume-loss-fraction {:l3-l4 0.211 :l4-l5 0.187 :l5-s1 0.216
                          :lower-three-lumbar-mean 0.162}
   :citation "Botsford DJ, Esses SI, Ogilvie-Harris DJ. In vivo diurnal variation in intervertebral disc volume and morphology. Spine. 1994;19(8):935-940."
   :doi "10.1097/00007632-199404150-00012"
   :pmid "8009352"
   :obtained :abstract})

(def nachemson-pressure-index
  "The quotient that separates a NUCLEUS PRESSURE from a DISC MEAN STRESS.

  Nachemson A. Measurement of Intradiscal Pressure. Acta Orthopaedica
  Scandinavica. 1960;XXVIII:269-289. :obtained :FULL-TEXT -- the scanned PDF at
  actaorthop.org, read here directly rather than through a consumer's record of
  it (cloud-itonami/suji carries the same values from the same source, and they
  agree; that agreement is a check, not the provenance).

  WHAT IT IS, FROM THE TABLE THAT COMPUTES IT. Table 1 shows the arithmetic in
  its own numerators: for specimen 252/L2, surface area 14.8 cm^2, a 40 kg load
  and a calibrated intradiscal pressure of 4.0 kp/cm^2 give an index of
  4.0 * 14.8 / 40 = 1.48. So

      index = P_nucleus / (P_applied / A_disc)

  i.e. the pressure a catheter in the nucleus reads, over the MEAN STRESS on the
  whole disc. Table 5 tabulates it, verbatim: `Pressure indices tabulated by
  interspace and state of discs` -- normal L1 1.6, L2 1.7, L3 1.5, L4 1.7;
  degenerated L1 1.5, L2 1.4, L3 1.3, L4 1.2.

  WHY THIS NAMESPACE CARRIES IT AT ALL. Because it is the size of the category
  error. Wilke's 0.46 MPa is a nucleus pressure -- his Methods say so verbatim,
  `a pressure transducer with a diameter of 1.5 mm was implanted in the nucleus
  pulposus of a nondegenerated L4-L5 disc` -- and the confined-compression law
  in `equilibrium-strain` wants a stress on the specimen. They differ by this
  index, and the whole residual overshoot this namespace refuses on is about
  that big. See the tests.

  NO SINGLE VALUE IS OFFERED, ONLY THE MEASURED SPREAD, and
  `nucleus-pressure->disc-mean-stress` takes the index as a REQUIRED argument
  for the same reason cloud-itonami/suji does: it is an assumption, and an
  assumption with a default is an assumption nobody sees. Nachemson measured it
  on cadaver discs under pure axial load; Wilke's spine was alive and being
  squeezed by its own muscles, and Wilke performs no such conversion and does
  not endorse one. Nachemson also notes the nucleus `occupies on an average 60
  per cent of the cross-sectional area of the disc`, so the mean disc stress is
  not the nucleus's own share of it either."
  {:normal-by-interspace {"L1" 1.6 "L2" 1.7 "L3" 1.5 "L4" 1.7}
   :degenerated-by-interspace {"L1" 1.5 "L2" 1.4 "L3" 1.3 "L4" 1.2}
   :normal-range [1.5 1.7]
   :citation "Nachemson A. Measurement of Intradiscal Pressure. Acta Orthop Scand. 1960;XXVIII:269-289. Table 1 (worked index), Table 5 (indices by interspace and state)."
   :url "https://actaorthop.org/actao/article/download/30762/35650/84307"
   :obtained :full-text})

(defn nucleus-pressure->disc-mean-stress
  "Nucleus pressure [Pa] -> mean stress on the whole disc [Pa], through
  `index`, which is REQUIRED and has no default.

      disc mean stress = nucleus pressure / index

  This is the inverse of Nachemson's definition and nothing more. It is not a
  correction to the tissue model and does not make an out-of-range answer valid;
  it converts one measured quantity into the other, so that a caller holding a
  Wilke-style intradiscal pressure can at least hand this namespace a quantity
  of the right KIND. Nil on a missing or non-positive index."
  [pressure-pa index]
  (when (and (number? pressure-pa) (number? index) (pos? (double index)))
    (/ (double pressure-pa) (double index))))

(defn poroelastic-diffusivity
  "H_A * k [m^2/s] -- the diffusivity of the biphasic consolidation problem.

  DERIVED, NOT LOOKED UP. Mow's biphasic mixture with the solid elastic and the
  only dissipation the Darcy drag between phases gives, in one dimension, a
  diffusion equation for the solid displacement whose coefficient is the product
  of the confined stiffness and the permeability. You can see it must be that
  product without solving anything: H_A is [N/m^2], k is [m^4/(N*s)], and their
  product is [m^2/s]. Nothing else in the theory has those units.

  Returns nil if either input is missing or non-positive: a tissue with no
  permeability has no time scale, and must not be given one."
  [aggregate-modulus-pa permeability-m4-n-s]
  (when (and (number? aggregate-modulus-pa) (number? permeability-m4-n-s)
             (pos? (double aggregate-modulus-pa))
             (pos? (double permeability-m4-n-s)))
    (* (double aggregate-modulus-pa) (double permeability-m4-n-s))))

(defn two-sided-drainage-path
  "Half of `height-m`. The drainage path of a disc whose fluid leaves through
  BOTH cartilage endplates, measured from mid-height to the nearest free surface.

  THIS IS THE MOST LEVERAGED ASSUMPTION IN THE WHOLE SECTION and it is a
  separate named function so that it can be argued with rather than buried in a
  formula. The time constant goes as the SQUARE of this length, so choosing the
  full height instead of the half doubles the path and QUADRUPLES the time.

  It is also the assumption least supported by what was read. MacLean JJ, Owen
  JP, Iatridis JC (J Biomech. 2007;40(1):55-63, PMID 16427060, :obtained
  :abstract) tested rat caudal motion segments with and without endplates and
  report, verbatim, that `differences in endplate permeability conditions had a
  significant effect on viscoelastic behaviors`. Treating the endplate as a free
  surface -- which is what this function does -- is therefore known to be wrong
  in the direction of a time constant that is too SHORT."
  [height-m]
  (when (and (number? height-m) (pos? (double height-m)))
    (* 0.5 (double height-m))))

(defn poroelastic-time-constant
  "tau = h^2 / (H_A * k), in SECONDS. Nil if any input is missing or non-positive.

  Read from a source, in a source. Yuan D, Somers SM, Grayson WL, Spector AA.
  A Poroelastic Model of a Fibrous-Porous Tissue Engineering Scaffold. Sci Rep.
  2018;8:5043. doi:10.1038/s41598-018-23214-8, PMCID PMC5864912. :obtained
  :full-text, via the Europe PMC REST full-text XML (CC BY). Verbatim:

    `It is convenient to use the gel diffusion time, t_g, instead, as an
    additional independent parameter because it is directly visible in the
    experiment. The t_g-time is related to the permeability, k, by the following
    equation: t_g = a^2 / (k C_11)`

  C_11 is the constrained stiffness in the drainage direction, which under
  confined compression IS the aggregate modulus, and a is the drainage length.
  So this is that equation, not an analogy to it."
  [drainage-path-m aggregate-modulus-pa permeability-m4-n-s]
  (let [d (poroelastic-diffusivity aggregate-modulus-pa permeability-m4-n-s)]
    (when (and d (number? drainage-path-m) (pos? (double drainage-path-m)))
      (/ (* (double drainage-path-m) (double drainage-path-m)) d))))

(def ^:private consolidation-series-terms
  "Terms kept in the large-time series. Twelve, and that is not a guess: at the
  T = 0.1 changeover the second term is ~1e-2 of the first, the third ~1e-5, and
  the twelfth is below double precision. Truncating this series at SMALL T is
  the failure mode -- the neglected tail is ~8/((2N+1)pi^2), which at N = 12 is
  3% and would swamp a genuine U of 0.4% -- which is why the small-T branch
  below exists at all rather than being an optimisation."
  12)

(defn consolidation-fraction
  "The fraction of the equilibrium strain reached at `time-s`, given a time
  constant `tau-s`. Dimensionless, 0 at t=0 and rising to 1.

  This is the step-load solution of the diffusion equation the previous
  functions set up, for a layer draining at one face:

    U(T) = 1 - SUM_{m>=0} (2/M^2) exp(-M^2 T),  M = (2m+1)pi/2,  T = t/tau

  and for T <= 0.1 the exact early-time equivalent U(T) = 2 sqrt(T/pi), which is
  used because the series converges from the WRONG SIDE there: with any
  affordable number of terms the truncated series returns a value near its own
  tail rather than near U. The two branches agree to 1.2e-6 at the changeover
  and the largest disagreement with a 6000-term reference anywhere in T is
  1.4e-6, which is at the changeover and is the whole of the error.

  Nil time or nil/non-positive tau returns nil. A negative or zero time returns
  0.0 -- no load has been applied yet, so no fluid has left."
  [time-s tau-s]
  (when (and (number? time-s) (number? tau-s) (pos? (double tau-s)))
    (let [t (double time-s)]
      (if (<= t 0.0)
        0.0
        (let [T (/ t (double tau-s))]
          (if (<= T 0.1)
            (* 2.0 (Math/sqrt (/ T Math/PI)))
            (loop [m 0 acc 0.0]
              (if (>= m consolidation-series-terms)
                (- 1.0 acc)
                (let [mm (* (+ (* 2.0 m) 1.0) (/ Math/PI 2.0))
                      m2 (* mm mm)]
                  (recur (inc m)
                         (+ acc (* (/ 2.0 m2) (Math/exp (- (* m2 T)))))))))))))))

(defn equilibrium-strain
  "The strain the confined-compression law reaches at t = infinity:

    epsilon_inf = (sigma - sigma_swelling) / H_A

  and NOT sigma / H_A, which is what `axial-strain` above computes and is the
  half of the constitutive law that produced 82%. Iatridis 1998 fits a
  `reference stress offset` alongside H_A0 precisely because the tissue at zero
  strain is already carrying stress.

  A NEGATIVE RESULT IS MEANINGFUL AND IS RETURNED, NOT CLAMPED: it says the
  applied stress is below the tissue's own swelling stress, so the tissue takes
  fluid UP rather than losing height. Callers must not read it as a height gain
  -- the law was fitted in compression -- but they must be able to see it.

  Nil swelling stress is treated as nil, not as zero. A tissue whose swelling
  stress was never measured is not a tissue whose swelling stress is zero, and
  substituting one for the other is how the offset silently disappears again."
  [stress-pa swelling-stress-pa aggregate-modulus-pa]
  (when (and (number? stress-pa) (number? swelling-stress-pa)
             (number? aggregate-modulus-pa)
             (pos? (double aggregate-modulus-pa)))
    (/ (- (double stress-pa) (double swelling-stress-pa))
       (double aggregate-modulus-pa))))

(defn missing-quantities
  "The named quantities `axial-creep` does not have for tissue `t`.

  A vector of keywords, never empty. This is the point of the whole section: a
  refusal that says `the strain came out large` tells a caller nothing it can
  act on, and a refusal that names the term the model is missing tells it what
  to go and measure or read.

  The first entry is unconditional and is the one the literature actually
  supports. The rest distinguish `this tissue has the coefficient and this
  linear model does not use it` from `nobody in the sources read here measured
  it`, which are different problems with different fixes."
  [t]
  (cond-> [:effective-stress-on-solid-phase]
    (tissue/nonlinear-stiffening-coefficient t)
    (conj :measured-nonlinear-stiffening-not-used)

    (nil? (tissue/nonlinear-stiffening-coefficient t))
    (conj :nonlinear-stiffening-never-measured)

    (tissue/permeability-strain-coefficient t)
    (conj :measured-strain-dependent-permeability-not-used)

    (nil? (tissue/permeability-strain-coefficient t))
    (conj :strain-dependent-permeability-never-measured)))

(defn axial-creep
  "Compress a disc tissue axially under a STEP load held for `time-s`, and
  report what the biphasic reading can and cannot defend.

  Arguments: a tissue map `t`, the axial compressive stress in PASCALS, the
  unloaded disc height in METRES, the elapsed time in SECONDS, and optionally a
  strain limit (default `default-linear-strain-limit`).

  Returns a map. Beyond the fields `axial-compression` returns it carries
  :swelling-stress-pa, :permeability-m4-n-s, :drainage-path-m,
  :diffusivity-m2-s, :time-constant-s, :time-constant-h, :time-s,
  :consolidation-fraction, :equilibrium-strain, and :missing.

  THE REFUSAL IS DECIDED ON THE EQUILIBRIUM STRAIN, NOT ON THE STRAIN AT
  `time-s`, and that is the design. A trajectory is only as trustworthy as the
  destination it is heading for: if epsilon_inf is 32% then every point on the
  path was computed with a modulus evaluated far outside where it was fitted,
  including the points that happen to be small because little time has passed.
  Refusing on the instantaneous strain would hand back answers for short times
  that are wrong for exactly the reason the long-time answer is refused.

  WHY THE HEIGHT LOSS IS STILL WITHHELD AT WILKE'S PRESSURE, NOW THAT TIME IS
  MODELLED. Because time was not the problem. See `measured-diurnal-disc-loss`
  and the tests: at 0.46 MPa the nucleus reaches equilibrium in about a day and
  its equilibrium strain is 32%, against a measured diurnal VOLUME loss of at
  most 21.6% -- and height strain is smaller still than that. The remaining
  factor is not a clock. It is that a transducer in the nucleus pulposus
  measures a hydrostatic fluid pressure, and this model spends all of it on the
  solid phase."
  ([t stress-pa height-m time-s]
   (axial-creep t stress-pa height-m time-s default-linear-strain-limit))
  ([t stress-pa height-m time-s limit]
   (let [h-a     (tissue/aggregate-modulus t)
         k       (tissue/permeability t)
         p-sw    (tissue/swelling-stress t)
         path    (two-sided-drainage-path height-m)
         diff    (poroelastic-diffusivity h-a k)
         tau     (poroelastic-time-constant path h-a k)
         eps-inf (equilibrium-strain stress-pa p-sw h-a)
         frac    (consolidation-fraction time-s tau)
         strain  (when (and eps-inf frac) (* eps-inf frac))
         base    {:tissue (:name t)
                  :source (tissue/source t)
                  :stress-pa (when (number? stress-pa) (double stress-pa))
                  :aggregate-modulus-pa h-a
                  :swelling-stress-pa p-sw
                  :permeability-m4-n-s k
                  :drainage-path-m path
                  :diffusivity-m2-s diff
                  :time-constant-s tau
                  :time-constant-h (when tau (/ tau 3600.0))
                  :time-s (when (number? time-s) (double time-s))
                  :consolidation-fraction frac
                  :equilibrium-strain eps-inf
                  :strain strain
                  :limit (double limit)
                  :missing (missing-quantities t)
                  :height-loss-m nil
                  :height-loss-mm nil}]
     (cond
       (nil? h-a)
       (assoc base :refused :no-aggregate-modulus
              :note "no confined-compression aggregate modulus on this tissue")

       (nil? k)
       (assoc base :refused :no-permeability
              :note (str "tissue " (pr-str (:name t)) " carries no hydraulic"
                         " permeability, so it has no poroelastic time constant"
                         " and this function cannot say how far the creep has"
                         " got; kotoba.biomech.disc/axial-compression answers"
                         " the equilibrium question without one"))

       (nil? p-sw)
       (assoc base :refused :no-swelling-stress
              :note (str "tissue " (pr-str (:name t)) " carries no swelling"
                         " stress; treating it as zero would attribute the whole"
                         " applied stress to matrix deformation, which is the"
                         " error this path exists to remove"))

       (nil? strain)
       (assoc base :refused :strain-not-computable
              :note "a stress, a height and a time are all required")

       (<= (double eps-inf) 0.0)
       (assoc base :refused :below-swelling-stress
              :note (str "applied stress " stress-pa " Pa does not exceed this"
                         " tissue's own swelling stress " p-sw " Pa, so the"
                         " confined-compression law says fluid flows IN; that"
                         " law was fitted in compression and is not run"
                         " backwards here"))

       (>= (double eps-inf) (double limit))
       (assoc base :refused :equilibrium-strain-beyond-linear-range
              :note (str "equilibrium strain " eps-inf " is at or past the limit "
                         limit ", so the whole trajectory including its early"
                         " points was computed with a modulus outside its"
                         " fitted range; the missing quantities are named in"
                         " :missing, and the first of them is the one that"
                         " matters -- the applied stress is an intradiscal"
                         " HYDROSTATIC PRESSURE and this model spends all of it"
                         " on the solid phase. A caller holding an"
                         " intradiscal pressure can convert it to a disc mean"
                         " stress with nucleus-pressure->disc-mean-stress and"
                         " an index it chooses; that changes the KIND of the"
                         " input, it does not validate this model"))

       :else
       (let [loss-m (* (double height-m) (double strain))]
         (assoc base
                :height-loss-m loss-m
                :height-loss-mm (* 1000.0 loss-m)
                :refused nil
                :note nil))))))
