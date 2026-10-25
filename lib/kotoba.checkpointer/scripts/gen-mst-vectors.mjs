// Regenerate test/resources/checkpointer/mst-vectors.edn -- cross-language
// known-answer vectors the Clojure port's MST/CAR/dag-cbor implementation is
// checked against. These vectors are computed by calling THIS repo's own
// installed @atproto/repo (+ @atproto/lex-cbor / @atproto/lex-data) directly
// -- never hand-typed CIDs/CAR bytes -- per this port's mandatory
// verification discipline (checkpointer.ts's #commitMst determinism
// contract: "Same (cell_did, checkpoint_id, payload bytes) -> same rootCid,
// bit-for-bit").
//
// Usage (from the repo root, after `npm install`):
//   node scripts/gen-mst-vectors.mjs > test/resources/checkpointer/mst-vectors.edn
import {
  BlockMap,
  MemoryBlockstore,
  MST,
  blocksToCarFile,
  mstUtil,
} from '@atproto/repo';
import { encode as cborEncode } from '@atproto/lex-cbor';
import { cidForCbor } from '@atproto/lex-data';

const hex = (b) => Buffer.from(b).toString('hex');

const out = {};

// ---- leadingZerosOnHash: standalone known-answer vectors ----
{
  const keys = [
    'hello',
    'kotodama.cell.checkpoint/aaaaaaaaaaaa',
    'coll/000',
    'coll/001',
    'coll/002',
    '',
    'a',
  ];
  out.leading_zeros = [];
  for (const k of keys) {
    const z = await mstUtil.leadingZerosOnHash(k);
    out.leading_zeros.push({ key: k, zeros: z });
  }
}

// ---- countPrefixLen: standalone known-answer vectors ----
{
  out.prefix_len = [
    { a: '', b: '', n: mstUtil.countPrefixLen('', '') },
    { a: 'abc', b: 'abd', n: mstUtil.countPrefixLen('abc', 'abd') },
    { a: 'bsky/posts/abcdefg', b: 'bsky/posts/abcdehi', n: mstUtil.countPrefixLen('bsky/posts/abcdefg', 'bsky/posts/abcdehi') },
    { a: 'abc', b: 'ab', n: mstUtil.countPrefixLen('abc', 'ab') },
  ];
}

// ---- dag-cbor + CID (tag 42) encode() known-answer vectors ----
// Exercises: canonical map-key sort (length-first, then bytewise), byte
// strings, arrays, nested maps, null, and CID links via @atproto/lex-cbor's
// tag-42 (0x00-prefixed CID bytes) encoding -- the exact profile our
// checkpointer.mst.dagcbor port must reproduce byte-for-byte.
{
  const body1 = { hello: 'world', n: 42, list: [1, 2, 3] };
  out.cbor_body1 = { encoded: hex(cborEncode(body1)) };

  const smallPayload = { $type: 'test.checkpoint', a: 1, b: 'two', c: [1, 2, 3] };
  const smallBytes = cborEncode(smallPayload);
  const smallCid = await cidForCbor(smallBytes);
  out.cbor_cid_link_body = {
    encoded: hex(smallBytes),
    cid: smallCid.toString(),
  };

  // A map containing a CID link (tag 42) plus a null field -- shape used by
  // checkpointer.ts's `ref` object ($type, blob: CID, checkpoint_id, ...).
  const withCid = { $type: 'x.ref', blob: smallCid, note: null };
  out.cbor_with_cid_link = { encoded: hex(cborEncode(withCid)) };

  // NodeData-shaped map: {l: null, e: [{p,k,v,t}]} -- exact MST node schema.
  const nodeData = {
    l: null,
    e: [
      { p: 0, k: new Uint8Array(Buffer.from('abc', 'ascii')), v: smallCid, t: null },
    ],
  };
  out.cbor_node_data_single = { encoded: hex(cborEncode(nodeData)) };
}

