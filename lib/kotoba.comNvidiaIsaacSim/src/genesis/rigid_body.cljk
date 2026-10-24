(ns genesis.rigid-body
  "Minimal free 6-DOF rigid body (sphere collider) dynamics + sequential-
  impulse contact resolution against N *static* obstacles (Projected
  Gauss-Seidel over the per-contact 1-D normal + Coulomb-friction rows).

  Scope (ADR-2607110900, M2 minimal-scope redesign, 2026-07-10): a single
  free rigid body against static obstacles only — no articulation, no
  multi-body coupling, no RNEA/CRBA. This is new code written for this
  milestone, not a `kami-genesis` port like the rest of `genesis.*`. It is
  built directly on the real `genesis.vec3` primitives and the real
  `genesis.contact/obstacle-contact` geometry query (both already ported,
  ADR-2607010930).

  Deliberately does NOT use `genesis.spatial`'s 6x6 spatial-inertia
  machinery: a sphere's inertia tensor is isotropic
  (`(2/5) * mass * radius^2 * I3`), so the general asymmetric-inertia /
  Plucker-transform apparatus `genesis.spatial` exists for has no work to
  do here — forcing it in for a single-frame, single-body case would be
  premature generality. It becomes relevant once a follow-up milestone
  extends this to articulated multi-body contact.

  Not a substitute for the Featherstone-class articulated solver that
  ADR-2607110900 originally (and wrongly) claimed already existed — see
  that ADR's Addendum (2026-07-10, 2nd) for the retraction."
  (:require [genesis.vec3 :as v3]
            [genesis.contact :as contact]))

(defn ->free-sphere
  "A free rigid body with a sphere collider of `radius`, uniform `mass`,
  at rest at world-space `pos`."
  [pos radius mass]
  {:pos pos :radius radius :mass mass
   :inertia (* 0.4 mass radius radius)
   :lin-vel v3/zero :ang-vel v3/zero})

(defn- integrate-velocity [body gravity dt]
  (update body :lin-vel v3/add (v3/scale gravity dt)))

(defn- integrate-position [body dt]
  (update body :pos v3/add (v3/scale (:lin-vel body) dt)))

(defn- point-velocity
  "World-space velocity of the material point at offset `r` from the
  body's centre of mass (world frame): v + w x r."
  [{:keys [lin-vel ang-vel]} r]
  (v3/add lin-vel (v3/cross ang-vel r)))

(defn- effective-mass-inv
  "1/m_eff along direction `d` for a contact at offset `r`: the standard
  sequential-impulse K = 1/m + d . (Iinv (r x d)) x r, specialised to the
  isotropic sphere inertia (Iinv v = v / inertia)."
  [{:keys [mass inertia]} r d]
  (let [r-cross-d (v3/cross r d)
        iinv-applied (v3/scale r-cross-d (/ 1.0 inertia))
        back-cross (v3/cross iinv-applied r)]
    (+ (/ 1.0 mass) (v3/dot d back-cross))))

(defn- apply-impulse [body r impulse]
  (-> body
      (update :lin-vel v3/add (v3/scale impulse (/ 1.0 (:mass body))))
      (update :ang-vel v3/add (v3/scale (v3/cross r impulse) (/ 1.0 (:inertia body))))))

(defn resolve-contact
  "One sequential-impulse sweep over a single contact `{:p :n :depth}`:
  normal impulse (with restitution, clamped non-negative so contacts only
  push apart) followed by a Coulomb-friction tangential impulse (clamped
  to `friction * lambda-n`)."
  [body {:keys [p n]} {:keys [restitution friction]}]
  (let [r (v3/sub p (:pos body))
        vn0 (v3/dot (point-velocity body r) n)]
    (if (>= vn0 0.0)
      body
      (let [kn (effective-mass-inv body r n)
            lambda-n (max 0.0 (/ (- (* (+ 1.0 restitution) vn0)) kn))
            body (apply-impulse body r (v3/scale n lambda-n))
            vrel (point-velocity body r)
            vt-vec (v3/sub vrel (v3/scale n (v3/dot vrel n)))
            vt-len (v3/length vt-vec)]
        (if (< vt-len 1e-9)
          body
          (let [tangent (v3/scale vt-vec (/ 1.0 vt-len))
                kt (effective-mass-inv body r tangent)
                lambda-t-raw (/ (- vt-len) kt)
                bound (* friction lambda-n)
                lambda-t (max (- bound) (min bound lambda-t-raw))]
            (apply-impulse body r (v3/scale tangent lambda-t))))))))

(defn resolve-contacts
  "Projected Gauss-Seidel: `(:iters params)` sweeps over `contacts`,
  re-reading the just-updated body velocity on every sweep (Gauss-Seidel,
  not Jacobi) so simultaneous contacts — e.g. a sphere resting in the
  corner between two planes — converge to a mutually-consistent solution."
  [body contacts params]
  (let [iters (:iters params)]
    (loop [b body i 0]
      (if (>= i iters)
        b
        (recur (reduce (fn [acc c] (resolve-contact acc c params)) b contacts)
               (inc i))))))

(defn detect-contacts
  "Contacts between the body's sphere collider and each of `obstacles`
  (a coll of `genesis.contact/obstacle-*` maps), at the body's current
  position."
  [body obstacles slop]
  (keep #(contact/obstacle-contact % 0 (:pos body) (:radius body) slop) obstacles))

(defn- baumgarte-correct
  "Nudge position along each contact normal by `baumgarte` of the
  penetration beyond `slop`, to bleed off residual numerical penetration
  without injecting energy (a position-level correction, not a velocity
  one)."
  [body contacts {:keys [baumgarte slop]}]
  (reduce (fn [b {:keys [n depth]}]
            (update b :pos v3/add (v3/scale n (* baumgarte (max 0.0 (- depth slop))))))
          body contacts))

(defn step
  "One semi-implicit-Euler + sequential-impulse step: integrate velocity
  under `gravity`, detect contacts against `obstacles`, resolve them
  (Gauss-Seidel over `(:iters params)` sweeps), integrate position, then
  apply Baumgarte position correction for the (pre-integration) penetration
  depth. `params` defaults to `genesis.contact/default-contact-params`."
  ([body gravity dt obstacles] (step body gravity dt obstacles contact/default-contact-params))
  ([body gravity dt obstacles params]
   (let [body (integrate-velocity body gravity dt)
         contacts (detect-contacts body obstacles (:slop params))
         body (resolve-contacts body contacts params)
         body (integrate-position body dt)]
     (baumgarte-correct body contacts params))))
