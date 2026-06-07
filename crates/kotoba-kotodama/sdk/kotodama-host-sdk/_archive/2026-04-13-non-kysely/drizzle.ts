/**
// CHARTER-VIOLATION §substrate (centralized DB forbidden — migrate to AT MST + IPFS + Base L2)
 * @deprecated Use Kysely instead. Import createKyselyDb from "./kysely.js"
 *
 * This file is maintained for backward compatibility only.
 * Drizzle ORM has been replaced with Kysely for type-safe SQL queries.
 */

// Re-export from graph-schema for LABEL_TABLE_MAP (migration support)
export { schema } from "@etzhayyim/graph-schema/schema";

// For backward compatibility, proxy to Kysely
import { createKyselyDb } from "./kysely.js";
import type { KagamiRpcBinding } from "./kysely.js";

export type { KagamiRpcBinding };

/**
 * @deprecated Use createKyselyDb instead
 */
export function createDrizzleDb(kagamiRpc?: KagamiRpcBinding) {
  return createKyselyDb(kagamiRpc);
}

/**
 * @deprecated Drizzle is no longer used
 */
export type DrizzleDb = ReturnType<typeof createKyselyDb>;
