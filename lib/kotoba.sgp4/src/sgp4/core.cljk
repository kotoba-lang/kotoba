(ns sgp4.core
  "SGP4 -- the near-Earth half of the SGP4/SDP4 pair, in portable `.cljc`.

  Algorithm: Vallado, Crawford, Hujsak & Kelso, *Revisiting Spacetrack
  Report #3* (AIAA 2006-6753), WGS-72 constants, which is the model the
  published TLEs are fitted against. Using WGS-84 constants here would be
  more modern and less correct: the elements were produced by a WGS-72
  fit and the two are not interchangeable.

  ## Deep space is refused, not approximated

  `initialize` classifies an element set the way the reference does: an
  orbital period of 225 minutes or more is deep space, and needs SDP4's
  lunar-solar and resonance terms. **Those are not implemented here**, and
  the near-Earth path is not run in their place. A GEO satellite pushed
  through near-Earth SGP4 returns a position -- a wrong one, drifting by
  hundreds of kilometres within a day -- and nothing about the answer says
  so. So `initialize` returns

      {:ok? false :error :sgp4/deep-space-unsupported}

  and `propagate` on that record does the same. This covers the low-Earth
  catalogue (ISS, Starlink, the sun-synchronous imagers, the NOAA birds);
  it does not cover GEO, Molniya or GPS. Which of those a caller has is
  visible in the value, not in a comment.

  ## Errors are values

  Every entry point returns either `{:ok? true ...}` or
  `{:ok? false :error <keyword> :detail <string>}`. A propagator is called
  in a loop over a catalogue; a decayed satellite is an ordinary outcome,
  not an exceptional one.

  Positions are TEME, kilometres. Velocities are TEME, km/s. See
  `sgp4.frames` for TEME -> ECEF -> geodetic."
  (:require [sgp4.time :as t]
            [sgp4.tle :as tle]))

;; ---------------------------------------------------------------- constants

