import assert from "node:assert/strict";
import test from "node:test";
import {EvmRpcInterpreter, privateAnchorMaterial} from "../evm-interpreter.mjs";

const saltA = `0x${"11".repeat(32)}`;
const saltB = `0x${"22".repeat(32)}`;
const contract = `0x${"33".repeat(20)}`;
const txHash = `0x${"44".repeat(32)}`;
const blockA = `0x${"55".repeat(32)}`;
const blockB = `0x${"66".repeat(32)}`;
const submitEffect = {"effect/type": "fevm/submit-checkpoint", idempotency_key: "private-job",
  payload: {"database-id": "private/database", epoch: 7,
    "logical-checkpoint-root": "secret-logical-root"}};

test("private checkpoint material is salted, opaque and unlinkable across deployments", () => {
  const a = privateAnchorMaterial(submitEffect, saltA);
  const b = privateAnchorMaterial(submitEffect, saltB);
  assert.match(a.idempotencyKey, /^0x[0-9a-f]{64}$/);
  assert.match(a.checkpointDigest, /^0x[0-9a-f]{64}$/);
  assert.notEqual(a.idempotencyKey, b.idempotencyKey);
  assert.notEqual(a.checkpointDigest, b.checkpointDigest);
  assert.equal(JSON.stringify(a).includes("private/database"), false);
  assert.equal(JSON.stringify(a).includes("secret-logical-root"), false);
});

test("submission enforces gas budget and emits only the transaction hash", async () => {
  let submitted;
  const fakeContract = {anchor: Object.assign(async (...args) => {
    submitted = args; return {hash: txHash};
  }, {estimateGas: async () => 100_000n})};
  const interpreter = new EvmRpcInterpreter({provider: {}, signer: {}, contractAddress: contract,
    disclosureSalt: saltA, contractFactory: () => fakeContract});
  assert.deepEqual(await interpreter.interpret(submitEffect),
    {"result/type": "submitted", "tx-hash": txHash});
  assert.equal(submitted.length, 3);
  assert.equal(submitted[2].gasLimit, 120_000n);
});

test("submission reads pending nonce directly after a reorg", async () => {
  let options;
  const fakeContract = {anchor: Object.assign(async (...args) => {
    options = args[2]; return {hash: txHash};
  }, {estimateGas: async () => 100_000n})};
  const provider = {send: async (method, params) => {
    assert.equal(method, "eth_getTransactionCount");
    assert.deepEqual(params, [`0x${"77".repeat(20)}`, "pending"]);
    return "0x2";
  }};
  const interpreter = new EvmRpcInterpreter({provider,
    signer: {address: `0x${"77".repeat(20)}`}, contractAddress: contract,
    disclosureSalt: saltA, contractFactory: () => fakeContract});
  await interpreter.interpret(submitEffect);
  assert.equal(options.nonce, 2);
});

test("receipt polling records block identity, finality and reorg", async () => {
  let receipt = {status: 1, blockNumber: 100, blockHash: blockA};
  let head = 102;
  const provider = {getTransactionReceipt: async () => receipt, getBlockNumber: async () => head};
  const interpreter = new EvmRpcInterpreter({provider, signer: {}, contractAddress: contract,
    disclosureSalt: saltA, minConfirmations: 5, contractFactory: () => ({})});
  const base = {"effect/type": "fevm/read-receipt", transaction_hash: txHash};
  assert.deepEqual(await interpreter.interpret(base),
    {"result/type": "confirmed", height: 100, "block-hash": blockA});
  assert.deepEqual(await interpreter.interpret({...base, expected_block_hash: blockA}),
    {"result/type": "not-final"});
  head = 104;
  assert.deepEqual(await interpreter.interpret({...base, expected_block_hash: blockA}),
    {"result/type": "finalized", confirmations: 5});
  receipt = {...receipt, blockHash: blockB};
  assert.deepEqual(await interpreter.interpret({...base, expected_block_hash: blockA}),
    {"result/type": "reorged"});
  receipt = null;
  assert.deepEqual(await interpreter.interpret({...base, expected_block_hash: blockA}),
    {"result/type": "reorged"});
});
