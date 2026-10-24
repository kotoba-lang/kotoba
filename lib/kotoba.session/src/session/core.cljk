(ns session.core
  (:require [session.model :as m]
            [session.ports :as p]))

(defn active? [s now]
  (and (= :active (:session/status s))
       (or (nil? (:session/expires-at s))
           (neg? (compare (str now) (str (:session/expires-at s)))))))

(defn revoke [s reason at]
  [(assoc s :session/status :revoked)
   (m/event s :revoked {:reason reason :at at})])

(defn refresh [s expires-at at]
  [(assoc s :session/status :active :session/expires-at expires-at :session/last-seen-at at)
   (m/event s :refreshed {:at at})])

(defn binding-map [request]
  {:session/token-binding (:token-binding request)
   :session/cookie-binding (:cookie-binding request)
   :session/header-binding (:header-binding request)
   :session/device-id (:device-id request)
   :session/ip (:ip request)})

(defn bind [s request]
  (merge s (binding-map request)))

(defn binding-problems [s request]
  (let [bindings (binding-map request)]
    (into []
          (keep (fn [[k actual]]
                  (when (and (contains? s k)
                             (some? (get s k))
                             (not= (get s k) actual))
                    {:session.problem/code :binding-mismatch
                     :session.binding/key k})))
          bindings)))

(defn valid-binding! [s request]
  (when-let [ps (seq (binding-problems s request))]
    (throw (ex-info "session binding mismatch" {:session/problems ps
                                                :session/id (:session/id s)})))
  s)

(defn expire [s reason at]
  [(assoc s :session/status :expired)
   (m/event s :expired {:reason reason :at at})])

(defn create! [store session]
  (p/put-session! store session))

(defn create-bound! [store session request]
  (create! store (bind session request)))

(defn revoke! [store session-id reason at]
  (let [s (p/get-session store session-id)]
    (when-not s
      (throw (ex-info "session not found" {:session/id session-id})))
    (let [[next event] (revoke s reason at)]
      (p/put-session! store next)
      (p/put-event! store event)
      next)))

(defn refresh! [store session-id expires-at at]
  (let [s (p/get-session store session-id)]
    (when-not s
      (throw (ex-info "session not found" {:session/id session-id})))
    (let [[next event] (refresh s expires-at at)]
      (p/put-session! store next)
      (p/put-event! store event)
      next)))

(defn touch! [store session-id request at opts]
  (let [s (p/get-session store session-id)]
    (when-not s
      (throw (ex-info "session not found" {:session/id session-id})))
    (valid-binding! s request)
    (let [idle-expires-at (:idle-expires-at opts)
          ;; absolute :session/expires-at -- same comparison active? uses,
          ;; so touch! can't silently keep extending a session active? has
          ;; already declared expired.
          absolute-expired? (and (:session/expires-at s)
                                  (not (neg? (compare (str at) (str (:session/expires-at s))))))
          idle-expired? (and idle-expires-at
                             (:session/last-seen-at s)
                             (not (neg? (compare (str at) (str idle-expires-at)))))]
      (cond
        absolute-expired?
        (let [[next event] (expire s :absolute-timeout at)]
          (p/put-session! store next)
          (p/put-event! store event)
          next)

        idle-expired?
        (let [[next event] (expire s :idle-timeout at)]
          (p/put-session! store next)
          (p/put-event! store event)
          next)

        :else
        (let [next (assoc s :session/last-seen-at at)
              event (m/event s :touched {:at at})]
          (p/put-session! store next)
          (p/put-event! store event)
          next)))))

(defn rotate! [store session-id new-session request at]
  (let [s (p/get-session store session-id)]
    (when-not s
      (throw (ex-info "session not found" {:session/id session-id})))
    (valid-binding! s request)
    (let [[revoked revoke-event] (revoke s :rotated at)
          next (-> new-session
                   (assoc :session/subject (:session/subject s)
                          :session/authn-ref (:session/authn-ref s)
                          :session/rotated-from (:session/id s)
                          :session/status :active)
                   (bind request))
          rotate-event (m/event next :rotated {:reason (:session/id s) :at at})]
      (p/put-session! store revoked)
      (p/put-event! store revoke-event)
      (p/put-session! store next)
      (p/put-event! store rotate-event)
      next)))

(defn enforce-concurrency! [store subject max-active at]
  (when-not (satisfies? p/ISessionIndex store)
    (throw (ex-info "session index not available" {:subject subject})))
  (let [active-sessions (->> (p/sessions-for-subject store subject)
                             (filter #(active? % at))
                             (sort-by #(or (:session/created-at %) "")))
        excess (max 0 (- (count active-sessions) max-active))
        to-revoke (take excess active-sessions)]
    (doseq [s to-revoke]
      (let [[next event] (revoke s :concurrency-limit at)]
        (p/put-session! store next)
        (p/put-event! store event)))
    (vec (map :session/id to-revoke))))
