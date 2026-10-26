(ns browser.script-engine
  "Long-lived page script engine lifecycle for browser sessions."
  (:require [browser.compat.quickjs-execution :as execution]))

(defn missing-engine-factory
  [_]
  {:script-engine/error :script-engine/missing-engine-factory})

(defn empty-manager
  [{:keys [kind engine-factory dispose-fn] :as opts}]
  {:script-engine/kind (or kind :quickjs)
   :script-engine/status :empty
   :script-engine/engine nil
   :script-engine/pending nil
   :script-engine/engine-factory (or engine-factory missing-engine-factory)
   :script-engine/dispose-fn (or dispose-fn execution/dispose-engine)
   :script-engine/meta (dissoc opts :kind :engine-factory :dispose-fn)})

(defn manager
  [session]
  (or (:browser.session/script-engine session)
      (empty-manager {})))

#?(:cljs
   (defn- abort-controller []
     (when (exists? js/AbortController)
       (js/AbortController.))))

#?(:clj
   (defn- abort-controller []
     (atom {:aborted? false})))

#?(:cljs
   (defn- abort-signal [controller]
     (when controller
       (.-signal controller))))

#?(:clj
   (defn- abort-signal [controller]
     controller))

#?(:cljs
   (defn abort-controller! [controller reason]
     (when controller
       (try
         (.abort controller (name reason))
         (catch :default _
           (.abort controller))))))

#?(:clj
   (defn abort-controller! [controller reason]
     (when controller
       (swap! controller assoc :aborted? true :reason reason))))

#?(:cljs
   (defn aborted? [signal]
     (boolean (and signal (.-aborted signal)))))

#?(:clj
   (defn aborted? [signal]
     (boolean (:aborted? @signal))))

#?(:cljs
   (defn- promise-like?
     [x]
     (and x (fn? (.-then x)))))

#?(:clj
   (defn- promise-like?
     [_]
     false))

#?(:cljs
   (defn- error-value
     [error]
     (or (some-> ^js error .-message) error)))

#?(:clj
   (defn- error-value
     [error]
     error))

(defn ready?
  [session]
  (execution/engine-ready? (get-in session [:browser.session/script-engine :script-engine/engine])))

(defn next-token
  [session]
  (let [m (manager session)]
    (inc (or (:script-engine/next-token m) 0))))

(defn begin-start!
  [session]
  (let [m (manager session)
        token (next-token session)
        generation (:browser.session/page-generation session)
        controller (abort-controller)
        signal (abort-signal controller)
        session-with-signal (cond-> session
                              signal (assoc :browser.session/abort-signal signal))
        engine-or-promise ((:script-engine/engine-factory m) session-with-signal)
        pending {:script-engine/token token
                 :script-engine/generation generation
                 :script-engine/abort-controller controller
                 :script-engine/abort-signal signal
                 :script-engine/value engine-or-promise}]
    {:session (assoc session :browser.session/script-engine
                     (assoc m
                            :script-engine/status :pending
                            :script-engine/pending pending
                            :script-engine/next-token token))
     :token token
     :generation generation
     :engine-or-promise engine-or-promise}))

(defn- pending-matches?
  [session token generation]
  (let [pending (get-in session [:browser.session/script-engine :script-engine/pending])]
    (and (= token (:script-engine/token pending))
         (= generation (:script-engine/generation pending))
         (= generation (:browser.session/page-generation session)))))

(defn complete-start!
  [session {:keys [token generation engine]}]
  (let [m (manager session)]
    (if (pending-matches? session token generation)
      (assoc session :browser.session/script-engine
             (assoc m
                    :script-engine/status :ready
                    :script-engine/engine engine
                    :script-engine/pending nil
                    :script-engine/generation generation))
      (let [dispose-fn (:script-engine/dispose-fn m)]
        (when engine
          (dispose-fn engine))
        (update session :browser.session/script-engine
                (fn [m]
                  (let [pending-token (get-in m [:script-engine/pending :script-engine/token])
                        same-pending? (= token pending-token)]
                    (cond-> (assoc m :script-engine/stale-completions
                                   (conj (vec (:script-engine/stale-completions m))
                                         {:script-engine/token token
                                          :script-engine/generation generation}))
                      same-pending? (assoc :script-engine/status :empty
                                           :script-engine/pending nil)))))))))

(defn fail-start!
  [session {:keys [token generation error]}]
  (let [m (manager session)]
    (if (pending-matches? session token generation)
      (assoc session :browser.session/script-engine
             (assoc m
                    :script-engine/status :error
                    :script-engine/error error
                    :script-engine/pending nil
                    :script-engine/generation generation))
      session)))

(defn abort-pending!
  [session reason]
  (let [m (manager session)
        pending (:script-engine/pending m)]
    (if pending
      (do
        (abort-controller! (:script-engine/abort-controller pending) reason)
        (assoc session :browser.session/script-engine
               (assoc m
                      :script-engine/status :empty
                      :script-engine/pending nil
                      :script-engine/aborted-starts
                      (conj (vec (:script-engine/aborted-starts m))
                            (assoc pending :script-engine/abort-reason reason)))))
      session)))

(defn ensure!
  "Ensure a session owns a script engine.

  On the JVM this returns an updated session. In ClojureScript, if the engine
  factory returns a Promise, this returns a Promise of the updated session while
  marking the immediate session state as pending through the pending handle.

  If that Promise REJECTS (a real, reachable case -- e.g. the WASM binary
  fails to load), the returned Promise still resolves (never rejects) with
  the session transitioned to :script-engine/status :error via
  fail-start!, mirroring browser.script-scheduler/start!'s own
  swallow-the-rejection-into-a-properly-marked-session convention. Without
  this, a rejection would propagate as an unhandled rejection on the
  Promise this fn itself returns, and -- independent of whether the
  caller's own code happens to catch that -- fail-start! would never run,
  permanently stranding the session at :script-engine/status :pending
  (since ensure!'s own :pending case is a no-op, this would block every
  future call to ensure! on this session from ever attempting to start a
  new engine again, even after the caller notices the failure and wants to
  retry)."
  [session]
  (let [m (manager session)]
    (case (:script-engine/status m)
      :ready session
      :pending session
      (let [{:keys [session token generation engine-or-promise]} (begin-start! session)]
        (if (promise-like? engine-or-promise)
          (.then engine-or-promise
                 (fn [engine]
                   (complete-start! session {:token token
                                             :generation generation
                                             :engine engine}))
                 (fn [error]
                   (fail-start! session {:token token
                                        :generation generation
                                        :error (error-value error)})))
          (complete-start! session {:token token
                                    :generation generation
                                    :engine engine-or-promise}))))))

(defn mark-pending
  [session pending]
  (assoc session :browser.session/script-engine
         (assoc (manager session)
                :script-engine/status :pending
                :script-engine/pending pending)))

(defn dispose!
  [session]
  (let [m (manager session)
        dispose-fn (:script-engine/dispose-fn m)
        engine (:script-engine/engine m)
        disposed (if engine (dispose-fn engine) engine)]
    (assoc session :browser.session/script-engine
           (assoc m
                  :script-engine/status :disposed
                  :script-engine/engine disposed
                  :script-engine/pending nil))))
