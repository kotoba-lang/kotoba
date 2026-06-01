import { encode, decode } from 'cbor-x';
// Pure-JS BSP driver — the browser-side equivalent of kotoba-vm::WasmPregelRunner.
// Re-feeds run()'s output_cbor as the next ctx_cbor while status == "continue".
export function pregelRun(guestRun, initialState, { maxSupersteps = 64 } = {}) {
  let ctx = encode(initialState);
  let steps = 0, final = null;
  const trace = [];
  while (steps < maxSupersteps) {
    const out = decode(guestRun(ctx)); // throws on guest error
    steps++; final = out; trace.push(out.status);
    if (out.status === 'continue') { ctx = encode({ n: out.n, acc: out.acc }); continue; }
    break;
  }
  return { supersteps: steps, final, trace };
}
