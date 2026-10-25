/**
 * Landing Play boot: existing wasm-webcomponent host + digest check.
 * Not a compiler. Edits in the source box are not compiled.
 */
import { KotobaWasmElement } from "./kotoba-wasm-element.js";

const TAG = "kotoba-play-run";
if (!customElements.get(TAG)) {
  KotobaWasmElement.define(TAG, {
    render(pre, ctx) {
      const status = document.getElementById("kot-play-status");
      const template = status?.dataset.success || "{result}";
      const text = template.replace("{result}", String(ctx.result));
      pre.textContent = text;
      if (status) status.textContent = text;
    },
  });
}

function convert(name) {
  try {
    const clickId = new URLSearchParams(location.search).get("bfcid");
    if (window.freebuff && clickId) {
      window.freebuff("conversion", name, { eventId: `${clickId}:${name}` });
    }
  } catch {
    /* attributed visits only */
  }
}

function hex(bytes) {
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

async function verifiedBytes(play) {
  const wasmUrl = play.dataset.wasm;
  const expected = play.dataset.sha;
  const response = await fetch(wasmUrl, { cache: "no-store" });
  if (!response.ok) throw new Error(`artifact fetch failed: HTTP ${response.status}`);
  const bytes = new Uint8Array(await response.arrayBuffer());
  const digest = hex(new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)));
  if (digest !== expected) throw new Error("artifact digest mismatch");
  const module = await WebAssembly.compile(bytes);
  if (WebAssembly.Module.imports(module).length !== 0) {
    throw new Error("demo artifact requested a host import");
  }
  return bytes;
}

async function mountPlay(fireTrial) {
  const play = document.getElementById("play");
  const host = document.getElementById("kot-play-host");
  const status = document.getElementById("kot-play-status");
  const button = document.getElementById("kot-play-run");
  if (!play || !host || !status) return;
  if (button) button.disabled = true;
  status.textContent = status.dataset.verifying || "";
  try {
    const bytes = await verifiedBytes(play);
    const url = URL.createObjectURL(new Blob([bytes], { type: "application/wasm" }));
    const el = document.createElement(TAG);
    el.setAttribute("src", url);
    const done = new Promise((resolve, reject) => {
      el.addEventListener("kotoba-wasm:done", (event) => resolve(event.detail.result), { once: true });
      el.addEventListener("kotoba-wasm:error", (event) => reject(new Error(event.detail.error)), { once: true });
    });
    host.replaceChildren(el);
    const result = await done;
    if (result !== 42n && result !== 42) throw new Error("unexpected result");
    if (fireTrial) convert("trial_started");
  } catch (error) {
    status.textContent = `${status.dataset.error || ""}${error.message}`;
  } finally {
    if (button) button.disabled = false;
  }
}

function bootHooks() {
  const copy = document.getElementById("kot-install-copy");
  const cmd = document.getElementById("kot-install-command");
  if (copy && cmd) {
    copy.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(cmd.textContent || "");
        copy.textContent = copy.dataset.copied;
        convert("cli_copy");
      } catch {
        /* clipboard may be blocked */
      }
    });
  }
  document.addEventListener("click", (event) => {
    const a = event.target.closest && event.target.closest("a");
    if (!a) return;
    if (a.dataset.micro === "docs") convert("docs_view");
    if (a.dataset.micro === "github") convert("github_click");
  });
  const button = document.getElementById("kot-play-run");
  if (button) button.addEventListener("click", () => mountPlay(true));
}

bootHooks();
mountPlay(false);
