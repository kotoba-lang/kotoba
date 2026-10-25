(ns shitsuke.re-frame.core
  "Host-independent re-frame seam.

  App code requires `[shitsuke.re-frame.core :as rf]` (NOT `re-frame.core`
  directly) so the SAME code runs on:
    :cljs browser build → real re-frame 1.4.3 (reagent reactions, async queue)
    :clj  JVM SSR / tests → shitsuke.re-frame mini runtime (synchronous atoms)

  Portable contract (the subset app code may use — pinned by test/re_frame_test):
    reg-event-db, reg-sub, dispatch, dispatch-sync, subscribe, clear!, app-db.
  App code MUST NOT use: reg-event-fx, reg-fx, reg-cofx, inject-cofx,
  interceptors, subscription chaining (<-). Those are not in the mini runtime
  and would break JVM SSR / WASM hosts.

  A THIRD host now sits behind the same contract: `install-guest!` registers
  handlers whose bodies are a Kotoba module compiled by amu, so the handlers
  move out of ClojureScript while `rf/dispatch` and `rf/subscribe` call sites
  do not move at all."
  (:require [shitsuke.kotoba.guest :as guest])
  #?(:clj  (:require [shitsuke.re-frame :as sr]))
  #?(:cljs (:require [re-frame.core :as rframe]
                     [re-frame.db :as rfdb])))

;; reg-event-db / reg-sub are plain vars here so callers can use the same
;; rf/reg-event-db form from both portable CLJC registration functions and
;; browser CLJS builds.
#?(:clj
   (do
     (def reg-event-db sr/reg-event-db)
     (def reg-sub       sr/reg-sub)
     (def dispatch-sync sr/dispatch-sync)
     (def subscribe     sr/subscribe)
     (def app-db        sr/app-db))
   :cljs
   (do
     (def reg-event-db rframe/reg-event-db)
     (def reg-sub       rframe/reg-sub)
     (def dispatch-sync rframe/dispatch-sync)
     (def subscribe     rframe/subscribe)
     (def app-db        rfdb/app-db)))

;; --- guest effects --------------------------------------------------------
;;
;; A Kotoba handler returns `{:db .. :fx [[id value] ...]}`: the next db and an
;; ORDERED list of inert effects. Performing them is this side's authority.
;;
;; Only `:dispatch` is performed by default, and the two hosts have to do it
;; differently -- which is the whole reason this seam exists:
;;
;;   :cljs real re-frame's dispatch is QUEUED, so dispatching from inside a
;;         handler is ordinary and safe.
;;   :clj  the mini runtime's dispatch is synchronous and runs inside
;;         `swap!`, so dispatching from inside a handler would nest one swap
;;         in another. The effect is queued here and drained by `dispatch`
;;         after the handler has returned.
;;
;; Any other effect id must be given a performer explicitly. An unknown effect
;; id throws rather than being dropped: an effect the app asked for and nobody
;; performed is the failure this data shape exists to prevent.

(defonce ^:private pending-fx (atom []))

(defn- default-performers []
  #?(:clj  {:dispatch (fn [event] (swap! pending-fx conj event))}
     :cljs {:dispatch (fn [event] (rframe/dispatch event))}))

(defn- perform-fx! [performers fx]
  (doseq [effect fx]
    (let [[id value] effect
          f (get performers id)]
      (when-not f
        (throw (ex-info "no performer for effect" {:effect-id id :effect effect})))
      (f value))))

#?(:clj
   (defn dispatch
     "Synchronous in the mini runtime. Drains any effects a Kotoba handler
     asked for after the handler has returned."
     [event]
     (sr/dispatch event)
     (loop [n 0]
       (let [queued (first @pending-fx)]
         (when queued
           (when (> n 64)
             (throw (ex-info "guest effect dispatch did not settle" {:pending @pending-fx})))
           (swap! pending-fx subvec 1)
           (sr/dispatch queued)
           (recur (inc n)))))
     nil)
   :cljs
   (def dispatch rframe/dispatch))

(defn clear! []
  (reset! pending-fx [])
  #?(:clj  (sr/clear!)
     :cljs (reset! rfdb/app-db {})))

;; --- the Kotoba guest -----------------------------------------------------

(defn install-guest!
  "Register the event ids and subscription ids a Kotoba guest owns.

  `g` is a `shitsuke.kotoba.guest/guest`. `:events` and `:queries` are the ids
  the guest handles; ids not listed keep whatever cljs handler they had, so a
  component can be moved across one id at a time.

  After this, `(rf/dispatch [:counter/inc])` and `@(rf/subscribe [:counter/count])`
  run inside the guest and nothing at the call site says so.

  Fails closed on an empty registration: installing nothing would leave every
  dispatch answering exactly as it did before, which is indistinguishable from
  a guest that works."
  ([g] (install-guest! g {}))
  ([g {:keys [events queries performers]}]
   (when (and (empty? events) (empty? queries))
     (throw (ex-info "install-guest! was given no event or query ids to install"
                     {:events events :queries queries})))
   (let [performers (merge (default-performers) performers)]
     (doseq [id events]
       (reg-event-db id
                     (fn [db event]
                       (let [answer (guest/handle g db event)]
                         (perform-fx! performers (:fx answer))
                         (:db answer)))))
     (doseq [id queries]
       (reg-sub id (fn [db q] (guest/query g db q)))))
   {:events (set events) :queries (set queries)}))

(defn init-db!
  "Reset app-db to the guest's `init`. The db is ordinary Clojure data, so
  everything that already reads app-db keeps reading it."
  [g]
  (reset! app-db (guest/init g))
  nil)
