(ns columnar.bytes
  "Where the bytes come from — the other half of the seam `columnar.source`
  declares.

  `IColumnSource` says what an engine may ask a format for. This says what a
  format may ask the world for, and it is here rather than in a format library
  for the reason that only became visible when there were two of them:
  **`org-apache-parquet` and `org-apache-arrow` need the identical protocol.**
  A copy in each means a caller holding a range-reader cannot hand it to both,
  and an instrument that counts bytes has to be written once per format — two
  things that can substitute for each other, which is one thing.

  ## Why ranges, and not a byte array

  The first version of the Parquet reader took the whole file as a vector. It
  was correct and it defeated the point: these formats exist so that a query
  reads a footer and two column chunks instead of forty gigabytes, and a
  reader that demands the forty gigabytes first has thrown that away before it
  starts.

  So a source answers **ranges**, and every read a format library performs is
  one of them. `counting` records what was asked for, which is how a test
  proves a reader touched one column chunk and nothing else — an assertion on
  the *answer* cannot tell that apart from reading everything and slicing.

  ## Synchronous, deliberately

  `IColumnSource` is synchronous, so this is too. On a host where fetching a
  range is asynchronous — a Worker doing HTTP Range requests — the caller
  pre-fetches into `prefetched` and passes that. Each format exposes what its
  own metadata costs (Parquet's `footer-ranges`, Arrow's tail-then-footer) so
  such a caller knows what to fetch before it can parse anything. Pretending
  otherwise would mean either an async rewrite of the engine or a silent
  whole-file read."
  (:refer-clojure :exclude [bytes])
  #?(:clj (:import [java.nio ByteBuffer])))

(defprotocol IByteView
  "A bounded, borrowed window over bytes already owned by the host.

  A view does not promise that ingress itself allocated nothing: an HTTP
  response, decompressor, or device upload may necessarily own a new buffer.
  It promises that narrowing and handing the selected range to the next host
  boundary do not materialise another byte collection."
  (-view-size [view] "Number of bytes in the window.")
  (-view-byte [view index] "Unsigned byte at `index` within the window.")
  (-view-slice [view start end] "Borrow `[start,end)` from the same backing.")
  (-native-view [view]
    "The narrowest platform-native zero-copy view: SubVector, ByteBuffer, or
    Uint8Array. Callers must treat it as borrowed and immutable."))

(defprotocol IByteViewSource
  (-read-view-range [src start end]
    "Borrow `[start,end)` without materialising when the source can expose a
    stable backing. Network and decompression sources may fall back to one
    owned ingress buffer."))

(defn- backing-size [backing]
  #?(:clj
     (cond
       (instance? ByteBuffer backing) (.remaining ^ByteBuffer backing)
       (bytes? backing) (alength ^bytes backing)
       :else (count backing))
     :cljs
     (if (instance? js/Uint8Array backing)
       (.-byteLength backing)
       (count backing))))

(defn- backing-byte [backing index]
  #?(:clj
     (cond
       (instance? ByteBuffer backing)
       (bit-and 0xff (.get ^ByteBuffer backing (+ (.position ^ByteBuffer backing)
                                                   (int index))))
       (bytes? backing) (bit-and 0xff (aget ^bytes backing (int index)))
       :else (nth backing index))
     :cljs
     (if (instance? js/Uint8Array backing)
       (aget backing index)
       (nth backing index))))

(defn- native-slice [backing start end]
  #?(:clj
     (cond
       (instance? ByteBuffer backing)
       (let [base (.position ^ByteBuffer backing)
             dup (.duplicate ^ByteBuffer backing)]
         (.position dup (+ base (int start)))
         (.limit dup (+ base (int end)))
         (.asReadOnlyBuffer (.slice dup)))
       (bytes? backing) (let [slice (.slice
                                     (ByteBuffer/wrap ^bytes backing (int start)
                                                      (int (- end start))))]
                          (.asReadOnlyBuffer slice))
       :else (subvec backing start end))
     :cljs
     (if (instance? js/Uint8Array backing)
       (.subarray backing start end)
       (subvec backing start end))))

(defrecord ByteView [backing start end]
  IByteView
  (-view-size [_] (- end start))
  (-view-byte [_ index]
    (when-not (and (integer? index) (<= 0 index) (< index (- end start)))
      (throw (ex-info "byte-view index out of range"
                      {:type :columnar/view-index-out-of-range
                       :index index :size (- end start)})))
    (backing-byte backing (+ start index)))
  (-view-slice [this from to]
    (when-not (and (integer? from) (integer? to)
                   (<= 0 from) (<= from to) (<= to (- end start)))
      (throw (ex-info "byte-view slice out of range"
                      {:type :columnar/view-slice-out-of-range
                       :want [from to] :size (- end start)})))
    (if (and (zero? from) (= to (- end start)))
      this
      (assoc this :start (+ start from) :end (+ start to))))
  (-native-view [_] (native-slice backing start end)))

(defn view
  "Borrow all bytes in `x`. Existing views retain their backing identity."
  [x]
  (if (satisfies? IByteView x)
    x
    (->ByteView x 0 (backing-size x))))

(defn view-size [x] (-view-size (view x)))
(defn view-byte [x index] (-view-byte (view x) index))
(defn view-slice [x start end] (-view-slice (view x) start end))
(defn native-view [x] (-native-view (view x)))
(defn materialize
  "Copy a borrowed view into the legacy portable unsigned-byte vector shape."
  [x]
  (let [v (view x)]
    (mapv #(view-byte v %) (range (view-size v)))))

(defprotocol IByteSource
  (-size [src] "Total bytes in the object. Known without reading it — from a
    HEAD, a stat, or the catalog's `:object/size-bytes`.")
  (-read-range [src start end] "Bytes in `[start end)` as a vector of unsigned
    ints. `end` is exclusive."))

(defn read-view-range
  "Borrow a range when supported, otherwise wrap the source's one owned read.

  This function makes the copy boundary observable: callers can distinguish a
  host-owned ingress allocation from an avoidable second materialisation."
  [src start end]
  (if (satisfies? IByteViewSource src)
    (-read-view-range src start end)
    (view (-read-range src start end))))

(defn of-vector
  "A source over a whole file already in memory. For tests, and for objects
  small enough that ranging them is pointless."
  [v]
  (let [v (vec v)]
    (reify IByteSource
      (-size [_] (count v))
      (-read-range [_ start end] (subvec v start end))
      IByteViewSource
      (-read-view-range [_ start end] (->ByteView v start end)))))

(defn of-view
  "A source over a host-owned vector, byte array, ByteBuffer, or Uint8Array.

  View-aware consumers borrow slices. Legacy `-read-range` consumers receive
  the historical unsigned-byte vector and therefore pay one explicit copy."
  [backing]
  (let [v (view backing)]
    (reify IByteSource
      (-size [_] (view-size v))
      (-read-range [_ start end]
        (materialize (view-slice v start end)))
      IByteViewSource
      (-read-view-range [_ start end]
        (view-slice v start end)))))

(defn prefetched
  "A source over ranges someone else already fetched.

  `chunks` is a seq of `[start bytes]`. A range that no chunk covers throws
  rather than returning short: a decoder handed fewer bytes than it asked for
  produces nonsense, and the caller who under-fetched is the one who can fix
  it."
  [size chunks]
  (let [chunks (vec chunks)]
    (reify IByteSource
      (-size [_] size)
      (-read-range [_ start end]
        (or (some (fn [[at bs]]
                    (let [stop (+ at (count bs))]
                      (when (and (<= at start) (<= end stop))
                        (subvec (vec bs) (- start at) (- end at)))))
                  chunks)
            (throw (ex-info "range was not prefetched"
                            {:type :columnar/missing-range
                             :want [start end]
                             :have (mapv (fn [[at bs]] [at (+ at (count bs))]) chunks)}))))
      IByteViewSource
      (-read-view-range [_ start end]
        (or (some (fn [[at bs]]
                    (let [v (view bs)
                          stop (+ at (view-size v))]
                      (when (and (<= at start) (<= end stop))
                        (view-slice v (- start at) (- end at)))))
                  chunks)
            (throw (ex-info "range was not prefetched"
                            {:type :columnar/missing-range
                             :want [start end]
                             :have (mapv (fn [[at bs]] [at (+ at (count bs))]) chunks)})))))))

(defn counting
  "Wrap a source so every range is recorded.

  The reason this exists is the same reason `columnar.source/counting` does:
  correct answers prove nothing about how much was read to get them."
  [src]
  (let [log (atom {:ranges [] :bytes 0})]
    {:log log
     :source (reify IByteSource
               (-size [_] (-size src))
               (-read-range [_ start end]
                 (swap! log (fn [l] (-> l
                                        (update :ranges conj [start end])
                                        (update :bytes + (- end start)))))
                 (-read-range src start end))
               IByteViewSource
               (-read-view-range [_ start end]
                 (swap! log (fn [l] (-> l
                                        (update :ranges conj [start end])
                                        (update :bytes + (- end start)))))
                 (read-view-range src start end)))}))

(defn read-counts
  "`{:ranges [[start end] ..] :bytes n}`."
  [c]
  @(:log c))

(defn source
  "Coerce `x` to an `IByteSource`.

  Vectors preserve the historical fast subvec path. Existing byte views and
  platform-native ByteBuffer/Uint8Array storage retain their backing for
  view-aware readers."
  [x]
  (cond
    (satisfies? IByteSource x) x
    (satisfies? IByteView x) (of-view x)
    #?@(:clj  [(or (instance? ByteBuffer x) (bytes? x)) (of-view x)]
        :cljs [(instance? js/Uint8Array x) (of-view x)])
    :else (of-vector x)))

(defn of-fn
  "A source of `size` bytes whose ranges come from `(f start end)`.

  The shape a host hands down — `kotobase.lake.reader`'s scan handle carries
  `:size-bytes` and `:read-range` as a number and a function — so this is the
  adapter every format library would otherwise write for itself."
  [size f]
  (reify IByteSource
    (-size [_] size)
    (-read-range [_ start end] (f start end))))
