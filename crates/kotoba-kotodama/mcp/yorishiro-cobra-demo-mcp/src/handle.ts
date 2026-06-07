import { spawn } from "node:child_process";
import type { CobraDemoHandle } from "./tools.js";

export interface DefaultHandleOptions {
  binary?: string; // override the configured binary (otherwise uses "cobra-demo")
}

interface RunResult {
  exitCode: number;
  stdout?: string;
  stderr?: string;
  error?: string;
}

function runBinary(bin: string, argv: string[], timeoutMs: number): Promise<RunResult> {
  return new Promise((resolve) => {
    let stdout = "";
    let stderr = "";
    let settled = false;
    let child;
    try {
      child = spawn(bin, argv, { stdio: ["ignore", "pipe", "pipe"] });
    } catch (err) {
      resolve({ exitCode: -1, error: (err as Error).message });
      return;
    }
    const timer = setTimeout(() => {
      if (settled) return;
      settled = true;
      try { child.kill("SIGKILL"); } catch { /* noop */ }
      resolve({ exitCode: -1, stdout, stderr, error: `timeout after ${timeoutMs}ms` });
    }, timeoutMs);
    child.stdout?.on("data", (b: Buffer) => { stdout += b.toString("utf-8"); });
    child.stderr?.on("data", (b: Buffer) => { stderr += b.toString("utf-8"); });
    child.on("error", (err) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolve({ exitCode: -1, stdout, stderr, error: err.message });
    });
    child.on("close", (code) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolve({ exitCode: code ?? -1, stdout, stderr });
    });
  });
}

export function createDefaultCobraDemoHandle(opts: DefaultHandleOptions): CobraDemoHandle {
  const binary = opts.binary ?? "cobra-demo";
  const handle: CobraDemoHandle = {
  async cobra_demo(input) {
    const argv: string[] = [];
    if (input.verbose) argv.push("--verbose");
    if (input.config !== undefined && input.config !== "") { argv.push("--config"); argv.push(String(input.config)); }
    return await runBinary(binary, argv, 300000);
  },
  async greet(input) {
    const argv: string[] = [];
    if (input.verbose) argv.push("--verbose");
    if (input.config !== undefined && input.config !== "") { argv.push("--config"); argv.push(String(input.config)); }
    if (input.shout) argv.push("--shout");
    if (input.lang !== undefined && input.lang !== "") { argv.push("--lang"); argv.push(String(input.lang)); }
    {
      const v = (input.arg0 ?? undefined);
      if (v !== undefined && v !== "") argv.push(String(v));
    }
    return await runBinary(binary, argv, 300000);
  },
  async render(input) {
    const argv: string[] = [];
    if (input.verbose) argv.push("--verbose");
    if (input.config !== undefined && input.config !== "") { argv.push("--config"); argv.push(String(input.config)); }
    if (input.max_rows !== undefined && input.max_rows !== "") { argv.push("--max-rows"); argv.push(String(input.max_rows)); }
    if (input.quality !== undefined && input.quality !== "") { argv.push("--quality"); argv.push(String(input.quality)); }
    {
      const v = (input.arg0 ?? undefined);
      if (v !== undefined && v !== "") argv.push(String(v));
    }
    return await runBinary(binary, argv, 300000);
  },
  };
  return handle;
}
