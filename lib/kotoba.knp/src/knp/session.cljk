(ns knp.session
  "KNP session/handshake state: client/session id allocation, handshake
  state machine, and hello/welcome wire-message framing.

  Restored from the legacy kami-engine/kami-knp Rust crate (deleted in PR
  #82, path `kami-knp/src/session.rs`) as part of ADR-2607010930
  (com-junkawasaki/root, kami-engine Rust-workspace restoration to CLJC).

  Ported 1:1: `HandshakeState`, `ClientSession`, `SessionManager`
  (`accept-hello`, `get`, `assign-entity`, `broadcast-addrs`,
  `broadcast-addrs-except`, `count`, `prune`), and the hello/welcome
  handshake message encode/decode (`make-hello`, `make-welcome`,
  `parse-welcome`, `is-hello?`). All of it is pure bookkeeping over a
  `SocketAddr -> ClientSession` map plus byte-format logic — no actual
  socket I/O. The Rust `SocketAddr` key is represented here as an opaque
  CLJC value (any hashable identifier the caller supplies, e.g. a
  \"host:port\" string) since address *parsing/binding* is native-only and
  out of scope; nothing else from `session.rs` was excluded."
  #?(:clj (:import [java.nio ByteBuffer ByteOrder])))

;; ---------------------------------------------------------------------------
;; Handshake state

(def handshake-states #{:awaiting-hello :awaiting-ack :established})

;; ---------------------------------------------------------------------------
;; SessionManager

(defn session-manager
  "New session-manager state. `sessions` maps an opaque addr -> ClientSession
  map ({:id :session-id :addr :state :entity-index :last-recv-tick})."
  []
  {:sessions {}
   :next-client-id 1
   :next-session-id 1})

(defn accept-hello
  "Handle an incoming hello from an unknown `addr`. Returns
  [[session-id client-id] updated-manager]."
  [sm addr]
  (let [session-id (:next-session-id sm)
        client-id (:next-client-id sm)
        session {:id client-id
                  :session-id session-id
                  :addr addr
                  :state :established
                  :entity-index nil
                  :last-recv-tick 0}
        sm' (-> sm
                (assoc-in [:sessions addr] session)
                (update :next-session-id inc)
                (update :next-client-id inc))]
    [[session-id client-id] sm']))

(defn get-session [sm addr]
  (get-in sm [:sessions addr]))

(defn assign-entity
  "Assign an entity index to the client at `addr`, if a session exists."
  [sm addr entity-index]
  (if (get-in sm [:sessions addr])
    (assoc-in sm [:sessions addr :entity-index] entity-index)
    sm))

(defn broadcast-addrs
  "All addrs with an established session, for broadcast."
  [sm]
  (into [] (comp (filter #(= :established (:state %))) (map :addr))
        (vals (:sessions sm))))

(defn broadcast-addrs-except
  "All established addrs except `except`, for relay."
  [sm except]
  (into [] (comp (filter #(and (= :established (:state %)) (not= except (:addr %))))
                  (map :addr))
        (vals (:sessions sm))))

(defn session-count
  "Number of established sessions."
  [sm]
  (count (filter #(= :established (:state %)) (vals (:sessions sm)))))

(defn prune
  "Remove sessions that are established but haven't been heard from within
  `timeout-ticks` of `current-tick`. Non-established sessions are always
  kept (mirrors the Rust `retain` predicate)."
  [sm current-tick timeout-ticks]
  (update sm :sessions
          (fn [sessions]
            (into {}
                  (filter (fn [[_ s]]
                            (or (not= :established (:state s))
                                (< (- current-tick (:last-recv-tick s)) timeout-ticks))))
                  sessions))))

;; ---------------------------------------------------------------------------
;; Handshake wire messages

(def hello-size 6)   ;; magic "KN" + 4-byte zeroed client-id placeholder
(def welcome-size 14) ;; magic "KN" + 8-byte session-id + 4-byte client-id

#?(:clj
   (defn make-hello
     "Client -> server hello. 6 zero-padded bytes: magic \"KN\" + placeholder."
     []
     (let [b (byte-array hello-size)]
       (aset b 0 (unchecked-byte 0x4B))
       (aset b 1 (unchecked-byte 0x4E))
       b))
   :cljs
   (defn make-hello []
     (let [b (js/Uint8Array. hello-size)]
       (aset b 0 0x4B)
       (aset b 1 0x4E)
       b)))

#?(:clj
   (defn make-welcome
     "Server -> client welcome: magic \"KN\" + session-id (u64 LE) + client-id (u32 LE)."
     [session-id client-id]
     (let [bb (doto (ByteBuffer/allocate welcome-size)
                (.order ByteOrder/LITTLE_ENDIAN)
                (.put (unchecked-byte 0x4B))
                (.put (unchecked-byte 0x4E))
                (.putLong (long session-id))
                (.putInt (unchecked-int client-id)))]
       (.array bb)))
   :cljs
   (defn make-welcome [session-id client-id]
     (let [buf (js/ArrayBuffer. welcome-size)
           dv (js/DataView. buf)]
       (.setUint8 dv 0 0x4B)
       (.setUint8 dv 1 0x4E)
       ;; session-id as u64 LE via two 32-bit halves (goog.math.Long-free)
       (.setUint32 dv 2 (bit-and session-id 0xFFFFFFFF) true)
       (.setUint32 dv 6 (js/Math.floor (/ session-id 4294967296)) true)
       (.setUint32 dv 10 client-id true)
       (js/Uint8Array. buf))))

#?(:clj
   (defn parse-welcome
     "Parse a welcome message. Returns [session-id client-id] or nil."
     [data]
     (when (and (>= (alength ^bytes data) welcome-size)
                (= (aget ^bytes data 0) (unchecked-byte 0x4B))
                (= (aget ^bytes data 1) (unchecked-byte 0x4E)))
       (let [bb (doto (ByteBuffer/wrap data 2 12) (.order ByteOrder/LITTLE_ENDIAN))
             session-id (.getLong bb)
             client-id (bit-and (.getInt bb) 0xFFFFFFFF)]
         [session-id client-id])))
   :cljs
   (defn parse-welcome [data]
     (when (and (>= (.-length data) welcome-size)
                (= (aget data 0) 0x4B)
                (= (aget data 1) 0x4E))
       (let [dv (js/DataView. (.-buffer data) (.-byteOffset data) welcome-size)
             lo (.getUint32 dv 2 true)
             hi (.getUint32 dv 6 true)
             session-id (+ lo (* hi 4294967296))
             client-id (.getUint32 dv 10 true)]
         [session-id client-id]))))

#?(:clj
   (defn is-hello?
     [data]
     (and (>= (alength ^bytes data) 2)
          (= (aget ^bytes data 0) (unchecked-byte 0x4B))
          (= (aget ^bytes data 1) (unchecked-byte 0x4E))))
   :cljs
   (defn is-hello? [data]
     (and (>= (.-length data) 2)
          (= (aget data 0) 0x4B)
          (= (aget data 1) 0x4E))))
