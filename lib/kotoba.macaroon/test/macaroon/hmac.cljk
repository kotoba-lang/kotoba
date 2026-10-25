(ns macaroon.hmac
  "A real HMAC-SHA-256 on both runtimes, injected the way production would.

  Not a stub. The chaining property this library rests on — that a caveat
  cannot be removed — is a property of a PRF, and a test double that is not
  one would let the suite pass over a construction that is not a macaroon."
  (:require [kotoba.lang.crypto :as c]
            #?(:cljs ["node:crypto" :as nc])))

(def digest-fn
  #?(:clj c/default-digest-fn
     :cljs (fn [algo data]
             (-> (nc/createHash (if (= :sha512 algo) "sha512" "sha256"))
                 (.update (js/Buffer.from (clj->js (vec data))))
                 (.digest)
                 (js/Array.from)
                 vec))))

(defn ->bytes [x]
  (cond
    (string? x) #?(:clj (vec (.getBytes ^String x "UTF-8"))
                   :cljs (vec (js/Array.from (.encode (js/TextEncoder.) x))))
    (sequential? x) (vec x)
    :else #?(:clj (vec x) :cljs (vec (js/Array.from x)))))

(defn hmac [k d] (vec (c/hmac (->bytes k) (->bytes d) digest-fn)))
