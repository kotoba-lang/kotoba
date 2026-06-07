import { spawn } from "node:child_process";
import type { ArgparseSubHandle } from "./tools.js";

export interface DefaultHandleOptions {
  binary?: string; // override the configured binary (otherwise uses "argparse-sub")
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

export function createDefaultArgparseSubHandle(opts: DefaultHandleOptions): ArgparseSubHandle {
  const binary = opts.binary ?? "argparse-sub";
  const handle: ArgparseSubHandle = {
  async encode(input) {
    const argv: string[] = [];
    if (input.verbose) argv.push("--verbose");
    if (input.config !== undefined && input.config !== "") { argv.push("--config"); argv.push(String(input.config)); }
    if (input.output !== undefined && input.output !== "") { argv.push("--output"); argv.push(String(input.output)); }
    if (input.bitrate !== undefined && input.bitrate !== "") { argv.push("--bitrate"); argv.push(String(input.bitrate)); }
    if (input.lossless) argv.push("--lossless");
    {
      const v = (input.input_path ?? undefined);
      if (v !== undefined && v !== "") argv.push(String(v));
    }
    return await runBinary(binary, argv, 300000);
  },
  async decode(input) {
    const argv: string[] = [];
    if (input.verbose) argv.push("--verbose");
    if (input.config !== undefined && input.config !== "") { argv.push("--config"); argv.push(String(input.config)); }
    if (input.sample_rate !== undefined && input.sample_rate !== "") { argv.push("--sample-rate"); argv.push(String(input.sample_rate)); }
    {
      const v = (input.input_path ?? undefined);
      if (v !== undefined && v !== "") argv.push(String(v));
    }
    {
      const v = (input.output_path ?? "-");
      if (v !== undefined && v !== "") argv.push(String(v));
    }
    return await runBinary(binary, argv, 300000);
  },
  async inspect(input) {
    const argv: string[] = [];
    if (input.verbose) argv.push("--verbose");
    if (input.config !== undefined && input.config !== "") { argv.push("--config"); argv.push(String(input.config)); }
    {
      const v = (input.input_path ?? undefined);
      if (v !== undefined && v !== "") argv.push(String(v));
    }
    return await runBinary(binary, argv, 300000);
  },
  };
  return handle;
}
