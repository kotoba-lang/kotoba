(ns rotor.solver
  "Reduced-order rotor solver (:rom-rotor) — momentum theory plus a figure of
  merit. Hover induced velocity from disc loading (vi = sqrt(T/2*rho*A)), ideal
  power T*vi, shaft power vi/FM; tip speed and Mach from RPM and radius; blade
  loading CT/sigma against the stall limit; blade mass from geometry. Turns a
  multirotor's per-rotor THRUST requirement into a sized rotor — diameter, RPM,
  shaft power and torque — which is exactly the input
  `motor.solver/size-for-power` needs.

  Two power models are carried on purpose, and they must agree:

    hover   — the designer's model: P = T*vi / FM. One number, FM, absorbs
              profile drag and non-uniform inflow.
    forward — the decomposed model: P = k_i*T*vi + P_profile*(1 + 4.65*mu^2),
              with vi from the Glauert relation so it degrades to hover at
              mu = 0.

  `hover` therefore also reports `:fm-implied` — the FM the decomposed model
  implies at the same operating point. A caller who passes an `:fm` far from
  `:fm-implied` has two models disagreeing about one rotor, and the discrepancy
  is visible rather than averaged away.

  Scope: this solver answers for ONE rotor in isolation. It does not know how
  many rotors there are, does not model rotor-on-rotor interference or ground
  effect, and does not carry airframe parasite drag (that belongs to whatever
  sizes the airframe). A blade-resolved kami-cfd solve registers a
  higher-fidelity kind on the same cae-solver contract later."
  (:require [datom.core :as d]
            [cae.solver :as cae]
            [rotor.atmosphere :as atm]))

(def ^:const pi Math/PI)
(def ^:const g 9.80665)

;; CT/sigma at which a conventional rotor blade section stalls in hover.
;; Above this the momentum-theory answer is arithmetically fine and
;; physically meaningless, so it is reported, not silently returned.
(def ^:const blade-loading-limit 0.12)

(defn- positive!
  "Refuse a non-positive input rather than returning a NaN dressed as an answer."
  [m k]
  (let [v (get m k)]
    (when-not (and (number? v) (pos? v))
      (throw (ex-info "rotor solve needs a positive value"
                      {:key k :value v})))
    (double v)))

(defn- geometry
  "Chord, solidity and blade mass from radius and the blade description."
  [{:keys [blades blade-aspect tc fill rho-blade hub-frac]
    :or {blades 2 blade-aspect 8.0 tc 0.10 fill 0.5
         rho-blade 1550.0 hub-frac 0.35}}
   r]
  (let [chord (/ r blade-aspect)
        sigma (/ (* blades chord) (* pi r))
        ;; one blade ~ a tapered box: chord x radius x thickness, part-filled
        vol   (* blades chord r tc chord fill)
        mass  (* rho-blade vol (+ 1.0 hub-frac))]
    {:chord-m chord :solidity sigma :blades blades :rotor-mass-kg mass}))

(defn hover
  "Hover solve for ONE rotor.

  case: {:thrust-N :d-rotor-m :rpm :fm :altitude-m
         :blades :blade-aspect :cd0 :k-induced :tc :fill :rho-blade :hub-frac}"
  [{:keys [fm altitude-m cd0 k-induced]
    :or {fm 0.65 altitude-m 0.0 cd0 0.012 k-induced 1.15}
    :as case}]
  (let [t     (positive! case :thrust-N)
        d     (positive! case :d-rotor-m)
        rpm   (positive! case :rpm)
        r     (/ d 2.0)
        a-disc (* pi r r)
        rho   (atm/density altitude-m)
        a-snd (atm/speed-of-sound altitude-m)
        omega (* rpm (/ (* 2.0 pi) 60.0))
        vtip  (* omega r)
        dl    (/ t a-disc)                        ; disc loading, N/m^2
        vi    (Math/sqrt (/ t (* 2.0 rho a-disc)))
        p-id  (* t vi)                            ; ideal induced power, W
        p-sh  (/ p-id fm)                         ; shaft power, W
        torque (/ p-sh omega)
        {:keys [chord-m solidity rotor-mass-kg blades]} (geometry case r)
        ct    (/ t (* rho a-disc vtip vtip))
        bl    (/ ct solidity)
        p-prof (* (/ (* solidity cd0) 8.0) rho a-disc vtip vtip vtip)
        fm-imp (/ p-id (+ (* k-induced p-id) p-prof))]
    {:thrust-N t :d-rotor-m d :rpm rpm :radius-m r :disc-area-m2 a-disc
     :rho-kg-m3 rho :disc-loading-N-m2 dl
     :v-induced-mps vi :p-ideal-W p-id :p-shaft-W p-sh :torque-Nm torque
     :power-loading-N-per-W (/ t p-sh)
     :g-per-W (* 1000.0 (/ (/ t g) p-sh))          ; the number prop tables print
     :tip-speed-mps vtip :tip-mach (/ vtip a-snd)
     :blades blades :chord-m chord-m :solidity solidity
     :Ct ct :blade-loading bl
     :stalled? (> bl blade-loading-limit)
     :p-profile-W p-prof :fm fm :fm-implied fm-imp
     :rotor-mass-kg rotor-mass-kg
     :solver :rom-rotor}))

