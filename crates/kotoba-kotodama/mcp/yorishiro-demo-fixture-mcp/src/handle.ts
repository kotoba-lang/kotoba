import { spawn } from "node:child_process";
import type { DemoFixtureHandle } from "./tools.js";

export interface DefaultHandleOptions {
  binary?: string; // override the configured binary (otherwise uses "demo-fixture")
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

export function createDefaultDemoFixtureHandle(opts: DefaultHandleOptions): DemoFixtureHandle {
  const binary = opts.binary ?? "demo-fixture";
  const handle: DemoFixtureHandle = {
  async greet(input) {
    const argv: string[] = [];
    if (input.shout) argv.push("--shout");
    if (input.lang !== undefined && input.lang !== "") { argv.push("--lang"); argv.push(String(input.lang)); }
    {
      const v = (input.name ?? undefined);
      if (v !== undefined && v !== "") argv.push(String(v));
    }
    return await runBinary(binary, argv, 300000);
  },
  async head(input) {
    const argv: string[] = [];
    if (input.max_lines !== undefined && input.max_lines !== "") { argv.push("--max-lines"); argv.push(String(input.max_lines)); }
    if (input.encoding !== undefined && input.encoding !== "") { argv.push("--encoding"); argv.push(String(input.encoding)); }
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
  };
  return handle;
}
