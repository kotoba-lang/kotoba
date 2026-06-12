import type { WRPCError } from "@etzhayyim/xrpc/error";

export const DEFAULT_RPC_TIMEOUT_MS = 30_000;

export interface TimeoutSignal {
  signal: AbortSignal;
  cleanup: () => void;
}

/** Create a timeout-bound signal optionally chained to a parent signal. */
export function createTimeoutSignal(
  timeoutMs: number,
  parent?: AbortSignal
): TimeoutSignal {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);

  const onAbort = () => ctrl.abort();
  if (parent) {
    if (parent.aborted) ctrl.abort();
    else parent.addEventListener("abort", onAbort, { once: true });
  }

  return {
    signal: ctrl.signal,
    cleanup: () => {
      clearTimeout(timer);
      if (parent) parent.removeEventListener("abort", onAbort);
    },
  };
}

export function timeoutError(scope: string, timeoutMs: number): WRPCError {
  return {
    error: "TimeoutError",
    message: `${scope}: timeout ${timeoutMs}ms`,
    status: 408,
  };
}
