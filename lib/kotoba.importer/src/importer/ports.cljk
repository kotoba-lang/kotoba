(ns importer.ports
  "Host-injected ports. This library defines the protocols; the host supplies
  the implementations, and trades in values so that the interesting tests --
  did it plan the right page, did it refuse to advance -- are ordinary value
  comparisons with no network and no fake server.

  There is no port for obtaining a credential, for the same reason
  `connector.ports` has none (ADR-2608097000 D6): a kernel that could reach a
  token could leak one. The tenant credential lives in the actor that runs
  this, never in here.")

(defprotocol ISink
  (-persist! [this records]
    "Canonical records -> {:importer.sink/persisted n :importer.sink/rejected [...]}

    The count must be what the sink actually committed. A sink that echoes the
    input count without checking turns a partial write into a permanent,
    silent hole, because `importer.cursor/advance` believes it."))

(defprotocol IBlobs
  (-put! [this bytes media-type]
    "-> {:blob/cid ... :blob/size n}. Content-addressed; putting the same bytes
    twice is one blob.")
  (-has? [this cid]
    "true | false | nil. nil means the store could not answer -- absence of an
    answer is not absence of the blob, and a caller that reads nil as false
    will re-upload or, worse, report a gap that is not there."))

;; --- test seams -----------------------------------------------------------

(defn sink-fn
  "Adapt a plain function to `ISink`."
  [f]
  (reify ISink (-persist! [_ records] (f records))))

(defn counting-sink
  "An `ISink` that accepts everything and records what it was given. The
  default test double.

  `reject` is a predicate; matching records are rejected rather than persisted,
  which is how a partial write is reproduced without a broken database."
  ([] (counting-sink (constantly false)))
  ([reject]
   (let [seen (atom [])]
     (reify
       ISink
       (-persist! [_ records]
         (let [{ok false bad true} (group-by (comp boolean reject) records)]
           (swap! seen into ok)
           {:importer.sink/persisted (count ok)
            :importer.sink/rejected (vec bad)}))
       #?@(:clj [clojure.lang.IDeref (deref [_] @seen)]
           :cljs [IDeref (-deref [_] @seen)])))))

(defn blobs-fn
  "Adapt a put function to `IBlobs`. `-has?` answers nil -- the honest value
  for a store that was not asked to track membership."
  [f]
  (reify IBlobs
    (-put! [_ bytes media-type] (f bytes media-type))
    (-has? [_ _cid] nil)))
