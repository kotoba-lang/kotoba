import { spawn } from "node:child_process";
import type { ClapDemoHandle } from "./tools.js";

export interface DefaultHandleOptions {
  binary?: string; // override the configured binary (otherwise uses "clap-demo")
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

export function createDefaultClapDemoHandle(opts: DefaultHandleOptions): ClapDemoHandle {
  const binary = opts.binary ?? "clap-demo";
  const handle: ClapDemoHandle = {
  async clap_demo(input) {
    const argv: string[] = [];
    if (input.max_rows !== undefined && input.max_rows !== "") { argv.push("--max-rows"); argv.push(String(input.max_rows)); }
    if (input.encoding !== undefined && input.encoding !== "") { argv.push("--encoding"); argv.push(String(input.encoding)); }
    if (input.verbose) argv.push("--verbose");
    {
      const v = (input.input_path ?? undefined);
      if (v !== undefined && v !== "") argv.push(String(v));
    }
    {
      const v = (input.output_path ?? undefined);
      if (v !== undefined && v !== "") argv.push(String(v));
    }
    return await runBinary(binary, argv, 300000);
  },
  };
  return handle;
}
