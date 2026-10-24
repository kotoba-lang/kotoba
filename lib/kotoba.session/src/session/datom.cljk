(ns session.datom)

(defn- event-id [event]
  (str (:session.event/session-id event) ":" (name (:session.event/type event)) ":"
       (:session.event/at event)))

(defn session-datoms [session]
  [{:db/id [:session/id (:session/id session)]
    :session/id (:session/id session)
    :session/subject (:session/subject session)
    :session/status (:session/status session)
    :session/authn-ref (:session/authn-ref session)
    :session/device-id (:session/device-id session)
    :session/ip (:session/ip session)
    :session/token-binding (:session/token-binding session)
    :session/cookie-binding (:session/cookie-binding session)
    :session/header-binding (:session/header-binding session)
    :session/created-at (:session/created-at session)
    :session/last-seen-at (:session/last-seen-at session)
    :session/rotated-from (:session/rotated-from session)
    :session/expires-at (:session/expires-at session)}])

(defn event-datoms [event]
  [{:db/id [:session.event/id (event-id event)]
    :session.event/id (event-id event)
    :session.event/session-id (:session.event/session-id event)
    :session.event/type (:session.event/type event)
    :session.event/at (:session.event/at event)
    :session.event/reason (:session.event/reason event)}])
