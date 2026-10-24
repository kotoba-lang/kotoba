import fs from "node:fs";
import crypto from "node:crypto";
import {execFileSync} from "node:child_process";
import {ContractFactory, JsonRpcProvider, Wallet, keccak256} from "ethers";
import {FILECOIN_CALIBRATION as CALIBRATION} from "../profiles/filecoin-calibration.mjs";

function required(name) {
  const value = process.env[name];
  if (!value) throw new Error(`${name} is required`);
  return value;
}

const privateKey = required("FEVM_DEPLOYER_PRIVATE_KEY");
const revision = execFileSync("git", ["rev-parse", "HEAD"], {encoding: "utf8"}).trim();
if (!/^[0-9a-f]{40}$/.test(revision)) throw new Error("deployment requires a full Git revision");
const dirty = execFileSync("git", ["status", "--porcelain"], {encoding: "utf8"}).trim();
if (dirty) throw new Error("refusing to deploy a dirty worktree");
const rpcUrl = process.env.FEVM_RPC_URL ?? CALIBRATION.rpcUrl;
const provider = new JsonRpcProvider(rpcUrl);
const network = await provider.getNetwork();
if (Number(network.chainId) !== CALIBRATION.chainId) throw new Error("refusing to deploy outside Calibration");
const wallet = new Wallet(privateKey, provider);
const balance = await provider.getBalance(wallet.address);
if (balance === 0n) throw new Error(`Calibration deployer ${wallet.address} has no tFIL`);

execFileSync("forge", ["build"], {stdio: "inherit"});
const artifactPath = "contracts/out/KotobaseCheckpointAnchor.sol/KotobaseCheckpointAnchor.json";
const artifact = JSON.parse(fs.readFileSync(artifactPath, "utf8"));
const factory = new ContractFactory(artifact.abi, artifact.bytecode.object, wallet);
const contract = await factory.deploy();
const deployTransaction = contract.deploymentTransaction();
const receipt = await deployTransaction.wait(Number(process.env.FEVM_DEPLOY_CONFIRMATIONS ?? 5));
const address = await contract.getAddress();
const code = await provider.getCode(address);
if (code === "0x") throw new Error("deployed Calibration address has no code");
const evidence = {schema: "kotobase.fevm-contract-deployment.v1", chain_id: CALIBRATION.chainId,
  contract: address, transaction_hash: receipt.hash, block_number: receipt.blockNumber,
  block_hash: receipt.blockHash, deployer: wallet.address, gas_used: receipt.gasUsed.toString(),
  bytecode_keccak256: keccak256(code), source_revision: revision,
  captured_at: new Date().toISOString()};
const encoded = JSON.stringify(evidence);
console.log(JSON.stringify({...evidence,
  evidence_sha256: crypto.createHash("sha256").update(encoded).digest("hex")}, null, 2));
