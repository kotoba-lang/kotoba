import type { Plugin } from "vite";

export interface DeploySmokeOptions {
  /** Base URL to check, e.g. https://news.etzhayyim.com */
  baseUrl: string;
  /** Paths to probe, e.g. ["/ja", "/ja/games"] */
  paths: string[];
  /** Allowed status codes (default: [200]) */
  expectedStatuses?: number[];
  /** Request timeout in milliseconds (default: 10000) */
  timeoutMs?: number;
  /** Optional header map */
  headers?: Record<string, string>;
  /**
   * Run only when this env var is set.
   * If omitted, the check always runs once configured.
   */
  onlyWhenEnvVar?: string;
}

function normalizeBaseUrl(input: string): string {
  return input.endsWith("/") ? input.slice(0, -1) : input;
}

function normalizePath(input: string): string {
  return input.startsWith("/") ? input : `/${input}`;
}

export function deploySmoke(options: DeploySmokeOptions): Plugin {
  return {
    name: "deploy-smoke",
    enforce: "post",
    closeBundle: {
      sequential: true,
      order: "post",
      async handler() {
        if (!options.baseUrl || options.paths.length === 0) return;

        if (options.onlyWhenEnvVar && !process.env[options.onlyWhenEnvVar]) {
          return;
        }

        const baseUrl = normalizeBaseUrl(options.baseUrl);
        const expected = new Set(options.expectedStatuses ?? [200]);
        const timeoutMs = options.timeoutMs ?? 10_000;
        const failures: string[] = [];

        for (const rawPath of options.paths) {
          const p = normalizePath(rawPath);
          const url = `${baseUrl}${p}`;
          const controller = new AbortController();
          const timer = setTimeout(() => controller.abort(), timeoutMs);
          try {
            const res = await fetch(url, {
              method: "GET",
              redirect: "follow",
              headers: options.headers,
              signal: controller.signal,
            });
            if (!expected.has(res.status)) {
              failures.push(`${url} -> status ${res.status}`);
            }
          } catch (err) {
            const reason =
              err instanceof Error ? err.message : "unknown fetch error";
            failures.push(`${url} -> ${reason}`);
          } finally {
            clearTimeout(timer);
          }
        }

        if (failures.length > 0) {
          this.error(
            `[deploy-smoke] ${failures.length} route check(s) failed:\n- ${failures.join(
              "\n- "
            )}`
          );
        }
      },
    },
  };
}
