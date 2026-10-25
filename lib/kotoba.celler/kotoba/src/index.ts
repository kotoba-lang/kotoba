/**
 * celler kotoba — barrel.
 *
 * DID-addressed telephony number-provisioning registry on the etzhayyim
 * substrate (AT PDS records; no RW). Custody-safe: only the owner's own
 * DID ↔ E.164 bindings are stored; call content + CDR stay Signal-E2E and are
 * NOT server-logged (no CallRecord/CDR collection exists).
 *
 *   number : provisionNumber / getNumber / resolveByE164 / listNumbers /
 *            releaseNumber / coverage
 */

export * from "./types.js";
export {
  provisionNumber,
  getNumber,
  resolveByE164,
  listNumbers,
  releaseNumber,
  coverage,
} from "./number.js";
