(ns srtp.index
  "The 48-bit SRTP packet index — [RFC 3711] §3.3.1 — and the replay
  window — §3.3.2 — built on top of it.

  RTP's own sequence number is only 16 bits and wraps roughly every
  65,536 packets; SRTP layers a 32-bit rollover counter (ROC) on top so
  key derivation, encryption and replay protection all operate on a
  single monotonic 48-bit `i = 2^16 * ROC + SEQ` instead of a value that
  wraps in an hour of audio. The interesting part is not maintaining ROC
  on the sender side (trivially: increment on every SEQ wrap) but
  *guessing* it on the receiver side from an out-of-order, possibly
  duplicated, possibly-just-wrapped SEQ — which is exactly Appendix A's
  pseudocode, transcribed here rather than reinvented:

     if (s_l < 32,768)
        if (SEQ - s_l > 32,768)  set v to (ROC-1) mod 2^32
        else                     set v to ROC
     else
        if (s_l - 32,768 > SEQ)  set v to (ROC+1) mod 2^32
        else                     set v to ROC
     return SEQ + v*65,536

  where `s_l` is the receiver's own running estimate of \"the highest
  sequence number seen\" (RFC 3550's term, reused verbatim by 3711)."
)

(def two-32 (* 65536 65536))
(def two-16 65536)

(defn- mod32 [n] (mod n two-32))

(defn guess-roc
  "Appendix A verbatim: given the receiver's current `roc` and `s-l`
  (highest SEQ seen so far) and an incoming `seq`, return the ROC value
  `v` to use for *this* packet's index — which may be `roc`, `roc-1`, or
  `roc+1` (mod 2^32), depending on which is closest to the running
  estimate in the modulo-2^48 sense the RFC describes."
  [roc s-l seq]
  (if (< s-l 32768)
    (if (> (- seq s-l) 32768) (mod32 (dec roc)) roc)
    (if (> (- s-l 32768) seq) (mod32 (inc roc)) roc)))

(defn guess-index
  "The full index estimate `i = 2^16 * v + SEQ` for an incoming packet,
  using `guess-roc` for `v`."
  [roc s-l seq]
  (+ (* two-16 (guess-roc roc s-l seq)) seq))

(defn sender-index
  "The sender-side index — no guessing needed, since the sender is the
  one incrementing ROC. §3.3.1: \"the sender's packet index is then
  defined as i = 2^16 * ROC + SEQ.\""
  [roc seq]
  (+ (* two-16 roc) seq))

(defn advance-roc
  "§3.3.1's post-authentication update rule for the receiver's `roc`/
  `s-l` state, given the `v` a just-processed packet used: `(ROC-1)` ->
  no change; `ROC` -> `s-l` moves forward only if `seq` is larger;
  `(ROC+1)` -> both `s-l` and `roc` advance to the new value. Returns
  the updated `{:roc .. :s-l ..}`."
  [{:keys [roc s-l] :as state} v seq]
  (cond
    (= v (mod32 (dec roc))) state
    (= v roc) (if (> seq s-l) (assoc state :s-l seq) state)
    (= v (mod32 (inc roc))) {:roc v :s-l seq}
    :else state))

;; ── replay window — §3.3.2 ────────────────────────────────────────────────

(def min-window-size
  "\"SRTP-WINDOW-SIZE is a receiver-side, implementation-dependent
  parameter and MUST be at least 64\" — the default this namespace uses
  unless a caller asks for a larger one."
  64)

(defn new-window
  "A fresh replay window: `:max-index` is the highest index authenticated
  so far (`-1` meaning none yet), `:bitmap` is a set of the *offsets
  behind* `:max-index` that have been seen — offset 0 is `:max-index`
  itself, offset 1 is `(dec max-index)`, and so on, capped at
  `window-size`."
  ([] (new-window min-window-size))
  ([window-size] {:max-index -1 :bitmap #{} :window-size window-size}))

(defn check
  "\"Only packets with index ahead of the window, or, inside the window
  but not already received, SHALL be accepted.\" Returns `:ok` (accept)
  or a named rejection: `:srtp/replayed` (already in the bitmap) or
  `:srtp/too-old` (index lags `:max-index` by more than the window and
  is therefore assumed already received, per §3.3.2's own \"can be
  assumed to have been received\")."
  [{:keys [max-index bitmap window-size]} index]
  (cond
    (> index max-index) :ok
    (> (- max-index index) window-size) :srtp/too-old
    (contains? bitmap (- max-index index)) :srtp/replayed
    :else :ok))

(defn record
  "Record `index` as received. Sliding the window forward when `index`
  advances `:max-index` is the \"first the window is moved ahead\" step
  §3.3.2 describes before the list is updated — offsets are relative to
  `:max-index`, so advancing it is really just changing what 0 means,
  not rewriting the set."
  [{:keys [max-index bitmap window-size] :as w} index]
  (cond
    (> index max-index)
    (let [shift (- index max-index)
          kept (into #{} (filter #(< (+ % shift) window-size) (map #(+ % shift) bitmap)))]
      (assoc w :max-index index :bitmap (conj kept 0)))

    (<= index max-index)
    (update-in w [:bitmap] conj (- max-index index))))
