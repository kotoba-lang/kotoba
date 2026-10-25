(ns kotoba.wasm.host
  "Host-side commit protocol for kotoba DOM ABI batches."
  (:require [kotoba.wasm.abi :as abi]))

(defprotocol DomHost
  (apply-op! [host op])
  (present! [host])
  (poll-event! [host]))

(defn apply-host-op! [host op]
  (if (satisfies? DomHost host)
    (apply-op! host op)
    ((:apply-op! host) host op)))

(defn present-host! [host]
  (if (satisfies? DomHost host)
    (present! host)
    ((:present! host) host)))

(defn poll-host-event! [host]
  (if (satisfies? DomHost host)
    (poll-event! host)
    ((:poll-event! host) host)))

(defn commit! [host ops]
  (let [batch (abi/validate-batch (abi/encode-batch ops))]
    (doseq [op (:ops batch)]
      (apply-host-op! host op))
    (present-host! host)
    batch))

(defrecord RecordingHost [state]
  DomHost
  (apply-op! [_ op]
    (swap! state update :ops (fnil conj []) op)
    nil)
  (present! [_]
    (swap! state update :present-count (fnil inc 0))
    nil)
  (poll-event! [_]
    (let [event (first (:events @state))]
      (when event
        (swap! state update :events subvec 1)
        event))))

(defn recording-host
  ([] (recording-host []))
  ([events]
   (->RecordingHost (atom {:ops []
                           :events (vec events)
                           :present-count 0}))))

(defn recorded [host]
  @(:state host))