// ---- MST: empty tree ----
{
  const storage = new MemoryBlockstore();
  const mst = await MST.create(storage);
  const root = await mst.getPointer();
  out.mst_empty = { root: root.toString() };
}

// ---- MST: single-entry tree (mirrors checkpointer.ts #commitMst exactly) ----
async function commitOne(checkpointId, payload, blobInlineThreshold = 16 * 1024) {
  const blocks = new BlockMap();
  const payloadCid = await blocks.add(payload);
  const payloadBytes = blocks.get(payloadCid);
  let recordCid = payloadCid;
  let blobCount = 0;
  if (payloadBytes.byteLength > blobInlineThreshold) {
    const ref = {
      $type: 'kotodama.cell.checkpoint.ref',
      blob: payloadCid,
      checkpoint_id: checkpointId,
      cell_did: 'did:key:zTestCell',
      thread_id: 'thread-1',
      checkpoint_ns: '',
    };
    recordCid = await blocks.add(ref);
    blobCount = 1;
  }
  const storage = new MemoryBlockstore();
  await storage.putMany(blocks);
  let mst = await MST.create(storage);
  mst = await mst.add(`kotodama.cell.checkpoint/${checkpointId}`, recordCid);
  const unstored = await mst.getUnstoredBlocks();
  await storage.putMany(unstored.blocks);
  const carBlocks = blocks.addMap(unstored.blocks);
  const rootCid = await mst.getPointer();
  const carBytes = await blocksToCarFile(rootCid, carBlocks);
  return {
    rootCid: rootCid.toString(),
    carBytes,
    blobCount,
    payloadCid: payloadCid.toString(),
    recordCid: recordCid.toString(),
  };
}

{
  const payload = { messages: ['hi'], step: 1 };
  const r = await commitOne('1efc9a00-0000-7000-8000-000000000001', payload);
  out.commit_single_small = {
    checkpoint_id: '1efc9a00-0000-7000-8000-000000000001',
    payload_msgpack_json: JSON.stringify(payload),
    root: r.rootCid,
    payload_cid: r.payloadCid,
    record_cid: r.recordCid,
    blob_count: r.blobCount,
    car: hex(r.carBytes),
  };
}

{
  // Large payload -- exceeds the 16 KiB blobInlineThreshold, forcing the
  // ref-record indirection path (blobCount=1, two blocks: payload + ref).
  const bigString = 'x'.repeat(20000);
  const payload = { blob: bigString };
  const r = await commitOne('1efc9a00-0000-7000-8000-000000000002', payload);
  out.commit_single_large_blobref = {
    checkpoint_id: '1efc9a00-0000-7000-8000-000000000002',
    payload_byte_len: 20000,
    root: r.rootCid,
    payload_cid: r.payloadCid,
    record_cid: r.recordCid,
    blob_count: r.blobCount,
    car: hex(r.carBytes),
  };
}

