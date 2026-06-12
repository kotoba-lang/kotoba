import { spawn } from "node:child_process";
import type { ArgparseMultiHandle } from "./tools.js";

export interface DefaultHandleOptions {
  binary?: string; // override the configured binary (otherwise uses "argparse-multi")
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

export function createDefaultArgparseMultiHandle(opts: DefaultHandleOptions): ArgparseMultiHandle {
  const binary = opts.binary ?? "argparse-multi";
  const handle: ArgparseMultiHandle = {
  async main(input) {
    const argv: string[] = [];
    if (input.bitrate !== undefined && input.bitrate !== "") { argv.push("--bitrate"); argv.push(String(input.bitrate)); }
    if (input.mono) argv.push("--mono");
    {
      const v = (input.input_path ?? undefined);
      if (v !== undefined && v !== "") argv.push(String(v));
    }
    return await runBinary(binary, argv, 300000);
  },
  async main_1(input) {
    const argv: string[] = [];
    if (input.sample_rate !== undefined && input.sample_rate !== "") { argv.push("--sample-rate"); argv.push(String(input.sample_rate)); }
    {
      const v = (input.input_path ?? undefined);
      if (v !== undefined && v !== "") argv.push(String(v));
    }
    return await runBinary(binary, argv, 300000);
  },
  };
  return handle;
}
