import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, it } from "node:test";
import { generatePages, publicDir } from "../src/generate.ts";
import {
  PLAY_ELEMENT_SHA256,
  PLAY_FILES,
  PLAY_SOURCE_SHA256,
  PLAY_WASM_SHA256,
  playDir,
  playSource,
} from "../src/play.ts";

describe("reused Play artifact", () => {
  it("keeps the checked-in wasm and source digests", () => {
    const wasm = readFileSync(join(playDir(), "double-21.wasm"));
    const source = readFileSync(join(playDir(), "double-21.kotoba"));
    assert.equal(createHash("sha256").update(wasm).digest("hex"), PLAY_WASM_SHA256);
    assert.equal(createHash("sha256").update(source).digest("hex"), PLAY_SOURCE_SHA256);
    assert.equal(wasm.byteLength, 344);
    assert.ok(playSource().includes("(double 21)"));
    const element = readFileSync(join(playDir(), "kotoba-wasm-element.js"));
    assert.equal(createHash("sha256").update(element).digest("hex"), PLAY_ELEMENT_SHA256);
    assert.ok(element.includes("export class KotobaWasmElement"));
  });

  it("instantiates the reused wasm and returns 42 without imports", async () => {
    const wasm = readFileSync(join(playDir(), "double-21.wasm"));
    const module = await WebAssembly.compile(wasm);
    assert.equal(WebAssembly.Module.imports(module).length, 0);
    const instance = await WebAssembly.instantiate(module, {});
    const main = instance.exports.main;
    assert.equal(typeof main, "function");
    assert.equal((main as () => bigint)(), 42n);
  });

  it("copies the existing Play files into public/play", () => {
    generatePages();
    for (const name of PLAY_FILES) {
      const published = readFileSync(join(publicDir(), "play", name));
      const source = readFileSync(join(playDir(), name));
      assert.deepEqual(published, source, name);
    }
    const playPage = readFileSync(join(publicDir(), "play", "index.html"), "utf8");
    assert.ok(playPage.includes('rel="canonical" href="https://kotoba-lang.org/play/"'));
    assert.ok(playPage.includes('id="play"'));
    assert.ok(playPage.includes('id="install"'));
    const boot = readFileSync(join(publicDir(), "play", "play-boot.js"), "utf8");
    assert.ok(boot.includes("from \"./kotoba-wasm-element.js\""));
    assert.ok(boot.includes("trial_started"));
    assert.ok(boot.includes("docs_view"));
    assert.ok(boot.includes("github_click"));
    assert.ok(boot.includes("cli_copy"));
    assert.equal(/GMV/.test(boot), false);
  });
});