(def ^{:doc "WGS-72. `xke` is derived rather than written down, because the
  literal in Spacetrack Report #3 and the derived value differ in the last
  places and the derived one is what the reference implementation uses."}
  wgs72
  (let [mu 398600.8                                  ; km^3/s^2
        radiusearthkm 6378.135]                      ; km
    {:mu mu
     :radiusearthkm radiusearthkm
     :xke (/ 60.0 (Math/sqrt (/ (* radiusearthkm radiusearthkm radiusearthkm) mu)))
     :j2 0.001082616
     :j3 -0.00000253881
     :j4 -0.00000165597}))

(def two-pi (* 2.0 Math/PI))

(defn- err [k detail] {:ok? false :error k :detail detail})

(defn- fmod2pi
  "Floating remainder into [0, 2pi). `mod` in Clojure already returns a
  non-negative result for a positive divisor, so this is `mod` -- but the
  reference uses C `fmod`, which does not, and the difference matters at
  exactly one place (`mm` below) where a negative is then carried into
  `sin`/`cos`. Both are correct there; this is the sign-stable one."
  [x]
  (mod x two-pi))

;; ---------------------------------------------------------------- init

(defn initialize
  "Element set -> an initialized SGP4 record, or a refusal.

  Takes the map `sgp4.tle/parse` produces (angles in radians, `:no-kozai`
  in radians/minute). Everything derived once per satellite is computed
  here; `propagate` then costs no allocation beyond its own result."
  [{:keys [no-kozai ecco inclo nodeo argpo mo bstar jdsatepoch jdsatepoch-frac]
    :as tle}]
  (cond
    (nil? no-kozai) (err :sgp4/missing-elements ":no-kozai is absent")
    (not (pos? no-kozai)) (err :sgp4/non-positive-mean-motion (str no-kozai " rad/min"))
    (not (<= 0.0 ecco 0.9999999)) (err :sgp4/eccentricity-out-of-range (str "e = " ecco))
    :else
    (let [{:keys [radiusearthkm xke j2 j3 j4]} wgs72
          j3oj2 (/ j3 j2)
          x2o3 (/ 2.0 3.0)
          ;; ---- initl: recover the un-Kozai'd mean motion and semi-major axis
          eccsq (* ecco ecco)
          omeosq (- 1.0 eccsq)
          rteosq (Math/sqrt omeosq)
          cosio (Math/cos inclo)
          cosio2 (* cosio cosio)
          ak (Math/pow (/ xke no-kozai) x2o3)
          d1 (/ (* 0.75 j2 (- (* 3.0 cosio2) 1.0)) (* rteosq omeosq))
          del1 (/ d1 (* ak ak))
          adel (* ak (- 1.0
                        (/ (* del1 del1) 3.0)
                        (* del1 (+ (/ 1.0 3.0) (/ (* 134.0 del1 del1) 81.0)))))
          del2 (/ d1 (* adel adel))
          no (/ no-kozai (+ 1.0 del2))                  ; no_unkozai
          ao (Math/pow (/ xke no) x2o3)
          sinio (Math/sin inclo)
          po (* ao omeosq)
          con42 (- 1.0 (* 5.0 cosio2))
          con41 (- (- con42) cosio2 cosio2)             ; = 3cos^2 i - 1
          posq (* po po)
          rp (* ao (- 1.0 ecco))
          period-min (/ two-pi no)]
      (cond
        (>= period-min 225.0)
        (err :sgp4/deep-space-unsupported
             (str "orbital period " (Math/round period-min)
                  " min >= 225 min: this element set needs SDP4 "
                  "(lunar-solar periodics and resonance), which this "
                  "implementation does not have. Refusing rather than "
                  "running the near-Earth path on it."))

        (not (pos? rp))
        (err :sgp4/degenerate-orbit (str "perigee radius " rp " earth radii"))

        :else
        (let [;; ---- sgp4init, near-Earth branch
              ss (+ 1.0 (/ 78.0 radiusearthkm))
              qzms2t (Math/pow (/ (- 120.0 78.0) radiusearthkm) 4.0)
              isimp? (< rp (+ 1.0 (/ 220.0 radiusearthkm)))
              perige (* (- rp 1.0) radiusearthkm)
              ;; The atmospheric-drag constant is lowered for low perigees.
              sfour0 (cond (< perige 98.0) 20.0
                           (< perige 156.0) (- perige 78.0)
                           :else nil)
              qzms24 (if sfour0
                       (Math/pow (/ (- 120.0 sfour0) radiusearthkm) 4.0)
                       qzms2t)
              sfour (if sfour0 (+ 1.0 (/ sfour0 radiusearthkm)) ss)

              pinvsq (/ 1.0 posq)
              tsi (/ 1.0 (- ao sfour))
              eta (* ao ecco tsi)
              etasq (* eta eta)
              eeta (* ecco eta)
              psisq (Math/abs (- 1.0 etasq))
              coef (* qzms24 (Math/pow tsi 4.0))
              coef1 (/ coef (Math/pow psisq 3.5))
              cc2 (* coef1 no
                     (+ (* ao (+ 1.0 (* 1.5 etasq) (* eeta (+ 4.0 etasq))))
                        (* 0.375 j2 tsi (/ 1.0 psisq) con41
                           (+ 8.0 (* 3.0 etasq (+ 8.0 etasq))))))
              cc1 (* bstar cc2)
              cc3 (if (> ecco 1.0e-4)
                    (/ (* -2.0 coef tsi j3oj2 no sinio) ecco)
                    0.0)
              x1mth2 (- 1.0 cosio2)
              cc4 (* 2.0 no coef1 ao omeosq
                     (- (+ (* eta (+ 2.0 (* 0.5 etasq)))
                           (* ecco (+ 0.5 (* 2.0 etasq))))
                        (* (/ (* j2 tsi) (* ao psisq))
                           (+ (* -3.0 con41
                                 (+ (- 1.0 (* 2.0 eeta))
                                    (* etasq (- 1.5 (* 0.5 eeta)))))
                              (* 0.75 x1mth2
                                 (- (* 2.0 etasq) (* eeta (+ 1.0 etasq)))
                                 (Math/cos (* 2.0 argpo)))))))
              cc5 (* 2.0 coef1 ao omeosq
                     (+ 1.0 (* 2.75 (+ etasq eeta)) (* eeta etasq)))
              cosio4 (* cosio2 cosio2)
              temp1 (* 1.5 j2 pinvsq no)
              temp2 (* 0.5 temp1 j2 pinvsq)
              temp3 (* -0.46875 j4 pinvsq pinvsq no)
              mdot (+ no
                      (* 0.5 temp1 rteosq con41)
                      (* 0.0625 temp2 rteosq
                         (+ 13.0 (* -78.0 cosio2) (* 137.0 cosio4))))
              argpdot (+ (* -0.5 temp1 con42)
                         (* 0.0625 temp2 (+ 7.0 (* -114.0 cosio2) (* 395.0 cosio4)))
                         (* temp3 (+ 3.0 (* -36.0 cosio2) (* 49.0 cosio4))))
              xhdot1 (* (- temp1) cosio)
              nodedot (+ xhdot1
                         (* (+ (* 0.5 temp2 (- 4.0 (* 19.0 cosio2)))
                               (* 2.0 temp3 (- 3.0 (* 7.0 cosio2))))
                            cosio))
              omgcof (* bstar cc3 (Math/cos argpo))
              xmcof (if (> ecco 1.0e-4)
                      (/ (* (- x2o3) coef bstar) eeta)
                      0.0)
              nodecf (* 3.5 omeosq xhdot1 cc1)
              t2cof (* 1.5 cc1)
              ;; sgp4fix: guard the i = 180 deg singularity rather than
              ;; dividing by (1 + cos i) == 0.
              xlcof (* -0.25 j3oj2 sinio
                       (/ (+ 3.0 (* 5.0 cosio))
                          (if (> (Math/abs (+ cosio 1.0)) 1.5e-12)
                            (+ 1.0 cosio)
                            1.5e-12)))
              aycof (* -0.5 j3oj2 sinio)
              delmotemp (+ 1.0 (* eta (Math/cos mo)))
              delmo (* delmotemp delmotemp delmotemp)
              sinmao (Math/sin mo)
              x7thm1 (- (* 7.0 cosio2) 1.0)
              ;; Higher-order drag terms are only carried when the orbit is
              ;; high enough that the simplified path is not used.
              deep (when-not isimp?
                     (let [cc1sq (* cc1 cc1)
                           d2 (* 4.0 ao tsi cc1sq)
                           temp (/ (* d2 tsi cc1) 3.0)
                           d3 (* (+ (* 17.0 ao) sfour) temp)
                           d4 (* 0.5 temp ao tsi (+ (* 221.0 ao) (* 31.0 sfour)) cc1)]
                       {:d2 d2 :d3 d3 :d4 d4
                        :t3cof (+ d2 (* 2.0 cc1sq))
                        :t4cof (* 0.25 (+ (* 3.0 d3)
                                          (* cc1 (+ (* 12.0 d2) (* 10.0 cc1sq)))))
                        :t5cof (* 0.2 (+ (* 3.0 d4)
                                         (* 12.0 cc1 d3)
                                         (* 6.0 d2 d2)
                                         (* 15.0 cc1sq (+ (* 2.0 d2) cc1sq))))}))]
          {:ok? true
           :sat (merge
                 {:tle tle
                  :satnum (:satnum tle)
                  :method :near-earth
                  :period-min period-min
                  :jdsatepoch jdsatepoch
                  :jdsatepoch-frac jdsatepoch-frac
                  :gsto (t/gstime (+ jdsatepoch jdsatepoch-frac))
                  ;; mean elements at epoch
                  :no no :ecco ecco :inclo inclo :nodeo nodeo :argpo argpo
                  :mo mo :bstar bstar :ao ao
                  :isimp? isimp?
                  :con41 con41 :x1mth2 x1mth2 :x7thm1 x7thm1
                  :cc1 cc1 :cc4 cc4 :cc5 cc5
                  :mdot mdot :argpdot argpdot :nodedot nodedot :nodecf nodecf
                  :omgcof omgcof :xmcof xmcof :delmo delmo :sinmao sinmao
                  :eta eta :t2cof t2cof :xlcof xlcof :aycof aycof}
                 deep)})))))

(defn initialize-tle
  "`sgp4.tle/parse` then `initialize`, propagating the first refusal."
  ([l1 l2] (initialize-tle l1 l2 {}))
  ([l1 l2 opts]
   (let [r (tle/parse l1 l2 opts)]
     (if (:ok? r) (initialize (:tle r)) r))))

;; ---------------------------------------------------------------- propagate

(defn propagate
  "Propagate `sat` (from `initialize`) to `tsince` minutes after its epoch.

  Returns `{:ok? true :r [x y z] :v [vx vy vz] :tsince ...}` in TEME km and
  km/s, or a refusal. `tsince` may be negative.

  The refusals mirror the reference implementation's numbered errors, but
  named: `:sgp4/eccentricity-out-of-range` (1),
  `:sgp4/non-positive-mean-motion` (2), `:sgp4/negative-semi-latus-rectum`
  (4), `:sgp4/decayed` (6). Error 3 (`pl < 0` after perturbation) is folded
  into 4 -- the reference distinguishes them by where they are detected,
  not by what they mean."
  [{:keys [no ecco inclo nodeo argpo mo bstar isimp?
           con41 x1mth2 x7thm1 cc1 cc4 cc5
           mdot argpdot nodedot nodecf omgcof xmcof delmo sinmao eta
           t2cof xlcof aycof d2 d3 d4 t3cof t4cof t5cof]}
   tsince]
  (let [{:keys [radiusearthkm xke]} wgs72
        x2o3 (/ 2.0 3.0)
        vkmpersec (/ (* radiusearthkm xke) 60.0)
        t (double tsince)
        t2 (* t t)
        xmdf (+ mo (* mdot t))
        argpdf (+ argpo (* argpdot t))
        nodedf (+ nodeo (* nodedot t))
        nodem (+ nodedf (* nodecf t2))
        ;; Secular drag: the simplified path stops at the linear term.
        [mm argpm tempa tempe templ]
        (if isimp?
          [xmdf argpdf (- 1.0 (* cc1 t)) (* bstar cc4 t) (* t2cof t2)]
          (let [delomg (* omgcof t)
                delmtemp (+ 1.0 (* eta (Math/cos xmdf)))
                delm (* xmcof (- (* delmtemp delmtemp delmtemp) delmo))
                temp (+ delomg delm)
                mm (+ xmdf temp)
                argpm (- argpdf temp)
                t3 (* t2 t)
                t4 (* t3 t)]
            [mm argpm
             (- (- 1.0 (* cc1 t)) (* d2 t2) (* d3 t3) (* d4 t4))
             (+ (* bstar cc4 t) (* bstar cc5 (- (Math/sin mm) sinmao)))
             (+ (* t2cof t2) (* t3cof t3) (* t4 (+ t4cof (* t t5cof))))]))
        nm (* no 1.0)]
    (cond
      (not (pos? nm))
      (err :sgp4/non-positive-mean-motion (str "mean motion " nm " at t=" t))

      :else
      (let [am (* (Math/pow (/ xke nm) x2o3) tempa tempa)
            nm (/ xke (Math/pow am 1.5))
            em (- ecco tempe)]
        (cond
          (or (>= em 1.0) (< em -0.001))
          (err :sgp4/eccentricity-out-of-range
               (str "e = " em " at t=" t " min (drag has driven the fit "
                    "out of range; the element set is too old for this epoch)"))

          :else
          (let [em (if (< em 1.0e-6) 1.0e-6 em)
                mm (+ mm (* no templ))
                xlm (+ mm argpm nodem)
                nodem (fmod2pi nodem)
                argpm (fmod2pi argpm)
                xlm (fmod2pi xlm)
                mm (fmod2pi (- xlm argpm nodem))
                inclm inclo
                ;; long-period periodics
                axnl (* em (Math/cos argpm))
                temp (/ 1.0 (* am (- 1.0 (* em em))))
                aynl (+ (* em (Math/sin argpm)) (* temp aycof))
                xl (+ mm argpm nodem (* temp xlcof axnl))
                ;; Kepler's equation for (E + omega), Newton with the
                ;; reference's step clamp. The clamp is what makes this
                ;; converge for high-eccentricity fits; without it the
                ;; iteration oscillates instead of failing, which is worse.
                u (fmod2pi (- xl nodem))
                [eo1 sineo1 coseo1]
                (loop [eo1 u ktr 1]
                  (let [sineo1 (Math/sin eo1)
                        coseo1 (Math/cos eo1)
                        denom (- 1.0 (* coseo1 axnl) (* sineo1 aynl))
                        step (/ (+ (- u (* aynl coseo1)) (* axnl sineo1) (- eo1))
                                denom)
                        step (cond (>= step 0.95) 0.95
                                   (<= step -0.95) -0.95
                                   :else step)
                        eo1' (+ eo1 step)]
                    (if (and (>= (Math/abs step) 1.0e-12) (< ktr 10))
                      (recur eo1' (inc ktr))
                      [eo1' (Math/sin eo1') (Math/cos eo1')])))
                ecose (+ (* axnl coseo1) (* aynl sineo1))
                esine (- (* axnl sineo1) (* aynl coseo1))
                el2 (+ (* axnl axnl) (* aynl aynl))
                pl (* am (- 1.0 el2))]
            (if (neg? pl)
              (err :sgp4/negative-semi-latus-rectum (str "pl = " pl " at t=" t))
              (let [rl (* am (- 1.0 ecose))
                    rdotl (/ (* (Math/sqrt am) esine) rl)
                    rvdotl (/ (Math/sqrt pl) rl)
                    betal (Math/sqrt (- 1.0 el2))
                    temp (/ esine (+ 1.0 betal))
                    sinu (* (/ am rl) (- sineo1 aynl (* axnl temp)))
                    cosu (* (/ am rl) (+ (- coseo1 axnl) (* aynl temp)))
                    su (Math/atan2 sinu cosu)
                    sin2u (* (+ cosu cosu) sinu)
                    cos2u (- 1.0 (* 2.0 sinu sinu))
                    temp (/ 1.0 pl)
                    temp1 (* 0.5 (:j2 wgs72) temp)
                    temp2 (* temp1 temp)
                    ;; short-period periodics
                    mrt (+ (* rl (- 1.0 (* 1.5 temp2 betal con41)))
                           (* 0.5 temp1 x1mth2 cos2u))
                    su (- su (* 0.25 temp2 x7thm1 sin2u))
                    cosip (Math/cos inclm)
                    sinip (Math/sin inclm)
                    xnode (+ nodem (* 1.5 temp2 cosip sin2u))
                    xinc (+ inclm (* 1.5 temp2 cosip sinip cos2u))
                    mvt (- rdotl (/ (* nm temp1 x1mth2 sin2u) xke))
                    rvdot (+ rvdotl
                             (/ (* nm temp1
                                   (+ (* x1mth2 cos2u) (* 1.5 con41)))
                                xke))
                    ;; orientation vectors
                    sinsu (Math/sin su) cossu (Math/cos su)
                    snod (Math/sin xnode) cnod (Math/cos xnode)
                    sini (Math/sin xinc) cosi (Math/cos xinc)
                    xmx (* (- snod) cosi)
                    xmy (* cnod cosi)
                    ux (+ (* xmx sinsu) (* cnod cossu))
                    uy (+ (* xmy sinsu) (* snod cossu))
                    uz (* sini sinsu)
                    vx (- (* xmx cossu) (* cnod sinsu))
                    vy (- (* xmy cossu) (* snod sinsu))
                    vz (* sini cossu)]
                (if (< mrt 1.0)
                  (err :sgp4/decayed
                       (str "radius " (* mrt radiusearthkm) " km is below the "
                            "Earth's surface at t=" t " min: the object has "
                            "decayed, or the element set does not describe it "
                            "any more"))
                  {:ok? true
                   :tsince t
                   :r [(* mrt ux radiusearthkm)
                       (* mrt uy radiusearthkm)
                       (* mrt uz radiusearthkm)]
                   :v [(* (+ (* mvt ux) (* rvdot vx)) vkmpersec)
                       (* (+ (* mvt uy) (* rvdot vy)) vkmpersec)
                       (* (+ (* mvt uz) (* rvdot vz)) vkmpersec)]})))))))))

(defn propagate-at
  "Propagate `sat` to a Unix-epoch-milliseconds instant."
  [sat unix-ms]
  (let [[jd frac] (t/unix-ms->jd unix-ms)]
    (propagate sat (t/minutes-between (:jdsatepoch sat) (:jdsatepoch-frac sat) jd frac))))
