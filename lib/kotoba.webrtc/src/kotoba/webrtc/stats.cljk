(ns kotoba.webrtc.stats
  "WebRTC call quality stats — pure data contracts.

  Models an RTCStats-shaped quality sample (packets lost, jitter, round-trip
  time) as EDN and classifies it into :good/:degraded/:poor with fixed
  thresholds. No network I/O — the host runtime is responsible for actually
  calling RTCPeerConnection.getStats() and feeding samples in.

  Portable (.cljc) across JVM / ClojureScript / SCI / GraalVM.")

(defn stats-sample
  "Construct a quality-stats sample. packets-sent/packets-lost are counts.
  jitter-ms and round-trip-ms are milliseconds. Returns nil when a count is
  negative or packets-lost exceeds packets-sent."
  [{:keys [packets-sent packets-lost jitter-ms round-trip-ms]}]
  (when (and (integer? packets-sent) (not (neg? packets-sent))
             (integer? packets-lost) (not (neg? packets-lost))
             (<= packets-lost packets-sent)
             (number? jitter-ms) (not (neg? jitter-ms))
             (number? round-trip-ms) (not (neg? round-trip-ms)))
    {:webrtc.stats/packets-sent  packets-sent
     :webrtc.stats/packets-lost  packets-lost
     :webrtc.stats/jitter-ms     jitter-ms
     :webrtc.stats/round-trip-ms round-trip-ms}))

(defn packet-loss-ratio
  "Return the packet-loss ratio (0.0..1.0) for a stats sample. 0.0 when no
  packets were sent."
  [sample]
  (let [sent (:webrtc.stats/packets-sent sample)
        lost (:webrtc.stats/packets-lost sample)]
    (if (zero? sent) 0.0 (/ (double lost) sent))))

(def quality-thresholds
  "Fixed classification thresholds. :good requires all metrics to be at or
  below these; :poor is triggered by any metric exceeding the corresponding
  poor-* threshold; everything else is :degraded."
  {:good-loss-ratio 0.02  :poor-loss-ratio 0.10
   :good-jitter-ms  30    :poor-jitter-ms  100
   :good-rtt-ms     150   :poor-rtt-ms     400})

(defn classify
  "Classify a stats sample into :good, :degraded or :poor using
  quality-thresholds."
  [sample]
  (let [loss (packet-loss-ratio sample)
        jitter (:webrtc.stats/jitter-ms sample)
        rtt (:webrtc.stats/round-trip-ms sample)
        {:keys [good-loss-ratio poor-loss-ratio
                good-jitter-ms poor-jitter-ms
                good-rtt-ms poor-rtt-ms]} quality-thresholds]
    (cond
      (or (> loss poor-loss-ratio) (> jitter poor-jitter-ms) (> rtt poor-rtt-ms))
      :poor

      (and (<= loss good-loss-ratio) (<= jitter good-jitter-ms) (<= rtt good-rtt-ms))
      :good

      :else
      :degraded)))
