(ns kotoba.webrtc
  "WebRTC ICE candidates and SDP session/media descriptions — pure data
  contracts.

  A kotoba-lang capability library. No network, no I/O, no codec. Models the
  records a WebRTC signaling peer exchanges: ICE (RFC 8445) candidates and
  SDP (RFC 8866) session/media descriptions.

  The library models records, not the wire format. SDP on the wire is a
  line-oriented text protocol (v=, o=, m=, a=, ...) and ICE candidates are
  encoded as `a=candidate:` attribute lines; here both are EDN so a
  PolicyGovernor, host runtime, or test harness can reason structurally
  without a parser.

  Portable (.cljc) across JVM / ClojureScript / SCI / GraalVM.")

;; ---------------------------------------------------------------------------
;; ICE candidate (RFC 8445 §15.1)
;; ---------------------------------------------------------------------------

(def candidate-types
  "Valid ICE candidate types."
  #{:host :srflx :prflx :relay})

(def transports
  "Valid ICE candidate transport protocols."
  #{:udp :tcp})

(defn ice-candidate
  "Construct an ICE candidate record. component is 1 (RTP) or 2 (RTCP).
  transport is :udp or :tcp. priority is a non-negative integer. address/port
  are the candidate's transport address. cand-type is one of
  candidate-types. related-address/related-port are present for :srflx,
  :prflx and :relay candidates. Returns nil when a required field is
  malformed."
  [{:keys [foundation component transport priority address port cand-type
           related-address related-port]}]
  (when (and (string? foundation) (seq foundation)
             (contains? #{1 2} component)
             (contains? transports transport)
             (integer? priority) (not (neg? priority))
             (string? address) (seq address)
             (integer? port) (< 0 port 65536)
             (contains? candidate-types cand-type))
    {:webrtc/foundation       foundation
     :webrtc/component        component
     :webrtc/transport        transport
     :webrtc/priority         priority
     :webrtc/address          address
     :webrtc/port             port
     :webrtc/candidate-type   cand-type
     :webrtc/related-address  related-address
     :webrtc/related-port     related-port}))

(defn ice-candidate-valid?
  "True when m is a well-formed ICE candidate record (as produced by
  ice-candidate)."
  [m]
  (boolean
    (and (map? m)
         (ice-candidate {:foundation      (:webrtc/foundation m)
                         :component       (:webrtc/component m)
                         :transport       (:webrtc/transport m)
                         :priority        (:webrtc/priority m)
                         :address         (:webrtc/address m)
                         :port            (:webrtc/port m)
                         :cand-type       (:webrtc/candidate-type m)
                         :related-address (:webrtc/related-address m)
                         :related-port    (:webrtc/related-port m)}))))

;; ---------------------------------------------------------------------------
;; SDP media description (RFC 8866 §5.14, m=/a= lines modeled as EDN)
;; ---------------------------------------------------------------------------

(def media-kinds
  "Valid SDP media kinds."
  #{:audio :video :application})

(def directions
  "Valid SDP media direction attributes."
  #{:sendrecv :sendonly :recvonly :inactive})

(defn media-description
  "Construct an SDP media description record. kind is one of media-kinds.
  direction is one of directions. codecs is a vector of codec name strings
  (e.g. [\"VP8\" \"opus\"]). mid is the media identification tag. Returns nil
  when kind or direction is invalid."
  [{:keys [kind mid direction codecs ice-ufrag ice-pwd dtls-fingerprint]}]
  (when (and (contains? media-kinds kind)
             (contains? directions direction))
    {:webrtc/kind             kind
     :webrtc/mid              mid
     :webrtc/direction        direction
     :webrtc/codecs           (vec codecs)
     :webrtc/ice-ufrag        ice-ufrag
     :webrtc/ice-pwd          ice-pwd
     :webrtc/dtls-fingerprint dtls-fingerprint}))

;; ---------------------------------------------------------------------------
;; SDP session description (RFC 8866 §5)
;; ---------------------------------------------------------------------------

(defn sdp-session
  "Construct an SDP session description record. sdp-type is :offer or
  :answer. origin is a free-form string (o= line owner/session-id/version).
  media is a vector of media-description records. Returns nil when sdp-type
  is invalid or any media description is malformed."
  [{:keys [sdp-type origin session-version media]}]
  (when (and (contains? #{:offer :answer} sdp-type)
             (every? map? media))
    {:webrtc/sdp-type        sdp-type
     :webrtc/origin          origin
     :webrtc/session-version session-version
     :webrtc/media           (vec media)}))

;; ---------------------------------------------------------------------------
;; Validation
;; ---------------------------------------------------------------------------

(defn validate-ice-candidate
  "Return a validation result for a candidate ICE-candidate map."
  [m]
  (cond
    (not (map? m))                 {:webrtc/valid? false :webrtc/error :not-a-map}
    (not (ice-candidate-valid? m)) {:webrtc/valid? false :webrtc/error :malformed-candidate}
    :else                          {:webrtc/valid? true :webrtc/candidate m}))

(defn validate-sdp-session
  "Return a validation result for an SDP session record (as produced by
  sdp-session)."
  [m]
  (cond
    (not (map? m))                                {:webrtc/valid? false :webrtc/error :not-a-map}
    (not (contains? #{:offer :answer} (:webrtc/sdp-type m)))
    {:webrtc/valid? false :webrtc/error :invalid-sdp-type}
    (not (every? #(contains? media-kinds (:webrtc/kind %)) (:webrtc/media m)))
    {:webrtc/valid? false :webrtc/error :invalid-media-kind}
    :else                                          {:webrtc/valid? true :webrtc/sdp-type (:webrtc/sdp-type m)}))

(defn codec-names
  "Return the set of distinct codec name strings used across all media
  descriptions in an SDP session."
  [session]
  (->> (:webrtc/media session)
       (mapcat :webrtc/codecs)
       (into #{})))

(defn media-of-kind
  "Return the media descriptions of the given kind (:audio/:video/
  :application) from an SDP session."
  [session kind]
  (filterv #(= kind (:webrtc/kind %)) (:webrtc/media session)))
