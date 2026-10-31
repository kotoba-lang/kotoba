(ns rotor.atmosphere
  "ISA standard atmosphere, troposphere only (0-11 km) — the two properties a
  rotor solve needs: air density (thrust and power scale with it) and the speed
  of sound (which caps tip speed, and therefore RPM at a given diameter).

  A drone sized at sea level and flown at 2000 m is a different aircraft: rho
  falls ~18%, so induced velocity rises and hover power rises with it. Density
  altitude is an input here, never an assumption.

  Beyond 11 km the lapse-rate law below stops holding; `density` refuses rather
  than extrapolating (a rotorcraft is not there anyway).")

(def ^:const rho0 1.225)        ; kg/m^3   sea-level density
(def ^:const T0   288.15)       ; K        sea-level temperature
(def ^:const lapse 0.0065)      ; K/m      tropospheric lapse rate
(def ^:const gamma 1.4)         ; -        ratio of specific heats, air
(def ^:const R-air 287.05287)   ; J/(kg K) specific gas constant, dry air
(def ^:const troposphere-m 11000.0)
(def ^:const floor-m -500.0)

;; g / (lapse * R) = 9.80665 / (0.0065 * 287.05287)
(def ^:const beta 5.2558797)

(defn temperature
  "ISA temperature (K) at geopotential altitude `h` (m)."
  [h]
  (- T0 (* lapse h)))

(defn density
  "ISA density (kg/m^3) at altitude `h` (m). Throws above the troposphere
  rather than extrapolating a law that has stopped applying."
  [h]
  (when (or (> h troposphere-m) (< h floor-m))
    (throw (ex-info "altitude outside the ISA troposphere model"
                    {:altitude-m h :valid-range [floor-m troposphere-m]})))
  (* rho0 (Math/pow (- 1.0 (/ (* lapse h) T0)) (- beta 1.0))))

(defn speed-of-sound
  "ISA speed of sound (m/s) at altitude `h` (m). a = sqrt(gamma R T)."
  [h]
  (Math/sqrt (* gamma R-air (temperature h))))
