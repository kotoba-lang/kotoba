export interface SecretItem { format: 'kagitaba-secret-v1'; id: string; title: string; key: string; value: string }
export function validateSecretItem(item: unknown): SecretItem;
export function secretItem(input: Omit<SecretItem, 'format'>): SecretItem;
