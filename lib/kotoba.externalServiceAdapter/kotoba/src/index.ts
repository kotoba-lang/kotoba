/**
 * external-service-adapter kotoba — barrel.
 *
 * kotoba-E2E split (ADR-2605181100): provider catalog plaintext +
 * per-person mailbox-sync / oauth-grant metadata sealed via kotoba E2E.
 * OAuth token/secret custody + the external Graph/Gmail/Drive API call stay
 * etzhayyim via consent-capability.
 */
export * from "./types.js";
export {
  registerConnector,
  getConnector,
  listConnectors,
  recordSync,
  listSyncs,
  getSync,
  recordGrant,
  listGrants,
  getGrant,
  coverage,
} from "./registry.js";
