import { spawn } from "node:child_process";
import type { PdftotextHandle } from "./tools.js";

export interface DefaultHandleOptions {
  binary?: string; // override the configured binary (otherwise uses "pdftotext")
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

export function createDefaultPdftotextHandle(opts: DefaultHandleOptions): PdftotextHandle {
  const binary = opts.binary ?? "pdftotext";
  const handle: PdftotextHandle = {
  async convert(input) {
    const argv: string[] = [];
    if (input.first_page !== undefined && input.first_page !== "") { argv.push("-f"); argv.push(String(input.first_page)); }
    if (input.last_page !== undefined && input.last_page !== "") { argv.push("-l"); argv.push(String(input.last_page)); }
    if (input.layout) argv.push("-layout");
    if (input.raw) argv.push("-raw");
    if (input.encoding !== undefined && input.encoding !== "") { argv.push("-enc"); argv.push(String(input.encoding)); }
    {
      const v = (input.pdf_file ?? undefined);
      if (v !== undefined && v !== "") argv.push(String(v));
    }
    {
      const v = (input.text_file ?? "-");
      if (v !== undefined && v !== "") argv.push(String(v));
    }
    return await runBinary(binary, argv, 60000);
  },
  };
  return handle;
}
