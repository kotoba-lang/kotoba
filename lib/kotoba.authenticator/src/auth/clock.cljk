(ns auth.clock
  "The one wall-clock seam, kept out of the pure OTP core so tests stay
  deterministic (they pass fixed Unix timestamps straight to auth.otp).")

(defn now-ms []
  #?(:clj (System/currentTimeMillis)
     :cljs (.now js/Date)))

(defn now-seconds []
  (quot (now-ms) 1000))
