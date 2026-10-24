(ns haishin.execute
  "Turn a plan into effects — using only effect functions the caller supplied.

  ## Why this namespace contains no HTTP

  There is no transport here, no credential read, no environment lookup. The
  caller passes `:senders`, a map of target id to a function it wrote and owns.
  This is not indirection for its own sake; it is what makes the library safe to
  depend on. A library that could reach the network on its own would be a
  library that has to be *trusted* not to, and the workspace's rule is that
  credentials never pass through code that did not have to hold them. Here they
  never enter the library at all — a sender closes over its own auth.

  It also means the existing, separately tested clients keep their jobs.
  `kotoba-lang/com-youtube` already implements the resumable-upload protocol
  correctly; a sender for `:youtube` is a three-line adapter onto it, not a
  reimplementation.

  ## Grants fail closed

  `execute!` requires `:grant` — the set of targets the caller is authorising
  right now. A planned target that is not granted is *skipped with a receipt*,
  never sent. A granted target with no sender is likewise skipped rather than
  silently dropped. Mirrors the `capability-grant-mismatch` behaviour of the
  Kotoba runtime: the failure mode of an under-specified grant is that nothing
  goes out, never that something goes out unreviewed."
  (:require [haishin.receipt :as receipt]))

(defn- send-one
  [artifact-id {:entry/keys [target request]} senders at]
  (if-let [sender (get senders target)]
    (try
      (let [{:keys [remote-id url]} (sender request)]
        (receipt/sent artifact-id target {:remote-id remote-id :url url :at at}))
      (catch #?(:clj Exception :cljs :default) e
        (receipt/failed artifact-id target
                        {:error/message #?(:clj (.getMessage ^Exception e)
                                           :cljs (str (ex-message e)))
                         :error/data (ex-data e)}
                        at)))
    (receipt/skipped artifact-id target
                     {:error/message (str "no :senders entry for " target)
                      :error/kind :no-sender}
                     at)))

(defn execute!
  "Run `plan`, sending only to granted targets that have a sender.

  ctx:
    :grant    #{target-id ...} — required. Targets to actually send to.
    :senders  {target-id (fn [request] -> {:remote-id .. :url ..})}
    :at       caller-supplied timestamp for the receipts

  Returns {:run/receipts [..] :run/tally {..}}. Never throws for a per-target
  failure — that is what the receipt is for. Throws only when the call itself is
  malformed (no grant), because that is a programming error rather than an
  outcome to record.

  Rejected plan entries are not re-reported here; they were already reported by
  `haishin.plan/plan` and were never candidates to send."
  [plan {:keys [grant senders at] :as ctx}]
  (when-not (set? grant)
    (throw (ex-info "haishin: execute! requires :grant, a set of target ids"
                    {:haishin/error :missing-grant :ctx (dissoc ctx :senders)})))
  (let [artifact-id (:plan/artifact-id plan)
        at (or at (:plan/at plan))
        receipts
        (mapv (fn [{:entry/keys [target] :as e}]
                (if (contains? grant target)
                  (send-one artifact-id e senders at)
                  (receipt/skipped artifact-id target
                                   {:error/message (str target " planned but not granted")
                                    :error/kind :not-granted}
                                   at)))
              (:plan/entries plan))]
    {:run/artifact-id artifact-id
     :run/receipts receipts
     :run/tally (receipt/tally receipts)}))

(defn dry-run
  "Execute with an empty grant: every planned target yields a `:skipped`
  receipt and nothing leaves the process. Useful as the default path in a
  governor loop, where the interesting question is 'what would have gone out'."
  [plan]
  (execute! plan {:grant #{} :senders {}}))
