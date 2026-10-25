(ns keydist
  "What each root-key distribution costs, computed rather than asserted.

  The unit is **fetches per verification**, because on an edge a fetch is a
  round trip and everything else is noise beside it. The parameters are
  stated so the answer can be recomputed with different ones rather than
  believed.

  The decisive column is not cost at all — it is what a compromise of the
  distribution point buys an attacker — but that column is a property, not a
  number, so it is printed beside the arithmetic rather than folded into it."
  (:require [kotoba.lang.text :as str]))

(def params
  {:verifications-per-month 1000000
   :rotations-per-year 4          ; a quarterly rotation
   :isolate-lifetime-min 30       ; a Worker isolate's practical lifetime
   :isolates-per-day 400          ; cold starts across colos
   :kv-cache-ttl-s 60})           ; what you would set on a mutable lookup

(defn- per-month [{:keys [isolates-per-day]}] (* isolates-per-day 30))

(defn fetches-per-month
  "How many times the edge must go and ask, per month."
  [option {:keys [verifications-per-month rotations-per-year kv-cache-ttl-s] :as p}]
  (case option
    ;; Compiled into the bundle. Nothing is fetched, ever.
    :baked 0
    ;; A mutable lookup with a TTL: every isolate re-reads every TTL window
    ;; for as long as it lives.
    :kv (* (per-month p) (/ (* 30 60) kv-cache-ttl-s))
    ;; An HTTPS document, cached per isolate for its lifetime.
    :did-web (per-month p)
    ;; Same transport, but the log is append-only and each record is
    ;; immutable, so an isolate re-reads only when the tip moves.
    :did-webvh (+ (per-month p) (/ (* rotations-per-year (per-month p)) 12))
    ;; Records are content-addressed and immutable: an isolate fetches the
    ;; set once, and again only when a rotation adds one.
    :signed-log (+ (per-month p) (/ (* rotations-per-year 1.0) 12))))

(def properties
  {:baked {:rotation "redeploy every edge" :verifiable-rotation? false
           :compromise "bundle/CI: silently swap the key for everyone"
           :adds "nothing"}
   :kv {:rotation "one write" :verifiable-rotation? false
        :compromise "KV writer: silently swap the key for everyone"
        :adds "a mutable store on the auth path"}
   :did-web {:rotation "publish a document" :verifiable-rotation? false
             :compromise "DNS or the web host: silently swap the key"
             :adds "DNS + HTTPS on the auth path"}
   :did-webvh {:rotation "append a signed entry" :verifiable-rotation? true
               :compromise "host: withhold or serve stale — cannot introduce a key"
               :adds "DNS + HTTPS on the auth path"}
   :signed-log {:rotation "append a signed record" :verifiable-rotation? true
                :compromise "host: withhold or serve stale — cannot introduce a key"
                :adds "nothing (the shape signed-head/IPNS/kototama already use)"}})

(defn -main []
  (println "parameters:" (pr-str params))
  (println (str "verifications/month: " (:verifications-per-month params)))
  (println)
  (println (str/join "\t" ["option" "fetches/mo" "per 1M verifications" "verifiable rotation" "a compromised distribution point can"]))
  (doseq [o [:baked :kv :did-web :did-webvh :signed-log]]
    (let [f (fetches-per-month o params)
          per-verification (/ f (:verifications-per-month params))]
      (println (str/join "\t"
                         [(name o)
                          (js/Math.round f)
                          (str (.toFixed (* per-verification 1000000) 0))
                          (if (:verifiable-rotation? (get properties o)) "YES" "no")
                          (:compromise (get properties o))]))))
  (println)
  (println "note: :baked is cheapest and cannot rotate; :kv is the most expensive")
  (println "      AND unverifiable, which is the combination worth avoiding.")
  (println "      The two verifiable options cost the same order; one of them")
  (println "      adds DNS to the auth path and the other adds nothing new."))

(-main)
