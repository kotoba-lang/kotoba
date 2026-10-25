import crypto from "node:crypto";

const HEX32 = /^0x[0-9a-fA-F]{64}$/;

export function canonical(value) {
  if (value === null || typeof value !== "object") return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  return `{${Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${canonical(value[key])}`).join(",")}}`;
}

export function requiredHex32(value, name = "value") {
  if (!HEX32.test(value ?? "")) throw new Error(`${name} must be a 32-byte hex value`);
  return value.toLowerCase();
}

function keyedDigest(salt, domain, value) {
  const key = Buffer.from(requiredHex32(salt, "disclosure salt").slice(2), "hex");
  return `0x${crypto.createHmac("sha256", key).update(domain).update("\0").update(value).digest("hex")}`;
}

export function privateCheckpointMaterial(effect, disclosureSalt) {
  const payload = effect.payload;
  if (!payload || !Number.isSafeInteger(payload.epoch) || payload.epoch < 0)
    throw new Error("submission effect requires a non-negative payload epoch");
  const privatePayload = canonical(payload);
  const identity = String(effect.idempotency_key ?? effect["idempotency-key"] ?? "");
  if (!identity) throw new Error("submission effect requires an idempotency key");
  return {
    idempotencyKey: keyedDigest(disclosureSalt, "kotobase/anchor-idempotency/v1", identity),
    checkpointDigest: keyedDigest(disclosureSalt, "kotobase/private-checkpoint/v1", privatePayload)
  };
}
