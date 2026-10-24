(ns knp.channel
  "KNP channel manager: per-channel sequence numbers, peer-ACK bookkeeping,
  and retransmit scheduling — the pure state-machine half of channel
  handling.

  Restored from the legacy kami-engine/kami-knp Rust crate (deleted in PR
  #82, path `kami-knp/src/channel.rs`) as part of ADR-2607010930
  (com-junkawasaki/root, kami-engine Rust-workspace restoration to CLJC).

  Ported 1:1: `ReliableChannel` (send/recv sequence counters, unacked-packet
  bookkeeping) and `ChannelManager` (`send`, `receive`, `get_retransmits`),
  all of which are pure data + functions over that data — none of it touches
  a socket. `channel.rs` itself performs no I/O, so nothing from this
  specific file was excluded; wire encode/decode is delegated to
  `knp.packet`, and actual UDP transmission stays in the (unported)
  `socket.rs` / `client.rs` / `server.rs`."
  (:refer-clojure :exclude [send])
  (:require [knp.packet :as packet]))

(def send-buffer-size 256)
(def ack-timeout-ms 100)

;; ---------------------------------------------------------------------------
;; ReliableChannel: per-channel send/recv sequence + unacked ring buffer

(defn reliable-channel
  "New reliable-channel state. `unacked` is a sparse map keyed by
  `seq mod send-buffer-size` (CLJC analogue of the Rust fixed-size
  `[Option<UnackedPacket>; SEND_BUFFER_SIZE]` ring buffer)."
  []
  {:send-seq 0
   :recv-seq 0
   :unacked {}})

(defn reliable-channel-next-seq
  "Returns [next-seq updated-channel]. Sequence wraps at 16 bits, matching
  Rust's `u16::wrapping_add`."
  [rc]
  (let [seq (:send-seq rc)]
    [seq (update rc :send-seq (fn [s] (bit-and (inc s) 0xFFFF)))]))

;; ---------------------------------------------------------------------------
;; ChannelManager: all 4 KNP channels

(defn channel-manager
  "New channel-manager state covering all 4 KNP channels."
  []
  {:reliable-ordered (reliable-channel)
   :reliable-unordered (reliable-channel)
   :unreliable-seq 0
   :voice-seq 0
   ;; latest ACK per channel from peer, indexed by channel keyword
   :peer-ack {:unreliable 0 :reliable-ordered 0 :reliable-unordered 0 :voice 0}})

(defn- wrap16 [n] (bit-and n 0xFFFF))

(def ^:private reliable-channels #{:reliable-ordered :reliable-unordered})

(defn send
  "Prepare a packet for sending on `channel`. Returns
  [wire-bytes updated-manager]. `now-ms` timestamps the send; required for
  every channel (not just reliable ones) so callers always pass it the same
  way, but it's only actually used to queue reliable-channel sends into
  `:unacked` for retransmit tracking -- :unreliable/:voice ignore it."
  [cm channel payload now-ms]
  (let [[seq flags cm]
        (case channel
          :unreliable
          [(:unreliable-seq cm) #{} (update cm :unreliable-seq (comp wrap16 inc))]

          :reliable-ordered
          (let [[seq rc'] (reliable-channel-next-seq (:reliable-ordered cm))]
            [seq #{:reliable :ordered} (assoc cm :reliable-ordered rc')])

          :reliable-unordered
          (let [[seq rc'] (reliable-channel-next-seq (:reliable-unordered cm))]
            [seq #{:reliable} (assoc cm :reliable-unordered rc')])

          :voice
          [(:voice-seq cm) #{} (update cm :voice-seq (comp wrap16 inc))])

        ack (get (:peer-ack cm) channel 0)
        pkt (packet/make-packet channel flags seq ack payload)
        wire (packet/packet->bytes pkt)
        ;; queue the sent packet into the channel's unacked ring buffer so
        ;; get-retransmits has something to find -- this was the missing
        ;; half of the reliable-delivery contract: nothing populated
        ;; :unacked, so reliable-ordered/reliable-unordered silently
        ;; degraded to fire-and-forget (identical to :unreliable), and a
        ;; dropped packet was NEVER retransmitted regardless of how much
        ;; time passed.
        cm (if (contains? reliable-channels channel)
             (update-in cm [channel :unacked] assoc (mod seq send-buffer-size)
                        {:data wire :sent-at-ms now-ms :retransmit-count 0})
             cm)]
    [wire cm]))

(defn receive
  "Process a received wire packet. Returns [[channel payload] updated-manager]
  or [nil updated-manager] if the bytes didn't parse. For a reliable
  channel, the incoming packet's own `ack` field acknowledges one of OUR
  outstanding sends on that same channel (the piggyback-ack pattern every
  `send` above already builds into the outgoing header via `(peer-ack cm)`)
  -- clearing that ring-buffer slot from `:unacked` is the other missing
  half of the reliable-delivery contract: without it, a fix that only
  populated `:unacked` on send would retransmit every packet forever, even
  ones the peer already confirmed."
  [cm bytes]
  (if-let [pkt (packet/bytes->packet bytes)]
    (let [channel (packet/header-channel (:header pkt))
          seq (packet/header-sequence (:header pkt))
          peer-ack (packet/header-ack (:header pkt))
          cm' (assoc-in cm [:peer-ack channel] seq)
          cm' (if (contains? reliable-channels channel)
                (update-in cm' [channel :unacked] dissoc (mod peer-ack send-buffer-size))
                cm')]
      [[channel (:payload pkt)] cm'])
    [nil cm]))

(defn- due-retransmits
  "[due-wire-bytes updated-reliable-channel] for one reliable channel's
  unacked entries older than ack-timeout-ms."
  [rc now-ms]
  (let [due? (fn [[_ up]] (> (- now-ms (:sent-at-ms up)) ack-timeout-ms))
        due (filter due? (:unacked rc))
        result (mapv (fn [[_ up]] (:data up)) due)
        unacked' (reduce (fn [m [seq up]]
                            (assoc m seq (-> up
                                              (assoc :sent-at-ms now-ms)
                                              (update :retransmit-count inc))))
                          (:unacked rc)
                          due)]
    [result (assoc rc :unacked unacked')]))

(defn get-retransmits
  "Packets on EITHER reliable channel (reliable-ordered AND
  reliable-unordered -- both maintain their own :unacked ring buffer) whose
  `sent-at-ms` is older than `ack-timeout-ms` relative to `now-ms`. Returns
  [wire-bytes-seq updated-manager] with `sent-at-ms`/`retransmit-count`
  bumped for the ones returned (mirrors the Rust loop over the unacked ring
  buffer)."
  [cm now-ms]
  (let [[result-ordered rc-ordered'] (due-retransmits (:reliable-ordered cm) now-ms)
        [result-unordered rc-unordered'] (due-retransmits (:reliable-unordered cm) now-ms)
        result (into result-ordered result-unordered)
        cm' (assoc cm :reliable-ordered rc-ordered' :reliable-unordered rc-unordered')]
    [result cm']))