// ---- MST: multi-entry tree exercising a non-trivial layer split ----
// Search a deterministic key space for a mix of layer-0 and layer>=1 keys
// (via the REAL leadingZerosOnHash), so the resulting tree has actual
// internal structure (a non-null `l` pointer / multi-layer nesting), not
// just a flat single-layer run of leaves.
{
  const candidates = [];
  for (let i = 0; i < 4000; i++) {
    const key = `mst.vectors.coll/rkey${i}`;
    const zeros = await mstUtil.leadingZerosOnHash(key);
    candidates.push({ key, zeros });
  }
  const layer0 = candidates.filter((c) => c.zeros === 0).slice(0, 8);
  const layer1 = candidates.filter((c) => c.zeros === 1).slice(0, 3);
  const layer2 = candidates.filter((c) => c.zeros >= 2).slice(0, 1);
  const chosen = [...layer0, ...layer1, ...layer2].sort((a, b) =>
    a.key < b.key ? -1 : a.key > b.key ? 1 : 0,
  );
  if (layer1.length === 0) {
    throw new Error('vector search failed to find any layer>=1 key in range -- widen search');
  }

  const blocks = new BlockMap();
  const entries = [];
  for (const c of chosen) {
    const value = { key: c.key };
    const cid = await blocks.add(value);
    entries.push({ key: c.key, zeros: c.zeros, valueCid: cid.toString(), cid });
  }
  const storage = new MemoryBlockstore();
  await storage.putMany(blocks);
  let mst = await MST.create(storage);
  for (const e of entries) {
    mst = await mst.add(e.key, e.cid);
  }
  const unstored = await mst.getUnstoredBlocks();
  await storage.putMany(unstored.blocks);
  const carBlocks = blocks.addMap(unstored.blocks);
  const rootCid = await mst.getPointer();
  const carBytes = await blocksToCarFile(rootCid, carBlocks);
  const rootLayer = await mst.getLayer();

  out.mst_multi_entry_split = {
    entries: entries.map(({ key, zeros, valueCid }) => ({ key, zeros, valueCid })),
    add_order: entries.map((e) => e.key),
    root: rootCid.toString(),
    root_layer: rootLayer,
    car: hex(carBytes),
  };
}

// ---- msgpack: known-answer vectors via @msgpack/msgpack ----
{
  const { encode: mpEncode, decode: mpDecode } = await import('@msgpack/msgpack');
  const values = [
    { name: 'nil', value: null },
    { name: 'true', value: true },
    { name: 'false', value: false },
    { name: 'zero', value: 0 },
    { name: 'small_pos_fixint', value: 42 },
    { name: 'small_neg_fixint', value: -5 },
    { name: 'uint8', value: 200 },
    { name: 'uint16', value: 60000 },
    { name: 'uint32', value: 3000000000 },
    { name: 'int8', value: -100 },
    { name: 'int16', value: -30000 },
    { name: 'int32', value: -2000000000 },
    { name: 'float64', value: 3.5 },
    { name: 'str_short', value: 'hi' },
    { name: 'str_long', value: 'x'.repeat(500) },
    { name: 'bin', value: new Uint8Array([1, 2, 3, 255, 0]) },
    // NOTE: JS has one numeric type, so a literal like `3.0` is
    // indistinguishable from the integer `3` -- @msgpack/msgpack encodes it
    // as a fixint. Clojure has separate int/double types, so this array
    // deliberately contains ONLY unambiguous-as-integer numbers; float
    // encoding is covered separately by the `float64` vector above.
    { name: 'array', value: [1, 'two', 3, null, true] },
    { name: 'array_with_float', value: [1, 2.5, 3] },
    { name: 'map', value: { a: 1, b: 'two', c: [1, 2] } },
    { name: 'nested', value: { op: 'put', meta: { kind: 'writes' }, payload: new Uint8Array([9, 8, 7]) } },
  ];
  out.msgpack_vectors = [];
  for (const { name, value } of values) {
    const encoded = mpEncode(value, { useBigInt64: true });
    out.msgpack_vectors.push({ name, encoded: hex(encoded) });
  }
}

// ---- emit EDN ----
function ednStr(s) {
  return JSON.stringify(s);
}
function ednVal(v) {
  if (v === null || v === undefined) return 'nil';
  if (v === true) return 'true';
  if (v === false) return 'false';
  if (typeof v === 'number') return String(v);
  if (typeof v === 'string') return ednStr(v);
  if (Array.isArray(v)) return '[' + v.map(ednVal).join(' ') + ']';
  if (typeof v === 'object') {
    const entries = Object.entries(v).map(([k, val]) => `:${k} ${ednVal(val)}`);
    return '{' + entries.join(' ') + '}';
  }
  throw new Error(`ednVal: unsupported value ${v}`);
}

const lines = ['{'];
for (const [k, v] of Object.entries(out)) {
  lines.push(` :${k}\n ${ednVal(v)}`);
}
lines.push('}');
console.log(lines.join('\n'));
