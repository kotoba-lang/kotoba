(ns rdap.status
  "EPP object status → RDAP status, per **RFC 8056**.

  This mapping is specified, not a matter of taste, and it is the place a
  registry most often invents its own. The two vocabularies look similar enough
  that guessing feels safe: `clientDeleteProhibited` obviously becomes
  something like `client delete prohibited`. But the two ends do not line up
  one-to-one, and the places they do not are exactly the places a guess is
  wrong:

  - **`ok` becomes `active`.** Not `ok`. RDAP has no `ok`; a client checking for
    it finds nothing and concludes the domain has no status at all.
  - **The RGP statuses of RFC 3915 are in scope** (RFC 8056 §4), and they are
    what tells a redeemable name from one past rescue. A domain in redemption
    carries both `pendingDelete` and `redemptionPeriod` in EPP, so the
    projection produces both `pending delete` and `redemption period`. A
    registry that maps only the EPP core statuses emits `pending delete` alone
    and has dropped the distinction that decides whether a registrant can still
    get their name back.
  - **RDAP status values are space-separated lowercase**, not camelCase. This
    is the mechanical half and the easy half.

  RFC 9083 §10.2 fixes the value set; anything outside it is not a status a
  client is required to understand, so this namespace refuses to invent one."
  (:require [kotoba.lang.text :as str]))

(def epp->rdap
  "RFC 8056 §2 and §4. A status maps to a *set*, because the EPP side is not
  always one value."
  {:ok                        #{"active"}
   :inactive                  #{"inactive"}
   :pendingCreate             #{"pending create"}
   :pendingDelete             #{"pending delete"}
   :pendingRenew              #{"pending renew"}
   :pendingTransfer           #{"pending transfer"}
   :pendingUpdate             #{"pending update"}
   :clientDeleteProhibited    #{"client delete prohibited"}
   :clientHold                #{"client hold"}
   :clientRenewProhibited     #{"client renew prohibited"}
   :clientTransferProhibited  #{"client transfer prohibited"}
   :clientUpdateProhibited    #{"client update prohibited"}
   :serverDeleteProhibited    #{"server delete prohibited"}
   :serverHold                #{"server hold"}
   :serverRenewProhibited     #{"server renew prohibited"}
   :serverTransferProhibited  #{"server transfer prohibited"}
   :serverUpdateProhibited    #{"server update prohibited"}
   ;; RFC 8056 §4 — the RGP statuses of RFC 3915.
   :addPeriod                 #{"add period"}
   :autoRenewPeriod           #{"auto renew period"}
   :renewPeriod               #{"renew period"}
   :transferPeriod            #{"transfer period"}
   :redemptionPeriod          #{"redemption period"}
   :pendingRestore            #{"pending restore"}
   ;; RFC 8056 §2 — a host object's derived status. srs.host derives it from
   ;; the domains that delegate to the host, so it reaches RDAP through the
   ;; same projection as every other status rather than a second path.
   :linked                    #{"associated"}})

(def known
  "The RDAP status values this library will emit (RFC 9083 §10.2)."
  (into (sorted-set) (mapcat val) epp->rdap))

(defn project
  "An EPP status set → the RDAP status vector, sorted for a stable response.

  Sorted because RDAP responses are cached and compared: an unordered set
  serialized in hash order produces a different body for the same state on
  different hosts, which defeats both caching and any diff a registrar runs
  against yesterday's answer."
  [statuses]
  (into [] (sort (into #{} (mapcat #(get epp->rdap % #{})) statuses))))

(defn whois-line
  "The same statuses as WHOIS renders them: RFC 3912 has no schema, but every
  registry writes EPP status names in `Domain Status:` lines followed by the
  ICANN EPP-status URL, and registrars parse exactly that. So WHOIS keeps the
  camelCase EPP spelling while RDAP gets the RFC 8056 form — the one place the
  two outputs deliberately disagree."
  [status]
  (str (name status) " https://icann.org/epp#" (name status)))

(defn parse
  "RDAP status value → the EPP status it came from, or nil. Useful for a client
  reading someone else's RDAP; the round trip is lossy where the mapping is
  many-to-one, and that is a property of RFC 8056 rather than of this code."
  [rdap-status]
  (some (fn [[epp vs]] (when (contains? vs rdap-status) epp))
        (sort-by key epp->rdap)))

(defn camel->rdap
  "Mechanical fallback for a status this library does not know: camelCase to
  space-separated lowercase. Used only for statuses outside `epp->rdap`, and
  it does *not* make the result a valid RDAP status — it makes it legible.
  `project` deliberately drops unknown statuses instead of calling this,
  because emitting an invented value is worse than emitting none."
  [status]
  (-> (name status)
      (str/replace #"([a-z])([A-Z])" "$1 $2")
      str/lower))
