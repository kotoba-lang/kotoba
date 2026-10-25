(ns fix.dictionary
  "Field/message/group tables as **data**, passed as an explicit parameter
  to `fix.message/encode` and `fix.message/decode` — never baked into
  `fix.codec` or `fix.groups`, because FIX 4.2, FIX 4.4 and FIX 5.0 do not
  agree on every tag's meaning or on which groups exist, and a codec that
  hardcodes one version's answer is not a FIX codec, it is that one
  version's codec wearing FIX's name.

  Only the tags this library's own test suite exercises are populated: the
  standard header/trailer, the seven session-level messages (Logon/Logout/
  Heartbeat/TestRequest/ResendRequest/SequenceReset/Reject), and two
  application messages (NewOrderSingle/ExecutionReport) including
  NewOrderSingle's NoAllocs repeating group. This is deliberately not a
  transcription of the full FIX data dictionary (thousands of fields across
  hundreds of messages) — it exists to prove the dictionary is a parameter,
  not to be a complete one. Extending any of the three maps below with more
  tags does not require touching `fix.codec`, `fix.groups`, or
  `fix.message` at all, which is the point.")

(def common-fields
  "Tag -> field-name keyword. The tag numbers below are stable across
  FIX.4.2, FIX.4.4 and FIX.5.0 for the message set this library covers —
  none of the three versions renumber BeginString, MsgType, ClOrdID, and so
  on out from under an older session. What *does* differ across versions is
  which messages/groups a given tag legitimately appears in, which is a
  fact about `:messages`/`:groups`, not about this table."
  {;; standard header / trailer
   8 :begin-string 9 :body-length 35 :msg-type 49 :sender-comp-id
   56 :target-comp-id 34 :msg-seq-num 52 :sending-time 43 :poss-dup-flag
   97 :poss-resend 122 :orig-sending-time 10 :check-sum
   ;; Logon / Logout / test-request / resend / sequence-reset / reject
   98 :encrypt-method 108 :heart-bt-int 141 :reset-seq-num-flag
   112 :test-req-id 7 :begin-seq-no 16 :end-seq-no
   123 :gap-fill-flag 36 :new-seq-no
   45 :ref-seq-num 371 :ref-tag-id 372 :ref-msg-type 373 :session-reject-reason
   58 :text
   ;; NewOrderSingle
   11 :cl-ord-id 1 :account 21 :handl-inst 55 :symbol 54 :side
   60 :transact-time 40 :ord-type 38 :order-qty 44 :price 59 :time-in-force
   78 :no-allocs 79 :alloc-account 80 :alloc-shares
   ;; ExecutionReport
   37 :order-id 17 :exec-id 20 :exec-trans-type 150 :exec-type 39 :ord-status
   6 :avg-px 14 :cum-qty 151 :leaves-qty 32 :last-shares 31 :last-px})

(def common-messages
  "MsgType(35) value -> message-name keyword. Stable across the three
  versions for this message set (all seven session-level codes and these
  two application codes predate FIX.4.2)."
  {"A" :logon "5" :logout "0" :heartbeat "1" :test-request "2" :resend-request
   "4" :sequence-reset "3" :reject "D" :new-order-single "8" :execution-report})

(def fix42-groups
  "NoAllocs(78) — FIX.4.2 NewOrderSingle's inline allocation-instruction
  block (AllocAccount(79)/AllocShares(80) per entry, first-field/delimiter
  79). Verified against the FIX.4.2 NewOrderSingle message definition
  (b2bits FIXOpaedia / OnixS FIX Dictionary, FIX.4.2 'New Order - Single');
  later versions moved standalone allocation onto a separate Allocation
  Instruction message and this library has not verified whether NoAllocs
  still appears the same way on NewOrderSingle in FIX.4.4 or FIX.5.0, which
  is why it is declared **only** on `fix42` below and not copied onto
  `fix44`/`fix50` as if it were a verified fact about them too."
  {78 {:member-tags [79 80]}})

(def fix42
  {:fix-version "FIX.4.2" :begin-string "FIX.4.2"
   :fields common-fields :messages common-messages :groups fix42-groups})

(def fix44
  {:fix-version "FIX.4.4" :begin-string "FIX.4.4"
   :fields common-fields :messages common-messages :groups {}})

(def fix50
  "FIX.5.0's session layer is actually FIXT.1.1 (the transport/session
  protocol FIX.5.0 split out from the application layer) — BeginString(8)
  on the wire is literally the string \"FIXT.1.1\", with the application
  version carried separately in ApplVerID(1128)/DefaultApplVerID(1137) at
  the session-Logon level. This dictionary does not model ApplVerID or the
  session/application split at all; it exists only to demonstrate that
  `:begin-string` is a per-dictionary value, not a hardcoded literal, for a
  version where that value genuinely isn't \"FIX.5.0\"."
  {:fix-version "FIX.5.0" :begin-string "FIXT.1.1"
   :fields common-fields :messages common-messages :groups {}})
