import {spawn, execFileSync} from "node:child_process";
import crypto from "node:crypto";
import fs from "node:fs";
import net from "node:net";
import os from "node:os";
import path from "node:path";
import {ContractFactory, JsonRpcProvider, Wallet} from "ethers";
import {DurableAnchorJournal} from "../runtime/journal-store.mjs";
import {EvmRpcInterpreter} from "../runtime/evm-interpreter.mjs";

const ANVIL_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80";
const revision = execFileSync("git", ["rev-parse", "HEAD"], {encoding: "utf8"}).trim();
if (!/^[0-9a-f]{40}$/.test(revision)) throw new Error("reorg qualification requires a full Git revision");
if (execFileSync("git", ["status", "--porcelain"], {encoding: "utf8"}).trim())
  throw new Error("refusing to qualify a dirty worktree");
const port = await new Promise((resolve, reject) => {
  const server = net.createServer();
  server.once("error", reject);
  server.listen(0, "127.0.0.1", () => {
    const selected = server.address().port;
    server.close(() => resolve(selected));
  });
});
const anvil = spawn("anvil", ["--silent", "--host", "127.0.0.1", "--port", String(port)],
  {stdio: "ignore"});
const rpcUrl = `http://127.0.0.1:${port}`;
let provider;
try {
  for (let attempt = 0; attempt < 50; attempt += 1) {
    try {
      const response = await fetch(rpcUrl, {method: "POST", headers: {"content-type": "application/json"},
        body: JSON.stringify({jsonrpc: "2.0", id: 1, method: "eth_chainId", params: []})});
      if (response.ok) break;
    }
    catch { await new Promise(resolve => setTimeout(resolve, 100)); }
  }
  provider = new JsonRpcProvider(rpcUrl, {chainId: 31337, name: "anvil"}, {staticNetwork: true});
  const rpc = async (method, params = []) => provider.send(method, params);
  execFileSync("forge", ["build"], {stdio: "ignore"});
  const artifact = JSON.parse(fs.readFileSync(
    "contracts/out/KotobaseCheckpointAnchor.sol/KotobaseCheckpointAnchor.json", "utf8"));
  const signer = new Wallet(ANVIL_KEY, provider);
  const contract = await new ContractFactory(artifact.abi, artifact.bytecode.object, signer).deploy();
  await contract.waitForDeployment();
  const snapshot = await rpc("evm_snapshot");
  const salt = `0x${crypto.randomBytes(32).toString("hex")}`;
  const interpreter = new EvmRpcInterpreter({provider, signer,
    contractAddress: await contract.getAddress(), disclosureSalt: salt, minConfirmations: 3});
  const effect = {"effect/type": "fevm/submit-checkpoint", idempotency_key: "reorg-drill",
    payload: {"payload/version": 1, "database-id": "private/reorg-drill", epoch: 1,
      "logical-checkpoint-root": "private-root"}};
  const first = await interpreter.interpret(effect);
  const included = await interpreter.interpret({"effect/type": "fevm/read-receipt",
    transaction_hash: first["tx-hash"]});
  if (included["result/type"] !== "confirmed") throw new Error("first transaction was not included");
  if (!await rpc("evm_revert", [snapshot])) throw new Error("Anvil snapshot revert failed");
  // Ethers intentionally coalesces identical JSON-RPC reads for a short
  // interval. Cross that cache window so this observation represents the
  // canonical post-reorg node response.
  await new Promise(resolve => setTimeout(resolve, 500));
  const reorged = await interpreter.interpret({"effect/type": "fevm/read-receipt",
    transaction_hash: first["tx-hash"], expected_block_hash: included["block-hash"]});
  if (reorged["result/type"] !== "reorged") throw new Error("orphaned receipt was not reported as reorged");
  const second = await interpreter.interpret(effect);
  await new Promise(resolve => setTimeout(resolve, 500));
  const reincluded = await interpreter.interpret({"effect/type": "fevm/read-receipt",
    transaction_hash: second["tx-hash"]});
  await rpc("anvil_mine", ["0x2"]);
  await new Promise(resolve => setTimeout(resolve, 500));
  const finalized = await interpreter.interpret({"effect/type": "fevm/read-receipt",
    transaction_hash: second["tx-hash"], expected_block_hash: reincluded["block-hash"]});
  if (finalized["result/type"] !== "finalized")
    throw new Error(`replacement receipt did not finalize: ${JSON.stringify({reincluded, finalized,
      head: await provider.getBlockNumber()})}`);

  const evidenceDir = fs.mkdtempSync(path.join(os.tmpdir(), "kotobase-evm-reorg-"));
  fs.chmodSync(evidenceDir, 0o700);
  const journalPath = path.join(evidenceDir, "reorg.jsonl");
  const journal = new DurableAnchorJournal(journalPath);
  journal.recordEvidence("included", {transaction_hash: first["tx-hash"], ...included});
  journal.recordEvidence("reorged", {transaction_hash: first["tx-hash"], ...reorged});
  journal.recordEvidence("replacement-finalized", {transaction_hash: second["tx-hash"],
    block_hash: reincluded["block-hash"], confirmations: finalized.confirmations});
  journal.close();
  const rawSha256 = crypto.createHash("sha256").update(fs.readFileSync(journalPath)).digest("hex");
  console.log(JSON.stringify({schema: "kotobase.evm-local-reorg-evidence.v1",
    source_revision: revision,
    original_transaction: first["tx-hash"], replacement_transaction: second["tx-hash"],
    original_block_hash: included["block-hash"], replacement_block_hash: reincluded["block-hash"],
    reorg_detected: true, replacement_confirmations: finalized.confirmations,
    raw_journal_sha256: rawSha256, raw_journal: journalPath}, null, 2));
} finally {
  anvil.kill("SIGTERM");
  if (provider) await provider.destroy();
}
