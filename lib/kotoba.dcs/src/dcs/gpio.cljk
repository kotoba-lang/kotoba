(ns dcs.gpio
  "A SIMULATED GPIO addressing model over `dcs.ports/IFieldIO`.

  This is purely an in-process addressing abstraction — pin numbers and
  modes (`:digital-in` / `:digital-out` / `:analog-in` / `:analog-out`)
  mapped onto the same tag registry a host's `IFieldIO` already serves. It
  does NOT open a real transport, does NOT talk to a real GPIO chip driver
  (no `libgpiod`, no `RPi.GPIO`, no `/dev/gpiochip*`), and there is no
  physical pin anywhere behind it — the value returned by `digital-read` or
  `analog-read` is whatever the host's `IFieldIO` (ultimately, in this
  library's own tests, an in-memory map; in a real host, potentially a
  CFD-backed digital twin) says a tag currently holds. This mirrors the
  boundary documented for the rest of this protocol-simulation layer — see
  the README's \"Protocol-simulation layer\" section.

  A GPIO header is plain data, pin-number-keyed for O(1) lookup, in the same
  style as `dcs.model`:

    {:dcs/pins {0 {:dcs/pin 0 :dcs/mode :digital-out :dcs/tag \"ALARM.RELAY\"}
                1 {:dcs/pin 1 :dcs/mode :digital-in  :dcs/tag \"START.CMD\"}
                2 {:dcs/pin 2 :dcs/mode :analog-in   :dcs/tag \"TIC-101.PV\"}}}

  Digital pins are normalized to booleans at the GPIO edge (real digital I/O
  is a logic level, not a raw process value); analog pins pass the tag's
  numeric value through unchanged (this simulator has no ADC/DAC bit-depth
  to model — see `dcs.modbus` for a layer that DOES model a real wire
  encoding, 16-bit Modbus registers)."
  (:require [dcs.ports :as ports]))

(def pin-modes
  "Allowed :dcs/mode values for a GPIO pin."
  #{:digital-in :digital-out :analog-in :analog-out})

;; --- builder (threadable, mirrors dcs.model) ---

(defn header
  "A fresh, empty GPIO header."
  []
  {:dcs/pins {}})

(defn pin-spec
  "A bare GPIO pin map (to be attached via `add-pin`). `mode` is one of
  `pin-modes`; `tag-id` is the dcs.model tag this pin reads/writes through
  `IFieldIO`. opts: {:description}."
  ([n mode tag-id] (pin-spec n mode tag-id nil))
  ([n mode tag-id opts]
   (cond-> {:dcs/pin n :dcs/mode mode :dcs/tag tag-id}
     (:description opts) (assoc :dcs/description (:description opts)))))

(defn add-pin
  "Attach `pin-map` (built via `pin-spec`) into `hdr`."
  [hdr pin-map]
  (assoc-in hdr [:dcs/pins (:dcs/pin pin-map)] pin-map))

(defn pins [hdr] (vals (:dcs/pins hdr)))
(defn pin-by-number [hdr n] (get-in hdr [:dcs/pins n]))

;; --- validation (never throws, mirrors dcs.validate) ---

(defn validate
  "Structural problems in `hdr`: unknown pin mode, or a pin with no tag.
  Never throws — returns a (possibly empty) vector of problem maps."
  [hdr]
  (vec (keep (fn [p]
               (cond
                 (not (contains? pin-modes (:dcs/mode p)))
                 {:dcs/error :unknown-pin-mode :dcs/pin (:dcs/pin p) :dcs/mode (:dcs/mode p)}

                 (nil? (:dcs/tag p))
                 {:dcs/error :missing-pin-tag :dcs/pin (:dcs/pin p)}

                 :else nil))
             (pins hdr))))

(defn valid? [hdr] (empty? (validate hdr)))

;; --- I/O (directional, like real GPIO — reading an output pin or writing
;;     an input pin is a programming error, not a silent no-op) ---

(defn- pin-or-throw [hdr n]
  (or (pin-by-number hdr n)
      (throw (ex-info "no such GPIO pin" {:dcs/pin n}))))

(defn- require-mode [p mode]
  (when (not= mode (:dcs/mode p))
    (throw (ex-info "GPIO pin is not in the required mode"
                     {:dcs/pin (:dcs/pin p) :dcs/mode (:dcs/mode p) :dcs/required mode}))))

(defn digital-read
  "Read the current logic level of a :digital-in pin as a boolean."
  [hdr io n]
  (let [p (pin-or-throw hdr n)]
    (require-mode p :digital-in)
    (boolean (ports/read-tag io (:dcs/tag p)))))

(defn digital-write!
  "Drive a :digital-out pin's logic level. `level` is coerced to boolean."
  [hdr io n level]
  (let [p (pin-or-throw hdr n)]
    (require-mode p :digital-out)
    (ports/write-tag! io (:dcs/tag p) (boolean level))
    nil))

(defn analog-read
  "Read the current value of an :analog-in pin (raw passthrough of the
  underlying tag's numeric value — no ADC bit-depth is modeled here)."
  [hdr io n]
  (let [p (pin-or-throw hdr n)]
    (require-mode p :analog-in)
    (ports/read-tag io (:dcs/tag p))))

(defn analog-write!
  "Drive an :analog-out pin's value (raw passthrough)."
  [hdr io n value]
  (let [p (pin-or-throw hdr n)]
    (require-mode p :analog-out)
    (ports/write-tag! io (:dcs/tag p) value)
    nil))
