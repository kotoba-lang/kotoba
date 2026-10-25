(ns live-check
  "Live SigV4 proof against a real S3-compatible service. READ ONLY —
  a signature that is wrong returns 403, so listing is a complete proof of
  the whole ladder without writing a byte into anyone's bucket."
  (:require [kura.node.host-node :as host]
            [kura.node.s3 :as s3]))

(def key-id (or js/process.env.B2_KEY_ID (aget js/process.argv 2)))
(def secret (or js/process.env.B2_APP_KEY (aget js/process.argv 3)))
(def bucket (or js/process.env.B2_BUCKET (aget js/process.argv 4)))
(def host- "s3.us-west-004.backblazeb2.com")

(defn -main []
  (-> (host/signed-request
       {:http (host/node-http) :crypto (host/node-crypto)
        :key-id key-id :secret secret
        :region "us-west-004" :service "s3"
        :endpoint (str "https://" host-) :host host-
        :bucket bucket :key "" :method :get
        :query {"list-type" "2" "max-keys" "1"}})
      (.then (fn [{:keys [status body]}]
               (let [txt (.toString (js/Buffer.from body) "utf8")]
                 (println "status:" status)
                 (cond
                   (= 200 status)
                   (do (println "SIGV4 OK — service accepted the signature")
                       (println "response head:" (subs txt 0 (min 200 (count txt)))))
                   (= 403 status)
                   (println "SIGNATURE REJECTED:" (subs txt 0 (min 400 (count txt))))
                   :else
                   (println "unexpected:" (subs txt 0 (min 400 (count txt))))))))
      (.catch (fn [e] (println "transport error:" (.-message e))))))
(-main)
