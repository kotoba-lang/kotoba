import { node } from './node.js';
// kotoba:kais/kqe — the guest's only call here is assert-quad, wired into the
// in-wasm KotobaNode read engine (object payload decoded as text for storage).
export function assertQuad(q) {
  const val = new TextDecoder().decode(q.objectCbor);
  node.transact(JSON.stringify([{ e: q.subject, a: q.predicate, v_edn: JSON.stringify(val) }]));
}
export function retractQuad() {}
export function query() { return []; }
export function getObjects() { return []; }
export function getHead() { return undefined; }
