(ns loop-ka.observe
  "observe — what is due, and what has already been done.

  Pure: every input is passed in (the channel registry, the catalog listing, the
  ledger's consumed keys, the clock). Nothing here reads a filesystem or a
  clock, so the whole admission decision is testable without a fleet."
  (:require [kotoba.lang.text :as str]))

(defn slot-key
  "The idempotency key for one production slot: channel + date + slot index.

  This is what makes the loop safe to run twice. A cadence tick that fires
  again — a retried cron, an operator running it by hand, two nodes both
  believing they own the channel — resolves to the same key, finds it in the
  ledger, and does nothing. Without it, 'run the loop again' means 'publish a
  second episode today'."
  [channel-id date slot]
  (str (name channel-id) "/" date "/" slot))

(defn unconsumed
  "Catalog entries not yet claimed by a landed run.

  `entries` is whatever the channel's catalog listing yielded (plan ids, in the
  order the channel wants them produced); `consumed` is the set of ids the
  ledger already records as produced. Order is preserved — a catalog is a
  running order, not a set."
  [entries consumed]
  (let [consumed (set consumed)]
    (vec (remove #(contains? consumed %) entries))))

(defn due?
  "Is this channel due for the given slot?

  Due means: the slot key has not been consumed AND the channel has something
  to produce. A channel that is :episode-from-topic always has something to
  produce (the topic comes from the caller); a catalog channel with an empty
  remaining catalog is NOT due, and saying so is the difference between
  'nothing to do' and 'produced an empty episode'."
  [{:keys [produces]} {:keys [slot-consumed? remaining]}]
  (and (not slot-consumed?)
       (case produces
         :episode-from-catalog (boolean (seq remaining))
         :episode-from-topic true
         false)))

(defn plan
  "Channels + world state -> the ordered work list for this tick.

  `world` maps channel id -> {:slot-consumed? bool :remaining [ids]}. Returns a
  vector of {:channel :slot-key :next :reason}, including the channels that are
  NOT due with the reason why — a loop that silently omits them cannot be
  audited, and 'nothing ran last night' has more than one cause."
  [channels {:keys [date slot world] :or {slot 0}}]
  (vec
   (for [{:keys [id] :as ch} channels
         :let [w (get world id {})
               k (slot-key id date slot)
               d (due? ch w)]]
     (cond-> {:channel id :slot-key k :due? d}
       d (assoc :next (first (:remaining w)))
       (not d) (assoc :reason (cond
                               (:slot-consumed? w) :already-produced-this-slot
                               ;; "could not read the catalog" and "the catalog is
                               ;; finished" look identical from the outside and mean
                               ;; opposite things. Conflating them tells an operator
                               ;; the channel is done when in fact nothing looked.
                               (false? (:catalog-readable? w)) :catalog-unreadable
                               (empty? (:remaining w)) :catalog-exhausted
                               :else :not-schedulable))))))

(defn due-only [planned]
  (vec (filter :due? planned)))

(defn summary
  "One line per channel, for the tick's own log. Kept here (pure) so the CLI
  and the app render the same words."
  [planned]
  (str/join "\n"
            (for [{:keys [channel slot-key due? next reason]} planned]
              (str (if due? "DUE  " "skip ") (name channel)
                   "  " slot-key
                   (if due? (str "  -> " next) (str "  (" (name (or reason :unknown)) ")"))))))
