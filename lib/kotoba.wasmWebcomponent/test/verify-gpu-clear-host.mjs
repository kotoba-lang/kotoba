// Dependency-free unit test for src/gpu-clear-host.js's `unpackRgba8` --
// the pure bit-unpacking logic behind the `gpu_clear` host-import (ADR-
// 2607078000 Track B Phase 0), directly testable without a GPU/WebGPU
// context. Run: `node test/verify-gpu-clear-host.mjs`
import { setupGpuClearHost, unpackRgba8 } from '../src/gpu-clear-host.js';

let failed = false;
function check(cond, message) {
  if (!cond) {
    failed = true;
    console.error(`FAIL: ${message}`);
  } else {
    console.log(`OK: ${message}`);
  }
}

// unpackRgba8 returns a ClojureScript PersistentVector (iterable, but not a
// native Array -- no .length/.every), so spread it into a real array first.
function closeArr(cljsVec, b, tol = 1e-9) {
  const a = [...cljsVec];
  return a.length === b.length && a.every((v, i) => Math.abs(v - b[i]) <= tol);
}

// 0x00000000 -> black, fully transparent
check(closeArr(unpackRgba8(0x00000000 | 0), [0, 0, 0, 0]), 'rgba8(0x00000000) -> [0,0,0,0]');

// 0xFFFFFFFF as a signed i32 bit pattern is -1 -- this is exactly the
// "reinterpret signed i32 as unsigned" case the >>> 0 trick exists for.
check(closeArr(unpackRgba8(-1), [1, 1, 1, 1]), 'rgba8(-1 signed i32 == 0xFFFFFFFF unsigned) -> [1,1,1,1]');

// 0xFF0000FF -> pure opaque red. As a signed i32 this is a large negative
// number (bit 31 set), again exercising the sign-reinterpretation path.
check(closeArr(unpackRgba8(0xff0000ff | 0), [1, 0, 0, 1]), 'rgba8(0xFF0000FF) -> [1,0,0,1] (opaque red)');

// 0x00FF00FF -> pure opaque green
check(closeArr(unpackRgba8(0x00ff00ff | 0), [0, 1, 0, 1]), 'rgba8(0x00FF00FF) -> [0,1,0,1] (opaque green)');

// 0x0000FFFF -> pure opaque blue
check(closeArr(unpackRgba8(0x0000ffff | 0), [0, 0, 1, 1]), 'rgba8(0x0000FFFF) -> [0,0,1,1] (opaque blue)');

// 0x80808080 -> mid-grey-ish on every channel (128/255)
{
  const [r, g, b, a] = unpackRgba8(0x80808080 | 0);
  const expected = 128 / 255;
  check(
    Math.abs(r - expected) < 1e-9 && Math.abs(g - expected) < 1e-9 && Math.abs(b - expected) < 1e-9 && Math.abs(a - expected) < 1e-9,
    `rgba8(0x80808080) -> every channel ${expected.toFixed(6)} (got r=${r} g=${g} b=${b} a=${a})`
  );
}

// setupGpuClearHost's two fail-closed setup branches, run without any real
// WebGPU context. Node's global `navigator` has no `.gpu`, so the first
// check exercises today's actual environment; the second temporarily
// replaces `navigator` (a configurable-but-setter-less global accessor) via
// Object.defineProperty to force requestAdapter to resolve null.
await setupGpuClearHost({}).then(
  () => check(false, 'setupGpuClearHost({}) should reject when navigator.gpu is unavailable'),
  (e) =>
    check(
      /navigator\.gpu unavailable/.test(e.message),
      `setupGpuClearHost({}) rejects with a WebGPU-unavailable message (got "${e.message}")`
    )
);

{
  const savedDesc = Object.getOwnPropertyDescriptor(globalThis, 'navigator');
  Object.defineProperty(globalThis, 'navigator', {
    value: { gpu: { requestAdapter: async () => null } },
    configurable: true,
  });
  try {
    await setupGpuClearHost({}).then(
      () => check(false, 'setupGpuClearHost({}) should reject when requestAdapter resolves null'),
      (e) =>
        check(
          /requestAdapter returned null/.test(e.message),
          `setupGpuClearHost({}) rejects when requestAdapter resolves null (got "${e.message}")`
        )
    );
  } finally {
    Object.defineProperty(globalThis, 'navigator', savedDesc);
  }
}

if (failed) process.exit(1);
console.log("OK: unpackRgba8 correctly reinterprets signed i32 bit patterns as [r,g,b,a] in [0,1] across the full byte range, including the sign-bit-set cases a naive (i32 >> shift) without >>> 0 would get wrong");
