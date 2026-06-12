/**
 * audit-query-builder.ts — Typed audit trail query builder.
 *
 * Wraps the low-level auditEmit/auditQuery/auditCount WIT with a fluent
 * builder API. Any App can use these helpers to emit and query
 * audit entries without writing raw SQL.
 */
import type { HostImports } from "./types.js";
import { nowISO } from "./helpers.js";

/** Audit event categories. */
export type AuditCategory =
  | "agent"
  | "consent"
  | "budget"
  | "sync"
  | "auth"
  | "data"
  | "governance"
  | "system"
  | string;

/** Audit event outcomes. */
export type AuditOutcome = "success" | "failure" | "denied" | "error" | "pending" | string;

/** A typed audit entry for emission. */
export interface AuditEmitInput {
  /** Event category (e.g. "agent", "consent", "auth"). */
  category: AuditCategory;
  /** Action performed (e.g. "spawn", "approve", "login"). */
  action: string;
  /** Resource ID affected (e.g. agentId, requestId). */
  resourceId: string;
  /** Outcome of the action. */
  outcome: AuditOutcome;
  /** Additional details (JSON-serializable). */
  details?: Record<string, unknown>;
}

/** A typed audit entry from query results. */
export interface AuditEntry {
  eventId: string;
  category: AuditCategory;
  action: string;
  resourceId: string;
  outcome: AuditOutcome;
  actorDid: string;
  details: Record<string, unknown>;
  timestamp: string;
}

/** Fluent filter for audit queries. */
export interface AuditFilter {
  /** Filter by category. */
  category?: AuditCategory;
  /** Filter by actor DID. */
  actorDid?: string;
  /** Filter events after this ISO timestamp. */
  since?: string;
  /** Filter by outcome. */
  outcome?: AuditOutcome;
  /** Filter by resource ID. */
  resourceId?: string;
  /** Pagination offset. */
  offset?: number;
  /** Pagination limit (default 50). */
  limit?: number;
}

/** High-level audit trail helper. Constructed via `createAuditHelper()`. */
export interface AuditHelper {
  /** Emit an audit trail entry. */
  emit(input: AuditEmitInput): void;
  /** Query audit entries with a typed filter. */
  query(filter: AuditFilter): string;
  /** Count audit entries matching a filter. */
  count(filter: Pick<AuditFilter, "category" | "actorDid" | "since">): bigint;
  /** Emit an OCEL-compliant event. */
  ocelEmit(event: Record<string, unknown>): void;
  /** Query OCEL events. */
  ocelQuery(filter: Record<string, unknown>): string;
  /** Convenience: emit a success audit entry. */
  success(category: AuditCategory, action: string, resourceId: string, details?: Record<string, unknown>): void;
  /** Convenience: emit a failure audit entry. */
  failure(category: AuditCategory, action: string, resourceId: string, details?: Record<string, unknown>): void;
  /** Convenience: emit a denied audit entry (for consent/auth). */
  denied(category: AuditCategory, action: string, resourceId: string, details?: Record<string, unknown>): void;
}

/**
 * Create an audit trail helper bound to host imports.
 *
 * @param hostImports - Host imports for audit WIT calls
 */
export function createAuditHelper(hostImports: HostImports): AuditHelper {
  function emit(input: AuditEmitInput): void {
    hostImports.auditEmit(
      input.category,
      input.action,
      input.resourceId,
      input.outcome,
      JSON.stringify(input.details ?? {}),
    );
  }

  return {
    emit,

    query(filter: AuditFilter): string {
      const sinceMs = filter.since ? BigInt(new Date(filter.since).getTime()) : 0n;
      return hostImports.auditQuery(
        filter.category ?? "",
        filter.actorDid ?? "",
        sinceMs,
        filter.offset ?? 0,
        filter.limit ?? 50,
      );
    },

    count(filter: Pick<AuditFilter, "category" | "actorDid" | "since">): bigint {
      const sinceMs = filter.since ? BigInt(new Date(filter.since).getTime()) : 0n;
      return hostImports.auditCount(
        filter.category ?? "",
        filter.actorDid ?? "",
        sinceMs,
      );
    },

    ocelEmit(event: Record<string, unknown>): void {
      hostImports.ocelEmitEvent(JSON.stringify(event));
    },

    ocelQuery(filter: Record<string, unknown>): string {
      return hostImports.ocelQuery(JSON.stringify(filter));
    },

    success(category, action, resourceId, details) {
      emit({ category, action, resourceId, outcome: "success", details });
    },

    failure(category, action, resourceId, details) {
      emit({ category, action, resourceId, outcome: "failure", details });
    },

    denied(category, action, resourceId, details) {
      emit({ category, action, resourceId, outcome: "denied", details });
    },
  };
}
