/**
 * dns kotoba — barrel.
 *
 * Per ADR-2605203000 Option B Phase E reference impl. Domain transfer
 * workflow (Squarespace → Cloudflare) with 3-signer ClassA approvals.
 *
 * Slice 1: 6 commands covering all 7 vendor lexicons.
 *   createTransferRequest + getTransferRequest + transferFromSquarespace +
 *   putTransferStep + listTransferSteps + putTransferOutcome
 *
 * (vendor lexicon putTransferStep + transferStep both map to
 * putTransferStep; vendor lexicon putTransferOutcome + transferOutcome
 * both map to putTransferOutcome.)
 */

export * from "./types.js";
export {
  createTransferRequest,
  getTransferRequest,
  transferFromSquarespace,
  putTransferStep,
  listTransferSteps,
  putTransferOutcome,
} from "./transfer.js";
