import { createHash, createHmac, pbkdf2Sync } from 'node:crypto';

const utf8 = new TextEncoder();
function hmac(key, data) { return new Uint8Array(createHmac('sha256', key).update(data).digest()); }

export function createNodeCredentialProvider(options = {}) {
  const allowlist = new Set(options.credentialAllowlist || []);
  const maxProofs = options.maxProofs ?? 0;
  const resolveCredentials = typeof options.credentials === 'function'
    ? options.credentials : () => options.credentials || new Map();
  let proofs = 0;
  return {
    scramSha256({ credentialRef, salt, iterations, authMessage }) {
      if (proofs >= maxProofs || !allowlist.has(credentialRef) ||
          !(salt instanceof Uint8Array) || salt.length < 1 || salt.length > 1024 ||
          !Number.isInteger(iterations) || iterations < 4096 || iterations > 1000000 ||
          !(authMessage instanceof Uint8Array) || authMessage.length < 1 || authMessage.length > 8192) return null;
      const credentials = resolveCredentials();
      const secret = credentials instanceof Map ? credentials.get(credentialRef) : credentials[credentialRef];
      if (typeof secret !== 'string' && !(secret instanceof Uint8Array)) return null;
      const password = typeof secret === 'string' ? utf8.encode(secret) : secret.slice();
      const salted = new Uint8Array(pbkdf2Sync(password, salt, iterations, 32, 'sha256'));
      const clientKey = hmac(salted, utf8.encode('Client Key'));
      const storedKey = new Uint8Array(createHash('sha256').update(clientKey).digest());
      const clientSignature = hmac(storedKey, authMessage);
      const serverKey = hmac(salted, utf8.encode('Server Key'));
      const serverSignature = hmac(serverKey, authMessage);
      const result = new Uint8Array(64);
      for (let i = 0; i < 32; i += 1) result[i] = clientKey[i] ^ clientSignature[i];
      result.set(serverSignature, 32);
      salted.fill(0); clientKey.fill(0); storedKey.fill(0); serverKey.fill(0);
      password.fill(0);
      proofs += 1;
      return result;
    },
  };
}
