(ns kotoba.webrtc.session
  "WebRTC call-signaling negotiation as a pure reducer.

  Mirrors RTCPeerConnection.signalingState/connectionState as data, and
  drives negotiation the same way kotoba-lang/koe drives voice dialog: the
  reducer decides *what should happen next* and returns it as a list of
  effects; it never performs network I/O, never touches a real
  RTCPeerConnection, and never calls a signaling transport. The host runtime
  supplies both transports (signaling channel + media transport) and
  executes the returned effects.

  Portable (.cljc) across JVM / ClojureScript / SCI / GraalVM.")

(def states
  "Valid session states."
  #{:idle :have-local-offer :have-remote-offer :connecting :connected
    :disconnected :failed :ended})

(def terminal-states
  "States from which no further transition is possible."
  #{:ended :failed})

(defn create-session
  "Construct a new call session in :idle state for call-id between local-id
  and remote-id."
  [call-id local-id remote-id]
  {:webrtc.session/call-id      call-id
   :webrtc.session/local-id     local-id
   :webrtc.session/remote-id    remote-id
   :webrtc.session/state        :idle
   :webrtc.session/local-sdp    nil
   :webrtc.session/remote-sdp   nil
   :webrtc.session/ice-candidates []})

(defn- transition
  "Return the result of moving session to next-state with the given effects
  when session is not already terminal, otherwise a no-op result."
  [session next-state effects]
  (if (contains? terminal-states (:webrtc.session/state session))
    {:session session :effects []}
    {:session (assoc session :webrtc.session/state next-state)
     :effects effects}))

(defn apply-event
  "Apply a signaling event to session, returning {:session :effects}. event
  is a map with :type and event-specific keys:

    {:type :create-offer}
      :idle -> :have-local-offer, effect [:send-offer sdp]

    {:type :receive-offer :sdp sdp}
      :idle -> :have-remote-offer, effect [:send-answer sdp]

    {:type :receive-answer :sdp sdp}
      :have-local-offer -> :connecting, effect [:start-media]

    {:type :ice-candidate :candidate c}
      appends to :webrtc.session/ice-candidates, effect [:send-ice-candidate c]

    {:type :connected}   -> :connected
    {:type :disconnected}-> :disconnected
    {:type :failed}      -> :failed, effect [:teardown-media]
    {:type :hangup}      -> :ended, effect [:teardown-media]

  Unknown event types or events invalid for the current state return the
  session unchanged with no effects."
  [session {:keys [type sdp candidate]}]
  (let [state (:webrtc.session/state session)]
    (case type
      :create-offer
      (if (= state :idle)
        (let [next (assoc session :webrtc.session/local-sdp sdp)]
          (transition next :have-local-offer [[:send-offer sdp]]))
        {:session session :effects []})

      :receive-offer
      (if (= state :idle)
        (let [next (assoc session :webrtc.session/remote-sdp sdp)]
          (transition next :have-remote-offer [[:send-answer sdp]]))
        {:session session :effects []})

      :receive-answer
      (if (= state :have-local-offer)
        (let [next (assoc session :webrtc.session/remote-sdp sdp)]
          (transition next :connecting [[:start-media]]))
        {:session session :effects []})

      :ice-candidate
      (if (contains? terminal-states state)
        {:session session :effects []}
        {:session (update session :webrtc.session/ice-candidates conj candidate)
         :effects [[:send-ice-candidate candidate]]})

      :connected    (transition session :connected [])
      :disconnected (transition session :disconnected [])
      :failed       (transition session :failed [[:teardown-media]])
      :hangup       (transition session :ended [[:teardown-media]])

      {:session session :effects []})))

(defn active?
  "True when session is neither :idle nor a terminal state."
  [session]
  (let [state (:webrtc.session/state session)]
    (not (or (= state :idle) (contains? terminal-states state)))))
