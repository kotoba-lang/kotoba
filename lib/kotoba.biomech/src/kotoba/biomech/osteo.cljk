(ns kotoba.biomech.osteo
  "Closed-form bone mechanics (Euler-Bernoulli beam theory).
  Zero-dep, pure .cljc.

  Phase 1: analytical reference formulas for a cantilever beam under a
  point tip load — deflection and maximum bending stress, plus section
  helpers (second moment of area, extreme-fibre distance) for rectangular
  and solid circular cross-sections. These serve as verification
  references and quick structural estimates; full 3-D FEM for arbitrary
  bone geometry routes through kotoba-lang/fea in Phase 2.

  Sign convention: force, length, modulus, second moment are all positive
  scalars; the returned deflection/stress is the magnitude.")

(defn second-moment-area-rect
  "Second moment of area I [m^4] for a rectangular cross-section of width
  b [m] and height h [m], bending about the neutral axis parallel to b.
  I = b * h^3 / 12."
  [b h]
  (let [b (double b) h (double h)]
    (/ (* b h h h) 12.0)))

(defn second-moment-area-circle
  "Second moment of area I [m^4] for a solid circular cross-section of
  radius r [m]. I = pi * r^4 / 4."
  [r]
  (let [r (double r)]
    (/ (* Math/PI r r r r) 4.0)))

(defn extreme-fibre-rect
  "Distance c [m] from neutral axis to outer fibre of a rectangular section
  of height h [m]. c = h/2."
  [h] (/ (double h) 2.0))

(defn extreme-fibre-circle
  "Distance c [m] for a solid circular section of radius r [m]. c = r."
  [r] (double r))

(defn cantilever-tip-deflection
  "Tip deflection delta [m] of a cantilever beam of length L [m], Young's
  modulus E [Pa], second moment I [m^4], under a point tip load F [N].
  delta = F * L^3 / (3 * E * I)."
  [force length youngs-modulus second-moment]
  (let [force (double force) L (double length)
        E (double youngs-modulus) I (double second-moment)]
    (/ (* force L L L)
       (* 3.0 E I))))

(defn cantilever-max-bending-stress
  "Maximum bending stress sigma_max [Pa] at the fixed end of a cantilever
  under tip load F [N], length L [m], extreme-fibre distance c [m],
  second moment I [m^4]. sigma = M * c / I, M = F * L."
  [force length extreme-fibre second-moment]
  (let [force (double force) L (double length)
        c (double extreme-fibre) I (double second-moment)]
    (/ (* force L c) I)))
