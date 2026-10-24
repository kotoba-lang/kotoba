(ns macos-inventory.cli
  "Dump the inventory. Read-only; no probe here can prompt."
  (:require [kotoba.lang.text :as str]
            [macos-inventory.host :as h]))

(defn -main [& argv]
  (let [argv (vec argv)
        edn? (some #{"--edn"} argv)
        inv (h/inventory {:signatures? (not (some #{"--no-signatures"} argv))})]
    (if edn?
      (prn inv)
      (do
        (println)
        (doseq [[k label] [[:launchd "launchd jobs"]
                           [:login-items "login items"]
                           [:config-profiles "config profiles"]
                           [:system-extensions "system extensions"]
                           [:kexts "third-party kexts"]
                           [:browser-extensions "browser extensions"]
                           [:tcc-grants "TCC grant holders"]
                           [:listening "listening processes"]
                           [:installed-apps "installed apps"]]]
          (println (str "  " (str/join "" (repeat (max 0 (- 22 (count label))) " ")) label)
                   (count (get inv k))))
        (println)
        (println "  gatekeeper           " (name (:status (:gatekeeper inv))))
        (println "  XProtect             " (or (:version (:xprotect inv)) "unknown"))
        (println)
        (println "  coverage:")
        (doseq [[surface {:keys [status detail]}] (sort-by key (:coverage inv))]
          (println "   " (name surface) (str "[" (name status) "]") (or detail "")))
        (println)))))
