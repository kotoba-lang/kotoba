import {Contract, JsonRpcProvider, Wallet, getAddress} from "ethers";
import {privateCheckpointMaterial, requiredHex32} from "./checkpoint-material.mjs";

export const ANCHOR_ABI = [
  "function anchor(bytes32 idempotencyKey, bytes32 checkpointDigest) returns (bool)",
  "function receipts(bytes32) view returns (bytes32 checkpointDigest,uint64 anchoredAt)",
  "event CheckpointAnchored(bytes32 indexed idempotencyKey,bytes32 indexed checkpointDigest)"
];

function effectType(effect) {
  return effect["effect/type"] ?? effect.effect_type ?? effect.type;
}

export const privateAnchorMaterial = privateCheckpointMaterial;

export class EvmRpcInterpreter {
  constructor({provider, signer, contractAddress, disclosureSalt, minConfirmations = 20,
    maxGas = 2_000_000n, contractFactory = (address, abi, connectedSigner) =>
      new Contract(address, abi, connectedSigner)}) {
    if (!provider || !signer) throw new Error("EVM interpreter requires provider and signer");
    this.provider = provider;
    this.signer = signer;
    this.contractAddress = getAddress(contractAddress);
    this.disclosureSalt = requiredHex32(disclosureSalt, "disclosure salt");
    this.minConfirmations = minConfirmations;
    this.maxGas = BigInt(maxGas);
    this.contractFactory = contractFactory;
  }

  async interpret(effect) {
    const type = effectType(effect)?.replace(/^:/, "");
    if (["evm/submit-checkpoint", "fevm/submit-checkpoint"].includes(type)) return this.submit(effect);
    if (["evm/read-receipt", "fevm/read-receipt"].includes(type)) return this.readReceipt(effect);
    throw new Error(`unsupported EVM effect ${type}`);
  }

  async submit(effect) {
    const material = privateCheckpointMaterial(effect, this.disclosureSalt);
    const contract = this.contractFactory(this.contractAddress, ANCHOR_ABI, this.signer);
    const estimate = await contract.anchor.estimateGas(material.idempotencyKey, material.checkpointDigest);
    if (estimate > this.maxGas) return {"result/type": "failed", reason: "gas-budget-exceeded"};
    const options = {gasLimit: estimate * 12n / 10n};
    if (this.signer.address && typeof this.provider.send === "function") {
      const pending = await this.provider.send("eth_getTransactionCount", [this.signer.address, "pending"]);
      options.nonce = Number(BigInt(pending));
    }
    const transaction = await contract.anchor(material.idempotencyKey, material.checkpointDigest, options);
    return {"result/type": "submitted", "tx-hash": transaction.hash};
  }

  async readReceipt(effect) {
    const transactionHash = effect.transaction_hash ?? effect["transaction-hash"];
    const expectedBlockHash = effect.expected_block_hash ?? effect["expected-block-hash"];
    const receipt = await this.provider.getTransactionReceipt(transactionHash);
    if (!receipt) return expectedBlockHash ? {"result/type": "reorged"} : {"result/type": "not-final"};
    if (receipt.status !== 1) return {"result/type": "failed", reason: "transaction-reverted"};
    if (expectedBlockHash && receipt.blockHash.toLowerCase() !== expectedBlockHash.toLowerCase())
      return {"result/type": "reorged"};
    if (!expectedBlockHash)
      return {"result/type": "confirmed", height: receipt.blockNumber, "block-hash": receipt.blockHash};
    const head = await this.provider.getBlockNumber();
    const confirmations = Math.max(0, head - receipt.blockNumber + 1);
    return confirmations >= this.minConfirmations
      ? {"result/type": "finalized", confirmations}
      : {"result/type": "not-final"};
  }
}

export async function evmInterpreterFromEnv(profile, env = process.env) {
  const prefix = profile.envPrefix ?? "EVM";
  const privateKey = env[`${prefix}_PRIVATE_KEY`];
  const contractAddress = env[`${prefix}_CONTRACT_ADDRESS`];
  const disclosureSalt = env[`${prefix}_DISCLOSURE_SALT`];
  if (!privateKey || !contractAddress || !disclosureSalt)
    throw new Error(`${prefix}_PRIVATE_KEY, ${prefix}_CONTRACT_ADDRESS and ${prefix}_DISCLOSURE_SALT are required`);
  const provider = new JsonRpcProvider(env[`${prefix}_RPC_URL`] ?? profile.rpcUrl,
    {chainId: profile.chainId, name: profile.name}, {staticNetwork: true});
  const network = await provider.getNetwork();
  if (Number(network.chainId) !== profile.chainId) throw new Error(`refusing chain other than ${profile.chainId}`);
  return new EvmRpcInterpreter({provider, signer: new Wallet(privateKey, provider), contractAddress,
    disclosureSalt, minConfirmations: Number(env[`${prefix}_MIN_CONFIRMATIONS`] ?? profile.minConfirmations ?? 20),
    maxGas: BigInt(env[`${prefix}_MAX_GAS`] ?? profile.maxGas ?? 2_000_000)});
}
