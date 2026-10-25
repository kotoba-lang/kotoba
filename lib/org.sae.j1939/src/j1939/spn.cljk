(ns j1939.spn
  "Suspect Parameter Number decoding for a small, deliberately narrow set
  of PGNs — the ones cited widely enough in J1939 tooling and tutorials
  (Vector, Kvaser, and every OBD/telematics writeup covering engine data)
  that getting the scaling wrong here would be an embarrassment rather
  than an excuse. This is not a general SPN/PGN database — SAE J1939-71
  defines several hundred SPNs across dozens of PGNs, and reimplementing
  that whole table from memory, most of it unverifiable without the paid
  standard in hand, is exactly the kind of untested completeness
  `org-modbus`'s README warns against.

  Every scaling formula below follows J1939's universal convention for a
  linear parameter: `physical = raw * resolution + offset`, and a raw
  value of all-1-bits (0xFF for a 1-byte field, 0xFFFF for 2 bytes) means
  \"not available\" (SAE J1939-71 general data-field conventions) —
  decoded here as `nil`, never as a bogus physical value.")

(defn- rd16 [b0 b1] (bit-or (bit-and b0 0xFF) (bit-shift-left (bit-and b1 0xFF) 8)))

;; ── PGN 61444, EEC1 (Electronic Engine Controller 1) ────────────────────────
;; Byte layout followed here (bytes 1-indexed per J1939 convention, i.e.
;; byte 1 = data[0]):
;;   byte 2  SPN 512  Driver's Demand Engine - Percent Torque, 1 %/bit, -125% offset
;;   byte 3  SPN 513  Actual Engine - Percent Torque,          1 %/bit, -125% offset
;;   bytes 4-5 SPN 190 Engine Speed, little-endian, 0.125 rpm/bit, 0 offset
;; Byte 1 (SPN 899, Engine Torque Mode, a 4-bit code) and bytes 6-8 (source
;; address of the controlling device, starter mode, and a second torque
;; field) are in the standard but not decoded here — this library only
;; implements the three fields it is confident are correct.

(def pgn-eec1 61444)

(defn decode-eec1
  "8 EEC1 data bytes -> `{:driver-demand-percent-torque :actual-engine-percent-torque
  :engine-speed-rpm}`, each `nil` when its raw field is all-1-bits
  (\"not available\")."
  [bs]
  (let [bs (vec bs)]
    (if (not= 8 (count bs))
      [:error :j1939/bad-eec1-length (count bs)]
      (let [dd (bit-and (nth bs 1) 0xFF)
            ae (bit-and (nth bs 2) 0xFF)
            rpm-raw (rd16 (nth bs 3) (nth bs 4))]
        [:ok {:driver-demand-percent-torque (when (not= dd 0xFF) (- dd 125))
              :actual-engine-percent-torque (when (not= ae 0xFF) (- ae 125))
              :engine-speed-rpm (when (not= rpm-raw 0xFFFF) (* rpm-raw 0.125))}]))))

;; ── PGN 65262, ET1 (Engine Temperature 1) ───────────────────────────────────
;; Byte layout followed here:
;;   byte 1  SPN 110  Engine Coolant Temperature, 1 degC/bit, -40 degC offset
;;   byte 2  SPN 174  Engine Fuel Temperature 1,  1 degC/bit, -40 degC offset
;; Bytes 3-8 (oil/turbo-oil temperature, intercooler temperature and
;; thermostat opening) are in the standard but not decoded here.

(def pgn-et1 65262)

(defn decode-et1
  "8 ET1 data bytes -> `{:engine-coolant-temp-c :engine-fuel-temp-1-c}`."
  [bs]
  (let [bs (vec bs)]
    (if (not= 8 (count bs))
      [:error :j1939/bad-et1-length (count bs)]
      (let [coolant (bit-and (nth bs 0) 0xFF)
            fuel (bit-and (nth bs 1) 0xFF)]
        [:ok {:engine-coolant-temp-c (when (not= coolant 0xFF) (- coolant 40))
              :engine-fuel-temp-1-c (when (not= fuel 0xFF) (- fuel 40))}]))))
