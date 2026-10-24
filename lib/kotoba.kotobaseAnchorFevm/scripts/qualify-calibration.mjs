import crypto from "node:crypto";
import fs from "node:fs";
import {execFileSync} from "node:child_process";
import {evmInterpreterFromEnv} from "../runtime/evm-interpreter.mjs";
import {FILECOIN_CALIBRATION as CALIBRATION} from "../profiles/filecoin-calibration.mjs";
import {DurableAnchorJournal} from "../runtime/journal-store.mjs";

const interpreter = await evmInterpreterFromEnv(CALIBRATION);
const journalPath = process.env.FEVM_EVIDENCE_JOURNAL;
if (!journalPath) throw new Error("FEVM_EVIDENCE_JOURNAL is required");
if (fs.existsSync(journalPath) && fs.statSync(journalPath).size !== 0)
  throw new Error("FEVM_EVIDENCE_JOURNAL must be new or empty");
const revision = execFileSync("git", ["rev-parse", "HEAD"], {encoding: "utf8"}).trim();
if (!/^[0-9a-f]{40}$/.test(revision)) throw new Error("qualification requires a full Git revision");
if (execFileSync("git", ["status", "--porcelain"], {encoding: "utf8"}).trim())
  throw new Error("refusing to qualify a dirty worktree");
const journal = new DurableAnchorJournal(journalPath);
const nonce = crypto.randomBytes(32).toString("hex");
const effect = {"effect/type": "fevm/submit-checkpoint", idempotency_key: nonce,
  payload: {"payload/version": 1, "database-id": `private-canary-${nonce}`,
    epoch: Date.now(), "logical-checkpoint-root": crypto.randomBytes(32).toString("hex")}};
const submitted = await interpreter.interpret(effect);
if (submitted["result/type"] !== "submitted") throw new Error(`submission failed: ${JSON.stringify(submitted)}`);
journal.recordEvidence("submitted", {transaction_hash: submitted["tx-hash"], observed_at: new Date().toISOString()});
let expectedBlockHash;
let observation;
const startedAt = new Date().toISOString();
for (let polls = 1; polls <= Number(process.env.FEVM_MAX_POLLS ?? 120); polls += 1) {
  await new Promise(resolve => setTimeout(resolve, Number(process.env.FEVM_POLL_MS ?? 15000)));
  observation = await interpreter.interpret({"effect/type": "fevm/read-receipt",
    transaction_hash: submitted["tx-hash"], expected_block_hash: expectedBlockHash});
  journal.recordEvidence("receipt-poll", {polls, observation, observed_at: new Date().toISOString()});
  if (observation["result/type"] === "confirmed") expectedBlockHash = observation["block-hash"];
  else if (observation["result/type"] === "finalized") break;
  else if (!["not-final"].includes(observation["result/type"]))
    throw new Error(`qualification stopped: ${JSON.stringify(observation)}`);
}
if (observation?.["result/type"] !== "finalized") throw new Error("Calibration finality deadline exceeded");
const receipt = await interpreter.provider.getTransactionReceipt(submitted["tx-hash"]);
journal.recordReceipt(submitted["tx-hash"], {block_number: receipt.blockNumber,
  block_hash: receipt.blockHash, gas_used: receipt.gasUsed.toString(), status: receipt.status,
  confirmations: observation.confirmations});
journal.close();
const journalSha256 = crypto.createHash("sha256").update(fs.readFileSync(journalPath)).digest("hex");
const evidence = {schema: "kotobase.fevm-calibration-finality.v1", chain_id: CALIBRATION.chainId,
  contract: interpreter.contractAddress, transaction_hash: submitted["tx-hash"],
  block_hash: expectedBlockHash, confirmations: observation.confirmations,
  gas_used: receipt.gasUsed.toString(), source_revision: revision,
  raw_journal_sha256: journalSha256,
  started_at: startedAt, finalized_at: new Date().toISOString(),
  privacy: {onchain_fields: ["opaque_idempotency_key", "opaque_checkpoint_digest"],
    database_id_disclosed: false, epoch_disclosed: false,
    logical_root_disclosed: false, physical_root_disclosed: false}};
const encoded = JSON.stringify(evidence);
console.log(JSON.stringify({...evidence,
  evidence_sha256: crypto.createHash("sha256").update(encoded).digest("hex")}, null, 2));
