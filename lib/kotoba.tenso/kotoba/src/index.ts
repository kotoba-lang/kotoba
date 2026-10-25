/**
 * tenso kotoba — barrel. kotoba-E2E pattern: plaintext public aggregate stats
 * + kotoba-E2E confidential transfer envelopes (ADR-2605181100). B2 blob
 * store/download, Signal X3DH/prekey custody, and download/revoke ENFORCEMENT
 * stay etzhayyim, consumed via consent-capability.
 */
export * from "./types.js";
export {
  recordStat,
  listStats,
  recordTransfer,
  listTransfers,
  getTransfer,
  coverage,
} from "./registry.js";
