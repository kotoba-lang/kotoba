;; ADR-2609500000 live evidence — kotoba guest judged against REAL Filecoin chains.
;;
;; (all values below are pasted from the measured session; the probe driver is
;;  host/live_probe.cljk, read-only RPC, no keys)
;;
;; PROBE 1 — clock: calibration chain head, guest judges the chain's own claim
;;
;;   RPC eth_getBlockByNumber "latest" ->
;;     height 4039215, block timestamp 1788502830
;;   guest (native aarch64, kototama executor, entry judge-block):
;;     :status :ok :verdict-word 1000000000001
;;     :guest-abs-delta 0  :guest-drift-ok 1  :drift-seconds 0
;;   chain moved, re-probed: height 4039219, timestamp 1788502950
;;     :status :ok :verdict-word 1000000000001 :drift-seconds 0
;;   => the guest's genesis constants (1667326380, 30 s/epoch) reproduce the
;;      chain's own height<->time mapping EXACTLY, twice, on a live chain.
;;
;; PROBE 2 — upload plan: oracle PieceCID for a 1017-byte payload (SDK vectors
;;   pin the same geometry in test/filecoin/cloud/vectors.cljk):
;;   bafkzcibd64dqndgccvtyie2373ckzv66ofgbwcd3qsuuiix5zrmvheqsy436yobc
;;   height 6, padding 1015  (= the plan the guest's piece-plan module computes)
;;
;; PROBE 3 — funding calldata, executed against calibration:
;;   set-operator-approval (selector 0x875bc8b6, oracle-built calldata) on the
;;   deployed Filecoin Pay 0x09a0fDc2...55a0 -> eth_call returns "0x" (executed
;;   clean; it is a state-mutating call so eth_call runs it in an ephemeral
;;   state and returns empty). A malformed getRail(1) selector was REJECTED by
;;   the contract itself ("contract reverted at 343") — proving we are really
;;   talking to the deployed Warm Storage stack, not an echo.
