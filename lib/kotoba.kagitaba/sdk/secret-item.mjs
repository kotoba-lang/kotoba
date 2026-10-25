/** Restricted API credentials. The entire object must be encrypted, including its name. */
const keys = ['format', 'id', 'title', 'key', 'value'];
export function validateSecretItem(item) {
  if (!item || typeof item !== 'object' || Array.isArray(item) ||
      Object.keys(item).length !== keys.length || !keys.every(key => Object.hasOwn(item, key)) ||
      item.format !== 'kagitaba-secret-v1' ||
      typeof item.id !== 'string' || !/^[a-f0-9]{32}$/.test(item.id) ||
      typeof item.title !== 'string' || item.title.length < 1 || item.title.length > 256 ||
      typeof item.key !== 'string' || !/^[A-Z][A-Z0-9_]{0,127}$/.test(item.key) ||
      typeof item.value !== 'string' || item.value.length < 1 || item.value.length > 16384) {
    // Never include input or a secret value in validation errors.
    throw new Error('Invalid restricted secret item.');
  }
  return item;
}
export function secretItem(input) {
  return validateSecretItem({ format: 'kagitaba-secret-v1', ...input });
}
