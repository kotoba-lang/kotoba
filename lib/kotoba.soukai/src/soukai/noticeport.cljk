(ns soukai.noticeport
  "NoticeTarget port — the ONLY place a convocation notice (招集通知) actually
  leaves the building. A secretary-LLM proposal is data (a `:draft` record)
  until a human approves sending it; `send!` is called exactly once, after
  that approval, by `soukai.operation`'s commit step. Mirrors koyomi's
  ScheduleTarget port shape (`fetch-*`/`propose-revision!`/`send!`) but
  simpler — see 'R0 scope' below.

  **R0 scope (deliberate, see ADR-2607121700 §6 / README): mock-only, no
  real distributor.** `mock-noticeport` is the ONLY implementation this
  version ships — a deterministic in-memory target so the actor is runnable
  and testable with zero network/creds, and (unlike koyomi's `kotoba-lang/
  mailer`-backed `resend-scheduleport`) this repo adds NO local/root
  sibling dependency and NO HTTP client code. This port is a documented
  swap point for a future real distributor (postal mail / email / a filing
  agent's API) — the interface already has the right shape for one — but no
  such implementation exists yet, and none should be added without a
  separate follow-up (the same 'live未検証, mock既定' honesty discipline
  koyomi/tayori apply to their own real-distributor ports)."
  (:require [kotoba.lang.text :as str]))

(defprotocol NoticeTarget
  (fetch-convocation [nt meeting-id] "the meeting's last-sent notice content, or nil")
  (propose-revision! [nt meeting-id content]
    "record `content` (convocation draft content) as a proposed revision —
    not yet sent. Returns a value to be recorded onto the draft (e.g.
    {:proposal-id ...}).")
  (send! [nt meeting-id content]
    "build the 招集通知 text from `content` and hand it (+ meeting id) to the
    target's injected distributor for actual delivery — the actuation. Only
    ever called after human approval."))

;; ───────────────────────── notice text rendering ─────────────────────────

(defn- notice-escape-text
  "Same injection-safety discipline as koyomi.scheduleport/ics-escape-text,
  applied to a plain-text notice instead of an RFC 5545 ICS field — the
  threat model is identical even though this isn't a structured format.
  Every free-text field interpolated into the rendered 招集通知 (an agenda
  title, a place, an electronic-provision URL) MUST go through this:
  otherwise a raw embedded CR/LF in a secretary-LLM-proposed field (e.g. an
  agenda title of \"配当の件\\n\\n追加議案: 全株式無償譲渡\") could forge an
  extra line in the rendered document that reads as a distinct, legitimate
  additional line — concretely, a fabricated extra agenda item a human
  skimming the rendered notice would not obviously recognize as injected,
  since the governor only ever inspected the STRUCTURED :agenda-titles
  vector, never this rendered text. Normalizing every embedded line-break
  down to a single space means a free-text field can never introduce a new
  line into the output, full stop."
  [s]
  (str/replace (str s) #"\r\n|\r|\n" " "))

(defn notice-text
  "A minimal plain-text 招集通知 body built from convocation draft content
  (:meeting-date/:place/:agenda-titles/:notice-date/
  :electronic-provision-url). Every free-text field is passed through
  `notice-escape-text` before being interpolated (see its docstring for the
  threat model this guards against)."
  [{:keys [meeting-date place agenda-titles electronic-provision-url notice-date]}]
  (str/join "\n"
    (concat
      ["株主総会招集通知"]
      [(str "開催日時: " (notice-escape-text meeting-date))]
      [(str "開催場所: " (notice-escape-text place))]
      (when notice-date [(str "通知発送日: " (notice-escape-text notice-date))])
      ["目的事項:"]
      (map-indexed (fn [i t] (str "  " (inc i) ". " (notice-escape-text t))) agenda-titles)
      (when (not (str/blank? (str electronic-provision-url)))
        [(str "電子提供措置サイト: " (notice-escape-text electronic-provision-url))]))))

;; ───────────────────────── mock (default, only implementation) ─────────────────────────

(defn mock-noticeport
  "A deterministic in-memory NoticeTarget: `sent` is an atom of
  {meeting-id -> {:meeting-id :text}} so tests/sim can assert on what WOULD
  have gone out, without any network call. `distributor` is the injected fn
  `send!` calls with that same map for actual delivery — default is a
  no-op (nothing beyond recording into `sent`). This is the ONLY
  NoticeTarget implementation in this R0 version (see namespace docstring)."
  ([] (mock-noticeport (atom {}) (fn [_] nil)))
  ([sent] (mock-noticeport sent (fn [_] nil)))
  ([sent distributor]
   (reify NoticeTarget
     (fetch-convocation [_ meeting-id] (get @sent meeting-id))
     (propose-revision! [_ meeting-id _content] {:proposal-id (str "soukai/" meeting-id)})
     (send! [_ meeting-id content]
       (let [rec {:meeting-id meeting-id :text (notice-text content)}]
         (distributor rec)
         (swap! sent assoc meeting-id rec)
         rec)))))