(defn size-for-thrust
  "INVERSE sizing: given the thrust one rotor must make and a target disc
  loading, solve the rotor that makes it. A = T/DL fixes the diameter; the tip
  speed (given directly, or as a Mach fraction of the local speed of sound)
  fixes the RPM. This is what a multirotor design pass needs — it has a mass
  budget and a rotor count, not a diameter.

  Lower disc loading is a bigger, quieter, more efficient rotor that may not
  fit; the caller owns that trade, so DL is an input, not a default dressed as
  physics."
  [{:keys [thrust-N disc-loading-N-m2 tip-speed-mps tip-mach altitude-m]
    :or {disc-loading-N-m2 100.0 tip-mach 0.55 altitude-m 0.0}
    :as case}]
  (let [t     (positive! case :thrust-N)
        dl    (positive! {:disc-loading-N-m2 disc-loading-N-m2} :disc-loading-N-m2)
        a-disc (/ t dl)
        d     (Math/sqrt (/ (* 4.0 a-disc) pi))
        r     (/ d 2.0)
        vtip  (or tip-speed-mps (* tip-mach (atm/speed-of-sound altitude-m)))
        rpm   (/ (* vtip 60.0) (* 2.0 pi r))]
    (assoc (hover (assoc case :d-rotor-m d :rpm rpm :thrust-N thrust-N))
           :sized-for {:thrust-N t :disc-loading-N-m2 dl :tip-speed-mps vtip})))

(defn- glauert-vi
  "Induced velocity in forward flight: the root of vi = T / (2*rho*A*sqrt(V^2 + vi^2)).
  Damped fixed point seeded at the hover value — monotone and quick for every
  physical case; refuses instead of returning a half-converged number."
  [t rho a-disc v]
  (let [vh (Math/sqrt (/ t (* 2.0 rho a-disc)))]
    (loop [vi vh n 0]
      (let [vi' (* 0.5 (+ vi (/ t (* 2.0 rho a-disc
                                     (Math/sqrt (+ (* v v) (* vi vi)))))))]
        (cond
          (< (Math/abs (- vi' vi)) 1.0e-10) vi'
          (>= n 200) (throw (ex-info "Glauert induced velocity did not converge"
                                     {:thrust-N t :v-mps v :last vi'}))
          :else (recur vi' (inc n)))))))

(defn forward
  "Edgewise (forward-flight) solve for ONE rotor, by decomposition:
  P = k_i*T*vi + P_profile*(1 + 4.65*mu^2). At :v-mps 0 this reduces to the
  hover decomposition, which is what `:fm-implied` reports.

  Rotor only: airframe parasite drag is NOT here."
  [{:keys [v-mps cd0 k-induced]
    :or {v-mps 0.0 cd0 0.012 k-induced 1.15}
    :as case}]
  (let [h      (hover case)
        rho    (:rho-kg-m3 h)
        a-disc (:disc-area-m2 h)
        vtip   (:tip-speed-mps h)
        t      (:thrust-N h)
        vi     (glauert-vi t rho a-disc v-mps)
        mu     (/ v-mps vtip)
        p-ind  (* k-induced t vi)
        p-prof (* (/ (* (:solidity h) cd0) 8.0) rho a-disc vtip vtip vtip
                  (+ 1.0 (* 4.65 mu mu)))
        p-sh   (+ p-ind p-prof)
        omega  (* (:rpm h) (/ (* 2.0 pi) 60.0))]
    (assoc h
           :v-mps v-mps :advance-ratio mu
           :v-induced-mps vi
           :p-induced-W p-ind :p-profile-W p-prof
           :p-shaft-W p-sh :torque-Nm (/ p-sh omega)
           :power-loading-N-per-W (/ t p-sh)
           :g-per-W (* 1000.0 (/ (/ t g) p-sh))
           :model :decomposed)))

(defmethod cae/solve :rom-rotor [case]
  (cond
    (:disc-loading-N-m2 case) (size-for-thrust case)
    (pos? (or (:v-mps case) 0)) (forward case)
    :else (hover case)))

(defn run
  "Solve and datafy onto the kotoba Datom log, as every kami-engine solver does."
  [case]
  (let [r   (cae/solve (assoc-in case [:solver :kind] :rom-rotor))
        cid (or (:case/id case) "rotor-0")
        ent (d/entity "rotor" :RotorRun cid
                      {:thrustN  (Math/round (double (:thrust-N r)))
                       :diaMm    (Math/round (* 1000.0 (:d-rotor-m r)))
                       :rpm      (Math/round (double (:rpm r)))
                       :shaftW   (Math/round (double (:p-shaft-W r)))
                       :torqueMNm (Math/round (* 1000.0 (:torque-Nm r)))
                       :gPerW    (Math/round (* 100.0 (:g-per-W r)))
                       :tipMach  (Math/round (* 1000.0 (:tip-mach r)))
                       :massG    (Math/round (* 1000.0 (:rotor-mass-kg r)))
                       :stalled  (if (:stalled? r) 1 0)})
        led (d/log [ent])]
    (assoc r :datoms (:datoms led) :datom-count (:count led))))
