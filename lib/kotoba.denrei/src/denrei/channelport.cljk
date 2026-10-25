(ns denrei.channelport
  "ChannelTarget port — the ONLY place a message actually enters the space.
  A post-LLM proposal is data (a `:draft` record) until a human approves
  posting it; `post!` is called exactly once, after that approval, by
  `denrei.operation`'s commit step. `kaisha.model` has ZERO posting/delivery
  concept — it is a pure space model — so denrei owns building the delivery
  record itself here, then hands it to an injected Deliverer fn for actual
  fan-out (same injection shape as kekkai/tayori/koyomi's ports).
  `mock-channelport` is the default — a deterministic in-memory target so the
  actor is runnable and testable with no network/creds.

  Mention discipline: the delivery record's :mentions are derived ONLY via
  `kaisha.model/mentions` over the governed body — the SAME parser
  denrei.governor's consent-violations censored — never by re-parsing with a
  looser rule or accepting a proposal-supplied mention list. A proposal
  cannot smuggle a recipient the governor never inspected: whatever handle
  set the governor saw is, by construction, the handle set delivered."
  (:require [kaisha.model :as k]))

(defprotocol ChannelTarget
  (fetch-message [ct message-id] "the message's last-posted content, or nil")
  (propose-revision! [ct message-id content]
    "record `content` ({:tenant :space :channel :message <kaisha message
    EDN>}) as a proposed revision — not yet posted. Returns a value to be
    recorded onto the draft (e.g. {:proposal-id ...}).")
  (post! [ct message-id content]
    "build a delivery record from `content` and hand it (+ message id +
    mentions) to the target's injected deliverer for actual fan-out — the
    actuation. Only ever called after human approval."))

;; ───────────────────────── delivery record (denrei-owned) ─────────────────────────

(defn delivery-record
  "The wire form denrei hands the deliverer: the governed kaisha message EDN
  plus its channel coordinates and the mention set parsed from the SAME body
  the governor censored. kaisha.model itself has no delivery concept — this
  is denrei's own, and it is the only place in the actor that builds one."
  [message-id {:keys [space channel message]}]
  {:message-id message-id
   :space      space
   :channel    channel
   :author     (:kaisha/author message)
   :body       (:kaisha/body message)
   :at         (:kaisha/at message)
   :thread     (:kaisha/thread message)
   :mentions   (vec (sort (k/mentions (:kaisha/body message))))})

;; ───────────────────────── mock (default, runnable offline) ─────────────────────────

(defn mock-channelport
  "A deterministic in-memory ChannelTarget: `posted` is an atom of
  {message-id -> delivery-record} so tests/sim can assert on what WOULD have
  gone out, without any network call. `deliverer` is the injected fn `post!`
  calls with that same record for actual fan-out — default is a no-op
  (nothing beyond recording into `posted`)."
  ([] (mock-channelport (atom {}) (fn [_] nil)))
  ([posted] (mock-channelport posted (fn [_] nil)))
  ([posted deliverer]
   (reify ChannelTarget
     (fetch-message [_ message-id] (get @posted message-id))
     (propose-revision! [_ message-id _content] {:proposal-id (str "denrei/" message-id)})
     (post! [_ message-id content]
       (let [rec (delivery-record message-id content)]
         (deliverer rec)
         (swap! posted assoc message-id rec)
         rec)))))
