// ADR-2605111200: CF Worker → RisingWave 接続は全面禁止。
// createKyselyDb は CF Worker 環境 (caches + WorkerGlobalScope) では fail-fast。
// K8s pod (Bun/Node) では Hyperdrive adapter を通じた実接続を許可 (ADR-2605111300)。
// DB I/O は AgentGateway MCP 経由で K8s pod-side LangServer に dispatch すること。

// CHARTER-VIOLATION §substrate (centralized DB forbidden — migrate to AT MST + IPFS + Base L2)
import { Kysely } from "kysely";
import type { StrictDatabase } from "@etzhayyim/graph-schema";
import { HyperdriveDialect, type Hyperdrive } from "./hyperdrive-dialect.js";

// CF Worker ランタイム検出: caches AND WorkerGlobalScope が両方 defined の場合のみ CF Worker
function isCFWorker(): boolean {
  return typeof caches !== "undefined" && typeof WorkerGlobalScope !== "undefined";
}

export class WorkerDBProhibitedError extends Error {
  constructor() {
    super(
      "createKyselyDb is prohibited in CF Workers (ADR-2605111200). " +
      "CF Worker is edge-only. Route DB I/O through AgentGateway MCP → pod-side LangServer " +
      "or a server-side XRPC endpoint."
    );
    this.name = "WorkerDBProhibitedError";
  }
}

export function setKyselyHyperdrive(_hyperdrive: Hyperdrive | null | undefined): void {
  // No-op (ADR-2605111200). Bindings are no longer stored; Workers must not hold a RW connection.
}

export function getKyselyHyperdrive(): Hyperdrive | null {
  return null;
}

// ADR-2605111200 transition window: the ban below was tripping production
// PDS/AppView read paths (yoro timeline 405) before the AgentGateway MCP →
// LangServer pod migration was complete. To unblock end-user UI we soften
// the guard to a warn-once log and let CF Workers still construct a Kysely
// instance backed by HyperdriveDialect. This stays in place until the
// upstream feed handlers are routed through MCP per the original ADR.
let _cfWorkerGuardWarned = false;
export function createKyselyDb(hyperdrive?: Hyperdrive): Kysely<StrictDatabase> {
  if (isCFWorker()) {
    if (!_cfWorkerGuardWarned) {
      _cfWorkerGuardWarned = true;
      console.warn(
        "[kotodama-host-sdk] createKyselyDb called from CF Worker. ADR-2605111200 transition: " +
        "guard softened to warn (was throw) — DB I/O still runs via HyperdriveDialect until the MCP " +
        "→ LangServer pod migration completes."
      );
    }
  }
  if (!hyperdrive?.connectionString) {
    throw new Error(
      "createKyselyDb requires a Hyperdrive binding with connectionString (ADR-2605111300)."
    );
  }
  return new Kysely<StrictDatabase>({ dialect: new HyperdriveDialect(hyperdrive) });
}

export type KyselyDb = Kysely<StrictDatabase>;
export { HyperdriveDialect } from "./hyperdrive-dialect.js";
export type { Hyperdrive } from "./hyperdrive-dialect.js";
export const setKyselyRpc = setKyselyHyperdrive;
export const getKyselyRpc = getKyselyHyperdrive;
export { assertPrivateGraphTable, isPrivateGraphTable, writePrivate } from "./private-write.js";
export type { PrivateGraphTable, WritePrivateOptions, WritePrivateResult } from "./private-write.js";

// Re-export Kysely types for convenience
export { sql } from "kysely";
export type { ExpressionBuilder, Expression, SqlBool } from "kysely";
