(ns koe.arrival
  "How the call got here, and whether the number attached to it is the caller's.

  ## The premise that broke this

  A restaurant already has a telephone number and their customers dial it. The
  cheapest way to put a receptionist behind it — and the first way this will be
  deployed — is for the shop to **forward** their existing line to ours. Nothing
  about the conversation changes. What changes is who the presented number
  belongs to.

  On a directly dialled call, the network's caller ID is the caller. On a
  forwarded call it may be the caller, or it may be **the forwarding line
  itself** — the restaurant's own number — depending on whether that carrier
  passes the original in a Diversion, P-Asserted-Identity or Remote-Party-ID
  header. It is not guaranteed, it varies by carrier and by country, and it is
  exactly the kind of thing that works in the first test because the test dialled
  directly.

  ## Why this is worse than a missing number

  A dialog typically treats the caller's contact as a fact already in hand and
  therefore never asks for it. Fed a forwarded call whose caller ID is the shop's
  own line, it would seal *the restaurant's number* as the way to reach the
  customer, on every booking, confidently, without ever asking — and the 予約
  would look completely well-formed. A missing number produces one more question.
  A wrong one produces a table held for somebody nobody can reach.

  So a number becomes a fact only when its provenance says it is the caller's:

    :network-caller     the network asserts this is the calling party
    :diverted-unknown   the call was diverted and the original was not passed
    :withheld           the caller withheld it

  Only the first is used. And a presented number equal to the line that forwarded
  the call is treated as `:diverted-unknown` no matter what the provenance
  claims — a carrier that fills the Diversion header with the diverting number
  is not telling us who called."
  (:require [kotoba.lang.text :as str]))

(def usable-provenance
  "The one provenance that yields a fact. An allowlist, so a provenance nobody
  has thought about yet is unusable rather than usable."
  #{:network-caller})

(defn caller-contact
  "The caller's number, or nil with the reason it is not available.

  `:forwarded-from` is the line that diverted the call to us, when known."
  [{:keys [presented-number provenance forwarded-from]}]
  (let [n (some-> presented-number str str/trim)]
    (cond
      (str/blank? n)
      {:koe/contact nil :koe/reason :no-number-presented}

      (and (seq (str forwarded-from)) (= n (str/trim (str forwarded-from))))
      ;; The shop's own number arriving as the caller ID. Whatever the carrier
      ;; labelled it, this is the diversion showing through.
      {:koe/contact nil :koe/reason :presented-number-is-the-forwarding-line}

      (not (contains? usable-provenance provenance))
      {:koe/contact nil :koe/reason (or provenance :provenance-unknown)}

      :else
      {:koe/contact n :koe/reason nil})))

(defn describe
  "A small record of how the call arrived, kept on the session so a 予約 taken
  from a forwarded call is legible as one afterwards."
  [{:keys [via forwarded-from] :as arrival}]
  {:koe/via (or via :direct)
   :koe/forwarded-from (when (seq (str forwarded-from)) (str forwarded-from))
   :koe/contact-source (if (:koe/contact (caller-contact arrival))
                              :network-caller
                              :asked)})
