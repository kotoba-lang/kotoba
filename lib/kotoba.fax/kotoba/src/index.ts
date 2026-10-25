/**
 * fax kotoba — barrel. kotoba-E2E split (plaintext document catalog +
 * E2E faxTransmission / inboundFax message-metadata, ADR-2605181100). The
 * provider transmission CALL, provider-API credential custody, blob-byte
 * custody, and headless PDF render compute stay etzhayyim (consent-capability).
 */
export * from "./types.js";
export {
  registerDocument,
  getDocument,
  listDocuments,
  recordTransmission,
  listTransmissions,
  getTransmission,
  recordInbound,
  listInbound,
  coverage,
} from "./registry.js";
